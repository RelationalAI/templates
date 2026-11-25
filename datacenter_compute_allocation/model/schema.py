"""Semantic schema for the datacenter compute allocation template: campuses, labs, workloads, scenarios, and the GNN task tables."""

from relationalai.semantics import Boolean, Date, Float, Integer, Model, String

model = Model("Datacenter Compute Allocation")

# DataCenterRequest concept: the 5 hyperscaler campuses already approved
# and energized (snapshot of the upstream energy_grid_planning $300M decision).
DataCenterRequest = model.Concept("DataCenterRequest", identify_by={"id": String})
DataCenterRequest.name = model.Property(f"{DataCenterRequest} has {String:name}")
DataCenterRequest.hyperscaler = model.Property(
    f"{DataCenterRequest} from hyperscaler {String:hyperscaler}"
)
DataCenterRequest.requested_mw = model.Property(
    f"{DataCenterRequest} requesting {Float:requested_mw} MW"
)
DataCenterRequest.approved_mw = model.Property(
    f"{DataCenterRequest} approved at {Float:approved_mw} MW"
)
DataCenterRequest.pue = model.Property(
    f"{DataCenterRequest} has power usage effectiveness {Float:pue}"
)
DataCenterRequest.dollars_per_mwh = model.Property(
    f"{DataCenterRequest} energy rate {Float:dollars_per_mwh} USD per MWh"
)

AILab = model.Concept("AILab", identify_by={"id": String})
AILab.name = model.Property(f"{AILab} has {String:name}")
AILab.lab_type = model.Property(f"{AILab} has type {String:lab_type}")
AILab.contract_tier = model.Property(f"{AILab} has contract tier {String:contract_tier}")
AILab.is_strategic_anchor = model.Property(
    f"{AILab} is strategic anchor {Boolean:is_strategic_anchor}"
)
AILab.payment_per_gpu_hour = model.Property(
    f"{AILab} has {Float:payment_per_gpu_hour} payment per GPU hour"
)

GpuPool = model.Concept("GpuPool", identify_by={"id": String})
GpuPool.data_center = model.Relationship(f"{GpuPool} located at {DataCenterRequest}")
GpuPool.gpu_type = model.Property(f"{GpuPool} has GPU type {String:gpu_type}")
GpuPool.gpu_count = model.Property(f"{GpuPool} has {Integer:gpu_count} GPUs")
GpuPool.mem_per_gpu_gb = model.Property(
    f"{GpuPool} has {Integer:mem_per_gpu_gb} GB memory per GPU"
)
GpuPool.interconnect = model.Property(f"{GpuPool} uses interconnect {String:interconnect}")
GpuPool.power_per_gpu_kw = model.Property(
    f"{GpuPool} draws {Float:power_per_gpu_kw} kW per GPU"
)
GpuPool.available_gpu_count = model.Property(
    f"{GpuPool} has {Integer:available_gpu_count} available GPUs"
)
# Per-GPU hourly amortization. Grounded in capex/3-year life:
# H100 ~$1.14, H200 ~$1.52, GB200 ~$2.66 per GPU-hour. Captures the
# real margin pressure that the SemiAnalysis 14-16% net BMaaS figure
# surfaces (energy alone is ~1% of revenue; depreciation is the bulk).
GpuPool.hourly_depreciation_rate = model.Property(
    f"{GpuPool} has {Float:hourly_depreciation_rate} USD per GPU per hour"
)

Workload = model.Concept("Workload", identify_by={"id": String})
Workload.name = model.Property(f"{Workload} has {String:name}")
Workload.lab = model.Relationship(f"{Workload} owned by {AILab}")
Workload.workload_type = model.Property(f"{Workload} has type {String:workload_type}")
Workload.reservation_model = model.Property(
    f"{Workload} uses reservation model {String:reservation_model}"
)
Workload.gpu_count_required = model.Property(
    f"{Workload} requires {Integer:gpu_count_required} GPUs"
)
Workload.mem_required_gb = model.Property(
    f"{Workload} requires {Integer:mem_required_gb} GB per GPU"
)
Workload.gpu_type_preferred = model.Property(
    f"{Workload} prefers GPU type {String:gpu_type_preferred}"
)
Workload.duration_hours = model.Property(
    f"{Workload} runs for {Float:duration_hours} hours"
)
Workload.strategic_value_usd = model.Property(
    f"{Workload} has {Float:strategic_value_usd} strategic value USD"
)

