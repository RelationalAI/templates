# Runbook: Datacenter Compute Allocation — Multi-Reasoner Walkthrough

A neocloud operator has 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses (a snapshot of the campus set the upstream `energy_grid_planning` $300M solve approved). The chain forecasts per-lab demand, screens hardware compatibility, weights workloads by downstream gating, and produces a 48-cell scenario sweep — no single reasoner can answer this end-to-end.

## The chain

```
The 48-cell sweep (3 envelopes × 4 margin floors × 4 diversity caps)
traces two Pareto frontiers — margin × revenue and diversity × revenue.
The headline baseline cell (100pct / unconstrained / none) is persisted
as ontology so the plan survives the chain run.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  LabGrowth.multiplier            (6 labs)
                 (GNN)       OpenAI 1.12, Anthropic 1.10, xAI 1.08,
                             Together 1.04, Cohere 1.03, Stability 0.97.
                             Frontier ramps, research org contracts.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Compatibility(workload, gpu_pool) (~1,900)
                             Workload.priority_tier            (110)
                             P0 = 15, P1 = 80, P2 = 15 (weights 100/10/1).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Workload.gating_score             (110)
                 (downstream- Frontier pretrain shards (GPT/Grok/Claude-Next)
                  reach)      top the score, gating 4–5-deep chains.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Prescriptive ──►  Assignment.x_assign(env, mar, div)
                 (MIP)       48 cells: 33 OPTIMAL, 15 INFEASIBLE.
                             Baseline (100pct / unconstrained / none):
                             110 assigned · $25.3M revenue · 83% margin
                             · 95% anchor · binding axis: power envelope.
                             Persisted as AllocationPlan singleton +
                             Assignment.is_chosen (110 rows).
  ─────────────────────────────────────────────────────────────────
```

Prompts below are designed to run in order in a single session so each step inherits the ontology state from the previous step.

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a datacenter compute allocation ontology from the CSVs in data/. workload_dependencies is an edge concept (source/target workload). lab_metrics is keyed by (lab, date). The three scenario CSVs (power_envelope_levels, margin_floors, diversity_caps) each map to a Scenario Concept identified by name.
```

**Response**

Concepts: `DataCenterRequest`, `GpuPool`, `AILab`, `Workload`, `WorkloadDependency`, `WorkloadGpuCompat`, `LabMetric`, `LabGrowth`, and three Scenario Concepts (`PowerEnvelopeLevel`, `MarginFloor`, `DiversityCap`) — bound to the bundled CSVs (5 DCs, 28 GPU pools, 6 labs, 110 workloads, 138 dependency edges).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows in each, and what date range does the lab metrics history cover?
```

**Response**

12 concepts: 5 `DataCenterRequest` (xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal), 28 `GpuPool`, 6 `AILab`, 110 `Workload`, 138 `WorkloadDependency`, 2,190 `LabMetric` covering 365 days × 6 labs, plus 3 / 4 / 4 rows on the three Scenario Concepts (3 × 4 × 4 = 48 cells).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses. The operator is accountable on three axes — power envelope per campus, gross margin after energy and depreciation, and anchor concentration (CoreWeave-style single-customer risk). Which reasoners, in what order, produce a defensible compute allocation?
```

**Response**

Plan routes sub-questions to predictive (per-lab demand forecast), rules (hardware eligibility + priority tier), graph (downstream gating), and prescriptive (assignment MIP under a 3D scenario sweep with interpretation).

### 4. Scope demand

**Prompt**

```
/rai-querying How is workload demand distributed across labs, workload types, and contract tiers, and which labs dominate GPU-hour pressure (sum of gpu_count_required × duration_hours)?
```

**Response**

Frontier labs (Anthropic Research, OpenAI Pretrain, xAI Internal) carry the 15 P0 pretrains (256–1,024 GPUs each, GB200/H200/H100 mix). Applied labs (Cohere Inference, Together AI Multi-Lab) carry the 30 P1 fine-tunes + 50 P1 inference workloads. Stability Open carries the 15 P2 evals. Pretrain GPU-hour demand dwarfs inference even at a 50:15 workload-count ratio.

### 5. Forecast per-lab demand

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training What's each lab's next-period training-intensity multiplier, given the daily KPI history? The signal that matters most isn't each lab's own time series — it's cross-lab co-movement: when frontier labs collectively ramp, applied labs follow. Train on a heterogeneous graph that connects lab-metric rows on the same date when their labs share a workload_type, and bind the per-lab forecast back to the ontology as LabGrowth.multiplier so the optimizer can read it.
```

**Response**

`LabGrowth.multiplier` for all 6 labs: OpenAI ≈1.12, Anthropic ≈1.10, xAI ≈1.08, Together ≈1.04, Cohere ≈1.03, Stability ≈0.97. Frontier labs ramp 5–12%; the research org contracts slightly. The cross-lab `co_dated` edges are the load-bearing signal — a per-lab tabular baseline sits at higher RMSE because it can't see industry-wide co-movement.

