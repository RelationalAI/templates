"""Product Configurator (constraint satisfaction, multi-solution) template: the model.

For one target region, enumerate every feasible build of a configurable
product: pick one option per slot subject to implies/excludes feature-model
rules, regional regulations, and a total-price ceiling. Solve as constraint
satisfaction with `solution_limit=MAX_CONFIGURATIONS` (MiniZinc/Chuffed)
and surface every distinct build via `Variable.values(solution_index, value)`
-- a configurator UI rarely wants a single build; a buyer's quote, a sales
playbook, and a trade-off slider all need the population of configurations.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.feasible_builds` then prints the report from the deployed model.
"""

from .reasoning import MAX_CONFIGURATIONS, PRICE_CEILING_CENTS, problem, selected_var
from .schema import Excludes, Implies, Option, Slot, model
from .source import DATA_DIR, TARGET_REGION

__all__ = [
    "DATA_DIR",
    "MAX_CONFIGURATIONS",
    "PRICE_CEILING_CENTS",
    "TARGET_REGION",
    "Excludes",
    "Implies",
    "Option",
    "Slot",
    "model",
    "problem",
    "selected_var",
]
