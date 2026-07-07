---
title: "Datacenter Compute Allocation"
description: "Allocate GPU capacity across hyperscaler campuses using a graph neural network (GNN) that predicts per-workload utilization, hardware-compatibility rules, dependency PageRank, and a 24-cell scenario mixed-integer program (MIP). Picks up where energy_grid_planning leaves off."
featured: false
private: false
experience_level: advanced
industry: "Technology & Telecom"
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

## What this template is for

A datacenter operator — a neocloud, a colocation provider, or a hyperscaler running its own campuses — has energized GPU pools across several sites and must decide which AI lab's workloads get which GPUs in which pool right now. Frontier labs want long-running training reservations on the largest contiguous pools at anchor-customer rates; inference customers want a steady slice of right-sized GPUs; research orgs want bursty best-effort capacity. They all compete for the same physical pools under the same power envelope, and the operator has to keep three tensions in balance at once: staying under each campus's substation-bound power cap, holding gross margin after energy and depreciation, and serving anchor customers without letting any one customer's share grow into a concentration risk. Getting the allocation wrong strands expensive capacity — depreciation accruing on GPUs that sit idle — which is the operator's biggest economic exposure.

This template models that allocation as a scenario sweep across three axes (power envelope, margin floor, and anchor-diversity cap, for 24 combinations in all), tracing the trade-off frontiers the operator actually reasons about: how much revenue a tighter margin floor costs, and how much a tighter anchor cap costs. The strictest combinations come back infeasible, which is itself the answer — a signal that those constraints cannot all be met at once. A follow-on demand overlay then replays the chosen plan under softening-demand scenarios so the operator can see stranded-capacity exposure before committing. It picks up where the [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) template leaves off: that upstream template decides which campuses get built and energized, and the bundled `data_centers.csv` here is a snapshot of its approved campus set.

**The reasoning approach chains four reasoners on one shared ontology — a graph neural network (GNN) predicting per-workload utilization, declarative hardware-compatibility and priority rules, dependency-graph PageRank scoring how much downstream work each workload unblocks, and a scenario-parameterized mixed-integer program (MIP) that makes the assignment — with each stage writing signals the next stage reads.**

## Who this is for

- DC operators (neocloud, colo, hyperscaler infra teams) allocating GPU capacity across multi-tenant pools
- Capacity planners deciding when a (margin floor, diversity cap, envelope) point justifies acquiring more megawatts
- Operations researchers exploring multi-reasoner pipelines that compose a heterogeneous GNN, graph centrality, declarative rules, and a scenario-parameterized MIP
- Developers extending RelationalAI templates across decision lineages (capacity planning → allocation → scheduling)

## What you'll build

