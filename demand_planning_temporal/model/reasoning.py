"""Demand planning decision problems: a least-cost multi-week plan for each planning horizon."""

from typing import Any, NamedTuple

from relationalai.semantics import Float, Integer, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import DemandOrder, OrderInPlan, ProdCapacity, WeeklyDemand, model
from .source import SCENARIO_VALUES, weeks_in_horizon

# Other parameters
min_service_level = 0.95  # Must fulfill at least 95% of demand
safety_stock_weeks = 1  # Maintain at least 1 week of average demand as safety stock

# Penalty for unmet demand (high cost to encourage fulfillment)
unmet_penalty = 50.0  # $/unit penalty for unmet demand

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Variable properties (shared by the horizons' problems, which publish their values per problem)
ProdCapacity.x_production = model.Property(
    f"{ProdCapacity} in week {Integer:t} produces {Float:production}"
)
ProdCapacity.x_inventory = model.Property(
    f"{ProdCapacity} at end of week {Integer:t} has inventory {Float:inventory}"
)
DemandOrder.x_unmet = model.Property(f"{DemandOrder} has {Float:unmet}")

# Refs for aggregation expressions (module level)
week_ref = Integer.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()
x_inv_prev = Float.ref()
x_inv_curr = Float.ref()


class Plan(NamedTuple):
    """One planning horizon and the relationships its solve publishes."""

    planning_end: str
    num_weeks: int
    production: Any
    inventory: Any
    unmet: Any
    status: Any
    cost: Any


def build_plan(planning_end):
    """Define the problem for the horizon ending on planning_end."""
    num_weeks = weeks_in_horizon(planning_end)
    in_plan = OrderInPlan(DemandOrder, planning_end)

    # Time periods via std.common.range()
    weeks = std.common.range(1, num_weeks + 1)

    # One Problem for each horizon
    name = f"demand_planning_temporal_{planning_end.replace('-', '_')}"
    problem = Problem(model, Float, name=name)

    # Variable: production quantity per site x SKU x week
    production_var = problem.solve_for(
        ProdCapacity.x_production(week_ref, production_ref),
        type="cont",
        lower=0,
        upper=ProdCapacity.max_production_per_week,
        name=["prod", ProdCapacity.site_id, ProdCapacity.sku_id, week_ref],
        where=[week_ref == weeks],
        populate=False,
    )

    # Variable: inventory level per site x SKU x week (week 0 = initial)
    inventory_var = problem.solve_for(
        ProdCapacity.x_inventory(week_ref, inventory_ref),
        type="cont",
        lower=0,
        name=["inv", ProdCapacity.site_id, ProdCapacity.sku_id, week_ref],
        where=[week_ref == std.common.range(0, num_weeks + 1)],
        populate=False,
    )

    # Variable: unmet demand per order in the horizon
    unmet_var = problem.solve_for(
        DemandOrder.x_unmet,
        type="cont",
        lower=0,
        upper=DemandOrder.quantity,
        name=["unmet", DemandOrder.id],
        where=[in_plan],
        populate=False,
    )

    # Constraint: initial condition (inventory at week 0)
    problem.satisfy(
        model.where(
            ProdCapacity.x_inventory(0, inventory_ref),
        ).require(inventory_ref == ProdCapacity.initial_inventory)
    )

    # Constraint: flow conservation inv[t] = inv[t-1] + production[t] - demand[t]
    # (depends on num_weeks via WeeklyDemand data and week ranges)
    problem.satisfy(
        model.where(
            ProdCapacity.x_inventory(week_ref, x_inv_curr),
            ProdCapacity.x_inventory(week_ref - 1, x_inv_prev),
            ProdCapacity.x_production(week_ref, production_ref),
            WeeklyDemand.wk_planning_end == planning_end,
            WeeklyDemand.wk_site_id == ProdCapacity.site_id,
            WeeklyDemand.wk_sku_id == ProdCapacity.sku_id,
            WeeklyDemand.wk_week_num == week_ref,
            week_ref >= 1,
        ).require(x_inv_curr == x_inv_prev + production_ref - WeeklyDemand.wk_quantity)
    )

    # Constraint: service level over the horizon's orders
    problem.satisfy(
        model.require(
            sum(DemandOrder.x_unmet).where(in_plan)
            <= (1 - min_service_level) * sum(DemandOrder.quantity).where(in_plan)
        )
    )

    # Safety stock: inventory at end of each active week >= safety_stock_weeks × avg weekly demand
    if safety_stock_weeks > 0:
        avg_weekly_demand = (
            sum(WeeklyDemand.wk_quantity)
            .where(
                WeeklyDemand.wk_planning_end == planning_end,
                WeeklyDemand.wk_site_id == ProdCapacity.site_id,
                WeeklyDemand.wk_sku_id == ProdCapacity.sku_id,
            )
            .per(ProdCapacity)
            / num_weeks
        )
        problem.satisfy(
            model.where(
                ProdCapacity.x_inventory(week_ref, inventory_ref),
                week_ref >= 1,
            ).require(inventory_ref >= avg_weekly_demand * safety_stock_weeks)
        )

    # Objective: minimize total cost, each term summed over its own rows.
    prod_cost = sum(
        ProdCapacity, week_ref, ProdCapacity.production_cost * production_ref
    ).where(ProdCapacity.x_production(week_ref, production_ref))
    hold_cost = sum(
        ProdCapacity, week_ref, ProdCapacity.holding_cost_per_week * inventory_ref
    ).where(ProdCapacity.x_inventory(week_ref, inventory_ref), week_ref >= 1)
    unmet_cost = sum(DemandOrder, unmet_penalty * DemandOrder.x_unmet).where(in_plan)
    # With no orders in the horizon the unmet sum is empty; `| 0.0` makes it zero.
    problem.minimize(prod_cost + hold_cost + (unmet_cost | 0.0))

    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=60)

    # The solve's status and objective, which the deployed model publishes for the queries.
    status = model.Relationship(f"{name} solve status is {String:status}")
    cost = model.Relationship(f"{name} total cost is {Float:cost}")
    model.define(status(problem.termination_status()), cost(problem.objective_value()))

    # The solved plan, which the deployed model publishes for the queries.
    production = model.Relationship(
        f"{name} produces {Float:production} at site {Integer:site_id} of SKU {Integer:sku_id} in week {Integer:week}"
    )
    inventory = model.Relationship(
        f"{name} holds {Float:inventory} at site {Integer:site_id} of SKU {Integer:sku_id} at end of week {Integer:week}"
    )
    unmet = model.Relationship(f"{name} leaves {Float:unmet} unmet for order {Integer:order_id}")
    value = Float.ref()
    model.where(production_var.values(0, value)).define(
        production(
            value,
            production_var.prodcapacity.site_id,
            production_var.prodcapacity.sku_id,
            production_var.t,
        )
    )
    model.where(inventory_var.values(0, value)).define(
        inventory(
            value,
            inventory_var.prodcapacity.site_id,
            inventory_var.prodcapacity.sku_id,
            inventory_var.t,
        )
    )
    model.where(unmet_var.values(0, value)).define(unmet(value, unmet_var.demandorder.id))

    return Plan(planning_end, num_weeks, production, inventory, unmet, status, cost)


# One problem per planning horizon, so an infeasible horizon leaves the others solved.
PLANS = [build_plan(planning_end) for planning_end in SCENARIO_VALUES]
