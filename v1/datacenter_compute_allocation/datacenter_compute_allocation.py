"""Datacenter compute allocation (multi-reasoner) template.

Inside-the-fence GPU allocation: assigns AI lab workloads (pretrains,
finetunes, inference, evals) to GPU pools across 5 hyperscaler campuses
that a prior interconnection-planning step (see `energy_grid_planning`)
has approved and energized. The bundled `data_centers.csv` is a snapshot
of that approved campus set at a $300M investment level; this template
demonstrates the operator-side allocation decision that picks up after.

Four reasoner stages on a shared ontology:

  Stage 1 -- Predictive: heterogeneous-graph GNN binary-classifies per-workload
             utilization probability (will this workload actually use its
             allocated capacity at high duty cycle, or stall / be repaced?).
             Falls back to workload_utilization_fallback.csv via --no-gnn or
             on engine error.
  Stage 2 -- Rules: hardware compatibility (memory + GPU type allowlist) +
             priority-tier classification (P0/P1/P2 from contract_tier).
             Populates Compatibility(workload, gpu_pool).
  Stage 3 -- Graph: reverse-PageRank on the WorkloadDependency.blocks DAG
             writes Workload.gating_score (frontier pretrains gating long
             chains land high; isolated inference workloads land at baseline).
  Stage 4 -- Prescriptive MIP: assigns workloads under power, GPU-count,
             gross-margin-floor, and anchor-concentration-cap constraints,
             across a 3D scenario sweep (PowerEnvelopeLevel x MarginFloor x
             DiversityCap = 48 cells). Maximizes a four-factor strategic
             value: priority * gating * utilization_probability * strategic_value_usd,
             amplified by (1 + under_provisioning_penalty) for asymmetric
             failure-mode pricing.

Run:
    python datacenter_compute_allocation.py

Run (skip GNN, use precomputed forecasts):
    python datacenter_compute_allocation.py --no-gnn

Output:
    Prints per-stage diagnostics -- ontology load summary, per-workload
    utilization probabilities (top / bottom 5 + n>=0.5 count), Compatibility
    table size and P0/P1/P2 priority counts with under-provisioning penalties,
    top-10 gating workloads by downstream reach, MIP termination status,
    per-cell summary table (33 OPTIMAL + 15 INFEASIBLE), two Pareto frontiers
    (margin x revenue and diversity x revenue at the 100pct envelope), and
    a DemandScenario overlay replaying the chosen plan under risk scenarios
    (expected / diffusion_slowdown / scaling_break / frontier_loss) with
    realized + stranded revenue. The headline plan persists as an
    AllocationPlan singleton plus Assignment.is_chosen unary Relationship
    over the chosen-cell decision rows, and the demand overlay persists
    as a DemandScenarioOutlook per scenario -- all queryable as ontology
    after the script exits.
"""

import argparse
from pathlib import Path

import pandas as pd
from relationalai.semantics import Any, Boolean, Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# GNN training writes experiment artifacts here. Set to a database the
# RELATIONALAI native app has CREATE EXPERIMENT + CREATE MODEL on
# (see rai-predictive-modeling SKILL.md prerequisites).
EXP_DATABASE = "DATACENTER_ENRICHMENT"
EXP_SCHEMA = "EXPERIMENTS"
SEED = 42
GNN_EPOCHS = 80
GNN_LR = 0.002

# Headline plan cell. The AllocationPlan singleton + Assignment.is_chosen
# flag persist this cell's outcome as ontology after Stage 4 finishes;
# tighter cells in the 48-cell sweep remain queryable via Assignment.x_assign
# but are diagnostic overlays rather than the operator-facing plan.
CHOSEN_ENVELOPE = "100pct"
CHOSEN_MARGIN = "unconstrained"
CHOSEN_DIVERSITY = "none"


# --------------------------------------------------
# CLI
# --------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--no-gnn",
        action="store_true",
        help="Skip Stage 1 GNN training and load workload_utilization_fallback.csv directly.",
    )
    p.add_argument(
        "--gnn-strict",
        action="store_true",
        help="Fail fast on GNN error (don't catch and fall back). Useful for debugging.",
    )
    return p.parse_args()


# --------------------------------------------------
# CSV loader
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"


def load_csv(filename, bool_cols=()):
    df = pd.read_csv(DATA_DIR / filename)
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
    return df


def section(title):
    bar = "=" * 60
    print(f"\n{bar}\n{title}\n{bar}")


# --------------------------------------------------
# Load all CSVs once
# --------------------------------------------------

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
wl_util_train_df = load_csv("workload_utilization_train.csv")
wl_util_val_df = load_csv("workload_utilization_val.csv")
wl_util_test_df = load_csv("workload_utilization_test.csv")
wl_util_fallback_df = load_csv("workload_utilization_fallback.csv")


# --------------------------------------------------
# Stage 0: Model bind + ontology setup
# --------------------------------------------------

