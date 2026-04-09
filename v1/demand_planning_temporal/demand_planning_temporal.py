"""Demand Planning Temporal (prescriptive optimization) template.

This script demonstrates a multi-period production and inventory planning
optimization in RelationalAI with temporal filtering:

- Load sample CSVs describing sites, SKUs, demand orders, and production capacity.
- Model those entities as *concepts* with typed properties.
- Filter demand orders by a configurable date-range planning horizon (Pattern A:
  native date columns) and map dates to integer week periods.
- Solve a multi-period LP with inventory flow conservation:
  inv[t] = inv[t-1] + production[t] - demand[t].
- Enforce production capacity, service level, and initial inventory conditions.
- Minimize total cost (production + holding + unmet demand penalty).

Temporal filtering patterns demonstrated:
- Pattern A (native date columns, used here): filter by due_date string comparisons,
  then map dates to integer week numbers for std.common.range() periods.
- Pattern B (epoch integer timestamps, shown in comments): filter by Unix epoch
  seconds on columns like created_at, updated_at. See the sprint_scheduling
  template for a working epoch example.

Run:
    `python demand_planning_temporal.py`

Output:
    Prints the solver termination status, total cost, planning horizon summary,
    production plan, inventory levels, and unmet demand.
"""

import itertools
from datetime import datetime
from pathlib import Path

import pandas as pd
from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("demand_planning")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Parameters (editable planning horizon)
# --------------------------------------------------

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2025-11-01"  # Start of planning horizon

# Other parameters
min_service_level = 0.95  # Must fulfill at least 95% of demand
safety_stock_weeks = 1  # Maintain at least 1 week of average demand as safety stock

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: warehouse/distribution center sites
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.site_type = Property(f"{Site} has {String:site_type}")
Site.capacity_per_week = Property(f"{Site} has {Integer:capacity_per_week}")
site_csv = read_csv(data_dir / "sites.csv")
model.define(Site.new(model.data(site_csv).to_schema()))

# Concept: products (SKUs)
SKU = Concept("SKU", identify_by={"id": Integer})
SKU.name = Property(f"{SKU} has {String:name}")
SKU.unit_cost = Property(f"{SKU} has {Float:unit_cost}")
SKU.holding_cost_per_week = Property(f"{SKU} has {Float:holding_cost_per_week}")
sku_csv = read_csv(data_dir / "skus.csv")
model.define(SKU.new(model.data(sku_csv).to_schema()))

# Concept: demand orders (EVENT TABLE - has date column, needs filtering)
# Raw data spans Oct 2025 - Mar 2026. We filter to the planning horizon.
DemandOrder = Concept("DemandOrder", identify_by={"id": Integer})
DemandOrder.quantity = Property(f"{DemandOrder} has {Integer:quantity}")
DemandOrder.due_date = Property(f"{DemandOrder} has {String:due_date}")
DemandOrder.week_num = Property(f"{DemandOrder} falls in week {Integer:week_num}")

orders_df = read_csv(data_dir / "demand_orders.csv")
orders_df["due_date"] = pd.to_datetime(orders_df["due_date"])

# --------------------------------------------------
# EPOCH TIMESTAMP ALTERNATIVE (Pattern B):
# If DemandOrder had epoch integer timestamps instead of date strings,
# filtering would look like this:
#
#   start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
#   end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp()) + 86399
#
#   # Filter in pandas before loading
#   filtered_orders = orders_df[
#       (orders_df["created_at"] >= start_epoch) &
#       (orders_df["created_at"] <= end_epoch)
#   ].copy()
#
#   # Or filter in .where() clauses on constraints
#   p.satisfy(model.require(
#       sum(DemandOrder.x_unmet) <= (1 - min_service_level) * sum(DemandOrder.quantity)
#   ).where(
#       DemandOrder.created_at >= start_epoch, DemandOrder.created_at <= end_epoch
#   ))
#
#   # Period mapping from epoch: week_num = (epoch - start_epoch) // (7 * 86400) + 1
# --------------------------------------------------

