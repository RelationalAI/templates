"""Shift assignment report: reads the deployed shift_assignment model.

Run `python -m queries.shift_assignments` after `rai models deploy --path model`. Prints the
formulation, the termination status of the latest refresh's solve, and the worker assigned
to each shift in every coverage scenario.
"""

from model import Scenario, Shift, SolveStatus, Worker, assigned_ref, model, problem

if __name__ == "__main__":
    problem.display()

    # Status of the latest refresh's solve. A refresh records any termination
    # status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}\n")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No feasible shift assignment: termination status {status}")

    # ----------------------------------------------
    # Extract results per scenario
    # ----------------------------------------------

    print("\nAssignments per scenario:")
    model.select(
        Scenario.name.alias("scenario"),
        Worker.name.alias("worker"),
        Shift.name.alias("shift"),
    ).where(
        Worker.x_assign(Shift, Scenario, assigned_ref), assigned_ref > 0
    ).inspect()
