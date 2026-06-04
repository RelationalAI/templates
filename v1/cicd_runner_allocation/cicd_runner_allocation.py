"""CI/CD runner allocation (prescriptive optimization) template.

This script demonstrates a resource assignment optimization in RelationalAI, then
diagnoses what makes a maintenance outage *unschedulable*:

- Load sample CSVs describing CI/CD runners, workflow jobs, and compatibility.
- Model runners, workflows, and assignments as concepts with typed properties.
- Assign each workflow to exactly one compatible runner, minimizing total
  pipeline cost (runner cost_per_minute * estimated job duration).
- Respect per-runner concurrency limits.
- Compare costs across budget scenarios with different concurrency caps.

Then a **maintenance outage** takes two well-connected Linux runners offline. That
funnels every high-CPU Linux job onto the one surviving large runner, whose
concurrency cap cannot hold them all -- the model is infeasible. "Infeasible" alone
is not actionable, so the outage solve requests ``solve(conflict=True)``, which
computes an irreducible infeasible subsystem (IIS): a small set of rules that cannot
all hold at once. ``in_conflict`` is a bare predicate on each constraint instance --
true when the solver reports that instance in the conflict (it collapses the solver's
IN_CONFLICT and MAYBE_IN_CONFLICT into a single membership). Each constraint is declared
with ``keyed_by``, so it carries an entity back-pointer to what it grounds over
(``assign_one.workflow`` / ``conc.runner``) and the conflict reads back as the actual
*stranded jobs* and the *binding runner cap*, joined by KEY -- no rule-name parsing.

Run:
    `python cicd_runner_allocation.py`

Output:
    Per-scenario solver status, total pipeline cost, and the runner-to-workflow
    assignment table; then the maintenance-outage diagnosis naming the stranded
    jobs and the binding concurrency cap.
"""

import warnings
from collections import namedtuple
from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Scenario parameter: concurrency cap multiplier.
# 1.0 = use each runner's default max_concurrent.
# 0.5 = half capacity (maintenance window / cost reduction).
# 1.5 = burst mode (temporary scale-up).
SCENARIO_PARAM = "concurrency_multiplier"
SCENARIO_VALUES = [0.5, 1.0, 1.5]

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("cicd_runner_allocation")

# Runner concept: CI/CD runner types with resource specs, cost, and capacity.
Runner = model.Concept("Runner", identify_by={"runner_id": Integer})
Runner.name = model.Property(f"{Runner} has {String:runner_name}")
Runner.os = model.Property(f"{Runner} has {String:runner_os}")
Runner.cpu = model.Property(f"{Runner} has {Integer:cpu}")
Runner.memory_gb = model.Property(f"{Runner} has {Integer:memory_gb}")
Runner.cost_per_minute = model.Property(f"{Runner} has {Float:cost_per_minute}")
Runner.max_concurrent = model.Property(f"{Runner} has {Integer:max_concurrent}")

runner_csv = read_csv(DATA_DIR / "runners.csv")
runner_data = model.data(runner_csv)
model.define(
    r := Runner.new(runner_id=runner_data["id"]),
    r.name(runner_data["name"]),
    r.os(runner_data["os"]),
    r.cpu(runner_data["cpu"]),
    r.memory_gb(runner_data["memory_gb"]),
    r.cost_per_minute(runner_data["cost_per_minute"]),
    r.max_concurrent(runner_data["max_concurrent"]),
)

# Workflow concept: CI/CD jobs with resource requirements and estimated duration.
Workflow = model.Concept("Workflow", identify_by={"workflow_id": Integer})
Workflow.name = model.Property(f"{Workflow} has {String:workflow_name}")
Workflow.event = model.Property(f"{Workflow} has {String:workflow_event}")
Workflow.required_os = model.Property(f"{Workflow} has {String:required_os}")
Workflow.min_cpu = model.Property(f"{Workflow} has {Integer:min_cpu}")
Workflow.min_memory_gb = model.Property(f"{Workflow} has {Integer:min_memory_gb}")
Workflow.estimated_minutes = model.Property(
    f"{Workflow} has {Integer:estimated_minutes}"
)

