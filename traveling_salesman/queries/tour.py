"""Tour report: reads the deployed traveling_salesman model.

Run `python -m queries.tour` after `rai models deploy --path model`. Checks the problem's
size against the deployed edges and nodes, prints the formulation, the termination status
and tour distance of the latest refresh's solve, and the edges of the shortest tour. A
failed check stops the report with an error.
"""

from model import (
    Edge,
    Node,
    SolveStatus,
    TourDistance,
    edge_count,
    model,
    node_count,
    num_min_objectives,
    num_variables,
    problem,
)

if __name__ == "__main__":
    # Check model structure: one variable per edge and per node, one minimization objective.
    variables = model.select(num_variables).to_df().iloc[:, 0].tolist()
    edges = model.select(edge_count).to_df().iloc[:, 0].tolist()
    nodes_count = model.select(node_count).to_df().iloc[:, 0].tolist()
    if len(edges) != 1 or len(nodes_count) != 1 or variables != [edges[0] + nodes_count[0]]:
        raise SystemExit(
            f"expected one variable per edge and node, got {variables} for edges {edges}, "
            f"nodes {nodes_count}"
        )
    objectives = model.select(num_min_objectives).to_df().iloc[:, 0].tolist()
    if objectives != [1]:
        raise SystemExit(f"expected one minimization objective, got {objectives}")
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    distance = model.select(TourDistance).to_df().iloc[:, 0].tolist()
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal tour: termination status {status}")
    print(f"HiGHS: {status[0]}, tour distance={distance[0]:.1f}")

    # Extract solution: the tour leaves every node exactly once.
    nodes = sorted(model.select(Node.v).to_df().iloc[:, 0].tolist())
    tour = model.select(Edge.i.alias("from"), Edge.j.alias("to")).where(Edge.x > 0.5).to_df()
    if sorted(tour["from"].tolist()) != nodes:
        raise SystemExit(f"tour does not leave every node exactly once: {tour}")
    print("\nTour edges:")
    print(tour)
    print()
