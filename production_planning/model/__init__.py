"""Production Planning (prescriptive optimization) template: the model.

This package demonstrates a mixed-integer linear optimization (MILP) workflow
in RelationalAI:

- Load sample CSVs describing products, machines, and machine-product production rates.
- Model those entities as *concepts* with typed properties.
- Create a Production decision concept with an integer decision variable for each
  machine-product pair.
- Add constraints for machine hour capacity and product demand satisfaction.
- Maximize total profit, with scenario analysis over demand multipliers using
  Scenario as a first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a demand_multiplier parameter property.
- Decision variables are multi-argument Properties indexed by (Production, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all demand levels; results extracted via model.select().

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.production_plan` then prints the report from the deployed model.
"""

from .reasoning import Production, SolveStatus, TotalProfit, problem, x_qty
from .schema import Machine, Product, Rate, Scenario, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Machine",
    "Product",
    "Production",
    "Rate",
    "Scenario",
    "SolveStatus",
    "TotalProfit",
    "model",
    "problem",
    "x_qty",
]