workflow_csv = read_csv(DATA_DIR / "workflows.csv")
wf_data = model.data(workflow_csv)
model.define(
    w := Workflow.new(workflow_id=wf_data["id"]),
    w.name(wf_data["name"]),
    w.event(wf_data["event"]),
    w.required_os(wf_data["required_os"]),
    w.min_cpu(wf_data["min_cpu"]),
    w.min_memory_gb(wf_data["min_memory_gb"]),
    w.estimated_minutes(wf_data["estimated_minutes"]),
)

# Compatibility concept: which runners can execute which workflows.
# Pre-computed from OS match and resource requirements.
Compatibility = model.Concept(
    "Compatibility", identify_by={"workflow": Workflow, "runner": Runner}
)

compat_csv = read_csv(DATA_DIR / "compatibility.csv")
compat_data = model.data(compat_csv)
CompatWorkflow = Workflow.ref()
CompatRunner = Runner.ref()
model.define(
    Compatibility.new(workflow=CompatWorkflow, runner=CompatRunner)
).where(
    CompatWorkflow.workflow_id == compat_data["workflow_id"],
    CompatRunner.runner_id == compat_data["runner_id"],
)

# Assignment concept: (workflow, runner) pairs -- the decision space.
# Only compatible pairs exist.
Assignment = model.Concept(
    "Assignment", identify_by={"workflow": Workflow, "runner": Runner}
)
Assignment.x_assigned = model.Property(f"{Assignment} assigned {Float:x_assigned}")
model.define(
    Assignment.new(workflow=Compatibility.workflow, runner=Compatibility.runner)
)


# --------------------------------------------------
# Solve with scenario analysis (concurrency multiplier)
# --------------------------------------------------

# Handles returned by a solve: the solve_info plus the variable and the two named
# constraint families, so callers can read assignments (feasible) or IIS membership
# (infeasible) by entity key.
Allocation = namedtuple("Allocation", "si assign_var assign_one conc")


def solve_allocation(concurrency_multiplier, offline_runners=(), conflict=False):
    """Solve runner assignment under a concurrency cap.

    ``offline_runners`` takes the named runners offline (a maintenance outage) by
    excluding their assignments. ``conflict=True`` requests an IIS diagnosis on the
    same solve. Returns an ``Allocation`` with the named constraint handles.
    """
    # This builder runs once per scenario (the concurrency sweep, then the outage).
    # Rebuilding the Problem -- with its per-workflow and per-runner *named*
    # constraints -- that many times trips PyRel's "rules created in a loop"
    # heuristic. The pattern is intentional here (re-solving with a different cap is
    # the point) and harmless at this size, and the per-instance names are what let
    # the IIS read back by entity key. RAI diagnostics route through Python's
    # warnings module, so silence just that one message, scoped to this builder --
    # warning state outside it is untouched.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"\[Rules created in a loop\]")

        problem = Problem(model, Float)

        # Decision variable: binary assignment of workflow to runner. A maintenance
        # outage drops the offline runners' assignments via where=. With no offline
        # runners the comprehension is empty and `[] or None` collapses to None --
        # solve_for treats an empty where= and None the same ("no filter"); the
        # `or None` just makes the no-filter case explicit.
        where_clause = [Assignment.runner.name != r for r in offline_runners] or None
        assign_var = problem.solve_for(
            Assignment.x_assigned,
            type="bin",
            name=["assign", Assignment.workflow.name, Assignment.runner.name],
            where=where_clause,
            populate=False,
        )

        AssignRef = Assignment.ref()

        # Constraint: each workflow assigned to exactly one runner. ``keyed_by`` declares
        # the workflow key, so IIS membership reads back by it (assign_one.workflow); the
        # per-workflow name is a readable label.
        assign_one = problem.satisfy(
            model.require(
                sum(AssignRef.x_assigned).where(AssignRef.workflow == Workflow).per(Workflow) == 1
            ),
            name=["assign_one", Workflow.name],
            keyed_by={"workflow": Workflow},
        )

        # Constraint: per-runner concurrency limit (scaled by scenario multiplier).
        # ``keyed_by`` declares the runner key (conc.runner).
        conc = problem.satisfy(
            model.require(
                sum(AssignRef.x_assigned).where(AssignRef.runner == Runner).per(Runner)
                <= concurrency_multiplier * Runner.max_concurrent
            ),
            name=["concurrency", Runner.name],
            keyed_by={"runner": Runner},
        )

        # Objective: minimize total pipeline cost.
        problem.minimize(
            sum(
                Assignment.x_assigned
                * Assignment.runner.cost_per_minute
                * Assignment.workflow.estimated_minutes
            )
        )

        problem.solve("highs", time_limit_sec=60, conflict=conflict)
        return Allocation(problem.solve_info(), assign_var, assign_one, conc)


