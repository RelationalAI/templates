"""Gating scores: reverse PageRank on the workload-dependency DAG, and each workload's place in the
gating ranking."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

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

# The gating ranking, highest gating score first, ties broken by the lower workload id. It
# lives on a concept of its own: the GNN reads every property of Workload as a feature, so a
# rank on Workload would feed it. The score is negated so both keys sort ascending.
GatingRank = model.Concept("GatingRank", identify_by={"workload_id": String})
GatingRank.gating_score = model.Property(f"{GatingRank} has {Float:gating_score} gating score")
GatingRank.gating_rank = model.Property(f"{GatingRank} has {Integer:gating_rank}")
model.define(GatingRank.new(workload_id=Workload.id)).where(Workload.gating_score)
model.define(GatingRank.gating_score(Workload.gating_score)).where(
    Workload.id == GatingRank.workload_id
)
model.define(GatingRank.gating_rank(
    aggs.rank(-GatingRank.gating_score, GatingRank.workload_id)
))
