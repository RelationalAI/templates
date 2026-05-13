# Runbook: Datacenter Compute Allocation — Multi-Reasoner Walkthrough

A neocloud operator has 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses (a snapshot of the campus set the upstream `energy_grid_planning` $300M solve approved). The chain predicts per-workload utilization probability, screens hardware compatibility, weights workloads by downstream gating, and produces a 48-cell scenario sweep — no single reasoner can answer this end-to-end.

## The chain

```
The 48-cell sweep (3 envelopes × 4 margin floors × 4 diversity caps)
traces two Pareto frontiers — margin × revenue and diversity × revenue.
The headline baseline cell (100pct / unconstrained / none) is persisted
as ontology so the plan survives the chain run.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  Workload.utilization_probability  (110)
                 (GNN,        Binary classification: probability each workload
                  classify)   actually uses its allocated capacity at high
                              duty cycle. Frontier pretrains land 0.85+;
                              isolated Stability evals 0.20-0.35.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Compatibility(workload, gpu_pool) (~1,900)
                             Workload.priority_tier            (110)
                             Workload.under_provisioning_penalty
                             P0 = 15 (wt 100, pen 1.0), P1 = 80 (10, 0.3),
                             P2 = 15 (1, 0.0). Asymmetric failure pricing.
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
                             Assignment.is_chosen (110 rows) +
                             DemandScenarioOutlook (4 risk scenarios:
                             expected / diffusion_slowdown / scaling_break
                             / frontier_loss with realized + stranded $).
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

Concepts: `DataCenterRequest`, `GpuPool`, `AILab`, `Workload`, `WorkloadDependency`, `WorkloadGpuCompat`, `LabMetric`, and three Scenario Concepts (`PowerEnvelopeLevel`, `MarginFloor`, `DiversityCap`) — bound to the bundled CSVs (5 DCs, 28 GPU pools, 6 labs, 110 workloads, 138 dependency edges).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows in each, and what date range does the lab metrics history cover?
```

**Response**

10 concepts: 5 `DataCenterRequest` (xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal), 28 `GpuPool`, 6 `AILab`, 110 `Workload`, 181 `WorkloadGpuCompat` (workload-side GPU-type allowlist as a composite-key edge concept), 138 `WorkloadDependency`, 2,190 `LabMetric` covering 365 days × 6 labs (date range 2025-05-11 .. 2026-05-10), plus 3 / 4 / 4 rows on the three Scenario Concepts (3 × 4 × 4 = 48 cells).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses. The operator is accountable on three axes — power envelope per campus, gross margin after energy and depreciation, and anchor concentration (CoreWeave-style single-customer risk). Which reasoners, in what order, produce a defensible compute allocation?
```

**Response**

Plan routes sub-questions to predictive (per-workload utilization-probability classification — captures the operator's stranded-capacity exposure), rules (hardware eligibility + priority tier), graph (downstream gating), and prescriptive (assignment MIP under a 3D scenario sweep with interpretation).

### 4. Scope demand

**Prompt**

```
/rai-querying How is workload demand distributed across labs, workload types, and contract tiers, and which labs dominate GPU-hour pressure (sum of gpu_count_required × duration_hours)?
```

**Response**

Frontier labs (Anthropic Research, OpenAI Pretrain, xAI Internal) carry the 15 P0 pretrains (256–1,024 GPUs each, GB200/H200/H100 mix). Applied labs (Cohere Inference, Together AI Multi-Lab) carry the 30 P1 fine-tunes + 50 P1 inference workloads. Stability Open carries the 15 P2 evals. Pretrain GPU-hour demand dwarfs inference even at a 50:15 workload-count ratio.

### 5. Predict per-workload utilization probability

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Which workloads will actually use their allocated capacity at high duty cycle next period, vs stall or be repaced? This is the operator's biggest economic risk — stranded capacity is depreciation accruing without offsetting revenue. Train a binary-classification GNN over a heterogeneous graph: lab-side activity (LabMetric → Workload, same lab), dependency propagation (WorkloadDependency.blocks), and cross-lab industry co-movement (LabMetric ↔ LabMetric, same date, labs sharing a workload_type). Labels live in workload_utilization_train.csv / _val.csv (80 / 15 workloads); test on all 110 so every workload gets a probability. Bind the positive-class probability back to the ontology as Workload.utilization_probability.
```

**Response**

GNN binary classification (`task_type="binary_classification"`, `eval_metric="roc_auc"`). Per-workload `utilization_probability` distribution: ~70 workloads land at p ≥ 0.5 (likely high-utilization) and ~40 at p < 0.5. Frontier pretrain shards top the distribution (p ≈ 0.85–0.95) because they pull signal through three channels — their lab's recent ramp, the dep DAG (each gates 3–5 downstream evals + finetunes), and cross-lab co-movement. Stability evals sit at the bottom (p ≈ 0.20–0.35) — small lab, isolated dep position, and no cross-lab signal pulling them up. The cross-concept edges are the load-bearing signal: a per-workload tabular baseline can't see lab-side activity, dep propagation, or cross-lab co-movement, so it under-discriminates between similar-on-paper workloads in different lab contexts.

### 6. Screen hardware compatibility and priority

**Prompt**

```
/rai-rules-authoring Which (workload, GPU pool) pairs are technically eligible? A pair qualifies when (1) the pool's per-GPU memory meets the workload's mem_required_gb and (2) the pool's gpu_type is in the workload's allowlist. Also classify each workload's priority tier from its lab's contract_tier — frontier-anchor → P0 (weight 100), committed → P1 (10), on-demand → P2 (1) — and write the tier, numeric weight, and an under-provisioning penalty (P0 = 1.0, P1 = 0.3, P2 = 0.0) the optimizer can amplify against to model asymmetric failure modes (unfilled anchor seats cost more than the foregone revenue).
```