def assignment_df(assign_var):
    """The chosen (workflow, runner) assignments, read off the variable by key."""
    value_ref = Float.ref()
    return (
        model.select(
            assign_var.assignment.workflow.name.alias("workflow"),
            assign_var.assignment.runner.name.alias("runner"),
        )
        .where(assign_var.values(0, value_ref), value_ref > 0.5)
        .to_df()
    )


# --------------------------------------------------
# Main execution
# --------------------------------------------------

# Maintenance outage: take two well-connected Linux runners offline. Every high-CPU
# Linux job (min_cpu >= 4) is compatible only with runners in {ubuntu-large,
# ubuntu-xlarge, self-hosted-linux} (the two min_cpu=8 jobs with just the latter
# two); with ubuntu-large and self-hosted-linux down, all seven funnel onto the one
# survivor -- whose concurrency cap cannot hold them.
OFFLINE_RUNNERS = ["ubuntu-large", "self-hosted-linux"]
HIGH_CPU_LINUX_JOBS = {
    "build-mobile-android",
    "unit-tests-api",
    "integration-tests",
    "e2e-tests-chrome",
    "docker-build",
    "performance-tests",
    "nightly-build",
}
# Guard against CSV drift: this set must stay equal to the data's actual high-CPU Linux
# jobs (min_cpu >= 4 on a Linux runner), so editing workflows.csv can't silently
# invalidate the IIS assertions below.
assert HIGH_CPU_LINUX_JOBS == set(
    workflow_csv.loc[
        (workflow_csv["min_cpu"] >= 4) & (workflow_csv["required_os"] == "linux"),
        "name",
    ]
)