# Concept: production capacity per site x SKU (REFERENCE TABLE - no filtering needed)
ProdCapacity = Concept(
    "ProdCapacity", identify_by={"site_id": Integer, "sku_id": Integer}
)
ProdCapacity.max_production_per_week = Property(
    f"{ProdCapacity} has {Integer:max_production_per_week}"
)
ProdCapacity.production_cost = Property(f"{ProdCapacity} has {Float:production_cost}")

pc_df = read_csv(data_dir / "production_capacity.csv")
inv_df = read_csv(data_dir / "initial_inventory.csv")
sku_df = read_csv(data_dir / "skus.csv")

# Pre-join: merge initial inventory and SKU holding cost into ProdCapacity
# This avoids relationship traversal FD issues in solver expressions
pc_df = pc_df.merge(
    inv_df[["site_id", "sku_id", "quantity"]], on=["site_id", "sku_id"], how="left"
)
pc_df = pc_df.rename(columns={"quantity": "initial_inventory"}).fillna(0)
pc_df = pc_df.merge(
    sku_df[["id", "holding_cost_per_week"]],
    left_on="sku_id",
    right_on="id",
    how="left",
    suffixes=("", "_sku"),
)
pc_df = pc_df.drop(columns=["id"], errors="ignore")

ProdCapacity.initial_inventory = Property(
    f"{ProdCapacity} has {Float:initial_inventory}"
)
ProdCapacity.holding_cost_per_week = Property(
    f"{ProdCapacity} has {Float:holding_cost_per_week}"
)

pc_data = model.data(pc_df)
model.define(ProdCapacity.new(pc_data.to_schema()))

