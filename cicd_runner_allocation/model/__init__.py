"""CI/CD runner allocation (prescriptive optimization) template: the model.

This package declares a resource assignment optimization in RelationalAI, then
diagnoses what makes a maintenance outage *unschedulable*:

- Load sample CSVs describing CI/CD runners, workflow jobs, and compatibility.
- Model runners, workflows, and assignments as concepts with typed properties.
- Assign each workflow to exactly one compatible runner, minimizing total
  pipeline cost (runner cost_per_minute * estimated job duration).
- Respect per-runner concurrency limits.
- Compare costs across budget scenarios with different concurrency caps, one
  problem per scenario.

Then a **maintenance outage** takes two well-connected Linux runners offline. That
funnels every high-CPU Linux job onto the one surviving large runner, whose
concurrency cap cannot hold them all -- the model is infeasible. "Infeasible" alone
is not actionable, so the outage problem is configured with ``conflict=True``, which
computes an irreducible infeasible subsystem (IIS): a small set of rules that cannot
all hold at once. ``in_conflict`` is a bare predicate on each constraint instance --
true when the solver reports that instance in the conflict. Each constraint is declared
with ``keyed_by``, so it carries an entity back-pointer to what it grounds over
(``assign_one.workflow`` / ``conc.runner``) and the model publishes the conflict as the
actual *stranded jobs* and the *binding runner cap*, joined by KEY -- no rule-name parsing.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.allocation_report` then prints the report from the deployed model.
"""

from .reasoning import (
    SCENARIO_PARAM,
    SCENARIO_VALUES,
    Assigned,
    BindingCap,
    SolveStatus,
    Stranded,
    TotalCost,
    problems,
)
from .schema import Assignment, Compatibility, Runner, Workflow, model
from .source import DATA_DIR, OFFLINE_RUNNERS

__all__ = [
    "DATA_DIR",
    "OFFLINE_RUNNERS",
    "SCENARIO_PARAM",
    "SCENARIO_VALUES",
    "Assigned",
    "Assignment",
    "BindingCap",
    "Compatibility",
    "Runner",
    "SolveStatus",
    "Stranded",
    "TotalCost",
    "Workflow",
    "model",
    "problems",
]
