---
title: "Datacenter Compute Allocation"
description: "Multi-reasoner template (chain follow-up to energy_grid_planning): heterogeneous-graph GNN demand forecasting, hardware-compatibility rules, dependency PageRank, and 3D-scenario MIP for inside-the-fence GPU allocation across hyperscaler campuses."
featured: false
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
  - Heterogeneous Graph
  - Multi-Objective
  - Pareto Frontier
  - AI Compute
  - Data Centers
  - Capacity Planning
---

# Datacenter Compute Allocation

This template is a follow-up to **[energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning)**. Where the upstream template decides which AI campuses get built and energized at what MW envelope (a multi-year capex / interconnect decision over ~50 binaries), this template zooms into the energized campus and decides which AI lab's individual training, fine-tune, inference, and eval workloads get which GPUs in which pool right now. The two share a single ontology — `DataCenterRequest` — and reason at very different scales.

## What this template is for

The 5 hyperscaler campuses approved by the upstream $300M solve — xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal — are now energized and stocked with GPU pools. The DC operator (a neocloud / colocation provider, or the hyperscaler operating its own campus) has to allocate that GPU capacity across the AI labs renting time on it. Frontier model labs want long-running training reservations on the largest contiguous H100 / H200 / GB200 pools at preferential anchor-customer rates. Inference customers want a steady slice of right-sized GPUs in low-latency regions. Research orgs want bursty best-effort capacity. They all compete for the same physical pools under the same power envelope.

The decision is **multi-objective and operationally pressing**. Every major hyperscaler now reports AI compute as a binding constraint on growth (Microsoft has disclosed an $80B Azure backlog blocked specifically by power constraints). The operator is accountable on three publicly-discussed dimensions:

1. **Power envelope.** Each campus has a substation-bound MW cap (the upstream-solved `approved_mw`). At 100% the cap is grid-approved; at 85% it is a heat-wave / curtailment day; at 110% it is contracted-curtailment headroom.
2. **Gross-margin discipline.** SemiAnalysis quantifies neocloud BMaaS at 55-65% gross margin pre-depreciation but only **14-16% net** after labor, power, and depreciation, so even a single MWh-cost mis-allocation is meaningful to the P&L.
3. **Anchor concentration.** CoreWeave's Q2 2025 10-Q discloses **71% of revenue from a single customer (Microsoft)** and an $11.9B OpenAI commitment booked through October 2030 — the canonical example of the concentration risk that caps equity value. Operators win anchors (because they underwrite debt-financed buildouts) AND dilute them (because investor-visible concentration risk caps equity value).

This template combines the upstream-inherited `PowerEnvelopeLevel` with two new Scenario Concepts — `MarginFloor` and `DiversityCap` — into a **3D scenario sweep (3 × 4 × 4 = 48 cells)** that traces two Pareto frontiers the operator already discusses publicly: margin-floor vs. achievable revenue, and diversity-cap vs. achievable revenue, with envelope as outer sensitivity. The strictest cells return `INFEASIBLE` — this is the intended diagnostic signal showing which constraint combinations cannot be satisfied simultaneously.