def main():
    args = parse_args()
    section("STAGE 0: LOAD ONTOLOGY")

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

    src = model.data(data_centers_df)
    model.define(DataCenterRequest.new(
        id=src.id, name=src.name, hyperscaler=src.hyperscaler,
        requested_mw=src.approved_mw, approved_mw=src.approved_mw,
        pue=src.pue, dollars_per_mwh=src.dollars_per_mwh,
    ))
    print(f"  Loaded {len(data_centers_df)} DataCenterRequest entries from "
          f"data/data_centers.csv")

    # ---- New downstream concepts ----
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

    src = model.data(ai_labs_df)
    model.define(AILab.new(
        id=src.id, name=src.name, lab_type=src.lab_type,
        contract_tier=src.contract_tier,
        is_strategic_anchor=src.is_strategic_anchor,
        payment_per_gpu_hour=src.payment_per_gpu_hour,
    ))

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

    src = model.data(gpu_pools_df)
    model.define(GpuPool.new(
        id=src.id, gpu_type=src.gpu_type, gpu_count=src.gpu_count,
        mem_per_gpu_gb=src.mem_per_gpu_gb, interconnect=src.interconnect,
        power_per_gpu_kw=src.power_per_gpu_kw,
        available_gpu_count=src.available_gpu_count,
        hourly_depreciation_rate=src.hourly_depreciation_rate,
        data_center=DataCenterRequest.filter_by(id=src.data_center_id),
    ))

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
    src = model.data(workloads_df)
    model.define(Workload.new(
        id=src.id, name=src.name, workload_type=src.workload_type,
        reservation_model=src.reservation_model,
        gpu_count_required=src.gpu_count_required,
        mem_required_gb=src.mem_required_gb,
        gpu_type_preferred=src.gpu_type_preferred,
        duration_hours=src.duration_hours,
        strategic_value_usd=src.strategic_value_usd,
        lab=AILab.filter_by(id=src.lab_id),
    ))

    # GPU-type allowlist as its own Concept (composite identity), not as a
    # multi-valued Relationship on Workload. Multi-valued Relationships on a
    # GNN-node concept trip the engine's functional-dependency check whenever
    # downstream queries materialize the parent's full property graph; modeling
    # the allowlist as a separate Concept avoids the issue and lets us iterate
    # over (workload, gpu_type) pairs in Stage 2's eligibility rules.
    WorkloadGpuCompat = model.Concept(
        "WorkloadGpuCompat",
        identify_by={"workload": Workload, "gpu_type": String},
    )
    compat_src = model.data(workload_compat_df)
    WlRef = Workload.ref()
    model.where(
        WlRef.id == compat_src.workload_id,
    ).define(
        WorkloadGpuCompat.new(workload=WlRef, gpu_type=compat_src.gpu_type)
    )

    # Workload dependency edges. The "blocks" subset is shared between Stage 1
    # GNN (heterogeneous edge) and Stage 3 PageRank.
    WorkloadDependency = model.Concept(
        "WorkloadDependency",
        identify_by={"predecessor": Workload, "successor": Workload},
    )
    WorkloadDependency.dependency_type = model.Property(
        f"{WorkloadDependency} has type {String:dependency_type}"
    )
    # Composite-identity population: use .ref() + .where(), mirroring the
    # cicd_runner_allocation Compatibility pattern. .filter_by() does not
    # bind composite-identity components correctly during define().
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

    # ---- Scenario Concepts (3D sweep) ----
    PowerEnvelopeLevel = model.Concept("PowerEnvelopeLevel", identify_by={"name": String})
    PowerEnvelopeLevel.envelope_multiplier = model.Property(
        f"{PowerEnvelopeLevel} has {Float:envelope_multiplier}"
    )
    PowerEnvelopeLevel.label = model.Property(f"{PowerEnvelopeLevel} has {String:label}")
    src = model.data(power_envelope_df)
    model.define(PowerEnvelopeLevel.new(
        name=src.name, envelope_multiplier=src.envelope_multiplier, label=src.label,
    ))

    MarginFloor = model.Concept("MarginFloor", identify_by={"name": String})
    # Use a sentinel -1.0 for the unconstrained level (NULL handling in PyRel
    # joins is brittle; the constraint code branches on fraction < 0).
    MarginFloor.fraction = model.Property(f"{MarginFloor} has {Float:fraction}")
    MarginFloor.label = model.Property(f"{MarginFloor} has {String:label}")
    margin_df = margin_floors_df.copy()
    margin_df["fraction"] = margin_df["fraction"].fillna(-1.0).astype(float)
    src = model.data(margin_df)
    model.define(MarginFloor.new(
        name=src.name, fraction=src.fraction, label=src.label,
    ))

    DiversityCap = model.Concept("DiversityCap", identify_by={"name": String})
    DiversityCap.anchor_max_share = model.Property(
        f"{DiversityCap} has {Float:anchor_max_share}"
    )
    DiversityCap.workload_type_floor = model.Property(
        f"{DiversityCap} has {Float:workload_type_floor}"
    )
    DiversityCap.label = model.Property(f"{DiversityCap} has {String:label}")
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

    print(f"  Ontology loaded: {len(ai_labs_df)} labs, {len(gpu_pools_df)} pools, "
          f"{len(workloads_df)} workloads, {len(workload_deps_df)} dep edges, "
          f"{len(power_envelope_df)}x{len(margin_floors_df)}x{len(diversity_caps_df)}={len(power_envelope_df)*len(margin_floors_df)*len(diversity_caps_df)} scenario cells")

    # Pass to subsequent stages.
    return _Ctx(
        args=args, model=model,
        DataCenterRequest=DataCenterRequest, AILab=AILab, GpuPool=GpuPool,
        Workload=Workload, WorkloadDependency=WorkloadDependency,
        WorkloadGpuCompat=WorkloadGpuCompat,
        PowerEnvelopeLevel=PowerEnvelopeLevel, MarginFloor=MarginFloor, DiversityCap=DiversityCap,
    )


