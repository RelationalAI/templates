"""Tour report: reads the deployed traveling_salesman model.

Run `python -m queries.tour` after `rai models deploy --path model`. Prints the status and
objective of the latest refresh's solve, and the edges of the shortest tour; stops when no
edge is selected or the selected edges do not number one per node.
"""

from model import Edge, Node, SolveStatus, TourDistance, model

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    distance = model.select(TourDistance).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if distance:
        print(f"• objective: {round(distance[0], 9)}\n")
        print(f"HiGHS: {status[0]}, tour distance={distance[0]:.1f}")

    # A tour selects one edge per node. The count alone does not prove a single cycle, but
    # with the edges in both directions between every pair of nodes (as the README
    # requires) the degree and ordering constraints make any solution one cycle. A
    # time-limited incumbent with that count is still reported.
    tour = model.select(Edge.i.alias("from"), Edge.j.alias("to")).where(Edge.x > 0.5).to_df()
    if tour.empty or len(tour) != len(model.select(Node.v).to_df()):
        raise SystemExit(f"termination status {status}")
    print("\nTour edges:")
    print(tour)
    print()