This template demonstrates a multi-reasoner workflow combining **predictive** (per-lab training-intensity GNN), **rules** (hardware compatibility + priority-tier classification), **graph** (downstream-gating score on the workload-dependency DAG), and **prescriptive** (assignment MIP under a 3D Scenario sweep) reasoning on a single shared ontology — each stage's output narrows or scores the next.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 0. Chain bind | **Query** | Upstream `DataCenterRequest.x_approve(InvestmentLevel)` and properties | New properties: `approved_mw`, `dollars_per_mwh` | Bind upstream-approved DCs and attach side-table `dollars_per_mwh` for the energy-cost calculation. Defines all new concepts (`GpuPool`, `AILab`, `Workload`, `WorkloadDependency`, scenario concepts). |
| 1. Predictive | **Heterogeneous-graph GNN** | `LabMetric` time series + four edge types: same-lab temporal, intra-lab `lab_workloads`, `WorkloadDependency.blocks` (shared with Stage 3), cross-lab `co_dated` (LOAD-BEARING) | `LabGrowth.multiplier` per lab; `Workload.projected_demand_growth` joined via lab | Forecast per-lab training intensity using cross-lab co-movement (industry GPU supply shocks, AI funding waves, model-release seasons). The cross-lab `co_dated` edge is what makes this a real GNN problem, not 6 disjoint univariate forecasts. |
| 2. Rules | **Rules** (declarative) | `Workload` requirements, `GpuPool` specs | `Workload.fails_memory`, `.passes_gpu_type`, `.is_eligible` Relationships; `Workload.priority_tier` and `.priority_weight` Properties; `Compatibility(workload, gpu_pool)` precompute | Classify which (Workload, GpuPool) pairs are technically eligible (memory + GPU-type allowlist). Assign priority tier P0/P1/P2 from `contract_tier`. The Compatibility precompute keeps the Stage 4 MIP linear. |
| 3. Graph | **Reverse-PageRank** | `Workload` nodes, `WorkloadDependency.blocks` edges | `Workload.gating_score` | Score how much downstream work each workload unblocks. A frontier pretrain that gates 14 fine-tunes and evals lands high; an isolated inference workload sits at baseline. |
| 4. Prescriptive | **MIP** (HiGHS) | `Compatibility`, `priority_weight`, `gating_score`, `projected_demand_growth`, `dollars_per_mwh`, `hourly_depreciation_rate`, `approved_mw`, `is_strategic_anchor`, the three Scenario Concepts | `Assignment.x_assign` per `(PowerEnvelopeLevel, MarginFloor, DiversityCap)`; `AllocationPlan` singleton; `Assignment.is_chosen` | Assign each workload to one (DC, GpuPool) under power, GPU-count, gross-margin-floor (energy + depreciation cost), and anchor / workload-type-diversity constraints. Maximizes a four-factor strategic value: priority × gating × growth × strategic_value_usd. 48-cell sweep; strictest cells return INFEASIBLE as designed signal. The headline cell (`100pct / unconstrained / none`) is persisted as the `AllocationPlan` singleton, and its decision rows are flagged via `Assignment.is_chosen` so the plan is queryable as ontology after the script exits. |

**Key design patterns demonstrated:**

- **Cross-template ontology extension.** The upstream `DataCenterRequest` concept is extended with new properties (`approved_mw`, `dollars_per_mwh`) via `model.define()` calls that join on the existing identifier. No upstream rewrites; downstream stages query the extended concept uniformly.
- **One ontology relationship, two reasoners.** `WorkloadDependency.blocks` carries information into both the Stage 1 GNN (as a heterogeneous edge) and the Stage 3 PageRank (as the dependency DAG). Defined once in the ontology, consumed without duplication or DataFrame round-trips.
- **Per-cell aggregates queried from the ontology.** Stage 4's per-cell summary table (revenue, energy + depreciation cost, anchor share, workload-type counts) comes from `sum(...).where(Assignment.x_assign(env, mar, div, x), x > 0.5).per(env, mar, div)` aggregate expressions assembled inside a single `model.select()` call — mirroring `energy_grid_planning`'s `rev_per_level` pattern. No pandas-side groupby of raw assignments.
- **Headline plan persisted as ontology.** After the 48-cell sweep, the chosen baseline cell (`100pct / unconstrained / none`) is written back as a singleton `AllocationPlan` Concept carrying revenue, total_cost, realized_margin, anchor_share, n_assigned, status, and binding_axis — plus an `Assignment.is_chosen` unary Relationship that flags the decision rows in that cell. The plan is queryable as ontology after the script exits, mirroring the `RestorePlan` / `is_selected_upgrade` pattern in `telco_network_recovery`.
- **Heterogeneous GNN, not time-series-on-rails.** Stage 1 connects `LabMetric` to `Workload`, to other `LabMetric` rows on the same date (when their labs share a workload_type), and reuses `WorkloadDependency` — in addition to same-lab temporal lags. Pure same-entity temporal-lag topology is a misuse of the GNN reasoner; the cross-concept edges are what give it lift.
- **Three-dimensional Scenario Concept design.** `PowerEnvelopeLevel` (outer capacity sensitivity), `MarginFloor` (primary Pareto axis), `DiversityCap` (primary Pareto axis). Decision variable `Assignment.x_assign` is indexed by all three; the Pareto frontier emerges from constraint relaxation across cells, not from a multi-objective solve.
- **Lex-emulating priority weights.** P0 workloads carry weight 100, P1 carry 10, P2 carry 1, plus a hard P0-must-be-assigned constraint. This mirrors how production cluster schedulers (Borg, Singularity, MAST) balance priority dominance with throughput optimization.
- **Four-factor MIP objective.** `priority_weight × gating_score × projected_demand_growth × strategic_value_usd` — one factor per upstream reasoner (Stage 2 / Stage 3 / Stage 1) plus the raw dollar baseline. Single-MIP, weighted-sum; the multi-objective Pareto emerges from constraint relaxation, not the objective.

