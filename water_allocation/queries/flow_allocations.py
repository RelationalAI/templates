"""Flow allocation report: reads the deployed water_allocation model.

Run `python -m queries.flow_allocations` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and the non-trivial flow on each
connection.
"""

from model import Connection, SolveStatus, TotalCost, model

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")

    print(f"Status: {status[0]}")  # Ipopt returns LOCALLY_SOLVED
    if cost:
        print(f"Total cost: ${cost[0]:.2f}")

    print("\nFlow allocations:")
    model.select(
        Connection.source.name.alias("source"),
        Connection.user.name.alias("user"),
        Connection.x_flow
    ).where(Connection.x_flow > 0.001).inspect()
