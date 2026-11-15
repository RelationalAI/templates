"""Datacenter compute allocation reasoning: GNN, eligibility rules, gating PageRank, the allocation MIP, and its outcome rules."""

from relationalai.semantics import Float, Integer, String, not_, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math, strings

from .schema import (
    DataCenterRequest,
    DemandScenario,
    DiversityCap,
    GpuPool,
    LabMetric,
    MarginFloor,
    PowerEnvelopeLevel,
    Test,
    Train,
    Val,
    Workload,
    WorkloadDependency,
    WorkloadGpuCompat,
    model,
)

SEED = 42
GNN_EPOCHS = 80
GNN_LR = 0.002

# Headline plan cell. The AllocationPlan singleton + Assignment.is_chosen
# flag persist this cell's outcome; tighter cells in the 24-cell sweep
# remain queryable via Assignment.x_assign but are diagnostic overlays
# rather than the operator-facing plan.
CHOSEN_ENVELOPE = "100pct"
CHOSEN_MARGIN = "unconstrained"
CHOSEN_DIVERSITY = "none"
PLAN_ID = "DCCA_BASELINE"

# Stage 4 solver. HiGHS is the open-source default that ships with the
# prescriptive engine; switch to "gurobi" if your engine has a Gurobi
# license (faster convergence, tighter MIP gaps on the 24-cell sweep).
SOLVER = "highs"
SOLVER_TIME_LIMIT_SEC = 240

WORKLOAD_TYPES = ("pretrain", "finetune", "inference", "eval")

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

# Heterogeneous graph (three cross-concept edge types). All edges cross
# concept boundaries -- same-entity-only edges (e.g. pure temporal lag)
# would not give the GNN message-passing lift over a tabular model.
gnn_graph = Graph(model, directed=False, weighted=False)

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
# share a workload_type. LOAD-BEARING -- carries cross-lab co-movement
# signal a per-workload tabular baseline cannot replicate.
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

# --------------------------------------------------
# Stage 2: Rules -- eligibility + priority classification
#   Hardware compatibility (memory + GPU-type allowlist) + priority tier
#   from contract_tier. Asymmetric failure-mode pricing: under-provisioning
#   an anchor (P0) carries an SLA / contract / reputational penalty that is
#   a multiple of the raw foregone revenue; Stage 4 multiplies the
#   assignment reward by (1 + under_provisioning_penalty).
# --------------------------------------------------

# Rule family 1: hardware compatibility
# `is_eligible` is defined with positive conditions directly (PyRel
# does not support `~` negation on relationship-application expressions).
# Failure flags are still derived for reporting/queryability:
Workload.fails_memory = model.Relationship(
    f"{Workload} fails memory check on {GpuPool}"
)
model.where(
    Workload.mem_required_gb > GpuPool.mem_per_gpu_gb,
).define(Workload.fails_memory(GpuPool))

# Rule family 2: priority tier + numeric weight (lex-emulating spread)
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

# Asymmetric failure mode: unfilled P0 seats hurt more than unfilled P2.
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
Workload.is_eligible = model.Relationship(
    f"{Workload} is eligible on {GpuPool}"
)
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

# --------------------------------------------------
# Stage 3: Graph -- workload-dependency PageRank (gating score)
#   Reverse-PageRank on the WorkloadDependency.blocks DAG: a high
#   `gating_score` means many downstream workloads are gated by this
#   one (frontier pretrain that gates 14 fine-tunes + evals lands at
#   the top).
# --------------------------------------------------

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

# --------------------------------------------------
# Stage 4: Prescriptive -- compute allocation MIP (24-cell sweep)
#   Decision variable: Assignment.x_assign(PowerEnvelopeLevel, MarginFloor,
#                      DiversityCap), binary. One per (Workload, GpuPool)
#                      in Compatibility, per scenario cell.
#
#   Constraints:
#     C1+C2 -- At most one assignment per workload per cell.
#              (Hard P0 commitment relaxed to <=1; priority_weight=100 in
#               the objective dominates so P0 is pushed to 1 wherever
#               feasible. Per-cell P0 drops surface as the diagnostic
#               signal the design specifies.)
#     C3    -- Per-pool GPU-count capacity.
#     C4    -- Per-DC power envelope: gpu_count * power_per_gpu * pue <=
#              approved_mw * 1000 * envelope_multiplier.
#     C5    -- Gross-margin floor (linearized; skipped when fraction < 0).
#     C6    -- Anchor concentration cap (skipped when share < 0).
#     C7    -- Workload-type floor (one per type; skipped when floor < 0).
#
#   Objective: maximize sum over assignments of
#       priority_weight * gating_score * utilization_probability *
#       strategic_value_usd * (1 + under_provisioning_penalty)
# --------------------------------------------------

