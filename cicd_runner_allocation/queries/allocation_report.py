"""Runner allocation report: reads the deployed cicd_runner_allocation model.

Run `python -m queries.allocation_report` after `rai models deploy --path model`. Prints, per
concurrency scenario, the status and total pipeline cost of the latest refresh's solve and the
runner-to-workflow assignments; then the maintenance outage's status and its conflict: the
stranded jobs and the binding runner cap.
"""

from model import (
    OFFLINE_RUNNERS,
    SCENARIO_PARAM,
    SCENARIO_VALUES,
    Assigned,
    BindingCap,
    Runner,
    SolveStatus,
    Stranded,
    TotalCost,
    Workflow,
    model,
    problems,
)


def solve_result(key):
    """Print and return one solve's published status and cost."""
    status = model.select(SolveStatus[key]).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost[key]).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")
    return status, cost


if __name__ == "__main__":
    scenario_results = []

    for multiplier in SCENARIO_VALUES:
        print(f"\nRunning scenario: {SCENARIO_PARAM} = {multiplier}")
        print("-" * 50)

        status, cost = solve_result(multiplier)
        if status != ["OPTIMAL"]:
            print(f"  Status: {', '.join(status)} -- skipping results")
            scenario_results.append(
                {"scenario": multiplier, "status": ", ".join(status), "objective": None}
            )
            continue

        print(f"  Status: {status[0]}")
        print(f"  Total pipeline cost: ${cost[0]:.2f}")

        # Print assignments grouped by runner.
        assign_df = (
            model.select(Workflow.name.alias("workflow"), Runner.name.alias("runner"))
            .where(Assigned[multiplier](Workflow, Runner))
            .to_df()
        )
        print("\n  Assignments:")
        for runner_name in sorted(assign_df["runner"].unique()):
            jobs = assign_df[assign_df["runner"] == runner_name]
            workflows = ", ".join(sorted(jobs["workflow"]))
            print(f"    {runner_name} ({len(jobs)} jobs): {workflows}")

        scenario_results.append({"scenario": multiplier, "status": status[0], "objective": cost[0]})

    # --------------------------------------------------
    # Scenario comparison
    # --------------------------------------------------

    print(f"\n{'=' * 50}")
    print("Scenario Analysis Summary")
    print("=" * 50)

    for r in scenario_results:
        if r["objective"] is not None:
            print(f"  {SCENARIO_PARAM}={r['scenario']}: {r['status']}, cost=${r['objective']:.2f}")
        else:
            print(f"  {SCENARIO_PARAM}={r['scenario']}: {r['status']}")

    # --------------------------------------------------
    # Maintenance outage: diagnose the infeasibility (conflict / IIS)
    # --------------------------------------------------

    print(f"\n{'=' * 50}")
    print(f"Maintenance outage: {', '.join(OFFLINE_RUNNERS)} offline")
    print("=" * 50)

    # The outage is infeasible on purpose, so anything but a conflict found means the tables
    # below would not be a diagnosis: the outage was feasible, or the solver found no IIS.
    status, _ = solve_result("outage")
    if status not in (["INFEASIBLE"], ["INFEASIBLE_OR_UNBOUNDED"]):
        raise SystemExit(f"termination status {status}")
    conflict_status = problems["outage"].solve_info().conflict_status
    if conflict_status != "CONFLICT_FOUND":
        raise SystemExit(
            f"conflict status {conflict_status}: conflict analysis needs HiGHS 1.13 or later "
            "with MIP IIS support"
        )

    # The model publishes the conflict keyed by the workflow / runner each constraint was
    # declared over, so the stranded jobs and the binding cap read back by entity key.
    print("\nStranded jobs (assign-one rule in conflict):")
    stranded_df = (
        model.select(Workflow.name.alias("workflow"))
        .where(Stranded["outage"](Workflow))
        .to_df()
        .sort_values("workflow", ignore_index=True)
    )
    print(stranded_df.to_string(index=False))

    print("\nBinding runner caps (concurrency rule in conflict):")
    caps_df = (
        model.select(Runner.name.alias("runner"), Runner.max_concurrent.alias("max_concurrent"))
        .where(BindingCap["outage"](Runner))
        .to_df()
        .sort_values("runner", ignore_index=True)
    )
    print(caps_df.to_string(index=False))

    # The surviving large runner's cap binds, and any six of the seven high-CPU Linux jobs
    # already exceed it, so the conflict holds at least six distinct ones of those seven (the
    # solver chooses which).
    high_cpu_linux = set(
        model.select(Workflow.name)
        .where(Workflow.min_cpu >= 4, Workflow.required_os == "linux")
        .to_df()
        .iloc[:, 0]
    )
    stranded = set(stranded_df["workflow"])
    if (
        set(caps_df["runner"]) != {"ubuntu-xlarge"}
        or len(high_cpu_linux) != 7
        or len(stranded) < 6
        or not stranded <= high_cpu_linux
    ):
        raise SystemExit(
            "expected ubuntu-xlarge's cap and at least six of the seven high-CPU Linux jobs "
            f"in the conflict, got caps {sorted(caps_df['runner'])} and jobs {sorted(stranded)}"
        )
    print(
        "\nTo restore feasibility, relax one member of the conflict: bring "
        "ubuntu-large or self-hosted-linux back online, or raise ubuntu-xlarge's "
        "concurrency cap. All seven high-CPU jobs share the one survivor, so lift the "
        "cap (or restore a runner) enough for all of them and re-deploy to confirm -- "
        "clearing a single stranded job only resolves that row of the conflict."
    )
