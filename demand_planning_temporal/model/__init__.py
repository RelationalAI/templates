"""Demand Planning Temporal (prescriptive optimization) template: the model.

This package declares a multi-period production and inventory planning
optimization in RelationalAI with temporal filtering:

- Load sample CSVs describing sites, SKUs, demand orders, and production capacity.
- Model those entities as *concepts* with typed properties.
- Filter demand orders by a configurable date-range planning horizon (Pattern A:
  native date columns) and map dates to integer week periods.
- Solve a multi-period LP with inventory flow conservation:
  inv[t] = inv[t-1] + production[t] - demand[t].
- Enforce production capacity, service level, and initial inventory conditions.
- Minimize total cost (production + holding + unmet demand penalty).
- Solve one problem for each planning horizon, so the horizons are independent
  what-if scenarios.

Temporal filtering patterns demonstrated:
- Pattern A (native date columns, used here): filter by due_date string comparisons,
  then map dates to integer week numbers for std.common.range() periods.
- Pattern B (epoch integer timestamps, shown in comments in `model/source.py`): filter by
  Unix epoch seconds on columns like created_at, updated_at. See the sprint_scheduling
  template for a working epoch example.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.demand_planning` then prints the report from the deployed model.
"""

from .reasoning import PLANS, Plan
from .schema import DemandOrder, OrderInPlan, ProdCapacity, WeeklyDemand, model
from .source import DATA_DIR, planning_start

__all__ = [
    "DATA_DIR",
    "PLANS",
    "DemandOrder",
    "OrderInPlan",
    "Plan",
    "ProdCapacity",
    "WeeklyDemand",
    "model",
    "planning_start",
]