## Who this is for

- DC operators (neocloud, colo, hyperscaler infra teams) allocating GPU capacity across multi-tenant pools
- Capacity planners deciding when a (margin floor, diversity cap, envelope) point justifies acquiring more megawatts
- Operations researchers exploring multi-reasoner pipelines that compose a heterogeneous GNN, graph centrality, declarative rules, and a scenario-parameterized MIP
- Developers extending RelationalAI templates across decision lineages (capacity planning → allocation → scheduling)

## What you'll build

- A 6-lab × 5-DC compute allocation MIP, indexed by a 3D Scenario Concept sweep (3 envelopes × 4 margin floors × 4 diversity caps = 48 cells)
- A heterogeneous-graph GNN for per-lab training-intensity forecasting (with a per-lab gradient-boosted-trees baseline available for the GNN-vs-tabular lift comparison)
- Reverse-PageRank scoring on a workload dependency DAG (4-5 deep chains rooted at frontier pretrains)
- Declarative hardware-compatibility rules + lex-emulating priority weights (P0=100, P1=10, P2=1)
- Two headline Pareto frontiers (margin × revenue and diversity × revenue) at the 100% envelope, with 85% / 110% drawn as overlay sensitivity bands
- Per-cell results queryable directly from the ontology — realized revenue, energy + depreciation cost, anchor share, per-workload-type counts, binding-constraint signal (OPTIMAL vs INFEASIBLE)

## What's included

- `datacenter_compute_allocation.py` — main script: chain bind + 4 reasoner stages + Pareto reporting + ontology persistence
- `data/data_centers.csv` — 5 DCs (snapshot of upstream $300M-approved set; standalone mode only)
- `data/data_center_attrs.csv` — 5 rows: `dc_id → dollars_per_mwh` (chain mode side table)
- `data/gpu_pools.csv` — 28 pools across 5 DCs (H100 / H200 / GB200 mix), with per-GPU `hourly_depreciation_rate` ($1.14 H100, $1.52 H200, $2.66 GB200; capex/3-year amortization)
- `data/ai_labs.csv` — 6 labs: 3 frontier anchors (Anthropic, OpenAI, xAI Internal) + 2 applied (Cohere Inference, Together AI Multi-Lab) + 1 research (Stability Open)
- `data/workloads.csv` — 110 workloads: 15 P0 pretrains (frontier labs, 256-1024 GPUs each, GB200/H200/H100 mix), 30 P1 finetune (Together AI + Cohere), 50 P1 inference (Cohere + Together), 15 P2 eval (Stability)
- `data/workload_gpu_compatibility.csv` — per-workload GPU-type allowlist
- `data/workload_dependencies.csv` — 138 edges (~130 blocks + ~10 informs), DAG depth 4-5 rooted at frontier pretrains
- `data/lab_metrics.csv` — 365 days × 6 labs = 2,190 rows with cross-lab co-movement
- `data/train_metrics.csv`, `val_metrics.csv`, `test_metrics.csv` — GNN train/val/test splits
- `data/lab_growth_forecasts.csv` — Stage 1 fallback (lab × multiplier)
- `data/power_envelope_levels.csv` — 3 scenario rows (0.85 / 1.00 / 1.10)
- `data/margin_floors.csv` — 4 scenario rows (unconstrained / 75% / 80% / 85% gross margin post-depreciation)
- `data/diversity_caps.csv` — 4 scenario rows (none / anchor_max_70pct / anchor_max_50pct CoreWeave-target / anchor_max_40pct_with_type_floor)
- `runbook.md` — analyst paste-test walkthrough mapping each stage to its RAI agent skill + prompt

