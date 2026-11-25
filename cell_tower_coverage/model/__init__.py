"""Cell tower coverage (prescriptive optimization) template: the model.

This package demonstrates maximum coverage planning in RelationalAI:

- Load sample demand zones, candidate tower sites, and tower-zone coverage pairs.
- Choose tower sites to build under a fixed capital budget and tower-count limit.
- Assign each covered demand zone to one selected tower that can serve it.
- Enforce tower capacity limits on assigned population.
- Maximize total covered population.
- Report selected sites, assigned demand zones, tower utilization, and uncovered
  population.

The optimization is modeled as a mixed-integer linear problem. `site_selection.py` states the
decision problem and its solve; `coverage_summary.py` publishes the plan totals, each tower's load
and utilization, the tower serving each zone, and the coverage rate. Each module imports the modules
whose declarations it reads.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.coverage_report` then prints the report from the deployed model.
"""

from .coverage_summary import (
    BuildBudget,
    CandidateSiteCount,
    CoveragePairCount,
    CoverageRate,
    DemandZoneCount,
    MaxNewTowers,
    SelectedBuildCost,
    TotalPopulation,
    TowerLoad,
    UncoveredPopulation,
    ZoneAssignment,
)
from .schema import CoveragePair, DemandZone, TowerSite, model
from .site_selection import CoveredPopulation, SolveStatus, assigned, covered, problem, selected
from .source import BUILD_BUDGET, DATA_DIR, MAX_NEW_TOWERS

__all__ = [
    "BUILD_BUDGET",
    "DATA_DIR",
    "MAX_NEW_TOWERS",
    "BuildBudget",
    "CandidateSiteCount",
    "CoveragePair",
    "CoveragePairCount",
    "CoverageRate",
    "CoveredPopulation",
    "DemandZone",
    "DemandZoneCount",
    "MaxNewTowers",
    "SelectedBuildCost",
    "SolveStatus",
    "TotalPopulation",
    "TowerLoad",
    "TowerSite",
    "UncoveredPopulation",
    "ZoneAssignment",
    "assigned",
    "covered",
    "model",
    "problem",
    "selected",
]