### 6. Screen hardware compatibility and priority

**Prompt**

```
/rai-rules-authoring Which (workload, GPU pool) pairs are technically eligible? A pair qualifies when (1) the pool's per-GPU memory meets the workload's mem_required_gb and (2) the pool's gpu_type is in the workload's allowlist. Also classify each workload's priority tier from its lab's contract_tier — frontier-anchor → P0 (weight 100), committed → P1 (10), on-demand → P2 (1) — and write the tier and numeric weight back.
```

**Response**

`Compatibility(workload, gpu_pool)` precompute holds 1,918 eligible pairs; `Workload.priority_tier` distribution is P0 = 15 / P1 = 80 / P2 = 15 with weights 100 / 10 / 1. The numeric weights emulate lex-priority inside a single weighted-sum MIP, matching production cluster schedulers (Borg, Singularity, MAST).

### 7. Score downstream gating

**Prompt**

```
/rai-graph-analysis Which workloads gate the most downstream work — workloads where, if they slip, many later workloads slip too, and those gate even more? Score every workload by that downstream-reach metric on the WorkloadDependency.blocks DAG and bind it as Workload.gating_score.
```

**Response**

Frontier pretrain shards top the score: GPT-Next pretrain shard 02 ≈ 0.031, Grok-Next pretrain shard 04 ≈ 0.027, Claude-Next pretrain shard 02 ≈ 0.023 — they root 4–5-deep dependency chains. Isolated inference workloads sit at the baseline ≈ 1 / 110.

### 8. Allocate GPU capacity under the 3D scenario sweep

**Prompt**

```
/rai-prescriptive-problem-formulation Which workloads should be assigned to which (DC, GPU pool) under three scenario axes — power envelope (85% / 100% / 110% of approved_mw), gross-margin floor (unconstrained / 75% / 80% / 85%), and anchor-concentration cap (none / 70% / 50% / 40% with workload-type floor) — solved as one MIP indexed by all three? Stay within per-pool GPU capacity and per-DC power. Maximize Σ priority_weight × gating_score × projected_demand_growth × strategic_value_usd. Per-cell INFEASIBLE is diagnostic — the global solve should not fail when one cell binds too tight.
```

**Response**

HiGHS solves 48 cells in one pass: 33 OPTIMAL + 15 INFEASIBLE (at `time_limit_sec = 900` returns a feasible-but-not-proven-optimal solution; `TIME_LIMIT` is signal, not error). Baseline cell (100pct / unconstrained / none): 110 workloads, $25.28M revenue, 83% realized margin, 95% anchor share. The strictest cells (`anchor_max_40pct_with_type_floor` at any envelope; `anchor_max_50pct` paired with the 85% margin floor) return INFEASIBLE because the type-floor and anchor-cap combination forbids the pretrain volume that supplies the margin.

### 9. Read the frontiers

**Prompt**

```
/rai-prescriptive-results-interpretation What's the headline plan for the unconstrained baseline cell — revenue, total cost, realized margin, anchor share, n_assigned, and which axis would bind first if we tightened it? Where do the two Pareto frontiers (margin × revenue, diversity × revenue) cliff, and what does each cliff cost?
```

**Response**

Baseline cell: 110 workloads, $25.28M revenue, $4.19M total cost, 83% margin, 95% anchor, binding axis is the power envelope (no margin or diversity constraint active here). Margin frontier: revenue holds at $25.3M at 75% / 80% floors but cliffs to $22.0M at 85% (89 workloads dropped, 100% anchor). Diversity frontier: $25.3M with no cap → $4.4M at 70% → $2.6M at 50% (CoreWeave-target shape) → INFEASIBLE at 40% with type-floor.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Add an AllocationPlan singleton holding the baseline-cell summary (chosen envelope/margin/diversity, revenue_usd, total_cost_usd, realized_margin, anchor_share, n_assigned, status, binding_axis) and an Assignment.is_chosen unary Relationship narrowing Assignment to the decision rows in the chosen cell.
```

**Response**

Ontology gains a singleton `AllocationPlan` (id = `DCCA_BASELINE`) with revenue ≈ $25.28M, total cost ≈ $4.19M, margin ≈ 0.83, anchor share ≈ 0.95, n_assigned = 110, status = `OPTIMAL`, binding_axis = `power_envelope`; plus `Assignment.is_chosen` (110 rows). Headline plan is queryable as ontology rather than stdout — mirrors the `RestorePlan` / `is_selected_upgrade` pattern in `telco_network_recovery` and the `InvestmentPortfolio` pattern in `energy_grid_planning`.

## Data

Bundled CSVs in `data/`: 5 data centers, 28 GPU pools, 6 AI labs, 110 workloads (15 P0 pretrain / 30 P1 finetune / 50 P1 inference / 15 P2 eval), 138 workload dependencies, 2,190 lab-metric rows (365 days × 6 labs) split into train/val/test, plus 3 / 4 / 4 scenario rows. Full chain implemented in `datacenter_compute_allocation.py`.
