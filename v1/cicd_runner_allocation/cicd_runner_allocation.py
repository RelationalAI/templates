"""CI/CD runner allocation (prescriptive optimization) template.

This script demonstrates a resource assignment optimization in RelationalAI:

- Load sample CSVs describing CI/CD runners, workflow jobs, and compatibility.
- Model runners, workflows, and assignments as concepts with typed properties.
- Assign each workflow to exactly one compatible runner, minimizing total
  pipeline cost (runner cost_per_minute * estimated job duration).
- Respect per-runner concurrency limits.
- Compare costs across budget scenarios with different concurrency caps.

Run:
    `python cicd_runner_allocation.py`

Output:
    Prints per-scenario solver status, total pipeline cost, and the
    runner-to-workflow assignment table showing which runner handles each job.
"""

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

def solve_allocation(concurrency_multiplier):
    """Solve runner assignment with a given concurrency cap multiplier.

    Returns (solve_info, variable_values_df) or None if infeasible.
    """
    p = Problem(model, Float)

    # Decision variable: binary assignment of workflow to runner.
    p.solve_for(
        Assignment.x_assigned,
        type="bin",
        name=["assign", Assignment.workflow.name, Assignment.runner.name],
    )

    AssignRef = Assignment.ref()

    # Constraint: each workflow assigned to exactly one runner.
    p.satisfy(model.require(
        sum(AssignRef.x_assigned)
        .where(AssignRef.workflow == Workflow)
        .per(Workflow) == 1
    ))

    # Constraint: per-runner concurrency limit (scaled by scenario multiplier).
    p.satisfy(model.require(
        sum(AssignRef.x_assigned)
        .where(AssignRef.runner == Runner)
        .per(Runner) <= concurrency_multiplier * Runner.max_concurrent
    ))

    # Objective: minimize total pipeline cost.
    p.minimize(
        sum(
            Assignment.x_assigned
            * Assignment.runner.cost_per_minute
            * Assignment.workflow.estimated_minutes
        )
    )

    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()

    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        return None

    return si, p.variable_values().to_df()


# --------------------------------------------------
# Main execution
# --------------------------------------------------

if __name__ == "__main__":

    scenario_results = []

    for multiplier in SCENARIO_VALUES:
        print(f"\nRunning scenario: {SCENARIO_PARAM} = {multiplier}")
        print("-" * 50)

        result = solve_allocation(multiplier)

        if result is None:
            print("  Status: INFEASIBLE -- skipping results")
            scenario_results.append({
                "scenario": multiplier,
                "status": "INFEASIBLE",
                "objective": None,
            })
            continue

        si, var_df = result
        print(f"  Status: {si.termination_status}")
        print(f"  Total pipeline cost: ${si.objective_value:.2f}")

        # Extract assignments.
        assign_df = var_df[
            var_df["name"].str.startswith("assign_")
            & (var_df["value"] > 0.5)
        ].copy()
        assign_df[["_", "workflow", "runner"]] = (
            assign_df["name"].str.split("_", n=2, expand=True)
        )

        # Print assignments grouped by runner.
        print("\n  Assignments:")
        for runner_name in sorted(assign_df["runner"].unique()):
            jobs = assign_df[assign_df["runner"] == runner_name]
            workflows = ", ".join(sorted(jobs["workflow"]))
            print(f"    {runner_name} ({len(jobs)} jobs): {workflows}")

        scenario_results.append({
            "scenario": multiplier,
            "status": si.termination_status,
            "objective": si.objective_value,
        })

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
