"""Gating scores: each workload's gating score, from reverse PageRank on the workload-dependency DAG."""

from relationalai.semantics import Float
from relationalai.semantics.reasoners.graph import Graph

# The GNN takes as features the Workload properties declared before its predictions, so it is
# declared first: the gating score is a graph result, not a feature.
from . import utilization_forecast  # noqa: F401
from .schema import Workload, WorkloadDependency, model

# --------------------------------------------------
# Stage 3: Graph -- workload-dependency PageRank (gating score)
#   Reverse-PageRank on the WorkloadDependency.blocks DAG: a high
#   `gating_score` means many downstream workloads are gated by this
#   one (frontier pretrain that gates 14 fine-tunes + evals lands at
#   the top).
# --------------------------------------------------

dag = Graph(model, name="dependency_dag", directed=True, weighted=False, node_concept=Workload)

# Edge reversal: PageRank flows toward upstream gating workloads.
# We define edges as (successor -> predecessor) so a node's PageRank
# accumulates incoming flow from everything it gates.
dep_ref = WorkloadDependency.ref()
model.define(
    dag.Edge.new(src=dep_ref.successor, dst=dep_ref.predecessor)
).where(dep_ref.dependency_type == "blocks")

pagerank = dag.pagerank()
Workload.gating_score = model.Property(
    f"{Workload} has {Float:gating_score} gating score"
)
score_ref = Float.ref("g")
wl_ref = Workload.ref()
model.define(wl_ref.gating_score(score_ref)).where(pagerank(wl_ref, score_ref))