## Prerequisites

### Access

- A Snowflake account with the RelationalAI native app installed.
- A Snowflake user with permissions on the RAI native app and on `EXP_DATABASE` (the schema for GNN experiment artifacts).
- A prescriptive engine for Stage 4 and (optionally) a GPU-backed predictive engine for Stage 1.
- For **chain mode** specifically: the upstream [`energy_grid_planning`](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) template must have been run first on the same account so `Model("Energy Grid Infrastructure")` is populated with `DataCenterRequest.x_approve(InvestmentLevel)`.

### Tools

- Python ≥ 3.10.
- RelationalAI Python SDK with the predictive submodule (`relationalai.semantics.reasoners.predictive`) for Stage 1's GNN. Without it, Stage 1 falls back to the precomputed `lab_growth_forecasts.csv` automatically.

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

5. Run the template in **standalone** mode (no upstream prerequisite — starts here if you have not yet run `energy_grid_planning`):

   ```bash
   python datacenter_compute_allocation.py --standalone
   ```

6. Or run in **chain mode** (default; assumes `energy_grid_planning` has populated `Model("Energy Grid Infrastructure")`):

   ```bash
   python datacenter_compute_allocation.py
   ```

7. Pick a different upstream investment level (chain mode only):

   ```bash
   python datacenter_compute_allocation.py --investment-level "\$400M"
   ```

   At $400M the upstream solve approves 6 DCs (one more than $300M); the downstream supply set grows accordingly without any code change.

8. Skip the GNN and load `lab_growth_forecasts.csv` directly (useful for fast iteration on Stages 2–4):

   ```bash
   python datacenter_compute_allocation.py --no-gnn
   ```

9. Expected output (abbreviated):

   ```text
   STAGE 0: STANDALONE LOAD
     Ontology loaded: 6 labs, 28 pools, 110 workloads, 138 dep edges, 3x4x4=48 scenario cells

   STAGE 1: PREDICT -- per-lab training-intensity GNN
     Per-lab projected demand multiplier (frontier should ramp 1.05+, Stability < 1.0):
       + OpenAI Pretrain           multiplier=1.1192
       + Anthropic Research        multiplier=1.1011
       + xAI Internal              multiplier=1.0816
       + Together AI Multi-Lab     multiplier=1.0395
       + Cohere Inference          multiplier=1.0306
       - Stability Open            multiplier=0.9680

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
     Termination status: TIME_LIMIT
     Per-cell summary (48 cells: 33 optimal, 15 infeasible):
       100pct unconstrained    none   OPTIMAL    110  25,277,810.94  4,190,130.34  0.83  0.95
       100pct          85pct   none   OPTIMAL     18  22,032,899.59  3,304,895.87  0.85  1.00
       ...

     AllocationPlan singleton (queryable as ontology):
       plan_id        envelope        margin     diversity  status   n_assigned   revenue_usd   total_cost_usd   realized_margin   anchor_share    binding_axis
       DCCA_BASELINE    100pct  unconstrained         none  OPTIMAL         110   25277810.94      4190130.34         0.834237          0.947251  power_envelope

     Assignment.is_chosen rows: 110 (matches n_assigned above)
   ```

   Exact GNN multipliers depend on the seed and the predictive engine run; the `--no-gnn` fallback values are deterministic.

   **Expected runtime** (full pipeline, standalone, real GNN):
   - Stage 1 (GNN training + prediction): ~90-120s on `GPU_NV_S` predictive engine
   - Stages 2-3 (rules + PageRank): a few seconds
   - Stage 4 (48-cell MIP): hits the 900s `time_limit_sec` and returns a feasible solution. Per-cell results remain valid; objective is within demo-acceptable gap (`rai-prescriptive-results-interpretation`: a non-OPTIMAL termination is signal, not failure).

   **Expected per-cell behavior:**
   - `(*, unconstrained / 75% / 80% margin, none diversity)`: full assignment of all 110 workloads, ~$25M revenue, 83% realized margin, 95% anchor share
   - `(*, 85% margin, none)`: tight floor binds — drops 89 lower-margin workloads, retains 14 of 15 frontier P0 pretrains, revenue $22M @ 85% margin / 100% anchor
   - `(*, *, anchor_max_70pct)`: anchor cap drops most P0 pretrains, $4-5M revenue @ ~70% anchor
   - `(*, *, anchor_max_50pct)`: CoreWeave-target cap, $2.6M @ 49% anchor (only 2 of 15 P0 pretrains fit)
   - `(*, *, anchor_max_40pct_with_type_floor)`: INFEASIBLE — too tight to satisfy with this lab roster
   - `(*, 85% margin, anchor_max_50pct)`: INFEASIBLE — high margin floor wants pretrain-only, but anchor cap forbids that mix

