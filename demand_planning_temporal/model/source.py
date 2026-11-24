"""Load the sample sites, SKUs, orders, and capacity into the demand planning model, scoped to each planning horizon."""

import itertools
from datetime import datetime
from pathlib import Path

import pandas as pd

from .schema import (
    SKU,
    DemandOrder,
    OrderInPlan,
    ProdCapacity,
    Site,
    WeeklyDemand,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2025-11-01"  # Start of planning horizon

# Scenarios (what-if analysis): each planning_end value is one planning horizon,
# solved by its own Problem in model/reasoning.py.
SCENARIO_VALUES = ["2026-01-31", "2026-02-28", "2026-03-31"]


def weeks_in_horizon(planning_end):
    """Number of weekly periods from planning_start through planning_end."""
    start_date = datetime.strptime(planning_start, "%Y-%m-%d")
    end_date = datetime.strptime(planning_end, "%Y-%m-%d")
    return int((end_date - start_date).days / 7) + 1


# Map sites data from CSV.
site_csv = pd.read_csv(DATA_DIR / "sites.csv").rename(columns={"type": "site_type"})
model.define(Site.new(model.data(site_csv).to_schema()))

# Map SKUs data from CSV.
sku_csv = pd.read_csv(DATA_DIR / "skus.csv")
model.define(SKU.new(model.data(sku_csv).to_schema()))

orders_df = pd.read_csv(DATA_DIR / "demand_orders.csv")
orders_df["due_date"] = pd.to_datetime(orders_df["due_date"])

# DATE-TO-PERIOD MAPPING: Convert due_date to integer week number
orders_df["week_num"] = (
    (orders_df["due_date"] - pd.Timestamp(planning_start)).dt.days // 7 + 1
).astype(int)

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
#   problem.satisfy(model.require(
#       sum(DemandOrder.x_unmet) <= (1 - min_service_level) * sum(DemandOrder.quantity)
#   ).where(
#       DemandOrder.created_at >= start_epoch, DemandOrder.created_at <= end_epoch
#   ))
#
#   # Period mapping from epoch: week_num = (epoch - start_epoch) // (7 * 86400) + 1
# --------------------------------------------------

# Map demand orders data (all orders; each horizon below selects its own).
order_data = model.data(
    orders_df.assign(due_date=orders_df["due_date"].dt.strftime("%Y-%m-%d"))
)
model.define(
    o := DemandOrder.new(id=order_data.id),
    o.quantity(order_data.quantity),
    o.due_date(order_data.due_date),
    o.week_num(order_data.week_num),
)

# Link demand orders to SKU and Site via foreign keys
model.define(DemandOrder.sku(SKU)).where(DemandOrder.id == order_data.id, SKU.id == order_data.sku_id)
model.define(DemandOrder.site(Site)).where(DemandOrder.id == order_data.id, Site.id == order_data.site_id)

# Map production capacity data from CSV.
pc_df = pd.read_csv(DATA_DIR / "production_capacity.csv")
inv_df = pd.read_csv(DATA_DIR / "initial_inventory.csv")

# Pre-join: merge initial inventory and SKU holding cost into ProdCapacity
# This avoids relationship traversal FD issues in solver expressions
pc_df = pc_df.merge(
    inv_df[["site_id", "sku_id", "quantity"]], on=["site_id", "sku_id"], how="left"
)
pc_df = pc_df.rename(columns={"quantity": "initial_inventory"}).fillna(0)
pc_df = pc_df.merge(
    sku_csv[["id", "holding_cost_per_week"]],
    left_on="sku_id",
    right_on="id",
    how="left",
    suffixes=("", "_sku"),
)
pc_df = pc_df.drop(columns=["id"], errors="ignore")

pc_data = model.data(pc_df)
model.define(ProdCapacity.new(pc_data.to_schema()))

# Link to Site and SKU
model.define(ProdCapacity.site(Site)).where(Site.id == ProdCapacity.site_id)
model.define(ProdCapacity.sku(SKU)).where(SKU.id == ProdCapacity.sku_id)

# Per planning horizon: the orders in scope and the weekly demand over its weeks.
scope_frames = []
demand_frames = []
for planning_end in SCENARIO_VALUES:
    num_weeks = weeks_in_horizon(planning_end)

    # DATE FILTERING: Only orders within the planning horizon are in scope
    filtered_orders = orders_df[
        (orders_df["due_date"] >= planning_start)
        & (orders_df["due_date"] <= planning_end)
    ]
    scope_frames.append(
        pd.DataFrame({"id": filtered_orders["id"], "planning_end": planning_end})
    )

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
    full_demand["planning_end"] = planning_end
    demand_frames.append(full_demand)

scope_df = pd.concat(scope_frames, ignore_index=True)
# With no order inside any horizon there is nothing to scope.
if not scope_df.empty:
    scope_data = model.data(scope_df)
    model.define(OrderInPlan(DemandOrder, scope_data.planning_end)).where(
        DemandOrder.id == scope_data.id
    )

wd_data = model.data(pd.concat(demand_frames, ignore_index=True))
model.define(
    wd := WeeklyDemand.new(
        wk_planning_end=wd_data.planning_end,
        wk_site_id=wd_data.site_id,
        wk_sku_id=wd_data.sku_id,
        wk_week_num=wd_data.week_num,
    ),
    wd.wk_quantity(wd_data.quantity),
)