# Decision variable: Assignment indexed by the three scenario axes. A
# workload is assignable once it has a utilization forecast.
Assignment = model.Concept(
    "Assignment",
    identify_by={"workload": Workload, "gpu_pool": GpuPool},
)
model.define(
    Assignment.new(workload=Compatibility.workload, gpu_pool=Compatibility.gpu_pool)
).where(WorkloadForecast.workload_id == Compatibility.workload.id)

Assignment.x_assign = model.Property(
    f"{Assignment} per {PowerEnvelopeLevel} per {MarginFloor} per {DiversityCap} "
    f"assigned {Float:x_assign}"
)

problem = Problem(model, Float, name="datacenter_compute_allocation")

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

# C1+C2: at most one assignment per workload per cell
x2 = Float.ref()
Wany = Workload.ref()
problem.satisfy(model.where(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x2),
    Assignment.workload == Wany,
).require(
    sum(Assignment, x2).per(Wany, PowerEnvelopeLevel, MarginFloor, DiversityCap) <= 1.0
))

# C3: per-pool GPU count capacity
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

# C4: per-DC power envelope
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

# C5: gross-margin floor (linearized; skipped when fraction < 0)
# revenue * (1 - fraction) >= total_cost
# total_cost = energy_cost + depreciation_cost  (per workload, per duration)
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

# C6: anchor concentration cap (skipped when share < 0)
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

# C7: workload-type floor (one constraint per type; skipped when floor < 0)
for wt in WORKLOAD_TYPES:
    x7 = Float.ref()
    problem.satisfy(model.where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x7),
        DiversityCap.workload_type_floor >= 0.0,
    ).require(
        sum(Assignment, x7)
            .where(Assignment.workload.workload_type == wt)
            .per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
        >= DiversityCap.workload_type_floor
            * sum(Assignment, x7).per(PowerEnvelopeLevel, MarginFloor, DiversityCap)
    ))

# Objective: four-factor strategic value, amplified by under-provisioning penalty
# The (1 + under_provisioning_penalty) multiplier captures asymmetric failure modes:
# an unfilled anchor seat (P0) costs more than the foregone revenue, while an
# unfilled research eval costs only the revenue. P0 = 1.0 (2x amp), P1 = 0.3, P2 = 0.0.
x_obj = Float.ref()
problem.maximize(
    sum(PowerEnvelopeLevel, MarginFloor, DiversityCap,
        x_obj
        * Assignment.workload.priority_weight
        * Assignment.workload.gating_score
        * WorkloadForecast.utilization_probability
        * Assignment.workload.strategic_value_usd
        * (1.0 + Assignment.workload.under_provisioning_penalty))
    .where(
        Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x_obj),
        WorkloadForecast.workload_id == Assignment.workload.id,
    )
)

# Each refresh of the deployed model runs this solve.
problem.configure(SOLVER, time_limit_sec=SOLVER_TIME_LIMIT_SEC)

# The solve's status, time and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"datacenter allocation solve status is {String:status}")
SolveTime = model.Relationship(f"datacenter allocation solve time is {Float:seconds}")
SolveObjective = model.Relationship(f"datacenter allocation objective is {Float:objective}")
model.define(
    SolveStatus(problem.termination_status()),
    SolveTime(problem.solve_time_sec()),
    SolveObjective(problem.objective_value()),
)

# --------------------------------------------------
# Stage 4 (cont.): Per-cell outcomes + headline-plan persistence
#   One ScenarioCell per (env, mar, div). Its aggregates are computed from the
#   solved Assignment.x_assign values (mirrors energy_grid_planning's
#   InvestmentPortfolio). An infeasible cell has no assignments, so its
#   aggregates have no value. The chosen baseline cell is persisted as an
#   AllocationPlan singleton + Assignment.is_chosen flag + DemandScenario
#   overlay so the plan is queryable as ontology.
# --------------------------------------------------