## Template structure

```text
datacenter_compute_allocation/
  datacenter_compute_allocation.py  # Main script (chain bind + 4 chained reasoning stages + ontology persistence)
  data/
    data_centers.csv                # 5 DCs (snapshot of upstream $300M-approved set; standalone mode)
    data_center_attrs.csv           # 5 rows of dollars_per_mwh (chain mode side table)
    gpu_pools.csv                   # 28 GPU pools across 5 DCs (H100/H200/GB200 mix)
    ai_labs.csv                     # 6 labs (3 frontier, 2 applied, 1 research)
    workloads.csv                   # 110 workloads (15 P0 / 80 P1 / 15 P2)
    workload_gpu_compatibility.csv  # Per-workload GPU-type allowlist
    workload_dependencies.csv       # 138 directed edges in the dependency DAG
    lab_metrics.csv                 # 2,190 = 365 days × 6 labs daily KPIs
    train_metrics.csv               # GNN training split
    val_metrics.csv                 # GNN validation split
    test_metrics.csv                # GNN test split
    lab_growth_forecasts.csv        # Stage 1 fallback (deterministic per-lab multipliers)
    power_envelope_levels.csv       # 3 scenario rows (envelope multiplier)
    margin_floors.csv               # 4 scenario rows (gross margin floors)
    diversity_caps.csv              # 4 scenario rows (anchor concentration caps)
  README.md                         # this file
  runbook.md                        # multi-reasoner agent-skill walkthrough
  pyproject.toml                    # dependencies
```

## How it works

### Stage 1: Predictive — heterogeneous-graph GNN for per-lab demand

The GNN learns a per-`LabMetric` regression on `training_intensity_growth_rate` over a heterogeneous graph that connects three concepts via four edge types:

```python
gnn_graph = Graph(model, directed=False, weighted=False)

# Edge 1: LabMetric -> Workload owned by the same lab.
model.define(gnn_graph.Edge.new(src=LabMetric, dst=Workload)).where(
    LabMetric.lab == Workload.lab.name,
)

# Edge 2: WorkloadDependency.blocks DAG (shared with Stage 3).
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

The cross-lab `co_dated` edge carries the industry-wide co-movement signal — when frontier labs collectively ramp on a given workload_type, applied labs on the same type follow on the same date. This is the cross-concept signal a heterogeneous GNN is designed to propagate.

Per-`LabMetric` test predictions are averaged per lab to produce `LabGrowth.multiplier = 1.0 + mean_predicted_growth`, then joined onto each `Workload` via lab as `Workload.projected_demand_growth` — the multiplier that enters Stage 4's objective.

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
        * Assignment.workload.projected_demand_growth  # Stage 1 (predictive)
        * Assignment.workload.strategic_value_usd)   # raw $ baseline
    .where(Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap, x_obj))
)
```

After the solve, the per-cell summary table is assembled inside a single `model.select(...)` — `sum(...).where(Assignment.x_assign(env, mar, div, x), x > 0.5).per(env, mar, div)` aggregates run on the ontology, no pandas-side groupby. The chosen baseline cell (`100pct / unconstrained / none`) is persisted as a singleton `AllocationPlan` Concept with revenue / total_cost / margin / anchor_share / n_assigned / status / binding_axis, plus an `Assignment.is_chosen` unary Relationship over its decision rows — mirroring the `RestorePlan` / `is_selected_upgrade` pattern from `telco_network_recovery`.

