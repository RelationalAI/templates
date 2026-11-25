"""Product Configurator (constraint satisfaction, multi-solution) template: the model.

For one target region, enumerate every feasible build of a configurable
product: pick one option per slot subject to implies/excludes feature-model
rules, regional regulations, and a total-price ceiling. Solve as constraint
satisfaction with `solution_limit=MAX_CONFIGURATIONS` (MiniZinc/Chuffed)
and publish every distinct build, read via `Variable.values(solution_index, value)`
-- a configurator UI rarely wants a single build; a buyer's quote, a sales
playbook, and a trade-off slider all need the population of configurations.

Modules:
    `schema.py` declares the concepts, `source.py` loads the catalog and checks it for the
    target region, and `build_enumeration.py` states the decision problem, solves it, and
    publishes the builds and the price of each.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.feasible_builds` then prints the report from the deployed model.
"""

from .build_enumeration import (
    MAX_CONFIGURATIONS,
    PRICE_CEILING_CENTS,
    BuildTotal,
    NumPoints,
    SelectedOption,
    SolveSettings,
    SolveStatus,
    problem,
)
from .schema import Excludes, Implies, Option, Slot, model
from .source import DATA_DIR, TARGET_REGION

__all__ = [
    "DATA_DIR",
    "MAX_CONFIGURATIONS",
    "PRICE_CEILING_CENTS",
    "TARGET_REGION",
    "BuildTotal",
    "Excludes",
    "Implies",
    "NumPoints",
    "Option",
    "SelectedOption",
    "Slot",
    "SolveSettings",
    "SolveStatus",
    "model",
    "problem",
]
