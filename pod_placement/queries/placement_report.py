"""Placement report: reads the deployed pod_placement model.

Run `python -m queries.placement_report` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve, per-node utilization, the chosen
(pod, node) placements, and any unplaced deployments.
"""

from model import (
    Deployment,
    Node,
    PlacedDeployments,
    Pod,
    SolveStatus,
    model,
    x,
)
from relationalai.semantics import sum

if __name__ == "__main__":
    # The report stops unless the solver proved OPTIMAL: if you raise `time_limit_sec` and the
    # solver returns a feasible-but-not-proven-optimal result, the report raises rather than
    # print a partial solution. Soften to a `print(...)` warning if you want the inspection
    # blocks to run on partial solutions.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    placed = model.select(PlacedDeployments).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    print(f"• objective: {placed[0]}\n")

    # ----------------------------------------------
    # Inspect results
    # ----------------------------------------------

    print("\nPer-node utilization:")
    model.select(
        Node.id.alias("node_id"),
        Node.name.alias("node"),
        sum(Pod.cpu_millicores * x).where(Pod.on_node(Node, x)).per(Node).alias("cpu_used"),
        Node.cpu_millicores.alias("cpu_cap"),
        sum(Pod.memory_mib * x).where(Pod.on_node(Node, x)).per(Node).alias("memory_used"),
        sum(Pod.gpu_units * x).where(Pod.on_node(Node, x)).per(Node).alias("gpu_used"),
    ).inspect()

    print("\nPlaced pods (pod_id -> node_id):")
    model.select(
        Pod.id.alias("pod_id"),
        Node.id.alias("node_id"),
    ).where(Pod.on_node(Node, 1)).inspect()

    print("\nUnplaced deployments (if any):")
    model.select(
        Deployment.id.alias("deployment_id"),
        Deployment.name.alias("deployment"),
        Deployment.replicas.alias("replicas"),
    ).where(Deployment.placed == 0).inspect()
