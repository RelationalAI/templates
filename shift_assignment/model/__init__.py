"""Shift Assignment (prescriptive optimization) template: the model.

This package demonstrates a constraint satisfaction / feasibility problem in RelationalAI:

- Load sample CSVs describing workers, shifts, and worker-shift availability.
- Model workers and shifts as *concepts* with typed properties and an availability
  relationship.
- Choose a binary assignment variable for each available worker-shift pair.
- Enforce minimum coverage per shift and a maximum number of shifts per worker.
- Solve multiple minimum-coverage scenarios simultaneously using Scenario as a
  first-class Concept (single solve, all scenarios at once).

Modeling approach:
- Scenario is a Concept with a min_coverage parameter property.
- Decision variables are triple-argument Properties: (Worker, Shift, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all coverage levels; results extracted via model.select().

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.shift_assignments` then prints the report from the deployed model.
"""

from .reasoning import SolveStatus, problem
from .schema import Scenario, Shift, Worker, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Scenario",
    "Shift",
    "SolveStatus",
    "Worker",
    "model",
    "problem",
]
