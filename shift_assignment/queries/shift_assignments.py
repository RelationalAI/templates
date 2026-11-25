"""Shift assignment report: reads the deployed shift_assignment model.

Run `python -m queries.shift_assignments` after `rai models deploy --path model`. Prints the
status of the latest refresh's solve and the worker assigned to each shift in every
coverage scenario.
"""

from model import Scenario, Shift, SolveStatus, Worker, model
from relationalai.semantics import Integer

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}\n")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")

    # ----------------------------------------------
    # Extract results per scenario
    # ----------------------------------------------

    print("\nAssignments per scenario:")
    assigned = Integer.ref()
    model.select(
        Scenario.name.alias("scenario"),
        Worker.name.alias("worker"),
        Shift.name.alias("shift"),
    ).where(
        Worker.x_assign(Shift, Scenario, assigned), assigned > 0
    ).inspect()