ScenarioCell = model.Concept(
    "ScenarioCell",
    identify_by={"envelope": PowerEnvelopeLevel, "margin": MarginFloor, "diversity": DiversityCap},
)
ScenarioCell.n_assigned = model.Property(f"{ScenarioCell} has {Integer:n_assigned}")
ScenarioCell.revenue_usd = model.Property(f"{ScenarioCell} has {Float:revenue_usd}")
ScenarioCell.anchor_revenue_usd = model.Property(f"{ScenarioCell} has {Float:anchor_revenue_usd}")
ScenarioCell.energy_cost_usd = model.Property(f"{ScenarioCell} has {Float:energy_cost_usd}")
ScenarioCell.dep_cost_usd = model.Property(f"{ScenarioCell} has {Float:dep_cost_usd}")
ScenarioCell.total_cost_usd = model.Property(f"{ScenarioCell} has {Float:total_cost_usd}")
ScenarioCell.realized_margin = model.Property(f"{ScenarioCell} has {Float:realized_margin}")
ScenarioCell.anchor_share = model.Property(f"{ScenarioCell} has {Float:anchor_share}")
ScenarioCell.n_by_type = model.Relationship(
    f"{ScenarioCell} has {String:workload_type} workload count {Integer:n}"
)
ScenarioCell.n_by_tier = model.Relationship(
    f"{ScenarioCell} has {String:priority_tier} workload count {Integer:n}"
)
ScenarioCell.status = model.Property(f"{ScenarioCell} has status {String:status}")

model.define(ScenarioCell.new(
    envelope=PowerEnvelopeLevel, margin=MarginFloor, diversity=DiversityCap,
))

xq = Float.ref("xq")


def _assigned_in_cell():
    """Conditions selecting the Assignments the solve placed in ScenarioCell."""
    return (
        Assignment.x_assign(ScenarioCell.envelope, ScenarioCell.margin, ScenarioCell.diversity, xq),
        xq > 0.5,
    )


model.define(ScenarioCell.n_assigned(
    aggs.count(Assignment).where(*_assigned_in_cell()).per(ScenarioCell)
))
model.define(ScenarioCell.revenue_usd(
    sum(Assignment, Assignment.workload.strategic_value_usd)
    .where(*_assigned_in_cell()).per(ScenarioCell)
))
model.define(ScenarioCell.anchor_revenue_usd(
    sum(Assignment, Assignment.workload.strategic_value_usd)
    .where(*_assigned_in_cell(), Assignment.workload.lab.is_strategic_anchor == True)
    .per(ScenarioCell)
))
model.define(ScenarioCell.energy_cost_usd(
    sum(Assignment,
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.power_per_gpu_kw
        * Assignment.gpu_pool.data_center.pue
        * Assignment.gpu_pool.data_center.dollars_per_mwh / 1000.0)
    .where(*_assigned_in_cell()).per(ScenarioCell)
))
model.define(ScenarioCell.dep_cost_usd(
    sum(Assignment,
        Assignment.workload.gpu_count_required
        * Assignment.workload.duration_hours
        * Assignment.gpu_pool.hourly_depreciation_rate)
    .where(*_assigned_in_cell()).per(ScenarioCell)
))
model.define(ScenarioCell.total_cost_usd(ScenarioCell.energy_cost_usd + ScenarioCell.dep_cost_usd))
model.define(ScenarioCell.realized_margin(
    (ScenarioCell.revenue_usd - ScenarioCell.total_cost_usd) / ScenarioCell.revenue_usd
))
model.define(ScenarioCell.anchor_share(ScenarioCell.anchor_revenue_usd / ScenarioCell.revenue_usd))

# Per-(cell, workload_type) and per-(cell, priority_tier) counts.
wtype = String.ref()
model.define(ScenarioCell.n_by_type(
    wtype,
    aggs.count(Assignment)
    .where(*_assigned_in_cell(), Assignment.workload.workload_type == wtype)
    .per(ScenarioCell, wtype),
))
tier = String.ref()
model.define(ScenarioCell.n_by_tier(
    tier,
    aggs.count(Assignment)
    .where(*_assigned_in_cell(), Assignment.workload.priority_tier == tier)
    .per(ScenarioCell, tier),
))

