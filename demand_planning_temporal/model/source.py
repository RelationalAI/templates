"""Load the sample sites, SKUs, orders, capacity, and starting inventory into the demand planning model."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from .schema import SKU, DemandOrder, InitialInventory, ProdCapacity, Site, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# TEMPORAL PARAMETER: Planning horizon defined by date range
# Users adjust these to change the optimization window
planning_start = "2025-11-01"  # Start of planning horizon

# Scenarios (what-if analysis): each planning_end value is one planning horizon,
# solved by its own Problem in model/production_plans.py.
SCENARIO_VALUES = ["2026-01-31", "2026-02-28", "2026-03-31"]


def weeks_in_horizon(planning_end):
    """Number of weekly periods from planning_start through planning_end.

    A Python value because it sets the index ranges of the decision variables.
    """
    start_date = datetime.strptime(planning_start, "%Y-%m-%d")
    end_date = datetime.strptime(planning_end, "%Y-%m-%d")
    return int((end_date - start_date).days / 7) + 1


# Map sites data from CSV.
site_csv = pd.read_csv(DATA_DIR / "sites.csv").rename(columns={"type": "site_type"})
model.define(Site.new(model.data(site_csv).to_schema()))

# Map SKUs data from CSV.
sku_csv = pd.read_csv(DATA_DIR / "skus.csv")
model.define(SKU.new(model.data(sku_csv).to_schema()))

# --------------------------------------------------
# EPOCH TIMESTAMP ALTERNATIVE (Pattern B):
# If DemandOrder had epoch integer timestamps instead of date strings, the rules in
# horizon_scope.py would compare them with epoch bounds:
#
#   start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
#   end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp()) + 86399
#
#   model.where(
#       DemandOrder.created_at >= start_epoch, DemandOrder.created_at <= end_epoch
#   ).define(OrderInPlan(DemandOrder, planning_end))
#
#   # Period mapping from epoch: week_num = (created_at - start_epoch) // (7 * 86400) + 1
# --------------------------------------------------

# Map demand orders data (all orders; horizon_scope.py selects each horizon's).
order_data = model.data(pd.read_csv(DATA_DIR / "demand_orders.csv"))
model.define(
    o := DemandOrder.new(id=order_data.id),
    o.quantity(order_data.quantity),
    o.due_date(order_data.due_date),
    o.site_id(order_data.site_id),
    o.sku_id(order_data.sku_id),
)

# Link demand orders to SKU and Site via foreign keys
model.define(DemandOrder.sku(SKU)).where(DemandOrder.id == order_data.id, SKU.id == order_data.sku_id)
model.define(DemandOrder.site(Site)).where(DemandOrder.id == order_data.id, Site.id == order_data.site_id)

# Map production capacity and starting inventory data from CSV.
model.define(
    ProdCapacity.new(model.data(pd.read_csv(DATA_DIR / "production_capacity.csv")).to_schema())
)
model.define(
    InitialInventory.new(model.data(pd.read_csv(DATA_DIR / "initial_inventory.csv")).to_schema())
)

# Link to Site and SKU
model.define(ProdCapacity.site(Site)).where(Site.id == ProdCapacity.site_id)
model.define(ProdCapacity.sku(SKU)).where(SKU.id == ProdCapacity.sku_id)
