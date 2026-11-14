"""Flow allocation report: reads the deployed water_allocation model.

Run `python -m queries.flow_allocations` after `rai models deploy --path model`. Prints the
formulation, the termination status and total cost of the latest refresh's solve, and the
non-trivial flow on each connection.
"""

from model import Connection, SolveStatus, TotalCost, model, problem

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it. Ipopt returns LOCALLY_SOLVED.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    if status not in (["OPTIMAL"], ["LOCALLY_SOLVED"]):
        raise SystemExit(f"No usable water allocation: termination status {status}")
    print(f"Status: {status[0]}")
    print(f"Total cost: ${cost[0]:.2f}")

    print("\nFlow allocations:")
    model.select(
        Connection.source.name.alias("source"),
        Connection.user.name.alias("user"),
        Connection.x_flow
    ).where(Connection.x_flow > 0.001).inspect()
