"""Diet optimization (prescriptive optimization) template: the model.

This package declares a classic diet linear optimization problem in RelationalAI:

- Map sample data from CSVs describing foods, nutrients, and per-food nutrient quantities.
- Model foods and nutrients as *concepts* with typed properties.
- Choose a non-negative amount of each food to satisfy nutrient bounds.
- Minimize total cost.
- Solve multiple scenarios scaling nutrient requirements using Scenario as a
  first-class Concept (single solve, all scenarios simultaneously).

Modeling approach:
- Scenario is a Concept with a nutrient_scaling parameter property.
- Decision variables are multi-argument Properties indexed by (Food, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all scaling levels; results extracted via model.select().

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.diet_plan` then prints the report from the deployed model.
"""

from .reasoning import SolveStatus, TotalCost, problem, x_amt
from .schema import Food, Nutrient, Scenario, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Food",
    "Nutrient",
    "Scenario",
    "SolveStatus",
    "TotalCost",
    "model",
    "problem",
    "x_amt",
]