- A 6-lab × 5-DC compute allocation MIP, indexed by a 3-axis Scenario Concept sweep (2 envelopes × 3 margin floors × 4 diversity caps = 24 cells)
- A heterogeneous-graph GNN that **classifies per-workload utilization probability** (will this workload actually use its allocated capacity?) — the operator's real forward-looking signal, propagated through lab→workload, dep-DAG, and cross-lab co_dated edges
- Reverse-PageRank scoring on a workload dependency DAG (4-5 deep chains rooted at frontier pretrains)
- Declarative hardware-compatibility rules + lex-emulating priority weights (P0=100, P1=10, P2=1)
- Two headline Pareto frontiers (margin × revenue and diversity × revenue) at the 100% envelope, with the 85% envelope drawn as an overlay sensitivity band
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
- `data/power_envelope_levels.csv` — 2 scenario rows (0.85 / 1.00)
- `data/margin_floors.csv` — 3 scenario rows (unconstrained / 80% / 85% gross margin post-depreciation)
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
   STAGE 4: PRESCRIPTIVE -- compute allocation MIP (24-cell sweep)
     Termination status: OPTIMAL
     Per-cell summary (24 cells: 16 optimal, 8 infeasible)
     AllocationPlan singleton (100pct / unconstrained / none):
       110 workloads assigned, $25.28M revenue, 83% margin, 95% anchor share
   ```

   Full stage-by-stage log (GNN distribution, PageRank scores, both Pareto frontiers, the demand-scenario overlay, and expected per-cell behavior) is in `runbook.md`. GNN probabilities depend on seed and predictive engine; the `--no-gnn` fallback values are deterministic. Stage 4 reaches `OPTIMAL` in seconds with Gurobi; the open-source HiGHS default returns a feasible solution at the `time_limit_sec=240` wall and may surface `TIME_LIMIT` (signal, not failure, per `rai-prescriptive-results`). Set `SOLVER` in `datacenter_compute_allocation.py` to switch.

## Template structure

```text
datacenter_compute_allocation/
  datacenter_compute_allocation.py  # Main script (4 chained reasoning stages + ontology persistence)
  data/
    data_centers.csv                # 5 DCs (snapshot of upstream $300M-approved set)
    gpu_pools.csv                   # 28 GPU pools across 5 DCs (H100/H200/GB200 mix)
    ai_labs.csv                     # 6 labs (3 frontier, 2 applied, 1 research)
    workloads.csv                   # 110 workloads (15 P0 / 80 P1 / 15 P2)
    workload_gpu_compatibility.csv  # Per-workload GPU-type allowlist
    workload_dependencies.csv       # 138 directed edges in the dependency DAG
    lab_metrics.csv                 # 2,190 = 365 days × 6 labs daily KPIs
    workload_utilization_train.csv  # GNN train split: 7 historical months × 110 = 770 obs
    workload_utilization_val.csv    # GNN val split: 1 month × 110 = 110 obs
    workload_utilization_test.csv   # GNN test: current period × 110, no label
    workload_utilization_fallback.csv  # Stage 1 fallback (GNN-shape per-workload p)
    power_envelope_levels.csv       # 2 scenario rows (envelope multiplier)
    margin_floors.csv               # 3 scenario rows (gross margin floors)
    diversity_caps.csv              # 4 scenario rows (anchor concentration caps)
  README.md                         # this file
  runbook.md                        # multi-reasoner agent-skill walkthrough
  pyproject.toml                    # dependencies
```

**Start here**: run `python datacenter_compute_allocation.py` for the full four-stage chain end to end (add `--no-gnn` to skip Stage 1's GNN and load the deterministic fallback), or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is synthetic and illustrative — designed to teach the four-stage reasoning flow on a Snowflake-connected RAI account, not to match a specific operator's fleet. The five campuses, six labs, GPU generations, and workload mix are shaped so every stage does visible work and the Pareto frontiers and infeasible cells show up as intended.

- **`data_centers.csv`** (5 rows) — campuses (snapshot of the upstream $300M-approved set), each with an approved power cap, PUE, and energy cost.
- **`gpu_pools.csv`** (28 rows) — GPU pools across the 5 campuses (H100 / H200 / GB200 mix), each with a per-GPU hourly depreciation rate.
- **`ai_labs.csv`** (6 rows) — labs: 3 frontier anchors, 2 applied, 1 research, each with a contract tier and anchor flag.
- **`workloads.csv`** (110 rows) — training, fine-tune, inference, and eval workloads with GPU and memory requirements and a strategic dollar value.
- **`workload_gpu_compatibility.csv`** — the per-workload GPU-type allowlist (multi-valued, so it lives as its own concept).
- **`workload_dependencies.csv`** (138 rows) — directed dependency edges (`blocks` / `informs`), DAG depth 4-5 rooted at frontier pretrains.
- **`lab_metrics.csv`** (2,190 rows) — 365 days x 6 labs of daily lab-activity KPIs with cross-lab co-movement, the GNN's temporal feature source.
- **`workload_utilization_train.csv` / `_val.csv` / `_test.csv`** — the GNN's temporal binary-classification splits (7 historical months / 1 validation month / current period, no label).
- **`workload_utilization_fallback.csv`** — the deterministic Stage 1 fallback used when `--no-gnn` is set.
- **`power_envelope_levels.csv` / `margin_floors.csv` / `diversity_caps.csv`** — the three scenario-axis tables (2 / 3 / 4 rows) that index the 24-cell sweep.

## Model overview

One shared ontology threads all four stages: each stage reads concepts and properties earlier stages wrote and writes new ones for downstream stages.

- **Key entities**: `DataCenterRequest` (a campus), `GpuPool`, `AILab`, `Workload`, `WorkloadGpuCompat` and `WorkloadDependency` (workload relationships as their own concepts), the three scenario concepts `PowerEnvelopeLevel` / `MarginFloor` / `DiversityCap`, plus the derived `Compatibility` and `Assignment` (decision space), the `AllocationPlan` singleton, and the `DemandScenario` overlay.
- **Primary identifiers**: string ids on `DataCenterRequest`, `GpuPool`, `AILab`, and `Workload`; the scenario concepts are identified by `name`; `WorkloadGpuCompat`, `WorkloadDependency`, `Compatibility`, and `Assignment` carry composite keys.
- **Important invariants**: `envelope_multiplier`, `fraction`, and `anchor_max_share` are fractions; a negative sentinel on `MarginFloor.fraction` / `DiversityCap.anchor_max_share` marks the unconstrained row (its constraint is skipped); the `is_high_utilization` label is binary; `Assignment.x_assign` decision variables are binary; power / cost / GPU counts are non-negative.

For the full concept and property definitions — the entity concepts, the three scenario concepts, and the derived `Compatibility` / `Assignment` / `AllocationPlan` / `DemandScenario` concepts each stage writes — see `datacenter_compute_allocation.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

