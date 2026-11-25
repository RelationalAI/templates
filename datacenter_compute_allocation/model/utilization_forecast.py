"""Utilization forecast: the per-workload utilization-probability GNN, each workload's forecast
probability and its rank, and the split of workloads at the high-utilization cutoff."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.std import aggregates as aggs

from .schema import LabMetric, Test, Train, Val, Workload, WorkloadDependency, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

SEED = 42
GNN_EPOCHS = 80
GNN_LR = 0.002

# A workload forecast at or above this probability is expected to run at high utilization.
HIGH_UTILIZATION = 0.5

# --------------------------------------------------
# Stage 1: Predictive -- per-workload utilization-probability GNN
#   Binary node classification: for each Workload, predict the probability
#   that the workload will be high-utilization next period. Stranded
#   capacity (depreciation accruing without offsetting revenue) is the
#   operator's biggest economic exposure, so this is the load-bearing
#   forward-looking signal.
#
#   Heterogeneous graph with three cross-concept edge types:
#     1. lab_workloads: LabMetric -> Workload owned by the same lab
#     2. WorkloadDependency.blocks DAG (shared with Stage 3)
#     3. co_dated: LabMetric -> LabMetric on the same date when their
#        labs share a workload_type (cross-lab industry co-movement)
# --------------------------------------------------

# Heterogeneous graph over LabMetric and Workload with three edge types.
gnn_graph = Graph(model, name="gnn_graph", directed=False, weighted=False)

# Edge 1: LabMetric -> Workload owned by the same lab.
model.define(gnn_graph.Edge.new(src=LabMetric, dst=Workload)).where(
    LabMetric.lab == Workload.lab.name,
)

# Edge 2: WorkloadDependency.blocks DAG -- shared with Stage 3 PageRank.
dep_ref = WorkloadDependency.ref()
model.define(
    gnn_graph.Edge.new(src=dep_ref.predecessor, dst=dep_ref.successor)
).where(dep_ref.dependency_type == "blocks")

# Edge 3: LabMetric -> LabMetric, cross-lab same-date pairs whose labs
# share a workload_type. They carry the cross-lab co-movement signal that
# a per-workload tabular model cannot see.
LM_a = LabMetric.ref()
LM_b = LabMetric.ref()
Wl_a = Workload.ref()
Wl_b = Workload.ref()
model.define(gnn_graph.Edge.new(src=LM_a, dst=LM_b)).where(
    LM_a.metric_date == LM_b.metric_date,
    LM_a.lab != LM_b.lab,
    Wl_a.lab.name == LM_a.lab,
    Wl_b.lab.name == LM_b.lab,
    Wl_a.workload_type == Wl_b.workload_type,
)

# Feature configuration -- drop PKs/identifiers; type the rest.
# LabMetric.metric_date is the time_col -- it must also appear in
# datetime= per the rai-predictive-training triple-coupling rule.
pt = PropertyTransformer(
    drop=[
        LabMetric.metric_id,
        Workload.id, Workload.name,
    ],
    category=[
        LabMetric.lab,
        Workload.lab, Workload.workload_type, Workload.gpu_type_preferred,
        Workload.reservation_model,
    ],
    continuous=[
        LabMetric.active_training_runs, LabMetric.gpu_hours_consumed,
        LabMetric.tokens_trained, LabMetric.inference_qps,
        LabMetric.eval_runs_launched, LabMetric.paper_submissions,
        LabMetric.funding_announced_usd, LabMetric.model_release_events,
        LabMetric.prev_day_growth, LabMetric.prev_week_growth,
        LabMetric.growth_7d_mean,
        Workload.gpu_count_required, Workload.mem_required_gb,
        Workload.strategic_value_usd, Workload.duration_hours,
    ],
    datetime=[LabMetric.metric_date],
    time_col=[LabMetric.metric_date],
)

# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.workload_utilization` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores the
# test split with it.
gnn = GNN(
    name="workload_utilization",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    stream_logs=False,
    seed=SEED,
    n_epochs=GNN_EPOCHS,
    lr=GNN_LR,
)
Workload.predictions = gnn.predictions(domain=Test)

# The probability is a property of its own concept, not of Workload: the GNN
# reads the Workload table, so a Workload property derived from the
# predictions would make the predictions depend on themselves.
WorkloadForecast = model.Concept("WorkloadForecast", identify_by={"workload_id": String})
WorkloadForecast.utilization_probability = model.Property(
    f"{WorkloadForecast} has {Float:utilization_probability} utilization probability"
)
model.define(WorkloadForecast.new(workload_id=Workload.id)).where(Workload.predictions)
model.define(WorkloadForecast.utilization_probability(Workload.predictions.probs)).where(
    Workload.predictions,
    Workload.id == WorkloadForecast.workload_id,
)

# Each forecast's place from either end, ties broken by the lower workload id: high_rank 1 is
# the workload most likely to run at high utilization, low_rank 1 the one most likely to stall.
# The probability is negated so both keys sort ascending: the Logic engine's rank does not mix
# ascending and descending keys.
WorkloadForecast.high_rank = model.Property(f"{WorkloadForecast} has {Integer:high_rank}")
WorkloadForecast.low_rank = model.Property(f"{WorkloadForecast} has {Integer:low_rank}")
model.define(WorkloadForecast.high_rank(
    aggs.rank(-WorkloadForecast.utilization_probability, WorkloadForecast.workload_id)
))
model.define(WorkloadForecast.low_rank(
    aggs.rank(WorkloadForecast.utilization_probability, WorkloadForecast.workload_id)
))

# How many workloads have a forecast, how many of them are at or above the
# high-utilization cutoff, and how many are below it.
UtilizationSplit = model.Relationship(
    f"the forecast covers {Integer:n_total} workloads, {Integer:n_high} at high utilization "
    f"and {Integer:n_low} below"
)
model.define(UtilizationSplit(
    aggs.count(WorkloadForecast).where(WorkloadForecast.utilization_probability),
    aggs.count(WorkloadForecast).where(
        WorkloadForecast.utilization_probability >= HIGH_UTILIZATION) | 0,
    aggs.count(WorkloadForecast).where(
        WorkloadForecast.utilization_probability < HIGH_UTILIZATION) | 0,
))
