"""Supplier reliability decision problems: a baseline sourcing plan with sensitivity, and supplier-disruption scenarios."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Product, Supplier, SupplyOption, SupplyOrder, model

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable: units ordered through each supply option.
SupplyOrder.x_quantity = model.Property(f"{SupplyOrder} has {Float:quantity}")
model.define(SupplyOrder.new(option=SupplyOption))

model.define(SupplyOrder.supplier(Supplier)).where(SupplyOrder.option(SupplyOption), SupplyOption.supplier(Supplier))
model.define(SupplyOrder.product(Product)).where(SupplyOrder.option(SupplyOption), SupplyOption.product(Product))
model.define(SupplyOrder.cost_per_unit(SupplyOption.cost_per_unit)).where(SupplyOrder.option(SupplyOption))

# --------------------------------------------------
# Phase A -- baseline solve with sensitivity analysis
# --------------------------------------------------
# The marginals are read off this baseline Problem's captured variable and constraint
# handles. The disruption scenarios below are separate Problems with their own variables.

baseline = Problem(model, Float, name="supplier_reliability_baseline")

# Variable: order quantity per supply lane (continuous, non-negative).
qty_var = baseline.solve_for(
    SupplyOrder.x_quantity,
    name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
    lower=0,
    populate=False,
)

# Constraints, captured as handles. ``keyed_by`` declares each instance's ENTITY KEY,
# so its marginal reads back through that key (cap.supplier / meet.product), never by
# parsing the constraint name string; the per-entity name is a readable label.
cap = baseline.satisfy(
    model.where(SupplyOrder.supplier == Supplier).require(
        sum(SupplyOrder.x_quantity)
        .where(SupplyOrder.supplier == Supplier)
        .per(Supplier)
        <= Supplier.capacity
    ),
    name=["cap", Supplier.name],
    keyed_by={"supplier": Supplier},
)
meet = baseline.satisfy(
    model.where(SupplyOrder.product == Product).require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product)
        >= Product.demand
    ),
    name=["demand", Product.name],
    keyed_by={"product": Product},
)

# Objective: minimize total sourcing cost.
baseline.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))

# Each refresh of the deployed model runs this solve, with sensitivity analysis.
baseline.configure("highs", time_limit_sec=60, sensitivity=True)

# The solve's status and objective, which the deployed model publishes for the queries.
BaselineStatus = model.Relationship(f"supplier_reliability_baseline solve status is {String:status}")
BaselineCost = model.Relationship(f"supplier_reliability_baseline total cost is {Float:cost}")
model.define(BaselineStatus(baseline.termination_status()), BaselineCost(baseline.objective_value()))

# The solved order quantity of each supply lane, which the deployed model publishes for the queries.
baseline_amount = Float.ref()
BaselineOrder = model.Relationship(f"supplier_reliability_baseline orders {SupplyOrder} in quantity {Float:quantity}")
model.where(qty_var.values(0, baseline_amount)).define(BaselineOrder(qty_var.supplyorder, baseline_amount))

# The sensitivity marginals, which the deployed model publishes for the queries: each lane's
# reduced cost and basis status, and each capacity's and demand's shadow price, keyed by the
# entity they belong to.
lane_reduced_cost, lane_basis, capacity_price, demand_price = Float.ref(), String.ref(), Float.ref(), Float.ref()
LaneReducedCost = model.Relationship(f"supplier_reliability_baseline {SupplyOrder} has reduced cost {Float:reduced_cost}")
LaneBasisStatus = model.Relationship(f"supplier_reliability_baseline {SupplyOrder} has basis status {String:basis_status}")
CapacityShadowPrice = model.Relationship(f"supplier_reliability_baseline {Supplier} has capacity shadow price {Float:shadow_price}")
DemandShadowPrice = model.Relationship(f"supplier_reliability_baseline {Product} has demand shadow price {Float:shadow_price}")
model.where(qty_var.reduced_cost(lane_reduced_cost)).define(LaneReducedCost(qty_var.supplyorder, lane_reduced_cost))
model.where(qty_var.basis_status(lane_basis)).define(LaneBasisStatus(qty_var.supplyorder, lane_basis))
model.where(cap.shadow_price(capacity_price)).define(CapacityShadowPrice(cap.supplier, capacity_price))
model.where(meet.shadow_price(demand_price)).define(DemandShadowPrice(meet.product, demand_price))

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