### Stage 1: Predictive — per-workload utilization-probability GNN

Binary node classification on `Workload`: predict the probability that each workload will be high-utilization (actually use its allocated capacity at high duty cycle) vs stall or be repaced. Stranded capacity (depreciation accruing without offsetting revenue) is the operator's biggest economic exposure, so this is the chain's load-bearing forward-looking signal.

The graph is heterogeneous with three cross-concept edge types: a `LabMetric → Workload` edge that carries lab-side recent activity into a workload's prediction neighborhood (a workload owned by a fast-ramping lab inherits its signal); the `WorkloadDependency.blocks` DAG shared with Stage 3, so a workload downstream of a high-utilization gating pretrain inherits signal through the dependency chain; and a load-bearing `LabMetric → LabMetric` edge between cross-lab same-date pairs sharing a workload type, which carries cross-lab co-movement (funding waves, supply shocks).

The task tables carry per-`(workload, observation_date)` historical labels. Each row is one monthly utilization observation, so the same workload appears in 7 training rows (one per historical month), giving the GNN per-period variety to learn from instead of a single label per entity — Train (7 months × 110 = 770) / Val (1 month × 110 = 110) / Test (current month × 110, no label, so every workload gets a probability for the upcoming period). The task relationships use `at` time slots and the GNN runs with `has_time_column=True` so LabMetric features are time-aligned with each (workload, month) prediction. The positive-class probability is bound back to the ontology as `Workload.utilization_probability` and consumed by Stage 4's objective.

### Stage 2: Rules — eligibility + priority tiers + Compatibility precompute

Two rule families run on the workload-pool product. The eligibility rule joins through the `WorkloadGpuCompat(workload, gpu_type)` composite-key concept (per the GNN-node FD trap: multi-valued allowlists on a GNN-node concept must live as their own concept, not as a Workload Relationship) and enforces both the memory check and the GPU-type allowlist. Eligible pairs are then materialized into a `Compatibility(workload, gpu_pool)` concept — a precompute that keeps the Stage 4 MIP linear and small. Priority tier classification reads `AILab.contract_tier` and writes both `Workload.priority_tier` (string) and `Workload.priority_weight` (100 / 10 / 1) — the numeric form is what Stage 4's objective consumes.

### Stage 3: Graph — reverse-PageRank for downstream gating

A directed `Workload` graph is built with edge reversal (successor → predecessor) so a node's PageRank accumulates flow from everything it gates downstream. The resulting score lands on `Workload.gating_score`. Workloads absent from the DAG get a backstop `gating_score = 1.0` so they enter the Stage 4 objective product without zeroing out.

### Stage 4: Prescriptive — assignment MIP under a 3D Scenario sweep

The decision variable `Assignment.x_assign` is a binary variable indexed by the three scenario concepts (`PowerEnvelopeLevel`, `MarginFloor`, `DiversityCap`), so the MIP solves all 24 cells in a single pass. Constraint families run one per scenario axis:

