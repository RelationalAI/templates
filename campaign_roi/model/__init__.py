"""Campaign ROI (prescriptive optimization) template: the model.

This package demonstrates a marketing budget reallocation LP in RelationalAI:

- Load sample CSV describing marketing campaigns across regions, each with a
  current budget and a conversion rate.
- Choose a non-negative new budget per campaign (continuous decision variable).
- Enforce a per-campaign floor (no campaign can drop below FLOOR_FRACTION of
  current) and cap (no campaign can exceed CAP_MULTIPLIER * current).
- Enforce a regional cap on a paused region: total spend in PAUSED_REGION
  cannot exceed PAUSED_CAP_FRACTION of TOTAL_BUDGET.
- Enforce a total budget constraint.
- Maximize total expected conversions = sum(budget * conversion_rate).

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.budget_reallocation` then prints the report from the deployed model.
"""

from .reasoning import (
    CAP_MULTIPLIER,
    FLOOR_FRACTION,
    PAUSED_CAP_FRACTION,
    PAUSED_REGION,
    TOTAL_BUDGET,
    SolveStatus,
    TotalConversions,
    problem,
)
from .schema import Campaign, model
from .source import DATA_DIR

__all__ = [
    "CAP_MULTIPLIER",
    "DATA_DIR",
    "FLOOR_FRACTION",
    "PAUSED_CAP_FRACTION",
    "PAUSED_REGION",
    "TOTAL_BUDGET",
    "Campaign",
    "SolveStatus",
    "TotalConversions",
    "model",
    "problem",
]
