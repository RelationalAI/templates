"""Disruption scenarios: one sourcing problem per excluded supplier, with each scenario's published
solve status, total cost, and order quantity of each supply lane."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Declares SupplyOrder.x_quantity and the supplier, product, and unit cost of each order.
from . import sourcing_plan  # noqa: F401
from .schema import Product, Supplier, SupplyOrder, model

# --------------------------------------------------
# Phase B -- disruption scenarios (separate solves)
# --------------------------------------------------
# Each scenario is its own Problem with a where= filter excluding one supplier -- a
# FINITE structural change (a supplier fully removed). A shadow price is a marginal at
# the current optimum, not an exclusion-impact ranking, so these re-solves are
# CONSISTENT WITH Phase A (SupplierC, the most valuable capacity, hurts most when
# excluded) without being predicted by the duals alone. One infeasible scenario leaves the
# others unaffected.

EXCLUDED_SUPPLIERS = ["SupplierC", "SupplierB"]


def build_scenario(excluded):
    """Build, configure, and publish the results of the scenario that excludes one supplier."""
    name = f"supplier_reliability_without_{excluded.lower()}"
    problem = Problem(model, Float, name=name)

    # Exclude one supplier via where=; populate=False leaves SupplyOrder.x_quantity
    # untouched so the Problems do not write the same property.
    qty_scn = problem.solve_for(
        SupplyOrder.x_quantity,
        name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
        lower=0,
        where=[SupplyOrder.supplier.name != excluded],
        populate=False,
    )

    # Capacity and demand over the remaining suppliers' orders: the excluded one's
    # orders have no variables.
    problem.satisfy(
        model.where(SupplyOrder.supplier == Supplier, Supplier.name != excluded).require(
            sum(SupplyOrder.x_quantity)
            .where(SupplyOrder.supplier == Supplier)
            .per(Supplier)
            <= Supplier.capacity
        )
    )
    problem.satisfy(
        model.where(SupplyOrder.product == Product, SupplyOrder.supplier.name != excluded).require(
            sum(SupplyOrder.x_quantity)
            .where(SupplyOrder.product == Product)
            .per(Product)
            >= Product.demand
        )
    )
    problem.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))

    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=60)

    # The solve's status and objective, which the deployed model publishes for the queries.
    status = model.Relationship(f"{name} solve status is {String:status}")
    cost = model.Relationship(f"{name} total cost is {Float:cost}")
    model.define(status(problem.termination_status()), cost(problem.objective_value()))

    # The solved order quantity of each supply lane, which the deployed model publishes for the queries.
    amount = Float.ref()
    orders = model.Relationship(f"{name} orders {SupplyOrder} in quantity {Float:quantity}")
    model.where(qty_scn.values(0, amount)).define(orders(qty_scn.supplyorder, amount))
    return status, cost, orders


scenarios = {excluded: build_scenario(excluded) for excluded in EXCLUDED_SUPPLIERS}
