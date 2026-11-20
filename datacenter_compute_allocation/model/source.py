"""Bundled datacenter CSVs, the demand-risk scenarios, and the base-fact mappings."""

from pathlib import Path

import pandas as pd

from .schema import (
    AILab,
    DataCenterRequest,
    DemandScenario,
    DiversityCap,
    GpuPool,
    LabMetric,
    MarginFloor,
    PowerEnvelopeLevel,
    Test,
    TestTable,
    Train,
    TrainTable,
    Val,
    ValTable,
    Workload,
    WorkloadDependency,
    WorkloadGpuCompat,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


# CSV loader with boolean auto-detection
def load_csv(filename, bool_cols=()):
    df = pd.read_csv(DATA_DIR / filename)
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
    return df


data_centers_df = load_csv("data_centers.csv")
gpu_pools_df = load_csv("gpu_pools.csv")
ai_labs_df = load_csv("ai_labs.csv", bool_cols=("is_strategic_anchor",))
workloads_df = load_csv("workloads.csv")
workload_compat_df = load_csv("workload_gpu_compatibility.csv")
workload_deps_df = load_csv("workload_dependencies.csv")
power_envelope_df = load_csv("power_envelope_levels.csv")
margin_floors_df = load_csv("margin_floors.csv")
diversity_caps_df = load_csv("diversity_caps.csv")
lab_metrics_df = load_csv("lab_metrics.csv")
lab_metrics_df["metric_date"] = pd.to_datetime(lab_metrics_df["metric_date"]).dt.date

wl_util_train_df = load_csv("workload_utilization_train.csv")
wl_util_train_df["observation_date"] = pd.to_datetime(wl_util_train_df["observation_date"]).dt.date
wl_util_val_df = load_csv("workload_utilization_val.csv")
wl_util_val_df["observation_date"] = pd.to_datetime(wl_util_val_df["observation_date"]).dt.date
wl_util_test_df = load_csv("workload_utilization_test.csv")
wl_util_test_df["observation_date"] = pd.to_datetime(wl_util_test_df["observation_date"]).dt.date

# DemandScenario factors: the share of non-P0 revenue the chosen plan realizes.
demand_scenarios_df = pd.DataFrame([
    {"name": "expected",            "factor": 1.00, "label": "baseline forecast"},
    {"name": "diffusion_slowdown",  "factor": 0.85, "label": "customer adoption hits change-management limits"},
    {"name": "scaling_break",       "factor": 0.70, "label": "capability plateau reduces incremental demand"},
    {"name": "frontier_loss",       "factor": 0.50, "label": "competitive displacement of one or more anchor labs"},
])

src = model.data(data_centers_df)
model.define(DataCenterRequest.new(
    id=src.id, name=src.name, hyperscaler=src.hyperscaler,
    requested_mw=src.approved_mw, approved_mw=src.approved_mw,
    pue=src.pue, dollars_per_mwh=src.dollars_per_mwh,
))

src = model.data(ai_labs_df)
model.define(AILab.new(
    id=src.id, name=src.name, lab_type=src.lab_type,
    contract_tier=src.contract_tier,
    is_strategic_anchor=src.is_strategic_anchor,
    payment_per_gpu_hour=src.payment_per_gpu_hour,
))

src = model.data(gpu_pools_df)
model.define(GpuPool.new(
    id=src.id, gpu_type=src.gpu_type, gpu_count=src.gpu_count,
    mem_per_gpu_gb=src.mem_per_gpu_gb, interconnect=src.interconnect,
    power_per_gpu_kw=src.power_per_gpu_kw,
    available_gpu_count=src.available_gpu_count,
    hourly_depreciation_rate=src.hourly_depreciation_rate,
    data_center=DataCenterRequest.lookup(id=src.data_center_id),
))

src = model.data(workloads_df)
model.define(Workload.new(
    id=src.id, name=src.name, workload_type=src.workload_type,
    reservation_model=src.reservation_model,
    gpu_count_required=src.gpu_count_required,
    mem_required_gb=src.mem_required_gb,
    gpu_type_preferred=src.gpu_type_preferred,
    duration_hours=src.duration_hours,
    strategic_value_usd=src.strategic_value_usd,
    lab=AILab.lookup(id=src.lab_id),
))

compat_src = model.data(workload_compat_df)
WlRef = Workload.ref()
model.where(
    WlRef.id == compat_src.workload_id,
).define(
    WorkloadGpuCompat.new(workload=WlRef, gpu_type=compat_src.gpu_type)
)

# Composite-identity population: use .ref() + .where(). Binding
# composite-identity components directly during define() does not populate
# them correctly.
deps_src = model.data(workload_deps_df)
PredRef = Workload.ref()
SuccRef = Workload.ref()
model.where(
    PredRef.id == deps_src.predecessor_id,
    SuccRef.id == deps_src.successor_id,
).define(
    d := WorkloadDependency.new(predecessor=PredRef, successor=SuccRef),
    d.dependency_type(deps_src.dependency_type),
)

src = model.data(power_envelope_df)
model.define(PowerEnvelopeLevel.new(
    name=src.name, envelope_multiplier=src.envelope_multiplier, label=src.label,
))

margin_df = margin_floors_df.copy()
margin_df["fraction"] = margin_df["fraction"].fillna(-1.0).astype(float)
src = model.data(margin_df)
model.define(MarginFloor.new(
    name=src.name, fraction=src.fraction, label=src.label,
))

div_df = diversity_caps_df.copy()
div_df["anchor_max_share"] = pd.to_numeric(div_df["anchor_max_share"], errors="coerce").fillna(-1.0)
div_df["workload_type_floor"] = pd.to_numeric(div_df["workload_type_floor"], errors="coerce").fillna(-1.0)
src = model.data(div_df)
model.define(DiversityCap.new(
    name=src.name,
    anchor_max_share=src.anchor_max_share,
    workload_type_floor=src.workload_type_floor,
    label=src.label,
))

src = model.data(demand_scenarios_df)
model.define(DemandScenario.new(
    name=src.name, factor=src.factor, label=src.label,
))

lm_src = model.data(lab_metrics_df)
model.define(LabMetric.new(
    metric_id=lm_src.metric_id, metric_date=lm_src.metric_date, lab=lm_src.lab,
    active_training_runs=lm_src.active_training_runs,
    gpu_hours_consumed=lm_src.gpu_hours_consumed,
    tokens_trained=lm_src.tokens_trained,
    eval_runs_launched=lm_src.eval_runs_launched,
    inference_qps=lm_src.inference_qps,
    model_release_events=lm_src.model_release_events,
    paper_submissions=lm_src.paper_submissions,
    funding_announced_usd=lm_src.funding_announced_usd,
    prev_day_growth=lm_src.prev_day_growth,
    prev_week_growth=lm_src.prev_week_growth,
    growth_7d_mean=lm_src.growth_7d_mean,
))

model.define(TrainTable.new(model.data(wl_util_train_df).to_schema()))
model.define(ValTable.new(model.data(wl_util_val_df).to_schema()))
model.define(TestTable.new(model.data(wl_util_test_df).to_schema()))

model.define(Train(
    Workload, TrainTable.observation_date, TrainTable.is_high_utilization
)).where(Workload.id == TrainTable.workload_id)
model.define(Val(
    Workload, ValTable.observation_date, ValTable.is_high_utilization
)).where(Workload.id == ValTable.workload_id)
model.define(Test(
    Workload, TestTable.observation_date
)).where(Workload.id == TestTable.workload_id)
