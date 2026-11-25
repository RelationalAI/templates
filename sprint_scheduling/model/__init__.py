"""Sprint Scheduling (prescriptive optimization) template: the model.

This package declares a sprint assignment optimization in RelationalAI with
epoch-based temporal filtering (Pattern B):

- Load sample CSVs describing developers, sprints, issues, and developer-team skills.
- Model those entities as *concepts* with typed properties.
- Filter issues by epoch timestamp (created_at) to scope the planning horizon
  (`source.py`).
- Map each issue's created_at epoch to a target sprint via epoch-to-period mapping
  (`target_sprints.py`).
- Assign each issue to exactly one developer in one sprint (binary variables).
- Enforce developer capacity per sprint and skill-matching constraints.
- Minimize weighted completion time (high-priority issues penalized more for delay).
- Solve one problem per capacity scenario, so an infeasible scenario leaves the
  others solved.

Temporal filtering pattern (epoch integers -- Pattern B):
- Convert date-range boundaries to Unix epoch seconds.
- Filter event rows by epoch as they load into the model.
- Map epochs to categorical periods (sprints) by comparing against sprint
  start/end epochs.
- Compare with Pattern A (native date strings) in the demand_planning_temporal
  template.

The sprint assignment problem is in `sprint_assignment.py`, which imports the
module declaring the target sprints it reads.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.sprint_plan` then prints the report from the deployed model.
"""

from .schema import Assignment, Developer, Issue, Skill, Sprint, model
from .source import DATA_DIR, PlanningHorizon
from .sprint_assignment import (
    SCENARIO_PARAM,
    SCENARIO_VALUES,
    Assigned,
    SolveStatus,
    WeightedCompletion,
    problems,
)

__all__ = [
    "DATA_DIR",
    "SCENARIO_PARAM",
    "SCENARIO_VALUES",
    "Assigned",
    "Assignment",
    "Developer",
    "Issue",
    "PlanningHorizon",
    "Skill",
    "SolveStatus",
    "Sprint",
    "WeightedCompletion",
    "model",
    "problems",
]