- **C1+C2** at-most-one per workload per cell (soft P0; priority_weight = 100 drives P0 from the objective).
- **C3** per-pool GPU-count capacity.
- **C4** per-DC power envelope: `Σ gpu_count × power_per_gpu × pue ≤ approved_mw × 1000 × envelope_multiplier`.
- **C5** linearized gross-margin floor (skipped when `MarginFloor.fraction < 0` for the unconstrained row).
- **C6** anchor-concentration cap (skipped when `DiversityCap.anchor_max_share < 0`).
- **C7** workload-type floor (skipped unless `DiversityCap.workload_type_floor >= 0`).

The objective is what makes this a real chain rather than four disjoint reasoners: it maximizes the sum over chosen assignments of `priority_weight` (Stage 2) × `gating_score` (Stage 3) × `utilization_probability` (Stage 1) × `strategic_value_usd` (raw $ baseline) — every prior stage's signal enters the same product. After the solve, the per-cell summary is assembled with ontology-side aggregation (no pandas groupby). The chosen baseline cell (`100pct / unconstrained / none`) is persisted as a singleton `AllocationPlan` concept with revenue / total_cost / margin / anchor_share / n_assigned / status / binding_axis, plus an `Assignment.is_chosen` flag over its decision rows.

Finally, a `DemandScenario` overlay replays the locked-in plan under four risk scenarios. Anchor (P0) revenue is treated as contractual (factor 1.0) — the operator gets paid for the seat regardless of utilization — while opportunistic (P1/P2) seats realize only the scenario factor of their assigned revenue. The overlay reports realized and stranded revenue per scenario and persists each as a `DemandScenarioOutlook(scenario)` concept row, so the stranded-capacity exposure of the chosen plan is queryable as ontology, not just printed.

See `datacenter_compute_allocation.py` for the implementation and `runbook.md` to reproduce each stage step by step with the RAI skills.

## Customize this template

### Use your own data

- Add or remove campuses by editing `data_centers.csv`. The bundled set is a snapshot of the upstream $300M-approved campuses; re-running `energy_grid_planning` at a different `InvestmentLevel` produces a different approved set you can copy in.
- Adjust the lab roster in `ai_labs.csv`. The anchor flag drives the `DiversityCap` constraint.
- Replace the GNN with the deterministic fallback by setting `--no-gnn` and editing `workload_utilization_fallback.csv` directly.

### Tune parameters

- Tune the scenario axes: edit `power_envelope_levels.csv`, `margin_floors.csv`, and `diversity_caps.csv`. Adding rows scales the cell count multiplicatively.
- Change the priority spread by editing the weights in the `# Stage 2: Rules` section (default 100 / 10 / 1).

### Extend the model

- Add a fourth GNN edge type, a new dependency relation, or extra scenario axes; the accretive-ontology pattern means downstream stages pick up new signals without restructuring.

### Scale up / productionize

- Tune the Stage 4 solve by adjusting the solver name or `time_limit_sec` in `problem.solve(...)`. The default works on any prescriptive engine; faster commercial solvers (when licensed) can reach OPTIMAL in a fraction of the time.
- Replace the bundled CSVs with CDC ingestion from the operator's inventory, telemetry, and contract systems; the ontology shape is independent of the load pipeline.

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

Expected at the default `time_limit_sec=240`. Per-cell numbers remain valid with `TIME_LIMIT` (`rai-prescriptive-results`: `TIME_LIMIT` is signal, not error). Raise `time_limit_sec` or switch to a faster solver in the `# Stage 4: Prescriptive` section if you need a tighter MIP gap.
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

This is a snapshot allocator, not a production scheduler. Workloads are assigned to a single `(Workload, GpuPool)` slot — gang scheduling, topology-aware placement, time-block reservations, and elastic sizing are out of scope. Utilization is modeled as a per-workload point estimate; per-workload (p10, p50, p90) bands would be a natural extension, with the scenario sweep providing the aggregate-level approximation today.

## Learn more

- Upstream template: [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) — the multi-year capex / interconnect decision that approves which campuses get built and energized.
- Peer multi-reasoner: [telco_network_recovery](https://github.com/RelationalAI/templates/tree/main/v1/telco_network_recovery) — same accretive-chain pattern in a tower-upgrade context, using a binary-classification GNN + three-branch rule + PageRank + MIP.
- RelationalAI documentation: <https://docs.relational.ai>

## Support

- File issues at <https://github.com/RelationalAI/templates/issues>.
- Reach the RAI team via the support channels listed at <https://relational.ai>.
