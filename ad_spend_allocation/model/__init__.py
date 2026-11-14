"""Ad spend allocation (prescriptive optimization) template: the model.

This package demonstrates a mixed-integer linear optimization (MILP) workflow
in RelationalAI:

- Load sample CSVs describing marketing channels, campaigns, and channel-campaign
  effectiveness (conversion rate).
- Model those entities as *concepts* with typed properties.
- Create an `Allocation` decision concept with two decision variables per
  channel-campaign pair: `spend` (continuous) and `active` (binary).
- Add constraints for channel min/max spend (when active), per-campaign budget,
  and "at least one channel per campaign" coverage.
- Maximize total expected conversions: sum(spend * conversion_rate).
- Run scenario analysis over different total budget levels using Scenario as a
  first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a total_budget parameter property.
- Decision variables are multi-argument Properties indexed by (Allocation, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all budget levels; results extracted via model.select().

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.spend_allocation` then prints the report from the deployed model.
"""

from .reasoning import problem, x_active, x_spend
from .schema import Allocation, Campaign, Channel, Effectiveness, Scenario, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Allocation",
    "Campaign",
    "Channel",
    "Effectiveness",
    "Scenario",
    "model",
    "problem",
    "x_active",
    "x_spend",
]