# Per-cell status: when the global solve proved optimality, cells with
# assignments are OPTIMAL and cells with none are INFEASIBLE. When the
# wall-clock ran out first, they are FEASIBLE and UNSOLVED.
solve_status = String.ref()
model.where(
    SolveStatus(solve_status), solve_status == "OPTIMAL", ScenarioCell.n_assigned > 0
).define(ScenarioCell.status("OPTIMAL"))
model.where(
    SolveStatus(solve_status), solve_status == "OPTIMAL", not_(ScenarioCell.n_assigned > 0)
).define(ScenarioCell.status("INFEASIBLE"))
model.where(
    SolveStatus(solve_status), solve_status != "OPTIMAL", ScenarioCell.n_assigned > 0
).define(ScenarioCell.status("FEASIBLE"))
model.where(
    SolveStatus(solve_status), solve_status != "OPTIMAL", not_(ScenarioCell.n_assigned > 0)
).define(ScenarioCell.status("UNSOLVED"))

# AllocationPlan is a singleton holding the operator-facing summary
# (revenue, cost, anchor share, n_assigned, status, binding axis) for
# the chosen cell; Assignment.is_chosen narrows the per-cell decision
# rows to the chosen scenario. Mirrors the telco_network_recovery
# RestorePlan / is_selected_upgrade pattern.
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

model.define(AllocationPlan.new(id=PLAN_ID))
chosen_cell = (
    AllocationPlan.id == PLAN_ID,
    ScenarioCell.envelope.name == CHOSEN_ENVELOPE,
    ScenarioCell.margin.name == CHOSEN_MARGIN,
    ScenarioCell.diversity.name == CHOSEN_DIVERSITY,
)
model.where(*chosen_cell).define(
    AllocationPlan.chosen_envelope(CHOSEN_ENVELOPE),
    AllocationPlan.chosen_margin(CHOSEN_MARGIN),
    AllocationPlan.chosen_diversity(CHOSEN_DIVERSITY),
)
model.where(*chosen_cell).define(AllocationPlan.n_assigned(ScenarioCell.n_assigned))
model.where(*chosen_cell).define(AllocationPlan.revenue_usd(ScenarioCell.revenue_usd))
model.where(*chosen_cell).define(AllocationPlan.total_cost_usd(ScenarioCell.total_cost_usd))
model.where(*chosen_cell).define(AllocationPlan.realized_margin(ScenarioCell.realized_margin))
model.where(*chosen_cell).define(AllocationPlan.anchor_share(ScenarioCell.anchor_share))
model.where(*chosen_cell).define(AllocationPlan.status(ScenarioCell.status))
model.where(*chosen_cell, ScenarioCell.n_assigned > 0).define(
    AllocationPlan.binding_axis("power_envelope")
)
model.where(*chosen_cell, not_(ScenarioCell.n_assigned > 0)).define(
    AllocationPlan.binding_axis(strings.lower(ScenarioCell.status))
)

Assignment.is_chosen = model.Relationship(f"{Assignment} is in chosen cell")
xc = Float.ref("xc")
chosen_env_c = PowerEnvelopeLevel.lookup(name=CHOSEN_ENVELOPE)
chosen_mar_c = MarginFloor.lookup(name=CHOSEN_MARGIN)
chosen_div_c = DiversityCap.lookup(name=CHOSEN_DIVERSITY)
model.where(
    Assignment.x_assign(chosen_env_c, chosen_mar_c, chosen_div_c, xc),
    xc > 0.5,
).define(Assignment.is_chosen())

# DemandScenario overlay: stranded-capacity exposure under risk.
# The chosen plan is locked in, but lab-side demand for the assigned
# workloads can soften from the GNN's point forecast. P0 revenue is
# contractual (factor = 1.0); P1/P2 realize only `factor`. The delta
# is stranded capacity: GPUs powered, depreciation accruing, no workload.
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
model.define(DemandScenarioOutlook.new(scenario=DemandScenario))

p0_revenue = sum(Assignment, Assignment.workload.strategic_value_usd).where(
    Assignment.is_chosen(), Assignment.workload.priority_tier == "P0"
)
other_revenue = sum(Assignment, Assignment.workload.strategic_value_usd).where(
    Assignment.is_chosen(), Assignment.workload.priority_tier != "P0"
)
model.where(DemandScenarioOutlook.scenario == DemandScenario).define(
    DemandScenarioOutlook.realized_revenue_usd(p0_revenue + other_revenue * DemandScenario.factor)
)
model.where(AllocationPlan.id == PLAN_ID).define(
    DemandScenarioOutlook.stranded_revenue_usd(
        math.maximum(AllocationPlan.revenue_usd - DemandScenarioOutlook.realized_revenue_usd, 0.0)
    )
)
