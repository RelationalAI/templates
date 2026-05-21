# Runbook: Datacenter Compute Allocation — Multi-Reasoner Walkthrough

A neocloud operator has 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses (a snapshot of the campus set the upstream `energy_grid_planning` $300M solve approved). The chain predicts per-workload utilization probability, screens hardware compatibility, weights workloads by downstream gating, and produces a 24-cell scenario sweep — no single reasoner can answer this end-to-end.

## The chain

```
The 24-cell sweep (2 envelopes × 3 margin floors × 4 diversity caps)
traces two Pareto frontiers — margin × revenue and diversity × revenue.
The headline baseline cell (100pct / unconstrained / none) is persisted
as ontology so the plan survives the chain run.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  Workload.utilization_probability  (110)
                 (temporal    Binary classification on 770 historical
                  hetero GNN) (workload, month) observations + 110 val.
                              Probability each workload actually uses its
                              allocated capacity at high duty cycle this
                              period. Frontier pretrains land ~0.78;
                              isolated Stability evals ~0.38.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Compatibility(workload, gpu_pool) (1,918)
                             Workload.priority_tier            (110)
                             Workload.under_provisioning_penalty
                             P0 = 15 (wt 100, pen 1.0), P1 = 80 (10, 0.3),
                             P2 = 15 (1, 0.0). Asymmetric failure pricing.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Workload.gating_score             (110)
                 (downstream- Frontier pretrain shards (GPT/Grok/Claude-Next)
                  reach)      top the score, gating 4–5-deep chains.
                              GPT-Next 02 ≈ 0.0310, Grok-Next 04 ≈ 0.0266.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Prescriptive ──►  Assignment.x_assign(env, mar, div)
                 (MIP)       24 cells: 16 OPTIMAL, 8 INFEASIBLE.
                             OPTIMAL in 6 s with Gurobi.
                             Baseline (100pct / unconstrained / none):
                             110 assigned · $25.28M revenue · 83% margin
                             · 95% anchor · binding axis: power envelope.
                             Margin cliff at 85% (-13% rev, 90 dropped).
                             Diversity cliff at any cap (-82% at 70%).
                             Persisted as AllocationPlan singleton +
                             Assignment.is_chosen (110 rows) +
                             DemandScenarioOutlook (4 risk scenarios:
                             expected / diffusion_slowdown / scaling_break
                             / frontier_loss; stranded $200K / $400K / $667K).
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

10 concepts wired to the bundled CSVs: 5 `DataCenterRequest`, 28 `GpuPool`, 6 `AILab`, 110 `Workload`, 181 `WorkloadGpuCompat`, 138 `WorkloadDependency`, 2,190 `LabMetric` (365 days × 6 labs, 2025-05-11 .. 2026-05-10), plus 2 / 3 / 4 rows on `PowerEnvelopeLevel` / `MarginFloor` / `DiversityCap` (2 × 3 × 4 = 24 scenario cells).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have 110 workloads from 6 AI labs competing for 28 GPU pools across 5 hyperscaler campuses. The operator is accountable on three axes — power envelope per campus, gross margin after energy and depreciation, and anchor concentration (CoreWeave-style single-customer risk). Which reasoners, in what order, produce a defensible compute allocation?
```

**Response**

Plan routes sub-questions to predictive (per-workload utilization-probability classification), rules (hardware eligibility + priority tier), graph (downstream gating on the dep DAG), and prescriptive (assignment MIP under a 3-axis scenario sweep with interpretation).

### 4. Scope demand

**Prompt**

```
/rai-querying How is workload demand distributed across labs, workload types, and contract tiers, and which labs dominate GPU-hour pressure (sum of gpu_count_required × duration_hours)?
```

**Response**

Frontier labs (Anthropic, OpenAI, xAI Internal) carry the 15 P0 pretrains (256–1,024 GPUs each, GB200/H200/H100 mix); applied labs (Cohere, Together AI) carry 30 P1 fine-tunes + 50 P1 inference; Stability Open carries 15 P2 evals. Pretrain GPU-hour pressure dominates despite the 15:50 pretrain-to-inference workload count.