**Response**

`Compatibility(workload, gpu_pool)` precompute holds 1,918 eligible pairs; `Workload.priority_tier` distribution is P0 = 15 / P1 = 80 / P2 = 15 with weights 100 / 10 / 1 and under-provisioning penalties 1.0 / 0.3 / 0.0. The numeric weights emulate lex-priority inside a single weighted-sum MIP, matching production cluster schedulers (Borg, Singularity, MAST); the under-provisioning penalty enters Stage 4's objective as a multiplier on assignment reward so an unfilled anchor counts as a 2× foregone-revenue loss, not 1×.

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
/rai-prescriptive-problem-formulation Which workloads should be assigned to which (DC, GPU pool) under three scenario axes — power envelope (85% / 100% / 110% of approved_mw, tracing the lower-cone / expected / upper-cone planning points), gross-margin floor (unconstrained / 75% / 80% / 85%), and anchor-concentration cap (none / 70% / 50% / 40% with workload-type floor) — solved as one MIP indexed by all three? Stay within per-pool GPU capacity and per-DC power. Maximize Σ priority_weight × gating_score × utilization_probability × strategic_value_usd × (1 + under_provisioning_penalty) so anchor under-provisioning is priced asymmetrically. Per-cell INFEASIBLE is diagnostic — the global solve should not fail when one cell binds too tight.
```

**Response**

HiGHS solves 48 cells in one pass: 33 OPTIMAL + 15 INFEASIBLE (at `time_limit_sec = 900` returns a feasible-but-not-proven-optimal solution; `TIME_LIMIT` is signal, not error). Baseline cell (100pct / unconstrained / none): 110 workloads, $25.28M revenue, 83% realized margin, 95% anchor share. The strictest cells (`anchor_max_40pct_with_type_floor` at any envelope; `anchor_max_50pct` paired with the 85% margin floor) return INFEASIBLE because the type-floor and anchor-cap combination forbids the pretrain volume that supplies the margin.

### 9. Read the frontiers and the demand-risk overlay

**Prompt**

```
/rai-prescriptive-results-interpretation What's the headline plan for the unconstrained baseline cell — revenue, total cost, realized margin, anchor share, n_assigned, and which axis would bind first if we tightened it? Where do the two Pareto frontiers (margin × revenue, diversity × revenue) cliff, and what does each cliff cost? Then replay the chosen plan under three demand-risk scenarios (diffusion slowdown, scaling-law plateau, frontier-lab displacement) to surface stranded-capacity exposure — anchor revenue is contractual, but opportunistic seats only realize a fraction of forecast under risk.
```

**Response**

Baseline cell: 110 workloads, $25.28M revenue, $4.19M total cost, 83% margin, 95% anchor, binding axis is the power envelope (no margin or diversity constraint active here). Margin frontier: revenue holds at $25.3M at 75% / 80% floors but cliffs to $22.0M at 85% (90 workloads dropped, 100% anchor — the cell retains 14 of 15 frontier P0 pretrains plus 4 P1 finetunes and 2 P2 evals that fit under the floor). Diversity frontier: $25.3M with no cap → $4.4M at 70% → $2.6M at 50% (CoreWeave-target shape) → INFEASIBLE at 40% with type-floor. Demand-risk overlay: P0 anchor revenue (~$23.9M, 95% of the envelope) is contractually locked, leaving only ~$1.33M of P1/P2 opportunistic revenue exposed — stranded exposure is ~$200K (0.8%) under diffusion-slowdown, ~$400K (1.6%) under scaling-break, and ~$667K (2.6%) under frontier-loss. The stranded-capacity envelope is small precisely because the headline plan is anchor-heavy; a more diverse cell (e.g., `anchor_max_70pct`) would have a much wider risk band — visible in `DemandScenarioOutlook` when the overlay is replayed against that cell.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Add an AllocationPlan singleton holding the baseline-cell summary (chosen envelope/margin/diversity, revenue_usd, total_cost_usd, realized_margin, anchor_share, n_assigned, status, binding_axis), an Assignment.is_chosen unary Relationship narrowing Assignment to the decision rows in the chosen cell, and a DemandScenario / DemandScenarioOutlook pair carrying the four risk scenarios and their realized/stranded revenue so the overlay survives the chain run.
```

**Response**

Ontology gains a singleton `AllocationPlan` (id = `DCCA_BASELINE`) with revenue ≈ $25.28M, total cost ≈ $4.19M, margin ≈ 0.83, anchor share ≈ 0.95, n_assigned = 110, status = `OPTIMAL`, binding_axis = `power_envelope`; plus `Assignment.is_chosen` (110 rows). Headline plan is queryable as ontology rather than stdout — mirrors the `RestorePlan` / `is_selected_upgrade` pattern in `telco_network_recovery` and the `InvestmentPortfolio` pattern in `energy_grid_planning`.

## Data

Bundled CSVs in `data/`: 5 data centers, 28 GPU pools, 6 AI labs, 110 workloads (15 P0 pretrain / 30 P1 finetune / 50 P1 inference / 15 P2 eval), 138 workload dependencies, 2,190 lab-metric rows (365 days × 6 labs) split into train/val/test, plus 3 / 4 / 4 scenario rows. Full chain implemented in `datacenter_compute_allocation.py`.
