---
title: "Datacenter Compute Allocation"
description: "Multi-reasoner template (chain follow-up to energy_grid_planning): heterogeneous-graph GNN classification of per-workload utilization probability, hardware-compatibility rules, dependency PageRank, and 3D-scenario MIP for inside-the-fence GPU allocation across hyperscaler campuses."
featured: false
private: true
experience_level: advanced
industry: "AI Infrastructure"
reasoning_types:
  - Predictive
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Cross-Template Ontology
  - GNN
  - Binary Classification
  - Heterogeneous Graph
  - PageRank
  - MIP
  - Scenario Analysis
  - Multi-Objective
  - Pareto Frontier
  - AI Compute
  - Data Centers
  - Capacity Planning
---

# Datacenter Compute Allocation

This template demonstrates the operator-side decision that picks up where **[energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning)** leaves off. That upstream template solves the multi-year capex / interconnect question — which AI campuses get built and energized at what MW envelope — across ~50 binaries. This template zooms into the *energized* campus and decides which AI lab's individual training, fine-tune, inference, and eval workloads get which GPUs in which pool *now*. The bundled `data_centers.csv` is a snapshot of the upstream $300M-approved campus set; the two templates form a conceptual sequence over the same domain, not a literal engine-level chain.

## What this template is for

The 5 hyperscaler campuses in the bundled snapshot — xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal — are energized and stocked with GPU pools. The DC operator (a neocloud / colocation provider, or the hyperscaler operating its own campus) has to allocate that GPU capacity across the AI labs renting time on it. Frontier model labs want long-running training reservations on the largest contiguous H100 / H200 / GB200 pools at preferential anchor-customer rates. Inference customers want a steady slice of right-sized GPUs in low-latency regions. Research orgs want bursty best-effort capacity. They all compete for the same physical pools under the same power envelope.

The decision is **multi-objective and operationally pressing**. Every major hyperscaler now reports AI compute as a binding constraint on growth (Microsoft has disclosed an $80B Azure backlog blocked specifically by power constraints). The operator is accountable on three publicly-discussed dimensions:

1. **Power envelope as cone of uncertainty.** Each campus has a substation-bound MW cap (`approved_mw`, set by the interconnection-planning decision the upstream template represents). The three envelope cells trace the cone: 85% is the lower-cone curtailment day (heat-wave or grid-stress de-rating), 100% is the expected grid-approved cap, and 110% is the upper-cone planning point — contracted-curtailment headroom the operator can lean on when frontier-lab demand outruns the midpoint. Hyperscaler compute is exponential and unstable; planning to the midpoint is how operators end up under-provisioned to anchors.
2. **Gross-margin discipline at the envelope, not per-token.** SemiAnalysis quantifies neocloud BMaaS at 55-65% gross margin pre-depreciation but only **14-16% net** after labor, power, and depreciation, so even a single MWh-cost mis-allocation is meaningful to the P&L. The discipline lives at the *envelope* — return on the full compute base across all uses — not on each individual workload-pool placement.
3. **Anchor concentration as a strategic floor.** CoreWeave's Q2 2025 10-Q discloses **71% of revenue from a single customer (Microsoft)** and an $11.9B OpenAI commitment booked through October 2030 — the canonical example of the concentration risk that caps equity value. Operators win anchors (because they underwrite debt-financed buildouts) AND dilute them (because investor-visible concentration risk caps equity value). Anchor contracts also act as a *hard floor* — they must be served wherever feasible, even when serving them squeezes margin elsewhere; under-provisioning an anchor is more costly than under-provisioning an opportunistic workload, because the penalty is contractual and reputational, not just foregone revenue.
4. **Generational layer cake.** A hyperscaler's GPU fleet is itself a portfolio. H100, H200, and GB200 pools sit at different points on the price-per-effective-GPU-hour curve ($1.14, $1.52, $2.66 per GPU-hour at capex/3-year amortization in the bundled data). The optimizer's job is to deploy each generation against the workload type that gets the best return per dollar of depreciation + power — not to treat all GPU-hours as fungible. Effective capacity is `gpu_count × generation_efficiency`, not nameplate.

This template combines three Scenario Concepts — `PowerEnvelopeLevel`, `MarginFloor`, and `DiversityCap` — into a **3D scenario sweep (3 × 4 × 4 = 48 cells)** that traces two Pareto frontiers the operator already discusses publicly: margin-floor vs. achievable revenue, and diversity-cap vs. achievable revenue, with envelope as outer sensitivity. The strictest cells return `INFEASIBLE` — this is the intended diagnostic signal showing which constraint combinations cannot be satisfied simultaneously. After the main solve, a `DemandScenario` overlay replays the chosen plan under risk scenarios (diffusion slowdown, scaling-law plateau, frontier loss) so the operator sees stranded-capacity exposure if lab-side demand softens.