## Customize this template

- **Add or remove DCs** by editing `data_centers.csv` (standalone) or running `energy_grid_planning` at a different `InvestmentLevel` (chain).
- **Adjust the lab roster** in `ai_labs.csv`. Anchor flag drives the `DiversityCap` constraint.
- **Tune scenario axes**: edit `power_envelope_levels.csv`, `margin_floors.csv`, `diversity_caps.csv`. Adding rows scales the cell count multiplicatively.
- **Change the priority spread** by editing the weights in `stage2_rules` (default 100 / 10 / 1).
- **Replace the GNN with a tabular baseline** by setting `--no-gnn` and editing `lab_growth_forecasts.csv` directly.
- **Use a different solver** by changing `problem.solve("highs", ...)` to `"gurobi"` if any single cell consistently exceeds 60s.
- **Validate the GNN lift over a tabular baseline** by training a per-lab `GradientBoostingRegressor` on the same lag features (`prev_day_growth`, `prev_week_growth`, `growth_7d_mean`, etc.) from `data/train_metrics.csv` and comparing per-lab test RMSE. The GNN should beat the baseline by the margin attributable to the cross-lab `co_dated` edges (the only cross-lab signal source).

## Troubleshooting

<details>
<summary><code>RuntimeError: no DataCenterRequest entries with x_approve > 0.5</code></summary>

Chain mode but the upstream `energy_grid_planning` template has not run on this account/engine. Run the upstream first, or use `--standalone`.
</details>

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

Expected for the 48-cell sweep. The solver hit the 900s wall but returned a feasible solution; per-cell numbers remain valid (`rai-prescriptive-results-interpretation`: `TIME_LIMIT` is signal, not error). Increase `time_limit_sec` in `stage4_prescriptive` if you need a tighter MIP gap.
</details>

<details>
<summary>Per-cell summary shows all cells <code>INFEASIBLE</code></summary>

Likely an upstream constraint (C5 / C6 / C7) firing at unintended cells. Check that the `-1.0` NULL-handling sentinels are filtered correctly in C5 / C6 / C7's `model.where(... .fraction >= 0.0 ...)` clauses.
</details>

<details>
<summary>Per-lab multiplier numbers do not match the README's expected ramp</summary>

GNN trained with non-default seed/epochs, or `--no-gnn` fallback used. The fallback values in `lab_growth_forecasts.csv` are the deterministic reference; these are what downstream stages consume when `--no-gnn` is set.
</details>

## What this template abstracts

This is a tutorial-grade allocator, not a production scheduler. Several real-world constraints are intentionally simplified:

- **Gang scheduling.** Production training requires all-or-nothing allocation across (e.g.) 256 GPUs with topology-aware placement. We model assignment as a single (Workload, GpuPool) binary; `interconnect` and `reservation_model` are informational, not constraints.
- **Time-block reservations.** Production training is reserved for hours-to-weeks; our snapshot allocation collapses all time into one period.
- **Elastic sizing.** Production schedulers (Pollux, Sia) adjust GPU count mid-training; our `gpu_count_required` is fixed.
- **Per-DC `dollars_per_mwh` is a scalar.** Real wholesale electricity prices vary intraday and seasonally; smart workload scheduling can arbitrage this. The snapshot omits this lever.
- **Anchor designation is binary.** Real concentration risk is a function of contract size and term, not just identity. The Boolean `is_strategic_anchor` is a tutorial simplification.

## Learn more

- Upstream template: [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) — the multi-year capex / interconnect decision that approves which campuses get built and energized.
- Peer multi-reasoner: [telco_network_recovery](https://github.com/RelationalAI/templates/tree/main/v1/telco_network_recovery) — same accretive-chain pattern in a tower-upgrade context, using a binary-classification GNN + three-branch rule + PageRank + MIP.
- RelationalAI documentation: <https://docs.relational.ai>

## Support

- File issues at <https://github.com/RelationalAI/templates/issues>.
- Reach the RAI team via the support channels listed at <https://relational.ai>.
