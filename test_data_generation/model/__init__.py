"""Test Data Generation (prescriptive optimization) template: the model.

This package demonstrates an LP-based test data sizing workflow in RelationalAI:

- Load schema definitions, referential integrity constraints, and row-count targets
  from CSV.
- Model database tables as *concepts* with target, min, and max row counts.
- Solve an LP to choose feasible table row counts close to targets, respecting
  foreign key relationships, cardinality bounds, and coverage requirements.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.test_data_plan` then prints the report from the deployed model.
"""

from .row_count_plan import SolveStatus, TotalDeviation, problem
from .schema import Table, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "SolveStatus", "Table", "TotalDeviation", "model", "problem"]
