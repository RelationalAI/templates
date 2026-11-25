"""Demand planning: the demand/inventory LP that plans production, inventory, and unmet demand for
each planning article and week at least cost, its solve status and cost, and the plan."""

from relationalai.semantics import Float, Integer, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .article_demand import ArticleDemand
from .planning_horizon import num_weeks
from .schema import ProdCapacity, Week, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Optimizer tuning knobs -- edit without retraining the GNN.
UNMET_PENALTY = 50.0

# --------------------------------------------------
# Phase 5: Demand/Inventory Planning (LP, minimize cost)
# --------------------------------------------------
dp_week_ref = Week.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()

dp = Problem(model, Float, name="retail_demand_planning")

ProdCapacity.x_production = model.Property(
    f"{ProdCapacity} in week {Week} produces {Float:production}")
dp.solve_for(
    ProdCapacity.x_production(dp_week_ref, production_ref),
    type="cont", lower=0,
    upper=ProdCapacity.max_production_per_week,
    name=["prod", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_weeks + 1)],
)

inv_week_ref = Integer.ref()
ProdCapacity.x_inventory = model.Property(
    f"{ProdCapacity} at end of week {Integer} has inventory {Float:inventory}")
dp.solve_for(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    type="cont", lower=0,
    name=["inv", ProdCapacity.pc_article_id, inv_week_ref],
    where=[inv_week_ref == std.common.range(0, num_weeks + 1)],
)

unmet_ref = Float.ref()
ProdCapacity.x_unmet = model.Property(
    f"{ProdCapacity} in week {Week} has unmet {Float:demand}")
dp.solve_for(
    ProdCapacity.x_unmet(dp_week_ref, unmet_ref),
    type="cont", lower=0,
    name=["unmet", ProdCapacity.pc_article_id, dp_week_ref.num],
    where=[dp_week_ref.num == std.common.range(1, num_weeks + 1)],
)

inv_init_ref = Float.ref()
dp.satisfy(model.where(
    ProdCapacity.x_inventory(0, inv_init_ref),
).require(inv_init_ref == ProdCapacity.pc_initial_inventory))

inv_curr = Float.ref()
inv_prev = Float.ref()
flow_prod_ref = Float.ref()
flow_unmet_ref = Float.ref()
flow_week_ref = Week.ref()

dp.satisfy(model.where(
    ProdCapacity.x_inventory(flow_week_ref.num, inv_curr),
    ProdCapacity.x_inventory(flow_week_ref.num - 1, inv_prev),
    ProdCapacity.x_production(flow_week_ref, flow_prod_ref),
    ProdCapacity.x_unmet(flow_week_ref, flow_unmet_ref),
    ArticleDemand.article_id == ProdCapacity.pc_article_id,
).require(
    inv_curr == inv_prev + flow_prod_ref
    - ArticleDemand.adjusted_demand * flow_week_ref.demand_multiplier
    + flow_unmet_ref
))

prod_cost_total = sum(
    ProdCapacity, dp_week_ref,
    ProdCapacity.production_cost * production_ref,
).where(ProdCapacity.x_production(dp_week_ref, production_ref))

hold_cost_total = sum(
    ProdCapacity, inv_week_ref,
    ProdCapacity.holding_cost_per_week * inventory_ref,
).where(
    ProdCapacity.x_inventory(inv_week_ref, inventory_ref),
    inv_week_ref >= 1,
)

unmet_cost_total = sum(
    ProdCapacity, dp_week_ref,
    UNMET_PENALTY * unmet_ref,
).where(ProdCapacity.x_unmet(dp_week_ref, unmet_ref))

dp.minimize(prod_cost_total + hold_cost_total + unmet_cost_total)

# Each refresh of the deployed model runs this solve.
dp.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
DemandPlanStatus = model.Relationship(f"retail demand planning status is {String:status}")
DemandPlanCost = model.Relationship(f"retail demand planning cost is {Float:cost}")
model.define(DemandPlanStatus(dp.termination_status()), DemandPlanCost(dp.objective_value()))

# The plan, which the deployed model publishes for the queries: production and unmet demand
# for each planning article and week, and inventory at the end of each week (week 0 is the
# opening stock).
ProdCapacity.planned_production = model.Relationship(
    f"{ProdCapacity} in week {Week} has planned production {Float:production}")
ProdCapacity.planned_inventory = model.Relationship(
    f"{ProdCapacity} at end of week {Integer:week} has planned inventory {Float:inventory}")
ProdCapacity.planned_unmet = model.Relationship(
    f"{ProdCapacity} in week {Week} has planned unmet demand {Float:unmet}")
plan_week, plan_end_week, plan_value = Week.ref(), Integer.ref(), Float.ref()
model.where(ProdCapacity.x_production(plan_week, plan_value)).define(
    ProdCapacity.planned_production(plan_week, plan_value))
model.where(ProdCapacity.x_inventory(plan_end_week, plan_value)).define(
    ProdCapacity.planned_inventory(plan_end_week, plan_value))
model.where(ProdCapacity.x_unmet(plan_week, plan_value)).define(
    ProdCapacity.planned_unmet(plan_week, plan_value))
