"""Sourcing plan: the baseline min-cost sourcing LP, solved with sensitivity analysis, and the
published solve status, total cost, and order quantity of each supply lane."""

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
# handles. The disruption scenarios are separate Problems with their own variables.

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