# GPU-type allowlist as its own Concept (composite identity), not as a
# multi-valued Relationship on Workload. Multi-valued Relationships on a
# GNN-node concept trip the engine's functional-dependency check whenever
# downstream queries materialize the parent's full property graph; modeling
# the allowlist as a separate Concept avoids the issue and lets us iterate
# over (workload, gpu_type) pairs in the eligibility rules.
WorkloadGpuCompat = model.Concept(
    "WorkloadGpuCompat",
    identify_by={"workload": Workload, "gpu_type": String},
)

# Workload dependency edges. The "blocks" subset is shared between the GNN
# (heterogeneous edge) and the gating-score PageRank.
WorkloadDependency = model.Concept(
    "WorkloadDependency",
    identify_by={"predecessor": Workload, "successor": Workload},
)
WorkloadDependency.dependency_type = model.Property(
    f"{WorkloadDependency} has type {String:dependency_type}"
)

# Scenario Concepts (3D sweep)
PowerEnvelopeLevel = model.Concept("PowerEnvelopeLevel", identify_by={"name": String})
PowerEnvelopeLevel.envelope_multiplier = model.Property(
    f"{PowerEnvelopeLevel} has {Float:envelope_multiplier}"
)
PowerEnvelopeLevel.label = model.Property(f"{PowerEnvelopeLevel} has {String:label}")

MarginFloor = model.Concept("MarginFloor", identify_by={"name": String})
# Use a sentinel -1.0 for the unconstrained level (NULL handling in PyRel
# joins is brittle; the constraint code branches on fraction < 0).
MarginFloor.fraction = model.Property(f"{MarginFloor} has {Float:fraction}")
MarginFloor.label = model.Property(f"{MarginFloor} has {String:label}")

DiversityCap = model.Concept("DiversityCap", identify_by={"name": String})
DiversityCap.anchor_max_share = model.Property(
    f"{DiversityCap} has {Float:anchor_max_share}"
)
DiversityCap.workload_type_floor = model.Property(
    f"{DiversityCap} has {Float:workload_type_floor}"
)
DiversityCap.label = model.Property(f"{DiversityCap} has {String:label}")

# Demand-risk scenarios the chosen plan is replayed under.
DemandScenario = model.Concept("DemandScenario", identify_by={"name": String})
DemandScenario.factor = model.Property(f"{DemandScenario} has {Float:factor}")
DemandScenario.label = model.Property(f"{DemandScenario} has {String:label}")

# LabMetric feature-node concept (single-PK metric_id required for
# FK joins; LabMetric is a feature source for the GNN, not the source
# concept -- the GNN predicts on Workload, with LabMetric features
# propagating in via the lab_workloads edge).
LabMetric = model.Concept("LabMetric", identify_by={"metric_id": Integer})
LabMetric.metric_date = model.Property(f"{LabMetric} has {Date:metric_date}")
LabMetric.lab = model.Property(f"{LabMetric} has {String:lab}")
LabMetric.active_training_runs = model.Property(f"{LabMetric} has {Float:active_training_runs}")
LabMetric.gpu_hours_consumed = model.Property(f"{LabMetric} has {Float:gpu_hours_consumed}")
LabMetric.tokens_trained = model.Property(f"{LabMetric} has {Float:tokens_trained}")
LabMetric.eval_runs_launched = model.Property(f"{LabMetric} has {Float:eval_runs_launched}")
LabMetric.inference_qps = model.Property(f"{LabMetric} has {Float:inference_qps}")
LabMetric.model_release_events = model.Property(f"{LabMetric} has {Float:model_release_events}")
LabMetric.paper_submissions = model.Property(f"{LabMetric} has {Float:paper_submissions}")
LabMetric.funding_announced_usd = model.Property(f"{LabMetric} has {Float:funding_announced_usd}")
LabMetric.prev_day_growth = model.Property(f"{LabMetric} has {Float:prev_day_growth}")
LabMetric.prev_week_growth = model.Property(f"{LabMetric} has {Float:prev_week_growth}")
LabMetric.growth_7d_mean = model.Property(f"{LabMetric} has {Float:growth_7d_mean}")

# Task tables: per-(workload, observation-month) historical labels.
# Train: 7 months x 110 = 770 obs; Val: 1 month x 110 = 110;
# Test: current month x 110 (NO labels -- predict for all workloads).
TrainTable = model.Concept("TrainTable")
ValTable = model.Concept("ValTable")
TestTable = model.Concept("TestTable")

Train = model.Relationship(f"{Workload} at {Date:obs_date} has {Integer:label}")
Val = model.Relationship(f"{Workload} at {Date:obs_date} has {Integer:label}")
Test = model.Relationship(f"{Workload} at {Date:obs_date}")