This template demonstrates a multi-reasoner workflow combining **predictive** (per-workload utilization-probability classification GNN — predicts which workloads will actually use their allocated capacity at high duty cycle vs stall or be repaced; stranded-capacity exposure is the operator's biggest economic risk), **rules** (hardware compatibility + priority-tier classification), **graph** (downstream-gating score on the workload-dependency DAG), and **prescriptive** (assignment MIP under a 3D Scenario sweep) reasoning on a single shared ontology — each stage's output narrows or scores the next.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1. Predictive | **Heterogeneous-graph temporal GNN** (binary classification) | `LabMetric` activity features (time-aligned via `metric_date`) + `Workload` features + three edge types: intra-lab `lab_workloads`, `WorkloadDependency.blocks` (shared with Stage 3), cross-lab `co_dated` (LOAD-BEARING) | `Workload.utilization_probability` per workload (positive-class probability) | Predict per-workload utilization probability for the current period: will this workload actually use its allocated capacity at high duty cycle, or stall / be repaced? Trained on 770 historical `(workload, month, is_high_utilization)` observations over 7 prior months + 1 validation month; the GNN uses `has_time_column=True` to align workload-period predictions with same-period LabMetric activity. Stranded-capacity exposure is the operator's biggest economic risk. Cross-concept message passing is genuinely load-bearing — utilization depends on the lab's broader activity at the prediction date (lab→workload), what upstream pretrains produced (dep DAG), and industry-wide trends (cross-lab co_dated). Bound directly as a per-workload signal Stage 4's objective consumes. |
| 2. Rules | **Rules** (declarative) | `Workload` requirements, `GpuPool` specs | `Workload.fails_memory`, `.passes_gpu_type`, `.is_eligible` Relationships; `Workload.priority_tier`, `.priority_weight`, and `.under_provisioning_penalty` Properties; `Compatibility(workload, gpu_pool)` precompute | Classify which (Workload, GpuPool) pairs are technically eligible (memory + GPU-type allowlist). Assign priority tier P0/P1/P2 from `contract_tier`, with a numeric weight (100/10/1) and an asymmetric under-provisioning penalty (1.0/0.3/0.0) that amplifies the Stage 4 reward for assigning anchor-tier workloads. The Compatibility precompute keeps the Stage 4 MIP linear. |
| 3. Graph | **Reverse-PageRank** | `Workload` nodes, `WorkloadDependency.blocks` edges | `Workload.gating_score` | Score how much downstream work each workload unblocks. A frontier pretrain that gates 14 fine-tunes and evals lands high; an isolated inference workload sits at baseline. |
| 4. Prescriptive | **MIP** | `Compatibility`, `priority_weight`, `under_provisioning_penalty`, `gating_score`, `utilization_probability`, `dollars_per_mwh`, `hourly_depreciation_rate`, `approved_mw`, `is_strategic_anchor`, the three Scenario Concepts | `Assignment.x_assign` per `(PowerEnvelopeLevel, MarginFloor, DiversityCap)`; `AllocationPlan` singleton; `Assignment.is_chosen`; `DemandScenario` + `DemandScenarioOutlook` (4 risk scenarios) | Assign each workload to one (DC, GpuPool) under power, GPU-count, gross-margin-floor (energy + depreciation cost), and anchor / workload-type-diversity constraints. Maximizes a four-factor strategic value amplified by the under-provisioning penalty: priority × gating × utilization_probability × strategic_value × (1 + penalty). 48-cell sweep; strictest cells return INFEASIBLE as designed signal. The headline cell (`100pct / unconstrained / none`) is persisted as the `AllocationPlan` singleton, its decision rows flagged via `Assignment.is_chosen`, and the chosen plan is replayed under four demand-risk scenarios (expected / diffusion_slowdown / scaling_break / frontier_loss) with realized + stranded revenue persisted as `DemandScenarioOutlook` per scenario. All queryable as ontology after the script exits. |

**Key design patterns demonstrated:**

- **One ontology relationship, two reasoners.** `WorkloadDependency.blocks` carries information into both the Stage 1 GNN (as a heterogeneous edge) and the Stage 3 PageRank (as the dependency DAG). Defined once in the ontology, consumed without duplication or DataFrame round-trips.
- **Per-cell aggregates queried from the ontology.** Stage 4's per-cell summary table (revenue, energy + depreciation cost, anchor share, workload-type counts) comes from `sum(...).where(Assignment.x_assign(env, mar, div, x), x > 0.5).per(env, mar, div)` aggregate expressions assembled inside a single `model.select()` call — mirroring `energy_grid_planning`'s `rev_per_level` pattern. No pandas-side groupby of raw assignments.
- **Headline plan persisted as ontology.** After the 48-cell sweep, the chosen baseline cell (`100pct / unconstrained / none`) is written back as a singleton `AllocationPlan` Concept carrying revenue, total_cost, realized_margin, anchor_share, n_assigned, status, and binding_axis — plus an `Assignment.is_chosen` unary Relationship that flags the decision rows in that cell. The plan is queryable as ontology after the script exits, mirroring the `RestorePlan` / `is_selected_upgrade` pattern in `telco_network_recovery`.
- **Heterogeneous GNN, not time-series-on-rails.** Stage 1 connects `LabMetric` to `Workload`, to other `LabMetric` rows on the same date (when their labs share a workload_type), and reuses `WorkloadDependency` — in addition to same-lab temporal lags. Pure same-entity temporal-lag topology is a misuse of the GNN reasoner; the cross-concept edges are what give it lift.
- **Three-dimensional Scenario Concept design.** `PowerEnvelopeLevel` (outer capacity sensitivity), `MarginFloor` (primary Pareto axis), `DiversityCap` (primary Pareto axis). Decision variable `Assignment.x_assign` is indexed by all three; the Pareto frontier emerges from constraint relaxation across cells, not from a multi-objective solve.
- **Lex-emulating priority weights.** P0 workloads carry weight 100, P1 carry 10, P2 carry 1, plus a hard P0-must-be-assigned constraint. This mirrors how production cluster schedulers (Borg, Singularity, MAST) balance priority dominance with throughput optimization.
- **Four-factor MIP objective as envelope-level ROI.** `priority_weight × gating_score × utilization_probability × strategic_value_usd` — one factor per upstream reasoner (Stage 2 / Stage 3 / Stage 1) plus the raw dollar baseline. Single-MIP, weighted-sum; the multi-objective Pareto emerges from constraint relaxation, not the objective. The operator's discipline lives at the envelope — return on the full compute base across anchor / opportunistic / research uses — not on each individual workload-pool placement.
- **Asymmetric failure-mode pricing.** Under-provisioning an anchor is more costly than missing a research eval: the SLA / contract / reputational penalty is a multiple of the raw revenue at stake. Stage 2 derives a `Workload.under_provisioning_penalty` from the priority tier; Stage 4's objective amplifies the reward for assigning high-penalty workloads, so the solver treats anchor under-provisioning as the asymmetric failure mode it is, not as a symmetric foregone-revenue line item.

## Who this is for

- DC operators (neocloud, colo, hyperscaler infra teams) allocating GPU capacity across multi-tenant pools
- Capacity planners deciding when a (margin floor, diversity cap, envelope) point justifies acquiring more megawatts
- Operations researchers exploring multi-reasoner pipelines that compose a heterogeneous GNN, graph centrality, declarative rules, and a scenario-parameterized MIP
- Developers extending RelationalAI templates across decision lineages (capacity planning → allocation → scheduling)

## What you'll build

- A 6-lab × 5-DC compute allocation MIP, indexed by a 3D Scenario Concept sweep (3 envelopes × 4 margin floors × 4 diversity caps = 48 cells)
- A heterogeneous-graph GNN that **classifies per-workload utilization probability** (will this workload actually use its allocated capacity?) — the operator's real forward-looking signal, propagated through lab→workload, dep-DAG, and cross-lab co_dated edges
- Reverse-PageRank scoring on a workload dependency DAG (4-5 deep chains rooted at frontier pretrains)
- Declarative hardware-compatibility rules + lex-emulating priority weights (P0=100, P1=10, P2=1)
- Two headline Pareto frontiers (margin × revenue and diversity × revenue) at the 100% envelope, with 85% / 110% drawn as overlay sensitivity bands
- Per-cell results queryable directly from the ontology — realized revenue, energy + depreciation cost, anchor share, per-workload-type counts, binding-constraint signal (OPTIMAL vs INFEASIBLE)

## What's included

- `datacenter_compute_allocation.py` — main script: 4 reasoner stages + Pareto reporting + ontology persistence
- `data/data_centers.csv` — 5 DCs (snapshot of the upstream $300M-approved set)
- `data/gpu_pools.csv` — 28 pools across 5 DCs (H100 / H200 / GB200 mix), with per-GPU `hourly_depreciation_rate` ($1.14 H100, $1.52 H200, $2.66 GB200; capex/3-year amortization)
- `data/ai_labs.csv` — 6 labs: 3 frontier anchors (Anthropic, OpenAI, xAI Internal) + 2 applied (Cohere Inference, Together AI Multi-Lab) + 1 research (Stability Open)
- `data/workloads.csv` — 110 workloads: 15 P0 pretrains (frontier labs, 256-1024 GPUs each, GB200/H200/H100 mix), 30 P1 finetune (Together AI + Cohere), 50 P1 inference (Cohere + Together), 15 P2 eval (Stability)
- `data/workload_gpu_compatibility.csv` — per-workload GPU-type allowlist
- `data/workload_dependencies.csv` — 138 edges (~130 blocks + ~10 informs), DAG depth 4-5 rooted at frontier pretrains
- `data/lab_metrics.csv` — 365 days × 6 labs = 2,190 rows with cross-lab co-movement
- `data/workload_utilization_train.csv`, `_val.csv`, `_test.csv` — GNN temporal binary-classification splits. **Train**: 7 historical months × 110 workloads = 770 `(workload, observation_date, is_high_utilization)` observations. **Val**: 1 month × 110 = 110. **Test**: the current month × 110 = 110 observations with no label (every workload gets a probability for the upcoming period).
- `data/workload_utilization_fallback.csv` — Stage 1 fallback (per-workload deterministic probability for the current period, used when `--no-gnn` is set)
- `data/power_envelope_levels.csv` — 3 scenario rows (0.85 / 1.00 / 1.10)
- `data/margin_floors.csv` — 4 scenario rows (unconstrained / 75% / 80% / 85% gross margin post-depreciation)
- `data/diversity_caps.csv` — 4 scenario rows (none / anchor_max_70pct / anchor_max_50pct CoreWeave-target / anchor_max_40pct_with_type_floor)
- `runbook.md` — analyst paste-test walkthrough mapping each stage to its RAI agent skill + prompt

## Prerequisites

### Access

- A Snowflake account with the RelationalAI native app installed.
- A Snowflake user with permissions on the RAI native app and on `EXP_DATABASE` (the schema for GNN experiment artifacts).
- A prescriptive engine for Stage 4. Optionally a GPU-backed predictive engine for Stage 1.

### Tools

- Python ≥ 3.10.
- RelationalAI Python SDK with the predictive submodule (`relationalai.semantics.reasoners.predictive`) for Stage 1's GNN. Without it, Stage 1 falls back to the precomputed `workload_utilization_fallback.csv` automatically.

### One-time Snowflake setup for GNN experiment artifacts

The predictive reasoner writes training artifacts (model checkpoints, metrics, predictions) to a Snowflake schema that the `RELATIONALAI` native app must own. Pick a database you control, then create + grant the schema:

```sql
CREATE DATABASE IF NOT EXISTS DATACENTER_ENRICHMENT;
CREATE SCHEMA   IF NOT EXISTS DATACENTER_ENRICHMENT.EXPERIMENTS;
GRANT USAGE             ON DATABASE DATACENTER_ENRICHMENT             TO APPLICATION RELATIONALAI;
GRANT USAGE             ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL      ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

Set `EXP_DATABASE` at the top of `datacenter_compute_allocation.py` to that database (default: `DATACENTER_ENRICHMENT`).

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/datacenter_compute_allocation.zip
   unzip datacenter_compute_allocation.zip
   cd datacenter_compute_allocation
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure your RAI connection:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python datacenter_compute_allocation.py
   ```

6. Skip the GNN and load `workload_utilization_fallback.csv` directly (useful for fast iteration on Stages 2–4):

   ```bash
   python datacenter_compute_allocation.py --no-gnn
   ```

7. Expected output (abbreviated):

   ```text
   STAGE 0: LOAD ONTOLOGY
     Ontology loaded: 6 labs, 28 pools, 110 workloads, 138 dep edges, 3x4x4=48 scenario cells

   STAGE 1: PREDICT -- per-workload utilization-probability GNN
     Workload utilization-probability distribution: n_total=110, n>=0.5: 99, n<0.5: 11
     Top 5 (most likely to be high-utilization):
       + Claude-Next pretrain shard 04                 p=0.881
       + Grok-Next pretrain shard 04                   p=0.881
       + Grok-Next pretrain shard 03                   p=0.881
       + Claude-Next pretrain shard 02                 p=0.881
       + GPT-Next pretrain shard 05                    p=0.880
     Bottom 5 (most likely to stall / be repaced):
       - Stability eval batch 14                       p=0.338
       - Stability eval batch 15                       p=0.339
       - Stability eval batch 11                       p=0.340
       - Stability eval batch 12                       p=0.342
       - Stability eval batch 13                       p=0.342

   STAGE 2: RULES -- eligibility + priority classification
     Compatibility table: 1918 eligible (Workload, GpuPool) pairs
     Priority tier counts: P0=15, P1=80, P2=15

   STAGE 3: GRAPH -- workload-dependency PageRank (gating score)
     Top-10 gating workloads (frontier pretrains expected to dominate):
       GPT-Next pretrain shard 02                    score=0.0310
       Grok-Next pretrain shard 04                   score=0.0266
       Claude-Next pretrain shard 02                 score=0.0227
       ...

   STAGE 4: PRESCRIPTIVE -- compute allocation MIP (48-cell sweep)
     Termination status: TIME_LIMIT  (or OPTIMAL depending on solver/limit)
     Per-cell summary (48 cells: 33 optimal, 15 infeasible):
       100pct unconstrained    none   OPTIMAL    110  25,277,810.94  4,197,891.06  0.83  0.95
       100pct          85pct   none   OPTIMAL     20  22,032,951.05  3,304,939.27  0.85  1.00
       ...

     AllocationPlan singleton (queryable as ontology):
       plan_id        envelope        margin     diversity  status   n_assigned   revenue_usd   total_cost_usd   realized_margin   anchor_share    binding_axis
       DCCA_BASELINE    100pct  unconstrained         none  OPTIMAL         110   25277810.94      4197891.06         0.833930          0.947251  power_envelope

     Assignment.is_chosen rows: 110 (matches n_assigned above)

     DemandScenario overlay (chosen plan replayed under risk):
                scenario  factor  realized_revenue_usd  stranded_revenue_usd  stranded_pct
                expected    1.00         25,277,810.94                  0.00          0.00
       diffusion_slowdown    0.85         25,077,803.93            200,007.01          0.79
            scaling_break    0.70         24,877,796.92            400,014.02          1.58
            frontier_loss    0.50         24,611,119.30            666,691.64          2.64
   ```

   Exact GNN multipliers depend on the seed and the predictive engine run; the `--no-gnn` fallback values are deterministic.

   **Expected runtime** (full pipeline, real GNN):
   - Stage 1 (GNN training + prediction): ~3-4 min on `GPU_NV_S` predictive engine (most of the total wall time)
   - Stages 2-3 (rules + PageRank): a few seconds
   - Stage 4 (48-cell MIP): the default `time_limit_sec=120` returns a feasible solution at the wall; `TIME_LIMIT` is signal, not failure per `rai-prescriptive-results-interpretation`. Increase or change the solver in the Customize section if you need tighter convergence.
   - Total wall time: ~6 min end-to-end (Stage 1 GNN dominates; ~3-4 min on `GPU_NV_S` predictive engine + Stage 4 MIP wall).

   **Expected per-cell behavior:**
   - `(*, unconstrained / 75% / 80% margin, none diversity)`: full assignment of all 110 workloads, ~$25M revenue, 83% realized margin, 95% anchor share
   - `(*, 85% margin, none)`: tight floor binds — drops 90 lower-margin workloads, retains 14 of 15 frontier P0 pretrains plus 4 P1 finetunes and 2 P2 evals that fit under the floor, revenue $22M @ 85% margin / 100% anchor
   - `(*, *, anchor_max_70pct)`: anchor cap drops most P0 pretrains, $4-5M revenue @ ~70% anchor
   - `(*, *, anchor_max_50pct)`: CoreWeave-target cap, $2.6M @ 49% anchor (only 2 of 15 P0 pretrains fit)
   - `(*, *, anchor_max_40pct_with_type_floor)`: INFEASIBLE — too tight to satisfy with this lab roster
   - `(*, 85% margin, anchor_max_50pct)`: INFEASIBLE — high margin floor wants pretrain-only, but anchor cap forbids that mix

## Template structure

```text
datacenter_compute_allocation/
  datacenter_compute_allocation.py  # Main script (4 chained reasoning stages + ontology persistence)
  data/
    data_centers.csv                # 5 DCs (snapshot of upstream $300M-approved set; standalone mode)
    data_center_attrs.csv           # 5 rows of dollars_per_mwh (chain mode side table)
    gpu_pools.csv                   # 28 GPU pools across 5 DCs (H100/H200/GB200 mix)
    ai_labs.csv                     # 6 labs (3 frontier, 2 applied, 1 research)
    workloads.csv                   # 110 workloads (15 P0 / 80 P1 / 15 P2)
    workload_gpu_compatibility.csv  # Per-workload GPU-type allowlist
    workload_dependencies.csv       # 138 directed edges in the dependency DAG
    lab_metrics.csv                 # 2,190 = 365 days × 6 labs daily KPIs
    workload_utilization_train.csv  # GNN train split: 7 historical months × 110 = 770 obs
    workload_utilization_val.csv    # GNN val split: 1 month × 110 = 110 obs
    workload_utilization_test.csv   # GNN test: current period × 110, no label
    workload_utilization_fallback.csv  # Stage 1 fallback (deterministic per-workload p)
    power_envelope_levels.csv       # 3 scenario rows (envelope multiplier)
    margin_floors.csv               # 4 scenario rows (gross margin floors)
    diversity_caps.csv              # 4 scenario rows (anchor concentration caps)
  README.md                         # this file
  runbook.md                        # multi-reasoner agent-skill walkthrough
  pyproject.toml                    # dependencies
```

## How it works

### Stage 1: Predictive — per-workload utilization-probability GNN

Binary node classification on `Workload`: predict the probability that each workload will be high-utilization (actually use its allocated capacity at high duty cycle) vs stall or be repaced. This is the operator's load-bearing forward-looking signal — stranded capacity (depreciation accruing without offsetting revenue) is the operator's biggest economic exposure, and a per-workload signal is sharper than a per-lab demand multiplier.

The graph is heterogeneous with three cross-concept edge types that let the GNN's message passing actually do work — same-entity temporal lag alone would not give the GNN lift over a tabular model:

```python
gnn_graph = Graph(model, directed=False, weighted=False)

# Edge 1: LabMetric -> Workload owned by the same lab.
# Carries lab-side recent activity into the per-workload prediction
# neighborhood -- a workload owned by a fast-ramping lab inherits signal.
model.define(gnn_graph.Edge.new(src=LabMetric, dst=Workload)).where(
    LabMetric.lab == Workload.lab.name,
)

# Edge 2: WorkloadDependency.blocks DAG (shared with Stage 3).
# A workload downstream of a high-utilization gating pretrain inherits
# signal through the dep chain.
dep_ref = WorkloadDependency.ref()
model.define(
    gnn_graph.Edge.new(src=dep_ref.predecessor, dst=dep_ref.successor)
).where(dep_ref.dependency_type == "blocks")

# Edge 3: LabMetric -> LabMetric, cross-lab same-date pairs sharing a workload_type.
# LOAD-BEARING -- carries cross-lab co-movement (funding waves, supply shocks).
co_pairs = _build_codated_pairs(lab_metrics_df, ai_labs_df, workloads_df)
co_src = model.data(co_pairs)
LM_a, LM_b = LabMetric.ref(), LabMetric.ref()
model.define(gnn_graph.Edge.new(src=LM_a, dst=LM_b)).where(
    LM_a.lab == co_src.lab_a, LM_a.metric_date == co_src.shared_date,
    LM_b.lab == co_src.lab_b, LM_b.metric_date == co_src.shared_date,
)
```

The task tables carry per-`(workload, observation_date)` historical labels (`workload_utilization_*.csv`). Each row is one monthly utilization observation; the same workload appears in 7 training rows (one per historical month), giving the GNN per-period variety to learn from instead of a single label per entity. Train (7 months × 110 = 770) / Val (1 month × 110 = 110) / Test (current month × 110, no label — every workload gets a probability for the upcoming period). The task relationships use `at {Date:obs_date}` time slots and the GNN runs with `has_time_column=True` so LabMetric features are time-aligned with each (workload, month) prediction:

```python
Train = model.Relationship(f"{Workload} at {Date:obs_date} has {Any:label}")
model.define(Train(
    Workload, TrainTable.observation_date, TrainTable.is_high_utilization
)).where(Workload.id == TrainTable.workload_id)

Test = model.Relationship(f"{Workload} at {Date:obs_date}")
model.define(Test(
    Workload, TestTable.observation_date
)).where(Workload.id == TestTable.workload_id)

pt = PropertyTransformer(
    ...
    datetime=[LabMetric.metric_date],
    time_col=[LabMetric.metric_date],
)

gnn = GNN(
    ...
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    ...
)
gnn.fit()
Workload.predictions = gnn.predictions(domain=Test)
```

The positive-class probability is bound back to the ontology as `Workload.utilization_probability` and consumed by Stage 4's objective.

GNN is the right tool for this task — the answer for any given workload depends on its lab's broader activity at the prediction date, what upstream pretrains in the dep DAG have produced, and industry-wide trends across labs that share its workload_type. A tabular model could only see the workload's own static features, missing all three.

### Stage 2: Rules — eligibility + priority tiers + Compatibility precompute

Two rule families run on the workload-pool product. The eligibility rule joins through the `WorkloadGpuCompat(workload, gpu_type)` composite-key concept (per the GNN-node FD trap: multi-valued allowlists on a GNN-node concept must live as their own concept, not as a Workload Relationship) and enforces both the memory check and the GPU-type allowlist:

```python
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
model.where(Workload.is_eligible(GpuPool)).define(
    Compatibility.new(workload=Workload, gpu_pool=GpuPool)
)
```

Priority tier classification reads `AILab.contract_tier` and writes both `Workload.priority_tier` (string) and `Workload.priority_weight` (100 / 10 / 1) — the numeric form is what Stage 4's objective consumes.

### Stage 3: Graph — reverse-PageRank for downstream gating

A directed `Workload` graph is built with edge reversal (successor → predecessor) so a node's PageRank accumulates flow from everything it gates downstream:

```python
dag = Graph(model, directed=True, weighted=False, node_concept=Workload)
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
```

Workloads absent from the DAG get a backstop `gating_score = 1.0` so they enter the Stage 4 objective product without zeroing out.

### Stage 4: Prescriptive — assignment MIP under a 3D Scenario sweep

The decision variable `Assignment.x_assign` is indexed by the three Scenario Concepts so the MIP solves all 48 cells in a single pass:

```python
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

problem = Problem(model, Float)
x = Float.ref("x")
problem.solve_for(
    Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x),
    type="bin",
    name=["assign", PowerEnvelopeLevel.name, MarginFloor.name, DiversityCap.name,
          Assignment.workload.id, Assignment.gpu_pool.id],
)
```

Constraint families (one per scenario axis):

- **C1+C2** at-most-one per workload per cell (soft P0; priority_weight = 100 drives P0 from the objective).
- **C3** per-pool GPU-count capacity.
- **C4** per-DC power envelope: `Σ gpu_count × power_per_gpu × pue ≤ approved_mw × 1000 × envelope_multiplier`.
- **C5** linearized gross-margin floor (skipped when `MarginFloor.fraction < 0` for the unconstrained row).
- **C6** anchor-concentration cap (skipped when `DiversityCap.anchor_max_share < 0`).
- **C7** workload-type floor (skipped unless `DiversityCap.workload_type_floor >= 0`).

The four-factor objective is what makes this a real chain rather than four disjoint reasoners:

```python
problem.maximize(
    sum(x_obj
        * Assignment.workload.priority_weight       # Stage 2 (rules)
        * Assignment.workload.gating_score          # Stage 3 (graph)
        * Assignment.workload.utilization_probability  # Stage 1 (predictive)
        * Assignment.workload.strategic_value_usd)   # raw $ baseline
    .where(Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x_obj))
)
```

After the solve, the per-cell summary table is assembled inside a single `model.select(...)` — `sum(...).where(Assignment.x_assign(env, mar, div, x), x > 0.5).per(env, mar, div)` aggregates run on the ontology, no pandas-side groupby. The chosen baseline cell (`100pct / unconstrained / none`) is persisted as a singleton `AllocationPlan` Concept with revenue / total_cost / margin / anchor_share / n_assigned / status / binding_axis, plus an `Assignment.is_chosen` unary Relationship over its decision rows.

Finally, a `DemandScenario` overlay replays the locked-in plan under four risk scenarios. Anchor (P0) revenue is treated as contractual (factor 1.0) — the operator gets paid for the seat regardless of utilization — while opportunistic (P1/P2) seats realize only the scenario factor of their assigned revenue. The overlay reports realized and stranded revenue per scenario and persists each as a `DemandScenarioOutlook(scenario)` concept row, so the stranded-capacity exposure of the chosen plan is queryable as ontology, not just printed.

## Customize this template

- **Add or remove DCs** by editing `data_centers.csv`. The bundled set is a snapshot of the upstream $300M-approved campuses; re-running `energy_grid_planning` at a different `InvestmentLevel` produces a different approved set you can copy in.
- **Adjust the lab roster** in `ai_labs.csv`. Anchor flag drives the `DiversityCap` constraint.
- **Tune scenario axes**: edit `power_envelope_levels.csv`, `margin_floors.csv`, `diversity_caps.csv`. Adding rows scales the cell count multiplicatively.
- **Change the priority spread** by editing the weights in `stage2_rules` (default 100 / 10 / 1).
- **Replace the GNN with the deterministic fallback** by setting `--no-gnn` and editing `workload_utilization_fallback.csv` directly.
- **Tune the Stage 4 solve** by adjusting the solver name or `time_limit_sec` in `problem.solve(...)`. The default works on any prescriptive engine; faster commercial solvers (when licensed) can reach OPTIMAL in a fraction of the time.
- **Validate the GNN lift over a tabular baseline** by training a `LogisticRegression` or `GradientBoostingClassifier` on the same workload-side features (`workload_type`, `priority_tier`, `gpu_count_required`, `strategic_value_usd`, etc.) using `workload_utilization_train.csv` as labels and comparing test ROC-AUC. The GNN should beat the tabular baseline by the margin attributable to message passing through `lab_workloads`, `WorkloadDependency.blocks`, and the cross-lab `co_dated` edges — the heterogeneous signal a per-workload tabular model cannot see.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError: relationalai.semantics.reasoners.predictive</code></summary>

The installed `relationalai` predates the predictive submodule. Pin a release that ships the GNN, or run with `--no-gnn` to load the deterministic fallback CSV.
</details>

<details>
<summary><code>Database does not exist or the GNN RelationalAI Native App lacks permissions</code></summary>

The `DATACENTER_ENRICHMENT.EXPERIMENTS` schema is not provisioned with the required grants. Run the four `GRANT` statements in [Prerequisites](#prerequisites).
</details>

<details>
<summary><code>TransactionAbortedException</code> during <code>gnn.fit()</code></summary>

Runtime error in one of the GNN's exported tables — usually a multi-valued Relationship on a GNN-node concept tripping the engine's functional-dependency check. Pull the engine-side root cause:

```bash
snow sql -q "CALL RELATIONALAI.API.GET_TRANSACTION_ARTIFACTS('<txn_id>', OBJECT_CONSTRUCT())"
```

Then download the `problems.json` artifact. The most common fix is moving the offending multi-valued relationship to its own composite-id Concept (mirrors how `Compatibility(workload, gpu_pool)` and `WorkloadGpuCompat(workload, gpu_type)` are themselves Concepts, not Workload Relationships).
</details>

<details>
<summary>Solver returns <code>INFEASIBLE</code> for the global solve</summary>

Some cell's constraints are mutually unsatisfiable AND the C1 P0 commitment is a hard `==1`. C1 should be soft `<=1`; the `priority_weight=100` in the objective drives P0 to 1 wherever feasible. Per-cell infeasibility then surfaces as `INFEASIBLE` in the per-cell summary, not as global failure.
</details>

<details>
<summary>Solver returns <code>TIME_LIMIT</code> with sensible per-cell results</summary>

Expected at the default `time_limit_sec=120`. Per-cell numbers remain valid with `TIME_LIMIT` (`rai-prescriptive-results-interpretation`: `TIME_LIMIT` is signal, not error). Raise `time_limit_sec` or switch to a faster solver in `stage4_prescriptive` if you need a tighter MIP gap.
</details>

<details>
<summary>Per-cell summary shows all cells <code>INFEASIBLE</code></summary>

Likely an upstream constraint (C5 / C6 / C7) firing at unintended cells. Check that the `-1.0` NULL-handling sentinels are filtered correctly in C5 / C6 / C7's `model.where(... .fraction >= 0.0 ...)` clauses.
</details>

<details>
<summary>Per-workload utilization probabilities do not match the README's distribution</summary>

GNN trained with non-default seed/epochs, or `--no-gnn` fallback used. The fallback values in `workload_utilization_fallback.csv` are the deterministic reference (the latent probability used to generate the synthetic labels); these are what downstream stages consume when `--no-gnn` is set.
</details>

## What this template abstracts

This is a tutorial-grade allocator, not a production scheduler. Several real-world constraints are intentionally simplified:

- **Gang scheduling.** Production training requires all-or-nothing allocation across (e.g.) 256 GPUs with topology-aware placement. We model assignment as a single (Workload, GpuPool) binary; `interconnect` and `reservation_model` are informational, not constraints.
- **Time-block reservations.** Production training is reserved for hours-to-weeks; our snapshot allocation collapses all time into one period.
- **Elastic sizing.** Production schedulers (Pollux, Sia) adjust GPU count mid-training; our `gpu_count_required` is fixed.
- **Per-DC `dollars_per_mwh` is a scalar.** Real wholesale electricity prices vary intraday and seasonally; smart workload scheduling can arbitrage this. The snapshot omits this lever.
- **Anchor designation is binary.** Real concentration risk is a function of contract size and term, not just identity. The Boolean `is_strategic_anchor` is a tutorial simplification.
- **Pool fungibility is implicit.** Each `GpuPool` here serves whichever workload type the eligibility rule accepts; a richer model would distinguish dedicated pools (long-running training reservations, expensive to repurpose) from swing pools (can flex between training and inference daily) from scratch pools (best-effort, low SLA). Adding a `pool_fungibility_class` Property with a workload-type-switching cost in the objective is a natural extension — fungible pools are strategically more valuable than single-purpose pools of equal nameplate capacity.
- **Utilization probability is a point estimate.** `Workload.utilization_probability` is one number per workload — the GNN's predicted positive-class probability. A more discipline-honest model would carry per-workload (p10, p50, p90) bands and let the operator plan against the upper end of the band for anchors and the lower end for opportunistic seats. The 3D scenario sweep approximates this at the aggregate axis (uniform `DemandScenario` factor on P1/P2 revenue); per-workload range forecasts would compound the sweep size but capture per-workload uncertainty at the same fidelity.

## Learn more

- Upstream template: [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) — the multi-year capex / interconnect decision that approves which campuses get built and energized.
- Peer multi-reasoner: [telco_network_recovery](https://github.com/RelationalAI/templates/tree/main/v1/telco_network_recovery) — same accretive-chain pattern in a tower-upgrade context, using a binary-classification GNN + three-branch rule + PageRank + MIP.
- RelationalAI documentation: <https://docs.relational.ai>

## Support

- File issues at <https://github.com/RelationalAI/templates/issues>.
- Reach the RAI team via the support channels listed at <https://relational.ai>.