# Link to Site and SKU
model.define(ProdCapacity.site(Site)).where(Site.id == pc_data.site_id)
model.define(ProdCapacity.sku(SKU)).where(SKU.id == pc_data.sku_id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Variable properties (defined on model, solved per scenario)
ProdCapacity.x_production = Property(
    f"{ProdCapacity} in week {Integer:t} produces {Float:production}"
)
ProdCapacity.x_inventory = Property(
    f"{ProdCapacity} at end of week {Integer:t} has inventory {Float:inventory}"
)
DemandOrder.x_unmet = Property(f"{DemandOrder} has {Float:unmet}")

# Refs for aggregation expressions (module level)
week_ref = Integer.ref()
production_ref = Float.ref()
inventory_ref = Float.ref()
x_inv_prev = Float.ref()
x_inv_curr = Float.ref()

# Static constraint expression: demand fulfillment bound (no scenario param dependency)
demand_bound = model.require(DemandOrder.x_unmet <= DemandOrder.quantity)

# Static constraint expression: global service level (no scenario param dependency)
service_level_constraint = model.require(
    sum(DemandOrder.x_unmet) <= (1 - min_service_level) * sum(DemandOrder.quantity)
)

# Penalty for unmet demand (high cost to encourage fulfillment)
unmet_penalty = 50.0  # $/unit penalty for unmet demand

# Scenarios (what-if analysis)
# NOTE: Values must be in increasing order — each iteration adds demand data to the
# shared model. Increasing dates ensure each scenario is a superset of the previous.
SCENARIO_PARAM = "planning_end"
SCENARIO_VALUES = ["2026-01-31", "2026-02-28", "2026-03-31"]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")
    planning_end = scenario_value

    # Recompute time-dependent data for this scenario
    start_date = datetime.strptime(planning_start, "%Y-%m-%d")
    end_date = datetime.strptime(planning_end, "%Y-%m-%d")
    num_weeks = int((end_date - start_date).days / 7) + 1

    # DATE FILTERING: Only load orders within the planning horizon
    filtered_orders = orders_df[
        (orders_df["due_date"] >= planning_start)
        & (orders_df["due_date"] <= planning_end)
    ].copy()

    # DATE-TO-PERIOD MAPPING: Convert due_date to integer week number
    filtered_orders["week_num"] = (
        (filtered_orders["due_date"] - pd.Timestamp(planning_start)).dt.days // 7 + 1
    ).astype(int)
    filtered_orders["due_date"] = filtered_orders["due_date"].dt.strftime("%Y-%m-%d")

    order_data = model.data(filtered_orders)
    model.define(
        o := DemandOrder.new(id=order_data.id),
        o.quantity(order_data.quantity),
        o.due_date(order_data.due_date),
        o.week_num(order_data.week_num),
    )

    # Link demand orders to SKU and Site via foreign keys
    model.define(DemandOrder.sku(SKU)).where(SKU.id == order_data.sku_id)
    model.define(DemandOrder.site(Site)).where(Site.id == order_data.site_id)

    # Pre-aggregate demand into weekly buckets per SKU per Site
    weekly_demand = (
        filtered_orders.groupby(["week_num", "sku_id", "site_id"])["quantity"]
        .sum()
        .reset_index()
    )

    # Build complete demand matrix: every (site, sku, week) combo, 0 for missing weeks
    all_combos = list(
        itertools.product(
            pc_df["site_id"].unique(), pc_df["sku_id"].unique(), range(1, num_weeks + 1)
        )
    )
    full_demand = pd.DataFrame(all_combos, columns=["site_id", "sku_id", "week_num"])
    full_demand = full_demand.merge(
        weekly_demand[["site_id", "sku_id", "week_num", "quantity"]],
        on=["site_id", "sku_id", "week_num"],
        how="left",
    ).fillna(0.0)

    WeeklyDemand = Concept(
        "WeeklyDemand",
        identify_by={
            "wk_site_id": Integer,
            "wk_sku_id": Integer,
            "wk_week_num": Integer,
        },
    )
    WeeklyDemand.wk_quantity = Property(f"{WeeklyDemand} has {Float:wk_quantity}")

    wd_data = model.data(full_demand)
    model.define(
        wd := WeeklyDemand.new(
            wk_site_id=wd_data.site_id,
            wk_sku_id=wd_data.sku_id,
            wk_week_num=wd_data.week_num,
        ),
        wd.wk_quantity(wd_data.quantity),
    )

    # Time periods via std.common.range()
    weeks = std.common.range(1, num_weeks + 1)

    # Create fresh Problem for each scenario
    p = Problem(model, Float)

    # Variable: production quantity per site x SKU x week
    production_var = p.solve_for(
        ProdCapacity.x_production(week_ref, production_ref),
        type="cont",
        lower=0,
        upper=ProdCapacity.max_production_per_week,
        name=["prod", ProdCapacity.site_id, ProdCapacity.sku_id, week_ref],
        where=[week_ref == weeks],
        populate=False,
    )

    # Variable: inventory level per site x SKU x week (week 0 = initial)
    inventory_var = p.solve_for(
        ProdCapacity.x_inventory(week_ref, inventory_ref),
        type="cont",
        lower=0,
        name=["inv", ProdCapacity.site_id, ProdCapacity.sku_id, week_ref],
        where=[week_ref == std.common.range(0, num_weeks + 1)],
        populate=False,
    )

    # Variable: unmet demand per order
    unmet_var = p.solve_for(
        DemandOrder.x_unmet,
        type="cont",
        lower=0,
        upper=DemandOrder.quantity,
        name=["unmet", DemandOrder.id],
        populate=False,
    )

    # Parameterized constraint: initial condition (inventory at week 0)
    p.satisfy(
        model.where(
            ProdCapacity.x_inventory(0, inventory_ref),
        ).require(inventory_ref == ProdCapacity.initial_inventory)
    )

    # Parameterized constraint: flow conservation inv[t] = inv[t-1] + production[t] - demand[t]
    # (depends on num_weeks via WeeklyDemand data and week ranges)
    p.satisfy(
        model.where(
            ProdCapacity.x_inventory(week_ref, x_inv_curr),
            ProdCapacity.x_inventory(week_ref - 1, x_inv_prev),
            ProdCapacity.x_production(week_ref, production_ref),
            WeeklyDemand.wk_site_id == ProdCapacity.site_id,
            WeeklyDemand.wk_sku_id == ProdCapacity.sku_id,
            WeeklyDemand.wk_week_num == week_ref,
            week_ref >= 1,
        ).require(x_inv_curr == x_inv_prev + production_ref - WeeklyDemand.wk_quantity)
    )

    # Static constraint: demand fulfillment bound
    p.satisfy(demand_bound)

    # Static constraint: global service level
    p.satisfy(service_level_constraint)

    # Safety stock: inventory at end of each active week >= safety_stock_weeks × avg weekly demand
    if safety_stock_weeks > 0:
        avg_weekly_demand = (
            sum(WeeklyDemand.wk_quantity)
            .where(
                WeeklyDemand.wk_site_id == ProdCapacity.site_id,
                WeeklyDemand.wk_sku_id == ProdCapacity.sku_id,
            )
            .per(ProdCapacity)
            / num_weeks
        )
        p.satisfy(
            model.where(
                ProdCapacity.x_inventory(week_ref, inventory_ref),
                week_ref >= 1,
            ).require(inventory_ref >= avg_weekly_demand * safety_stock_weeks)
        )

    # Parameterized objective: minimize total cost (depends on week ranges via production/inventory refs)
    prod_cost = ProdCapacity.production_cost * sum(production_ref).per(
        ProdCapacity
    ).where(ProdCapacity.x_production(week_ref, production_ref))
    hold_cost = ProdCapacity.holding_cost_per_week * sum(inventory_ref).per(
        ProdCapacity
    ).where(ProdCapacity.x_inventory(week_ref, inventory_ref), week_ref >= 1)
    unmet_cost = unmet_penalty * DemandOrder.x_unmet
    p.minimize(sum(model.union(prod_cost, hold_cost, unmet_cost)))

    p.display()
    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()
    si.display()

    scenario_results.append(
        {
            "scenario": scenario_value,
            "status": str(si.termination_status),
            "objective": si.objective_value,
        }
    )
    if si.termination_status != "OPTIMAL":
        print(f"  Status: {si.termination_status} — skipping results")
        continue
    print(f"  Status: {si.termination_status}")
    print(f"  Total cost: ${si.objective_value:,.2f}")
    print(f"  Planning horizon: {planning_start} to {planning_end} ({num_weeks} weeks)")
    print(
        f"  Demand orders in scope: {len(filtered_orders)} (of {len(orders_df)} total)"
    )

    value_ref = Float.ref()
    prod = model.select(
        production_var.prodcapacity.site_id.alias("site_id"),
        production_var.prodcapacity.sku_id.alias("sku_id"),
        production_var.t.alias("week"),
        value_ref.alias("production"),
    ).where(production_var.values(0, value_ref), value_ref > 0.01).to_df()
    inv = model.select(
        inventory_var.prodcapacity.site_id.alias("site_id"),
        inventory_var.prodcapacity.sku_id.alias("sku_id"),
        inventory_var.t.alias("week"),
        value_ref.alias("inventory"),
    ).where(inventory_var.values(0, value_ref)).to_df()
    unmet = model.select(
        unmet_var.demandorder.id.alias("order_id"),
        value_ref.alias("unmet"),
    ).where(unmet_var.values(0, value_ref), value_ref > 0.01).to_df()

    print("\n  === Production Plan (non-zero weeks) ===")
    if not prod.empty:
        print(prod.to_string(index=False))

    print("\n  === Inventory Levels (selected weeks) ===")
    if not inv.empty:
        print(inv.head(20).to_string(index=False))

    print("\n  === Unmet Demand ===")
    if unmet.empty:
        print("  All demand fulfilled!")
    else:
        print(unmet.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    obj = result["objective"]
    obj_str = f"${obj:,.2f}" if obj is not None else "N/A"
    print(f"  planning_end={result['scenario']}: {result['status']}, cost={obj_str}")
