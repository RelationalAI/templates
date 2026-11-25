"""Facing allocation: the integer facings per SKU that maximize total predicted demand within shelf
capacity and category bounds."""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

from .schema import Category, PredictedDemand, Shelf, Sku, model

# --------------------------------------------------
# Decision-valued properties on Sku
# --------------------------------------------------

Sku.facings = model.Property(f"{Sku} has {Integer:facings}")
Sku.realized_demand = model.Property(f"{Sku} has {Integer:realized_demand}")
# 0/1 indicator that EXISTS so the per-category cardinality can be written as
# `sum(Sku.active).per(Category)`. Without it, the natural form
# `sum(Sku.facings >= 1).per(Category)` is not a valid relational sum.
# Boolean is not a valid `solve_for` type, so the indicator is encoded as an
# Integer 0/1, coupled to facings via the linear inequality pair below.
Sku.active = model.Property(f"{Sku} has {Integer:active}")

problem = Problem(model, Integer, name="planogram_optimization")
problem.solve_for(Sku.facings, type="int", lower=0, upper=Sku.max_facings, name=["facings", Sku.id])
problem.solve_for(Sku.realized_demand, type="int", lower=0, name=["demand", Sku.id])
problem.solve_for(Sku.active, type="bin", name=["active", Sku.id])

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Element-style decision-indexed table lookup. The implies expands per row of
# PredictedDemand into `implies(k == Sku.facings, Sku.realized_demand ==
# table[sku, k])`; only the row with k == Sku.facings activates.
demand_lookup_ic = model.where(PredictedDemand.sku_id == Sku.id).require(
    implies(
        PredictedDemand.facings_count == Sku.facings,
        Sku.realized_demand == PredictedDemand.demand_units,
    )
)
problem.satisfy(demand_lookup_ic)

# Shelf capacity: total facings * width on each shelf cannot exceed length.
shelf_capacity_ic = model.where(Sku.shelf == Shelf).require(
    sum(Sku.facings * Sku.width_cm).per(Shelf) <= Shelf.length_cm
)
problem.satisfy(shelf_capacity_ic)

# Active iff facings >= 1, encoded as two linear inequalities:
# - `Sku.facings >= Sku.active` forces `facings >= 1` when `active == 1`.
# - `Sku.facings <= Sku.max_facings * Sku.active` forces `facings == 0` when
#   `active == 0`.
# Together they pin `active = 1` whenever `facings >= 1`, and `active = 0`
# otherwise.
active_lower_ic = model.where(Sku).require(Sku.facings >= Sku.active)
active_upper_ic = model.where(Sku).require(Sku.facings <= Sku.max_facings * Sku.active)
problem.satisfy(active_lower_ic)
problem.satisfy(active_upper_ic)

# Category cardinality bounds.
category_min_ic = model.where(Sku.category == Category.name).require(
    sum(Sku.active).per(Category) >= Category.min_skus_active
)
category_max_ic = model.where(Sku.category == Category.name).require(
    sum(Sku.active).per(Category) <= Category.max_skus_active
)
problem.satisfy(category_min_ic)
problem.satisfy(category_max_ic)

problem.maximize(sum(Sku.realized_demand))

# --------------------------------------------------
# Solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"planogram solve status is {String:status}")
TotalDemand = model.Relationship(f"planogram total demand is {Integer:demand}")
model.define(SolveStatus(problem.termination_status()), TotalDemand(problem.objective_value()))