### 5. Predict per-workload utilization probability

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Which workloads will actually use their allocated capacity at high duty cycle next period, vs stall or be repaced? Train a temporal binary-classification GNN over a heterogeneous graph spanning lab-side activity (LabMetric → Workload), dependency propagation (WorkloadDependency.blocks), and cross-lab industry co-movement (LabMetric ↔ LabMetric on the same date when labs share a workload_type). Labels are per-(workload, observation_date): 7 historical months in workload_utilization_train.csv plus 1 validation month in _val.csv; the test split is the current month, unlabeled. Bind the positive-class probability back as Workload.utilization_probability.
```

**Response**

GNN temporal binary classification (`task_type="binary_classification"`, `eval_metric="roc_auc"`, `has_time_column=True`) on 770 training + 110 validation + 110 test `(workload, observation_date)` observations across three cross-concept edges (`LabMetric→Workload`, `WorkloadDependency.blocks`, cross-lab `co_dated`). `Workload.utilization_probability` bound for all 110: 95 at p ≥ 0.5, 15 at p < 0.5. Frontier pretrain shards top the distribution (p ≈ 0.78), Stability evals sit at the bottom (p ≈ 0.38).

### 6. Screen hardware compatibility and priority

**Prompt**

```
/rai-rules-authoring Which (workload, GPU pool) pairs are technically eligible? A pair qualifies when (1) the pool's per-GPU memory meets the workload's mem_required_gb and (2) the pool's gpu_type is in the workload's allowlist. Also classify each workload's priority tier from its lab's contract_tier — frontier-anchor → P0 (weight 100), committed → P1 (10), on-demand → P2 (1) — and write the tier, numeric weight, and an under-provisioning penalty (P0 = 1.0, P1 = 0.3, P2 = 0.0) the optimizer can amplify against to model asymmetric failure modes (unfilled anchor seats cost more than the foregone revenue).
```

**Response**

`Compatibility(workload, gpu_pool)` precompute (1,918 eligible pairs); `Workload.priority_tier` (P0 = 15 / P1 = 80 / P2 = 15), `.priority_weight` (100 / 10 / 1), and `.under_provisioning_penalty` (1.0 / 0.3 / 0.0). Diagnostic relationships `Workload.is_eligible(GpuPool)` and `Workload.fails_memory(GpuPool)` also derived for queryability.

### 7. Score downstream gating

**Prompt**

```
/rai-graph-analysis Which workloads gate the most downstream work — workloads where, if they slip, many later workloads slip too, and those gate even more? Score every workload by that downstream-reach metric on the WorkloadDependency.blocks DAG and bind it as Workload.gating_score.
```

**Response**

`Workload.gating_score` for all 110: frontier pretrain shards top the score (GPT-Next pretrain shard 02 ≈ 0.031, Grok-Next 04 ≈ 0.027, Claude-Next 02 ≈ 0.023) rooting 4–5-deep dependency chains; isolated inference workloads sit at the baseline ≈ 1/110.

### 8. Allocate GPU capacity under the 3-axis scenario sweep

**Prompt**

```
/rai-prescriptive-problem-formulation Which workloads should be assigned to which (DC, GPU pool) under three scenario axes — power envelope (85% / 100% of approved_mw), gross-margin floor (unconstrained / 80% / 85%), and anchor-concentration cap (none / 70% / 50% / 40% with workload-type floor) — solved as one MIP indexed by all three? Stay within per-pool GPU capacity and per-DC power, hit the margin and diversity caps per cell, and amplify anchor reward by the under-provisioning penalty so unfilled anchor seats cost more than unfilled research seats. Per-cell INFEASIBLE is diagnostic — the global solve should not fail when one cell binds too tight.
```

**Response**

Single MIP across 24 cells: `Assignment.x_assign(PowerEnvelopeLevel, MarginFloor, DiversityCap)` written back per cell — 16 OPTIMAL, 8 INFEASIBLE (designed signal at the strictest anchor-cap + type-floor combinations). OPTIMAL in ~6 s with Gurobi. Baseline (100pct / unconstrained / none): 110 workloads, $25.28M revenue, 83% margin, 95% anchor.

### 9. Read the frontiers and the demand-risk overlay

**Prompt**

```
/rai-prescriptive-results-interpretation What's the headline plan for the unconstrained baseline cell — revenue, total cost, realized margin, anchor share, n_assigned, and which axis would bind first if we tightened it? Where do the two Pareto frontiers (margin × revenue, diversity × revenue) cliff, and what does each cliff cost? Then replay the chosen plan under three demand-risk scenarios (diffusion slowdown, scaling-law plateau, frontier-lab displacement) to surface stranded-capacity exposure — anchor revenue is contractual, but opportunistic seats only realize a fraction of forecast under risk.
```

**Response**

Baseline: 110 workloads, $25.28M revenue, $4.18M cost, 83% margin, 95% anchor, binding axis = power envelope. Margin frontier: $25.28M at unconstrained / 80% floors (80% is not binding — unconstrained naturally lands at 83%), cliffs to $22.03M at 85% (90 workloads dropped, 100% anchor). Diversity frontier: $25.28M (none) → $4.44M (70%, -82%) → $2.60M (50%, -90%) → INFEASIBLE (40% with type floor). Demand overlay on a ~$1.33M opportunistic base (P0 anchor revenue contractually locked): stranded ~$200K (diffusion_slowdown), ~$400K (scaling_break), ~$667K (frontier_loss).

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Add an AllocationPlan singleton holding the baseline-cell summary (chosen envelope/margin/diversity, revenue_usd, total_cost_usd, realized_margin, anchor_share, n_assigned, status, binding_axis), an Assignment.is_chosen unary Relationship narrowing Assignment to the decision rows in the chosen cell, and a DemandScenario / DemandScenarioOutlook pair carrying the four risk scenarios and their realized/stranded revenue so the overlay survives the chain run.
```

**Response**

Ontology gains a singleton `AllocationPlan(id="DCCA_BASELINE")` with `revenue_usd` ≈ $25.28M, `total_cost_usd` ≈ $4.18M, `realized_margin` ≈ 0.83, `anchor_share` ≈ 0.95, `n_assigned` = 110, `status` = `OPTIMAL`, `binding_axis` = `power_envelope`; plus `Assignment.is_chosen` (110 rows), `DemandScenario` (4 rows), and `DemandScenarioOutlook` (per-scenario realized + stranded revenue). All queryable as ontology, not stdout.

## Data

Bundled CSVs in `data/`: 5 data centers, 28 GPU pools, 6 AI labs, 110 workloads (15 P0 pretrain / 30 P1 finetune / 50 P1 inference / 15 P2 eval), 138 workload dependencies, 2,190 lab-metric rows (365 days × 6 labs) split into train/val/test, plus 2 / 3 / 4 scenario rows. Full chain implemented in `datacenter_compute_allocation.py`.
