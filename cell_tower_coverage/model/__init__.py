"""Cell tower coverage (prescriptive optimization) template: the model.

This package demonstrates maximum coverage planning in RelationalAI:

- Load sample demand zones, candidate tower sites, and tower-zone coverage pairs.
- Choose tower sites to build under a fixed capital budget and tower-count limit.
- Assign each covered demand zone to one selected tower that can serve it.
- Enforce tower capacity limits on assigned population.
- Maximize total covered population.
- Report selected sites, assigned demand zones, tower utilization, and uncovered
  population.

The optimization is modeled as a mixed-integer linear problem.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.coverage_report` then prints the report from the deployed model.
"""

from .reasoning import CoveredPopulation, SolveStatus, assigned, covered, problem, selected
from .schema import CoveragePair, DemandZone, TowerSite, model
from .source import BUILD_BUDGET, DATA_DIR, MAX_NEW_TOWERS

__all__ = [
    "BUILD_BUDGET",
    "DATA_DIR",
    "MAX_NEW_TOWERS",
    "CoveragePair",
    "CoveredPopulation",
    "DemandZone",
    "SolveStatus",
    "TowerSite",
    "assigned",
    "covered",
    "model",
    "problem",
    "selected",
]