if __name__ == "__main__":

    scenario_results = []

    for multiplier in SCENARIO_VALUES:
        print(f"\nRunning scenario: {SCENARIO_PARAM} = {multiplier}")
        print("-" * 50)

        alloc = solve_allocation(multiplier)

        if alloc.si.termination_status != "OPTIMAL":
            print(f"  Status: {alloc.si.termination_status} -- skipping results")
            scenario_results.append(
                {
                    "scenario": multiplier,
                    "status": str(alloc.si.termination_status),
                    "objective": None,
                }
            )
            continue

        print(f"  Status: {alloc.si.termination_status}")
        print(f"  Total pipeline cost: ${alloc.si.objective_value:.2f}")

        # Print assignments grouped by runner.
        assign_df = assignment_df(alloc.assign_var)
        print("\n  Assignments:")
        for runner_name in sorted(assign_df["runner"].unique()):
            jobs = assign_df[assign_df["runner"] == runner_name]
            workflows = ", ".join(sorted(jobs["workflow"]))
            print(f"    {runner_name} ({len(jobs)} jobs): {workflows}")

        scenario_results.append(
            {
                "scenario": multiplier,
                "status": str(alloc.si.termination_status),
                "objective": alloc.si.objective_value,
            }
        )

    # --------------------------------------------------
    # Scenario comparison
    # --------------------------------------------------

    print(f"\n{'=' * 50}")
    print("Scenario Analysis Summary")
    print("=" * 50)

    for r in scenario_results:
        if r["objective"] is not None:
            print(f"  {SCENARIO_PARAM}={r['scenario']}: "
                  f"{r['status']}, cost=${r['objective']:.2f}")
        else:
            print(f"  {SCENARIO_PARAM}={r['scenario']}: {r['status']}")

    # --------------------------------------------------
    # Maintenance outage: diagnose the infeasibility (conflict / IIS)
    # --------------------------------------------------

    print(f"\n{'=' * 50}")
    print(f"Maintenance outage: {', '.join(OFFLINE_RUNNERS)} offline")
    print("=" * 50)

    outage = solve_allocation(1.0, offline_runners=OFFLINE_RUNNERS, conflict=True)
    outage.si.display()

    assert outage.si.conflict is True
    # An infeasible model may be reported as INFEASIBLE or INFEASIBLE_OR_UNBOUNDED.
    assert outage.si.termination_status in ("INFEASIBLE", "INFEASIBLE_OR_UNBOUNDED")

    # conflict_status gates whether an IIS is available to read. A copyable diagnostic
    # dispatches on it -- inspect the conflict only for CONFLICT_FOUND, and report the
    # reason for the other documented outcomes -- rather than reading an empty IIS. This
    # model is built infeasible on purpose, so on a solver with MIP conflict support
    # (HiGHS >= 1.13) we expect CONFLICT_FOUND; the else branch is therefore also this
    # template's regression guard. (When you copy this for a model whose infeasibility is
    # not guaranteed, swap the raise for a print/return.)
    if outage.si.conflict_status == "CONFLICT_FOUND":
        # in_conflict is a bare predicate on each constraint instance; the declared
        # entity key (assign_one.workflow / conc.runner) joins the IIS to the actual
        # stranded jobs and the binding runner cap -- no rule-name parsing.
        print("\nStranded jobs (assign-one rule in conflict):")
        stranded_df = (
            model.select(outage.assign_one.workflow.name.alias("workflow"))
            .where(outage.assign_one.in_conflict)
            .to_df()
            .sort_values("workflow", ignore_index=True)
        )
        print(stranded_df.to_string(index=False))

        print("\nBinding runner caps (concurrency rule in conflict):")
        caps_df = (
            model.select(
                outage.conc.runner.name.alias("runner"),
                outage.conc.runner.max_concurrent.alias("max_concurrent"),
            )
            .where(outage.conc.in_conflict)
            .to_df()
            .sort_values("runner", ignore_index=True)
        )
        print(caps_df.to_string(index=False))

        stranded = set(stranded_df["workflow"])
        caps = set(caps_df["runner"])

        # The binding capacity is ubuntu-xlarge -- the only surviving cpu>=4 Linux runner,
        # and the sole runner cap in the IIS. (This <= constraint is the tested IIS path.)
        assert caps == {"ubuntu-xlarge"}
        # The stranded jobs are the high-CPU Linux jobs funneled onto it. A minimal IIS
        # names cap+1 = 6 of the seven (which six is solver-dependent), so assert the
        # provable lower bound and a subset rather than an exact set. This exercises
        # in_conflict on the equality (== 1) rows -- the on-engine validation point for
        # PyRel #1617.
        assert len(stranded) >= 6, (
            f"expected >= 6 stranded jobs (cap+1), got {len(stranded)}: {sorted(stranded)} "
            "-- check in_conflict on '== 1' rows"
        )
        assert stranded.issubset(HIGH_CPU_LINUX_JOBS)

        print(
            "\nTo restore feasibility, relax one member of the conflict: bring "
            "ubuntu-large or self-hosted-linux back online, or raise ubuntu-xlarge's "
            "concurrency cap. All seven high-CPU jobs share the one survivor, so lift the "
            "cap (or restore a runner) enough for all of them and re-solve to confirm -- "
            "clearing a single stranded job only resolves that row of the conflict."
        )
    else:
        # NO_CONFLICT_EXISTS => the model was feasible; NOT_SUPPORTED / FAILED => this
        # solver build produced no IIS (needs HiGHS >= 1.13 with MIP conflict support).
        raise AssertionError(
            f"expected CONFLICT_FOUND for this deliberately-infeasible model, got "
            f"{outage.si.conflict_status} -- conflict analysis needs HiGHS >= 1.13 "
            "with MIP IIS support"
        )
