"""Tour report: reads the deployed traveling_salesman model.

Run `python -m queries.tour` after `rai models deploy --path model`. Prints the status and
objective of the latest refresh's solve, and the edges of the best tour found (the shortest
when the status is OPTIMAL); stops when the formulation does not have one variable per edge
plus one per node and one minimization objective, when no edge is selected, or when the
selected edges do not number one per node.
"""

from model import Edge, Node, NumMinObjectives, NumVariables, SolveStatus, TourDistance, model
from relationalai.semantics import count

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    distance = model.select(TourDistance).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if distance:
        print(f"• objective: {round(distance[0], 9)}\n")
        print(f"HiGHS: {status[0]}, tour distance={distance[0]:.1f}")

    # Formulation check: one variable per edge plus one per node, and one minimization objective.
    n_vars = model.select(NumVariables).to_df().iloc[:, 0].tolist()
    n_objs = model.select(NumMinObjectives).to_df().iloc[:, 0].tolist()
    n_edges = model.select(count(Edge)).to_df().iloc[0, 0]
    n_nodes = model.select(count(Node)).to_df().iloc[0, 0]
    if n_vars != [n_edges + n_nodes] or n_objs != [1]:
        raise SystemExit(
            f"formulation check: {n_vars} variables for {n_edges} edges and {n_nodes} nodes, "
            f"{n_objs} minimization objectives"
        )

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