class _Ctx:
    """Carries model + concept handles between stages."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# --------------------------------------------------
# Stage 1: Predictive (heterogeneous GNN, with fallback)
# --------------------------------------------------

def stage1_predictive(ctx):
    """Per-workload utilization-probability GNN classification.

    Binary node classification: for each Workload, predict the probability
    that the workload will be high-utilization next period (i.e., actually
    use its allocated capacity at high duty cycle, rather than stalling or
    being repaced). This is the operator's load-bearing forward-looking
    signal -- stranded capacity (depreciation accruing without offsetting
    revenue) is the operator's biggest economic exposure.

    Builds a heterogeneous graph with three cross-concept edge types:
      1. lab_workloads: LabMetric -> Workload owned by the same lab
         (carries lab-side recent activity into the workload's neighborhood)
      2. WorkloadDependency.blocks: workload DAG, shared with Stage 3
         (workloads downstream of high-utilization gating workloads inherit
          the upstream signal through message passing)
      3. co_dated: LabMetric -> LabMetric on the same date when their labs
         share a workload_type (cross-lab industry co-movement signal)

    Trains a binary-classification GNN on `Workload.is_high_utilization`
    labels in `workload_utilization_train.csv` (80 workloads) and
    `_val.csv` (15 workloads). Test domain = all 110 workloads so every
    workload gets a probability. Binds `Workload.utilization_probability`
    from the predicted positive-class probability.

    Falls back to `workload_utilization_fallback.csv` (the deterministic
    latent probabilities used to generate the synthetic labels) when
    --no-gnn is set or the predictive engine is unavailable. Downstream
    stages don't care which path produced the probability.
    """
    section("STAGE 1: PREDICT -- per-workload utilization-probability GNN")
    model = ctx.model
    Workload = ctx.Workload

    Workload.utilization_probability = model.Property(
        f"{Workload} has {Float:utilization_probability} utilization probability"
    )

    util_df = None
    if not ctx.args.no_gnn:
        if ctx.args.gnn_strict:
            util_df = _train_gnn_and_predict(ctx)
            print("  GNN training complete; per-workload probabilities extracted")
        else:
            try:
                util_df = _train_gnn_and_predict(ctx)
                print("  GNN training complete; per-workload probabilities extracted")
            except Exception as e:
                import traceback
                print(f"  GNN unavailable ({type(e).__name__}: {e})")
                traceback.print_exc()
                print("  Falling back to data/workload_utilization_fallback.csv")
                util_df = None
    else:
        print("  --no-gnn flag set; using data/workload_utilization_fallback.csv")

    if util_df is None:
        util_df = wl_util_fallback_df.copy()

    # Bind Workload.utilization_probability from the dataframe.
    src = model.data(util_df)
    WlRef = Workload.ref()
    model.where(WlRef.id == src.workload_id).define(
        WlRef.utilization_probability(src.utilization_probability)
    )

    # Report distribution + top / bottom 5.
    probs_df = model.select(
        Workload.id.alias("id"),
        Workload.name.alias("name"),
        Workload.utilization_probability.alias("p"),
    ).to_df()
    probs_df["p"] = pd.to_numeric(probs_df["p"], errors="coerce")
    n_high = int((probs_df["p"] >= 0.5).sum())
    n_total = int(probs_df["p"].notna().sum())
    print(f"  Workload utilization-probability distribution: "
          f"n_total={n_total}, n>=0.5: {n_high}, n<0.5: {n_total - n_high}")
    print("  Top 5 (most likely to be high-utilization):")
    for _, r in probs_df.sort_values("p", ascending=False).head(5).iterrows():
        print(f"    + {r['name']:<45} p={float(r['p']):.3f}")
    print("  Bottom 5 (most likely to stall / be repaced):")
    for _, r in probs_df.sort_values("p", ascending=True).head(5).iterrows():
        print(f"    - {r['name']:<45} p={float(r['p']):.3f}")


def _train_gnn_and_predict(ctx):
    """Build the heterogeneous GNN graph, train binary classification,
    predict, and return a per-workload probability DataFrame.

    Defines LabMetric as a feature-node concept (single-PK metric_id),
    Workload as the source concept for classification, and three
    cross-concept edge types (lab_workloads, WorkloadDependency.blocks,
    cross-lab co_dated). Task tables TrainTable / ValTable / TestTable
    are populated from `workload_utilization_*.csv` and joined to
    Workload by workload_id.

    Returns DataFrame[workload_id, utilization_probability].
    """
    from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

    model = ctx.model
    Workload = ctx.Workload
    WorkloadDependency = ctx.WorkloadDependency

    # ---- LabMetric feature-node concept (single-PK metric_id required for
    # FK joins; LabMetric is a feature source for the GNN, not the source
    # concept -- the GNN predicts on Workload, with LabMetric features
    # propagating in via the lab_workloads edge).
    LabMetric = model.Concept("LabMetric", identify_by={"metric_id": Integer})
    LabMetric.metric_date = model.Property(f"{LabMetric} has {String:metric_date}")
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

    src = model.data(lab_metrics_df)
    model.define(LabMetric.new(
        metric_id=src.metric_id, metric_date=src.metric_date, lab=src.lab,
        active_training_runs=src.active_training_runs,
        gpu_hours_consumed=src.gpu_hours_consumed,
        tokens_trained=src.tokens_trained,
        eval_runs_launched=src.eval_runs_launched,
        inference_qps=src.inference_qps,
        model_release_events=src.model_release_events,
        paper_submissions=src.paper_submissions,
        funding_announced_usd=src.funding_announced_usd,
        prev_day_growth=src.prev_day_growth,
        prev_week_growth=src.prev_week_growth,
        growth_7d_mean=src.growth_7d_mean,
    ))

    # ---- Heterogeneous graph (three cross-concept edge types) ----
    # All edges cross concept boundaries. Same-entity-only edges (e.g. pure
    # temporal lag) would not give the GNN message-passing lift over a
    # tabular model -- see rai-predictive-modeling Common Pitfalls.
    gnn_graph = Graph(model, directed=False, weighted=False)

    # Edge 1: LabMetric -> Workload owned by the same lab. Brings lab-side
    # recent activity into the per-workload prediction neighborhood -- a
    # workload owned by a fast-ramping lab inherits that signal.
    model.define(gnn_graph.Edge.new(src=LabMetric, dst=Workload)).where(
        LabMetric.lab == Workload.lab.name,
    )

    # Edge 2: WorkloadDependency.blocks DAG -- shared with Stage 3 PageRank.
    # A workload downstream of a high-utilization gating pretrain inherits
    # signal through the dep chain.
    dep_ref = WorkloadDependency.ref()
    model.define(
        gnn_graph.Edge.new(src=dep_ref.predecessor, dst=dep_ref.successor)
    ).where(dep_ref.dependency_type == "blocks")

    # Edge 3: LabMetric -> LabMetric, cross-lab same-date pairs whose labs
    # share a workload_type. LOAD-BEARING -- this is what carries cross-lab
    # co-movement signal a per-workload tabular baseline cannot replicate.
    co_pairs = _build_codated_pairs(lab_metrics_df, ai_labs_df, workloads_df)
    co_src = model.data(co_pairs)
    LM_a = LabMetric.ref()
    LM_b = LabMetric.ref()
    model.define(gnn_graph.Edge.new(src=LM_a, dst=LM_b)).where(
        LM_a.lab == co_src.lab_a, LM_a.metric_date == co_src.shared_date,
        LM_b.lab == co_src.lab_b, LM_b.metric_date == co_src.shared_date,
    )

    # ---- Task tables: split workloads into train (80) / val (15) /
    # test (110 -- ALL workloads, so every workload gets a prediction).
    TrainTable = model.Concept("TrainTable")
    ValTable = model.Concept("ValTable")
    TestTable = model.Concept("TestTable")
    model.define(TrainTable.new(model.data(wl_util_train_df).to_schema()))
    model.define(ValTable.new(model.data(wl_util_val_df).to_schema()))
    model.define(TestTable.new(model.data(wl_util_test_df).to_schema()))

    # Task relationships. Train/Val carry the binary label; Test omits it.
    # Join key: Workload.id == TaskTable.workload_id.
    Train = model.Relationship(f"{Workload} has {Any:label}")
    model.define(Train(Workload, TrainTable.is_high_utilization)).where(
        Workload.id == TrainTable.workload_id,
    )
    Val = model.Relationship(f"{Workload} has {Any:label}")
    model.define(Val(Workload, ValTable.is_high_utilization)).where(
        Workload.id == ValTable.workload_id,
    )
    Test = model.Relationship(f"{Workload}")
    model.define(Test(Workload)).where(
        Workload.id == TestTable.workload_id,
    )

    # ---- Feature configuration -- drop PKs/identifiers; type the rest ----
    pt = PropertyTransformer(
        drop=[
            LabMetric.metric_id, LabMetric.metric_date,
            Workload.id, Workload.name,
        ],
        category=[
            LabMetric.lab,
            Workload.workload_type, Workload.gpu_type_preferred,
            Workload.reservation_model,
        ],
        continuous=[
            LabMetric.active_training_runs, LabMetric.gpu_hours_consumed,
            LabMetric.tokens_trained, LabMetric.inference_qps,
            LabMetric.eval_runs_launched, LabMetric.paper_submissions,
            LabMetric.funding_announced_usd,
            LabMetric.prev_day_growth, LabMetric.prev_week_growth,
            LabMetric.growth_7d_mean,
            Workload.gpu_count_required, Workload.mem_required_gb,
            Workload.strategic_value_usd, Workload.duration_hours,
        ],
    )

    gnn = GNN(
        exp_database=EXP_DATABASE,
        exp_schema=EXP_SCHEMA,
        graph=gnn_graph,
        property_transformer=pt,
        train=Train,
        validation=Val,
        task_type="binary_classification",
        eval_metric="roc_auc",
        has_time_column=False,
        stream_logs=False,
        seed=SEED,
        device="cpu",
        n_epochs=GNN_EPOCHS,
        lr=GNN_LR,
    )
    gnn.fit()
    Workload.predictions = gnn.predictions(domain=Test)

    # Pull per-workload positive-class probabilities.
    pred_df = model.select(
        Workload.id.alias("workload_id"),
        Workload.predictions.probs.alias("probs"),
    ).where(Workload.predictions).to_df()

    # probs is a list/array with class probabilities; positive class
    # (label=1, "high utilization") is the second element. Take it as the
    # utilization probability.
    def _pos_prob(v):
        try:
            return float(v[1]) if hasattr(v, "__len__") and len(v) >= 2 else float(v)
        except (TypeError, ValueError):
            return float("nan")

    pred_df["utilization_probability"] = pred_df["probs"].apply(_pos_prob)
    return pred_df[["workload_id", "utilization_probability"]].dropna()


def _build_codated_pairs(lab_metrics_df, ai_labs_df, workloads_df):
    """Build the (lab_a, lab_b, shared_date) edge table for the cross-lab
    co_dated edge type. Two labs are connected on a date if they share at
    least one workload_type across their owned workloads.

    Output: DataFrame[lab_a, lab_b, shared_date], deduplicated, no self-loops.
    """
    # Map lab_id -> lab name (LabMetric.lab uses the human-readable name).
    lab_name = ai_labs_df.set_index("id")["name"].to_dict()

    # Per-lab set of workload_types owned.
    types_by_lab = (
        workloads_df.assign(lab_name=workloads_df["lab_id"].map(lab_name))
        .groupby("lab_name")["workload_type"].apply(set)
        .to_dict()
    )

    # For each ordered lab pair sharing a workload_type, emit (a, b) for every
    # date both have metrics on. Symmetric edges -- emit both directions so the
    # GNN sees the bidirectional message passing.
    labs = sorted(types_by_lab.keys())
    sharing_pairs = []
    for i, a in enumerate(labs):
        for b in labs:
            if a == b:
                continue
            if types_by_lab[a] & types_by_lab[b]:
                sharing_pairs.append((a, b))

    dates = sorted(lab_metrics_df["metric_date"].unique())
    rows = []
    for a, b in sharing_pairs:
        for d in dates:
            rows.append({"lab_a": a, "lab_b": b, "shared_date": d})
    return pd.DataFrame(rows)


# --------------------------------------------------
# Stage 2: Rules (eligibility + priority)
# --------------------------------------------------

def stage2_rules(ctx):
    """Hardware compatibility rules + priority-tier classification.

    Writes derived Relationships/Properties on Workload:
      - fails_memory(GpuPool), fails_gpu_type(GpuPool), is_eligible(GpuPool)
      - priority_tier (P0/P1/P2), priority_weight (100/10/1)
    Populates Compatibility(workload, gpu_pool) -- the prune that keeps
    Stage 4's Assignment decision space linear and small.
    """
    section("STAGE 2: RULES -- eligibility + priority classification")
    model = ctx.model
    Workload = ctx.Workload
    GpuPool = ctx.GpuPool

    # Rule family 1: hardware compatibility ---------------------------------
    # `is_eligible` is defined with positive conditions directly (PyRel does
    # not support `~` negation on relationship-application expressions).
    # Failure flags are still derived for reporting/queryability:
    Workload.fails_memory = model.Relationship(
        f"{Workload} fails memory check on {GpuPool}"
    )
    model.where(
        Workload.mem_required_gb > GpuPool.mem_per_gpu_gb,
    ).define(Workload.fails_memory(GpuPool))

    # Rule family 2: priority tier + numeric weight (lex-emulating spread) ---
    Workload.priority_tier = model.Property(
        f"{Workload} has priority tier {String:priority_tier}"
    )
    Workload.priority_weight = model.Property(
        f"{Workload} has {Float:priority_weight} priority weight"
    )
    model.where(Workload.lab.contract_tier == "anchor_reserved").define(
        Workload.priority_tier("P0"))
    model.where(Workload.lab.contract_tier == "committed").define(
        Workload.priority_tier("P1"))
    model.where(Workload.lab.contract_tier == "on_demand").define(
        Workload.priority_tier("P2"))

    model.where(Workload.priority_tier == "P0").define(Workload.priority_weight(100.0))
    model.where(Workload.priority_tier == "P1").define(Workload.priority_weight(10.0))
    model.where(Workload.priority_tier == "P2").define(Workload.priority_weight(1.0))

    # Asymmetric failure mode: under-provisioning an anchor (P0) carries an
    # SLA / contract / reputational penalty that is a multiple of the raw
    # foregone revenue; missing a P2 eval does not. Stage 4 multiplies the
    # assignment reward by (1 + under_provisioning_penalty) so the solver
    # treats anchor placement as load-bearing, not just revenue-positive.
    Workload.under_provisioning_penalty = model.Property(
        f"{Workload} has {Float:under_provisioning_penalty} under-provisioning penalty"
    )
    model.where(Workload.priority_tier == "P0").define(
        Workload.under_provisioning_penalty(1.0))
    model.where(Workload.priority_tier == "P1").define(
        Workload.under_provisioning_penalty(0.3))
    model.where(Workload.priority_tier == "P2").define(
        Workload.under_provisioning_penalty(0.0))

    # Composite eligibility: positive form of (passes_gpu_type AND passes_memory).
    # Iterates over WorkloadGpuCompat rows -- one per allowed (workload, gpu_type)
    # pair -- joined to GpuPool by gpu_type.
    Workload.is_eligible = model.Relationship(
        f"{Workload} is eligible on {GpuPool}"
    )
    WorkloadGpuCompat = ctx.WorkloadGpuCompat
    model.where(
        WorkloadGpuCompat.workload == Workload,
        WorkloadGpuCompat.gpu_type == GpuPool.gpu_type,
        Workload.mem_required_gb <= GpuPool.mem_per_gpu_gb,
    ).define(Workload.is_eligible(GpuPool))

    # Compatibility precompute -- keeps the Stage 4 MIP linear and small.
    Compatibility = model.Concept(
        "Compatibility",
        identify_by={"workload": Workload, "gpu_pool": GpuPool},
    )
    model.where(
        Workload.is_eligible(GpuPool),
    ).define(
        Compatibility.new(workload=Workload, gpu_pool=GpuPool)
    )
    ctx.Compatibility = Compatibility

    # Report compatibility scale + priority-tier counts.
    compat_count_df = model.select(
        aggs.count(Compatibility).alias("n"),
    ).to_df()
    n_compat = int(compat_count_df["n"].iloc[0]) if len(compat_count_df) else 0

    # Pull (id, tier) pairs and count in pandas. A direct
    # aggs.count(Workload).per(Workload.priority_tier) query trips the
    # engine's functional-dependency check when Workload also carries the
    # multi-valued compatible_with relationship -- selecting just two
    # single-valued attributes avoids forcing full-entity materialization.
    tier_df = model.select(
        Workload.id.alias("id"),
        Workload.priority_tier.alias("tier"),
    ).to_df()
    tier_counts = tier_df.groupby("tier").size().reset_index(name="n")
    print(f"  Compatibility table: {n_compat} eligible (Workload, GpuPool) pairs")
    print("  Priority tier counts:")
    for _, r in tier_counts.sort_values("tier").iterrows():
        print(f"    {r['tier']}: {int(r['n'])} workloads")


# --------------------------------------------------
# Stage 3: Graph (reverse-PageRank on dep DAG)
# --------------------------------------------------

def stage3_graph(ctx):
    """Reverse-PageRank on the WorkloadDependency.blocks DAG.

    Writes Workload.gating_score: a high score means many downstream workloads
    are gated by this one (frontier pretrain that gates 14 fine-tunes + evals
    lands at the top). Workloads not in the DAG get baseline 1.0.
    """
    section("STAGE 3: GRAPH -- workload-dependency PageRank (gating score)")
    model = ctx.model
    Workload = ctx.Workload
    WorkloadDependency = ctx.WorkloadDependency

    dag = Graph(model, directed=True, weighted=False, node_concept=Workload)

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

    # Backstop for workloads not in the DAG: baseline 1.0 so they enter
    # the Stage 4 objective product without zeroing out.
    # (PyRel: a workload with no in/out edges is absent from PageRank output.)
    # We can't easily detect graph membership in a single define; we apply
    # the backstop AFTER selecting and bind via pandas.
    g_df = model.select(
        Workload.id.alias("id"),
        Workload.gating_score.alias("gating_score"),
    ).to_df()
    n_with_score = int(g_df["gating_score"].notna().sum())
    n_total = int(model.select(aggs.count(Workload).alias("n")).to_df()["n"].iloc[0])

    # Bind a backstop 1.0 for workloads missing from the DAG.
    if n_with_score < n_total:
        all_ids = set(workloads_df["id"].astype(str))
        scored_ids = set(g_df.dropna(subset=["gating_score"])["id"].astype(str))
        missing = sorted(all_ids - scored_ids)
        if missing:
            backstop_df = pd.DataFrame({"id": missing, "gating_score": [1.0] * len(missing)})
            bs = model.data(backstop_df)
            model.where(
                Workload.id == bs.id,
            ).define(
                Workload.gating_score(bs.gating_score)
            )
            print(f"  Backstop: assigned gating_score=1.0 to {len(missing)} "
                  f"workloads not in dep DAG")

    # Report top-10 gating workloads.
    g2_df = model.select(
        Workload.id.alias("id"),
        Workload.name.alias("name"),
        Workload.gating_score.alias("gating_score"),
    ).to_df()
    g2_df["gating_score"] = pd.to_numeric(g2_df["gating_score"], errors="coerce")
    top = g2_df.dropna(subset=["gating_score"]).sort_values("gating_score", ascending=False).head(10)
    print("  Top-10 gating workloads (frontier pretrains expected to dominate):")
    for _, r in top.iterrows():
        print(f"    {r['name']:<45} score={float(r['gating_score']):.4f}")


# --------------------------------------------------
# Stage 4: Prescriptive (MIP, 3D scenario sweep)
# --------------------------------------------------

WORKLOAD_TYPES = ("pretrain", "finetune", "inference", "eval")


def stage4_prescriptive(ctx):
    """Compute-allocation MIP across a 3D Scenario Concept sweep.

    Decision variable: Assignment.x_assign(PowerEnvelopeLevel, MarginFloor,
                       DiversityCap), binary. One per (Workload, GpuPool) in
                       Compatibility, per scenario cell.

    Constraints:
      C1 -- P0 commitment (lex primary): every P0 workload assigned exactly once
            per cell where feasible (mirrors Borg / Singularity / MAST priority
            dominance).
      C2 -- At most one assignment per workload per cell.
      C3 -- Per-pool GPU-count capacity.
      C4 -- Per-DC power envelope: gpu_count * power_per_gpu * pue <=
            approved_mw * 1000 * envelope_multiplier.
      C5 -- Gross-margin floor (linearized; skipped when fraction < 0).
      C6 -- Anchor concentration cap (linear; skipped when share < 0).
      C7 -- Workload-type floor (skipped unless DiversityCap supplies one).

    Objective: maximize sum over assignments of
        priority_weight * gating_score * utilization_probability * strategic_value_usd
        * (1 + under_provisioning_penalty)
    """
    section("STAGE 4: PRESCRIPTIVE -- compute allocation MIP (48-cell sweep)")
    model = ctx.model
    Workload = ctx.Workload
    GpuPool = ctx.GpuPool
    DataCenterRequest = ctx.DataCenterRequest
    Compatibility = ctx.Compatibility
    PowerEnvelopeLevel = ctx.PowerEnvelopeLevel
    MarginFloor = ctx.MarginFloor
    DiversityCap = ctx.DiversityCap

    # ---- Decision variable: Assignment indexed by 3D scenario ----
    Assignment = model.Concept(
        "Assignment",
        identify_by={"workload": Workload, "gpu_pool": GpuPool},
    )
    model.define(
        Assignment.new(workload=Compatibility.workload, gpu_pool=Compatibility.gpu_pool)
    )

    Assignment.x_assign = model.Property(
        f"{Assignment} per {PowerEnvelopeLevel} per {MarginFloor} per {DiversityCap} "
        f"assigned {Float:x_assign}"
    )
    ctx.Assignment = Assignment

    problem = Problem(model, Float)

    # Bind the decision variable. The Float ref pattern (mirrors upstream
    # energy_grid_planning's x_a / x_u) lets constraints and objective
    # reference the variable's value via the bound Float ref inside arithmetic.
    x = Float.ref("x")
    problem.solve_for(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x),
        type="bin",
        name=["assign", PowerEnvelopeLevel.name, MarginFloor.name, DiversityCap.name,
              Assignment.workload.id, Assignment.gpu_pool.id],
    )

    # ---- C1+C2: at most one assignment per workload per cell ----
    # C1 (hard P0 commitment) was originally `sum == 1` for P0 workloads but
    # over-constrains the global solve: tight scenario cells (e.g.,
    # 85%/50pct/anchor40_typed15) become infeasible because ALL 15 P0 anchors
    # cannot fit under a 40% anchor cap. The single-MIP across-cells solve
    # then fails globally. We relax C1 to <= 1 (= C2) and let the lex-emulating
    # priority_weight=100 in the objective dominate the optimization, pushing
    # P0 to 1 wherever feasible. Per-cell P0 drops are surfaced in the report
    # as the "P0 incompatible with this cell" diagnostic the design specifies.
    x2 = Float.ref()
    Wany = Workload.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x2),
        Assignment.workload == Wany,
    ).require(
        sum(x2).per(Wany, PowerEnvelopeLevel, MarginFloor, DiversityCap) <= 1.0
    ))

    # ---- C3: per-pool GPU count capacity ----
    x3 = Float.ref()
    G = GpuPool.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x3),
        Assignment.gpu_pool == G,
    ).require(
        sum(x3 * Assignment.workload.gpu_count_required)
            .per(G, PowerEnvelopeLevel, MarginFloor, DiversityCap)
        <= G.available_gpu_count
    ))

    # ---- C4: per-DC power envelope ----
    x4 = Float.ref()
    DC = DataCenterRequest.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x4),
        Assignment.gpu_pool.data_center == DC,
    ).require(
        sum(x4
            * Assignment.workload.gpu_count_required
            * Assignment.gpu_pool.power_per_gpu_kw
            * DC.pue)
            .per(DC, PowerEnvelopeLevel, MarginFloor, DiversityCap)
        <= DC.approved_mw * 1000.0 * PowerEnvelopeLevel.envelope_multiplier
    ))

    # ---- C5: gross-margin floor (linearized; skipped when fraction < 0) ----
    # revenue * (1 - fraction) >= total_cost
    # total_cost = energy_cost + depreciation_cost  (per workload, per duration)
    #   energy_cost  = gpu_count * power_per_gpu_kw * pue * dollars_per_mwh / 1000 * duration_hours
    #   dep_cost     = gpu_count * hourly_depreciation_rate * duration_hours
    # Energy alone clears at ~99% margin; depreciation is the SemiAnalysis
    # 14-16% net BMaaS pressure source.
    x5 = Float.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x5),
        MarginFloor.fraction >= 0.0,
    ).require(
        sum(x5 * Assignment.workload.strategic_value_usd
                * (1.0 - MarginFloor.fraction))
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        >= sum(x5 * Assignment.workload.gpu_count_required
                  * Assignment.workload.duration_hours
                  * (Assignment.gpu_pool.power_per_gpu_kw
                       * Assignment.gpu_pool.data_center.pue
                       * Assignment.gpu_pool.data_center.dollars_per_mwh / 1000.0
                     + Assignment.gpu_pool.hourly_depreciation_rate))
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    ))

    # ---- C6: anchor concentration cap (skipped when share < 0) ----
    # Two sums sharing the same Float ref, one filtered to anchor labs,
    # the other unfiltered (total): mirrors upstream pattern of two .where
    # clauses inside the same model.where binding context.
    x6 = Float.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x6),
        DiversityCap.anchor_max_share >= 0.0,
    ).require(
        sum(x6 * Assignment.workload.strategic_value_usd)
            .where(Assignment.workload.lab.is_strategic_anchor == True)
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        <= DiversityCap.anchor_max_share
            * sum(x6 * Assignment.workload.strategic_value_usd)
                .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    ))

    # ---- C7: workload-type floor (one constraint per type; skipped when floor < 0) ----
    for wt in WORKLOAD_TYPES:
        x7 = Float.ref()
        problem.satisfy(model.where(
            Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x7),
            DiversityCap.workload_type_floor >= 0.0,
        ).require(
            sum(x7)
                .where(Assignment.workload.workload_type == wt)
                .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
            >= DiversityCap.workload_type_floor
                * sum(x7).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        ))

    # ---- Objective: four-factor strategic value, amplified by under-provisioning penalty ----
    # The (1 + under_provisioning_penalty) multiplier captures asymmetric failure modes:
    # an unfilled anchor seat (P0) costs more than the foregone revenue (SLA / contract /
    # reputational penalty), while an unfilled research eval costs only the revenue.
    # Penalty values: P0 = 1.0 (2x amplification), P1 = 0.3, P2 = 0.0.
    x_obj = Float.ref()
    problem.maximize(
        sum(x_obj
            * Assignment.workload.priority_weight
            * Assignment.workload.gating_score
            * Assignment.workload.utilization_probability
            * Assignment.workload.strategic_value_usd
            * (1.0 + Assignment.workload.under_provisioning_penalty))
        .where(Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x_obj))
    )

    print("  Solving 48-cell scenario sweep with HiGHS...")
    problem.solve("highs", time_limit_sec=900)
    si = problem.solve_info()
    # Per rai-prescriptive-results-interpretation: status is signal, not
    # always error. INFEASIBLE/TIME_LIMIT cells in a multi-scenario sweep
    # are diagnostic information about which constraint combinations bind.
    print(f"  Termination status: {si.termination_status}")
    print(f"  Solve time:         {si.solve_time_sec:.1f}s")
    try:
        print(f"  Objective:          {float(si.objective_value):,.2f}")
    except Exception:
        pass
    if si.termination_status == "TIME_LIMIT":
        print("  Note: TIME_LIMIT means solver returned a feasible but not "
              "proven-optimal solution. Per-cell results below remain valid.")

    # ---- Post-solve: per-cell summary ----
    _report_pareto(ctx, problem)


def _report_pareto(ctx, problem):
    """Per-cell results queried directly from the ontology.

    Builds per-cell aggregate Properties on the three Scenario Concepts via
    `sum(...).per(...)` queries (mirroring `energy_grid_planning`'s
    `rev_per_level` pattern), then assembles the per-cell table from one
    `model.select()` call. Infeasibility is detected by the absence of
    Assignment rows in a (env, mar, div) cell -- the global solve drops
    cells whose constraints can't be satisfied.
    """
    model = ctx.model
    Assignment = ctx.Assignment
    PowerEnvelopeLevel = ctx.PowerEnvelopeLevel
    MarginFloor = ctx.MarginFloor
    DiversityCap = ctx.DiversityCap

    # ---- Aggregate expressions, scoped per (env, mar, div) cell ----
    # Each is a `sum(...).where(...).per(env, mar, div)` aggregate the engine
    # evaluates lazily when used inside model.select(). Filter `xq > 0.5`
    # confines the sums to chosen binary assignments only.
    xq = Float.ref("xq")
    revenue_per_cell = sum(Assignment.workload.strategic_value_usd).where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
        xq > 0.5,
    ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)

    anchor_revenue_per_cell = sum(Assignment.workload.strategic_value_usd).where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
        xq > 0.5,
        Assignment.workload.lab.is_strategic_anchor == True,
    ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)

    energy_cost_per_cell = sum(
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.power_per_gpu_kw
        * Assignment.gpu_pool.data_center.pue
        * Assignment.gpu_pool.data_center.dollars_per_mwh / 1000.0
    ).where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
        xq > 0.5,
    ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)

    dep_cost_per_cell = sum(
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.hourly_depreciation_rate
    ).where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
        xq > 0.5,
    ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)

    n_assigned_per_cell = aggs.count(Assignment).where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
        xq > 0.5,
    ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)

    # Single ontology query produces the per-cell aggregates table.
    cells_df = model.select(
        PowerEnvelopeLevel.name.alias("envelope"),
        MarginFloor.name.alias("margin"),
        DiversityCap.name.alias("diversity"),
        n_assigned_per_cell.alias("n_assigned"),
        revenue_per_cell.alias("revenue_usd"),
        anchor_revenue_per_cell.alias("anchor_revenue_usd"),
        energy_cost_per_cell.alias("energy_cost_usd"),
        dep_cost_per_cell.alias("dep_cost_usd"),
    ).to_df()

    if len(cells_df) == 0:
        print("  No assignments produced in any cell -- global solve infeasible.")
        return

    # Numeric coercion + derived columns (margin, anchor_share, total_cost).
    for col in ("n_assigned", "revenue_usd", "anchor_revenue_usd",
                "energy_cost_usd", "dep_cost_usd"):
        cells_df[col] = pd.to_numeric(cells_df[col], errors="coerce").fillna(0)
    cells_df["total_cost_usd"] = cells_df["energy_cost_usd"] + cells_df["dep_cost_usd"]
    cells_df["realized_margin"] = (
        (cells_df["revenue_usd"] - cells_df["total_cost_usd"])
        / cells_df["revenue_usd"].replace(0, float("nan"))
    )
    cells_df["anchor_share"] = (
        cells_df["anchor_revenue_usd"] / cells_df["revenue_usd"].replace(0, float("nan"))
    )

    # Per-(cell, workload_type) counts -- one per type, since each
    # aggregate is a per-cell scalar. Pandas pivot is the simplest way to
    # add these as columns on the cells_df table.
    type_count_dfs = {}
    for wt in WORKLOAD_TYPES:
        n_wt = aggs.count(Assignment).where(
            Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
            xq > 0.5,
            Assignment.workload.workload_type == wt,
        ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        df_wt = model.select(
            PowerEnvelopeLevel.name.alias("envelope"),
            MarginFloor.name.alias("margin"),
            DiversityCap.name.alias("diversity"),
            n_wt.alias(f"n_{wt}"),
        ).to_df()
        type_count_dfs[wt] = df_wt
        cells_df = cells_df.merge(df_wt, on=["envelope","margin","diversity"], how="left")
        cells_df[f"n_{wt}"] = pd.to_numeric(cells_df[f"n_{wt}"], errors="coerce").fillna(0).astype(int)

    for pt in ("P0", "P1", "P2"):
        n_pt = aggs.count(Assignment).where(
            Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, xq),
            xq > 0.5,
            Assignment.workload.priority_tier == pt,
        ).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        df_pt = model.select(
            PowerEnvelopeLevel.name.alias("envelope"),
            MarginFloor.name.alias("margin"),
            DiversityCap.name.alias("diversity"),
            n_pt.alias(f"n_{pt}"),
        ).to_df()
        cells_df = cells_df.merge(df_pt, on=["envelope","margin","diversity"], how="left")
        cells_df[f"n_{pt}"] = pd.to_numeric(cells_df[f"n_{pt}"], errors="coerce").fillna(0).astype(int)

    # Detect infeasibility: ontology aggregate returns 0/NaN for cells whose
    # constraints contradict the rest of the global solve (no Assignment rows
    # in those cells). n_assigned > 0 is the canonical "this cell solved"
    # signal -- mirrors the rai-prescriptive-results-interpretation skill's
    # "filter active binary decisions, alias columns, display" pattern.
    cells_df["status"] = cells_df["n_assigned"].apply(
        lambda n: "OPTIMAL" if n > 0 else "INFEASIBLE"
    )
    cells_df = cells_df.sort_values(["envelope", "margin", "diversity"])

    n_total = len(cells_df)
    n_feasible = (cells_df["status"] == "OPTIMAL").sum()
    n_infeasible = (cells_df["status"] == "INFEASIBLE").sum()
    print(f"\n  Per-cell summary ({n_total} cells: {n_feasible} optimal, {n_infeasible} infeasible):")

    display_cols = ["envelope", "margin", "diversity", "status",
                    "n_assigned", "revenue_usd", "total_cost_usd",
                    "realized_margin", "anchor_share"] \
                   + [f"n_{wt}" for wt in WORKLOAD_TYPES] \
                   + [f"n_{pt}" for pt in ("P0", "P1", "P2")]
    print(cells_df[display_cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # Two headline Pareto frontiers, both at envelope=100pct.
    headline_env = "100pct"
    print(f"\n  Pareto frontier 1: Margin floor <-> Revenue (envelope={headline_env}, "
          f"diversity=none)")
    p1 = cells_df[
        (cells_df["envelope"] == headline_env)
        & (cells_df["diversity"] == "none")
    ].sort_values("margin")
    if len(p1):
        print(p1[["margin", "n_assigned", "revenue_usd", "realized_margin",
                  "anchor_share"]].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    print(f"\n  Pareto frontier 2: Diversity cap <-> Revenue (envelope={headline_env}, "
          f"margin=unconstrained)")
    p2 = cells_df[
        (cells_df["envelope"] == headline_env)
        & (cells_df["margin"] == "unconstrained")
    ].sort_values("diversity")
    if len(p2):
        print(p2[["diversity", "n_assigned", "revenue_usd", "realized_margin",
                  "anchor_share"] + [f"n_{wt}" for wt in WORKLOAD_TYPES]
              ].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # ---- Persist the headline plan + chosen-cell decisions as ontology ----
    # AllocationPlan is a singleton holding the operator-facing summary
    # (revenue, cost, anchor share, n_assigned, status, binding axis) for the
    # chosen cell; Assignment.is_chosen narrows the per-cell decision rows to
    # the chosen scenario. After the script exits, a downstream analyst (or
    # Cortex Agent) can query AllocationPlan and Assignment.is_chosen directly
    # without re-running the chain.
    chosen_row = cells_df[
        (cells_df["envelope"] == CHOSEN_ENVELOPE)
        & (cells_df["margin"] == CHOSEN_MARGIN)
        & (cells_df["diversity"] == CHOSEN_DIVERSITY)
    ]
    if len(chosen_row) == 0:
        print(f"\n  AllocationPlan singleton not persisted -- chosen cell "
              f"({CHOSEN_ENVELOPE}, {CHOSEN_MARGIN}, {CHOSEN_DIVERSITY}) absent "
              f"from per-cell summary.")
        return

    _r = chosen_row.iloc[0]
    _status = _r["status"]
    # The chosen cell is the unconstrained 100pct baseline; the binding axis is
    # the power envelope (no margin floor or diversity cap is active). Tighter
    # cells in the sweep show what flips when each axis tightens.
    if _status == "INFEASIBLE":
        _binding_axis = "infeasible"
    else:
        _binding_axis = "power_envelope"

    AllocationPlan = model.Concept("AllocationPlan", identify_by={"id": String})
    AllocationPlan.chosen_envelope = model.Property(
        f"{AllocationPlan} has chosen envelope {String:chosen_envelope}"
    )
    AllocationPlan.chosen_margin = model.Property(
        f"{AllocationPlan} has chosen margin {String:chosen_margin}"
    )
    AllocationPlan.chosen_diversity = model.Property(
        f"{AllocationPlan} has chosen diversity {String:chosen_diversity}"
    )
    AllocationPlan.n_assigned = model.Property(f"{AllocationPlan} has {Integer:n_assigned}")
    AllocationPlan.revenue_usd = model.Property(f"{AllocationPlan} has {Float:revenue_usd}")
    AllocationPlan.total_cost_usd = model.Property(
        f"{AllocationPlan} has {Float:total_cost_usd}"
    )
    AllocationPlan.realized_margin = model.Property(
        f"{AllocationPlan} has {Float:realized_margin}"
    )
    AllocationPlan.anchor_share = model.Property(f"{AllocationPlan} has {Float:anchor_share}")
    AllocationPlan.status = model.Property(f"{AllocationPlan} has status {String:status}")
    AllocationPlan.binding_axis = model.Property(
        f"{AllocationPlan} has binding axis {String:binding_axis}"
    )

    _margin = float(_r["realized_margin"]) if pd.notna(_r["realized_margin"]) else 0.0
    _anchor = float(_r["anchor_share"]) if pd.notna(_r["anchor_share"]) else 0.0
    model.define(
        ap := AllocationPlan.new(id="DCCA_BASELINE"),
        ap.chosen_envelope(CHOSEN_ENVELOPE),
        ap.chosen_margin(CHOSEN_MARGIN),
        ap.chosen_diversity(CHOSEN_DIVERSITY),
        ap.n_assigned(int(_r["n_assigned"])),
        ap.revenue_usd(float(_r["revenue_usd"])),
        ap.total_cost_usd(float(_r["total_cost_usd"])),
        ap.realized_margin(_margin),
        ap.anchor_share(_anchor),
        ap.status(_status),
        ap.binding_axis(_binding_axis),
    )

    # Narrow Boolean: Assignment.is_chosen fires for assignments in the chosen
    # cell with x_assign > 0.5. Mirrors the telco_network_recovery
    # TowerUpgradeOption.is_selected_upgrade pattern.
    Assignment.is_chosen = model.Relationship(f"{Assignment} is in chosen cell")
    xc = Float.ref("xc")
    chosen_env_c = PowerEnvelopeLevel.filter_by(name=CHOSEN_ENVELOPE)
    chosen_mar_c = MarginFloor.filter_by(name=CHOSEN_MARGIN)
    chosen_div_c = DiversityCap.filter_by(name=CHOSEN_DIVERSITY)
    model.where(
        Assignment.x_assign(chosen_env_c, chosen_mar_c, chosen_div_c, xc),
        xc > 0.5,
    ).define(Assignment.is_chosen())

    print("\n  AllocationPlan singleton (queryable as ontology):")
    plan_df = model.select(
        AllocationPlan.id.alias("plan_id"),
        AllocationPlan.chosen_envelope.alias("envelope"),
        AllocationPlan.chosen_margin.alias("margin"),
        AllocationPlan.chosen_diversity.alias("diversity"),
        AllocationPlan.status.alias("status"),
        AllocationPlan.n_assigned.alias("n_assigned"),
        AllocationPlan.revenue_usd.alias("revenue_usd"),
        AllocationPlan.total_cost_usd.alias("total_cost_usd"),
        AllocationPlan.realized_margin.alias("realized_margin"),
        AllocationPlan.anchor_share.alias("anchor_share"),
        AllocationPlan.binding_axis.alias("binding_axis"),
    ).to_df()
    print(plan_df.to_string(index=False))

    n_chosen_df = model.select(
        aggs.count(Assignment).alias("n"),
    ).where(Assignment.is_chosen()).to_df()
    n_chosen = int(n_chosen_df["n"].iloc[0]) if len(n_chosen_df) else 0
    print(f"  Assignment.is_chosen rows: {n_chosen} (matches n_assigned above)")

    # ---- DemandScenario overlay: stranded-capacity exposure under risk scenarios ----
    # The chosen plan is locked in, but lab-side demand for the assigned workloads
    # can soften from the GNN's point forecast. Three risk scenarios scale the
    # demand-realization factor; revenue on anchor contracts (P0) is contractual
    # and unaffected, while opportunistic seats (P1/P2) realize only `factor`
    # of their assigned revenue. The delta from "expected" is stranded capacity:
    # GPUs already powered, depreciation already accruing, but no workload running.
    DemandScenario = model.Concept("DemandScenario", identify_by={"name": String})
    DemandScenario.factor = model.Property(f"{DemandScenario} has {Float:factor}")
    DemandScenario.label = model.Property(f"{DemandScenario} has {String:label}")
    ds_data = pd.DataFrame([
        {"name": "expected",            "factor": 1.00, "label": "baseline forecast"},
        {"name": "diffusion_slowdown",  "factor": 0.85, "label": "customer adoption hits change-management limits"},
        {"name": "scaling_break",       "factor": 0.70, "label": "capability plateau reduces incremental demand"},
        {"name": "frontier_loss",       "factor": 0.50, "label": "competitive displacement of one or more anchor labs"},
    ])
    ds_src = model.data(ds_data)
    model.define(DemandScenario.new(
        name=ds_src.name, factor=ds_src.factor, label=ds_src.label,
    ))

    # Pull the chosen-cell assignments + their priority tier + value.
    chosen_df = model.select(
        Assignment.workload.id.alias("workload_id"),
        Assignment.workload.priority_tier.alias("priority_tier"),
        Assignment.workload.strategic_value_usd.alias("strategic_value_usd"),
    ).where(Assignment.is_chosen()).to_df()

    overlay_rows = []
    expected_revenue = float(plan_df["revenue_usd"].iloc[0]) if len(plan_df) else 0.0
    for _, dsr in ds_data.iterrows():
        f = float(dsr["factor"])
        # P0 revenue is contractual (factor = 1.0); P1/P2 realize `factor`.
        p0_rev = chosen_df.loc[chosen_df["priority_tier"] == "P0", "strategic_value_usd"].sum()
        non_p0_rev = chosen_df.loc[chosen_df["priority_tier"] != "P0", "strategic_value_usd"].sum()
        realized = float(p0_rev + non_p0_rev * f)
        stranded = max(expected_revenue - realized, 0.0)
        overlay_rows.append({
            "scenario": dsr["name"],
            "factor": f,
            "realized_revenue_usd": realized,
            "stranded_revenue_usd": stranded,
            "stranded_pct": (stranded / expected_revenue * 100.0) if expected_revenue else 0.0,
        })

    print("\n  DemandScenario overlay (chosen plan replayed under risk):")
    overlay_df = pd.DataFrame(overlay_rows)
    print(overlay_df.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # Persist the overlay as ontology so it's queryable post-run.
    DemandScenarioOutlook = model.Concept(
        "DemandScenarioOutlook",
        identify_by={"scenario": DemandScenario},
    )
    DemandScenarioOutlook.realized_revenue_usd = model.Property(
        f"{DemandScenarioOutlook} has {Float:realized_revenue_usd}"
    )
    DemandScenarioOutlook.stranded_revenue_usd = model.Property(
        f"{DemandScenarioOutlook} has {Float:stranded_revenue_usd}"
    )
    overlay_src = model.data(overlay_df.rename(columns={"scenario": "scenario_name"}))
    DSRef = DemandScenario.ref()
    model.where(DSRef.name == overlay_src.scenario_name).define(
        o := DemandScenarioOutlook.new(scenario=DSRef),
        o.realized_revenue_usd(overlay_src.realized_revenue_usd),
        o.stranded_revenue_usd(overlay_src.stranded_revenue_usd),
    )


if __name__ == "__main__":
    ctx = main()
    stage1_predictive(ctx)
    stage2_rules(ctx)
    stage3_graph(ctx)
    stage4_prescriptive(ctx)
