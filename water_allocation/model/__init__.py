"""Water Allocation (nonlinear optimization) template: the model.

This package demonstrates a nonlinear optimization model solved with Ipopt
in RelationalAI:

- Load sample CSVs describing water sources, users (demand points), and connections.
- Model those entities as *concepts* with typed properties.
- Choose a non-negative flow on each connection to meet all user demands.
- Enforce source capacity limits and connection flow limits.
- Account for nonlinear transmission losses: loss increases with utilization,
  so effective delivery = flow * (1 - loss_rate * flow / max_flow).
  This quadratic constraint requires a nonlinear solver.
- Minimize total sourcing cost.

Solver: Ipopt (interior-point for nonlinear programs). Ipopt finds locally
optimal solutions for smooth NLP problems with continuous variables.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.flow_allocations` then prints the report from the deployed model.
"""

from .reasoning import SolveStatus, TotalCost, problem
from .schema import Connection, Source, User, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Connection",
    "Source",
    "SolveStatus",
    "TotalCost",
    "User",
    "model",
    "problem",
]
