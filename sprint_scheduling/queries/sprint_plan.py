"""Sprint plan report: reads the deployed sprint_scheduling model.

Run `python -m queries.sprint_plan` after `rai models deploy --path model`. Prints, for each
capacity scenario, the status and objective of the latest refresh's solve and, when the
scenario is solved, the planning horizon and the issue assignments, then a summary of all
scenarios.
"""

from model import (
    SCENARIO_PARAM,
    SCENARIO_VALUES,
    Assigned,
    Developer,
    Issue,
    SolveStatus,
    Sprint,
    WeightedCompletion,
    filtered_issues,
    issues_df,
    model,
    planning_end,
    planning_start,
)

if __name__ == "__main__":
    scenario_results = []

    for scenario_value in SCENARIO_VALUES:
        print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

        status = model.select(SolveStatus[scenario_value]).to_df().iloc[:, 0].tolist()
        objective = model.select(WeightedCompletion[scenario_value]).to_df().iloc[:, 0].tolist()
        print(f"\nSolve result:\n• status: {', '.join(status)}")
        if objective:
            print(f"• objective: {round(objective[0], 9)}\n")

        scenario_results.append(
            {
                "scenario": scenario_value,
                "status": ", ".join(status),
                "objective": round(objective[0], 9) if objective else None,
            }
        )
        if status != ["OPTIMAL"]:
            print(f"  Status: {', '.join(status)} — skipping results")
            continue
        print(f"  Status: {status[0]}, Objective: {round(objective[0], 9)}")
        print(f"  Planning horizon: {planning_start} to {planning_end}")
        print(f"  Issues in scope: {len(filtered_issues)} (of {len(issues_df)} total)")

        # Assignment results
        assigned = model.select(
            Issue.key.alias("issue"),
            Developer.name.alias("developer"),
            Sprint.name.alias("sprint"),
        ).where(Assigned[scenario_value](Issue, Developer, Sprint)).to_df()
        print("\n  Assignments:")
        print(assigned.to_string(index=False))

    # Summary
    print("\n" + "=" * 50)
    print("Scenario Analysis Summary")
    print("=" * 50)
    for result in scenario_results:
        obj = result["objective"]
        obj_str = f"{obj}" if obj is not None else "N/A"
        print(
            f"  capacity_multiplier={result['scenario']}: {result['status']}, obj={obj_str}"
        )
