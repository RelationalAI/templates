# Runbook: Datacenter Compute Allocation — Multi-Reasoner Walkthrough

The 5 hyperscaler campuses the upstream `energy_grid_planning` $300M solve approves are now energized and stocked with 28 GPU pools (H100 / H200 / GB200 mix). The operator has to allocate that capacity across 110 workloads from 6 AI labs (3 frontier anchors, 2 applied, 1 research) while staying inside the power envelope, holding gross margin against rising depreciation, and capping anchor concentration. No single reasoner gets there: predictive ramps per-lab demand, rules screen hardware compatibility and priority, graph weights workloads by downstream dependency, and prescriptive composes all three into the per-(envelope, margin floor, diversity cap) assignment. Each stage writes derived properties back to the same ontology the next stage consumes.

## The chain

```
The 48-cell sweep (3 envelopes × 4 margin floors × 4 diversity caps) traces
two Pareto frontiers — margin vs. revenue and diversity vs. revenue — and
the headline plan persists the unconstrained baseline as ontology.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive  ──►  LabGrowth.multiplier (per lab)
              (GNN)         Frontier ramp 1.05–1.12× (OpenAI 1.12,
                            Anthropic 1.10, xAI 1.08); applied 1.03–1.04×;
                            Stability 0.97× (slight contraction).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules       ──►  Workload.is_eligible, .priority_tier
                            Compatibility(workload, gpu_pool)  ~1,900 pairs
                            P0 = 15, P1 = 80, P2 = 15.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph       ──►  Workload.gating_score  (reverse-PageRank)
                            Frontier pretrains top the score; isolated
                            inference workloads sit at baseline.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Prescriptive──►  Assignment.x_assign(env, margin, diversity)
              (MIP)         48 cells: 33 OPTIMAL, 15 INFEASIBLE.
                            Baseline (100pct / unconstrained / none):
                            110 assigned · $25.3M revenue · 83% margin
                            · 95% anchor share.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Persist     ──►  AllocationPlan  (singleton)
                            Assignment.is_chosen  (110 rows)
                            Headline plan queryable as ontology.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a datacenter compute allocation ontology from the CSVs in data/: data_centers (or in chain mode, the upstream DataCenterRequest concept), gpu_pools, ai_labs, workloads, workload_gpu_compatibility, workload_dependencies, lab_metrics, train_metrics, val_metrics, test_metrics, lab_growth_forecasts, plus three scenario CSVs power_envelope_levels, margin_floors, diversity_caps. workload_dependencies is an edge concept (source_workload, target_workload, edge_type ∈ {blocks, informs}). lab_metrics is keyed by (lab, date) so it should be a composite-key concept. The three scenario CSVs each map to a Scenario Concept identified by name.
```

**Response**

Concepts: `DataCenterRequest` (5 rows), `GpuPool` (28, located_at DataCenterRequest), `AILab` (6), `Workload` (110, lab: AILab), `WorkloadDependency` (138 directed edges, source_workload → target_workload), `Compatibility(workload, gpu_pool)` (composite-key edge concept, populated in the Rules stage), `LabMetric` (2,190 = 365 days × 6 labs, composite-key on lab+date), `LabGrowth` (6 rows, multiplier per lab — populated in the Predictive stage), and three Scenario Concepts `PowerEnvelopeLevel` (3 rows), `MarginFloor` (4 rows), `DiversityCap` (4 rows). The decision-variable concept `Assignment(workload, gpu_pool)` is defined alongside the Prescriptive stage.

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows are in each, and what is the data range covered (LabMetric date span, scenario row counts)?
```

**Response**

12 concepts wired to the bundled CSVs: 5 `DataCenterRequest` (xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal — the upstream $300M-approved set), 28 `GpuPool`, 6 `AILab`, 110 `Workload`, 138 `WorkloadDependency`, 2,190 `LabMetric` covering 365 days × 6 labs, 6 `LabGrowth` placeholders, plus 3 / 4 / 4 rows on the three Scenario Concepts (3 × 4 × 4 = 48 cells).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery The 5 hyperscaler campuses approved at $300M are now energized. We have 110 workloads across 6 AI labs competing for 28 GPU pools. The operator is accountable on three publicly-discussed dimensions: a power envelope per campus (substation-bound MW), gross margin after energy + depreciation (the 14-16% net BMaaS pressure), and anchor concentration (CoreWeave-style single-customer risk). What reasoners do we need, in what order, to land on a defensible compute allocation grounded in the available data (per-lab daily KPIs, hardware specs, dependency DAG, contract tiers)?
```

**Response**

Plans the 4-reasoner chain on the shared ontology — predictive (`/rai-predictive-modeling` + `/rai-predictive-training`) to forecast per-lab training-intensity ramp using a heterogeneous GNN with cross-lab `co_dated` edges so industry-wide co-movement (funding waves, GPU supply shocks, model-release seasons) is in the signal; rules (`/rai-rules-authoring`) to screen which (workload, GPU pool) pairs are technically eligible (memory + GPU-type allowlist) and to classify priority tier from contract tier; graph (`/rai-graph-analysis`) to score how much downstream work each workload unblocks (reverse-PageRank on the `blocks` DAG); prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to compose all three signals into the assignment MIP under a 3D scenario sweep (envelope × margin floor × diversity cap) and explain the binding constraint.

### 4. Scope the demand picture

**Prompt**

```
/rai-querying How is demand distributed today across labs, workload types, and contract tiers? For each lab, show its workload counts by type (pretrain / finetune / inference / eval) and contract tier, the GPU types it has requested, and the rough capex pressure it represents (sum of gpu_count_required × duration_hours).
```

**Response**

Frontier labs (Anthropic Research, OpenAI Pretrain, xAI Internal) carry the 15 P0 pretrains (256-1024 GPUs each, GB200/H200/H100 mix). Applied labs (Cohere Inference, Together AI Multi-Lab) carry the 30 P1 fine-tunes + 50 P1 inference workloads. Stability Open carries the 15 P2 evals. The dependency DAG roots at frontier pretrains (depth 4-5 chains: pretrain → eval → finetune → inference). Pretrain GPU-hour demand dwarfs inference even at 50:15 workload-count ratio.

### 5. Forecast per-lab training intensity

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Predict each lab's next-period training intensity multiplier from its daily KPI history (train through October, validate Nov, test Dec). Use a heterogeneous graph with four edge types: same-lab 1-day-lag temporal edges, intra-lab lab→workload edges, WorkloadDependency.blocks edges, and cross-lab co_dated edges that connect lab-metric rows on the same date when their labs share a workload_type — the cross-lab edges are what let the model pick up industry-wide co-movement (funding waves, GPU supply shocks, model-release seasons). Bind the per-lab forecast multiplier as LabGrowth.multiplier and join it to each workload via lab.
```

**Response**

GNN node regression on 365d × 6 labs with the four-edge heterogeneous graph above. Per-lab Dec test-mean multipliers: OpenAI Pretrain ≈1.12, Anthropic Research ≈1.10, xAI Internal ≈1.08, Together AI Multi-Lab ≈1.04, Cohere Inference ≈1.03, Stability Open ≈0.97 (slight contraction). Frontier labs ramp 5–12% while the research org contracts — the cross-lab `co_dated` edges are the load-bearing signal here; a per-lab tabular baseline (gradient-boosted trees) trained on the same lag features sits at higher RMSE because it can't see the industry-wide co-movement.

### 6. Classify hardware compatibility and priority

**Prompt**

```
/rai-rules-authoring For each (workload, GPU pool) pair, flag it as eligible only when (a) the pool's per-GPU memory meets the workload's min_memory_gb_per_gpu requirement and (b) the workload's GPU-type allowlist (workload_gpu_compatibility) includes the pool's gpu_type. Precompute the eligible pairs as the Compatibility(workload, gpu_pool) concept so the assignment MIP stays linear. Separately, classify each workload's priority tier from its lab's contract tier — frontier-anchor labs are P0 (weight 100), applied/strategic labs are P1 (weight 10), research labs are P2 (weight 1) — and write both Workload.priority_tier and Workload.priority_weight.
```

**Response**

4 derived properties on `Workload` (`fails_memory`, `passes_gpu_type`, `is_eligible`, `priority_tier`) plus `Workload.priority_weight`. The `Compatibility(workload, gpu_pool)` composite-key concept holds 1,918 (workload, gpu_pool) pairs. Priority tier counts: P0 = 15 (frontier pretrains), P1 = 80 (fine-tunes + inference), P2 = 15 (evals). The priority weights (100 / 10 / 1) emulate lex-priority inside a single weighted-sum MIP, matching how production cluster schedulers (Borg, Singularity, MAST) balance priority dominance with throughput optimization.

### 7. Score downstream gating

**Prompt**

```
/rai-graph-analysis Build a directed workload-dependency graph from WorkloadDependency (source_workload → target_workload, edge_type = "blocks") and score each workload by how much downstream work it unblocks — the structural test is "importance flows backward along incoming directed edges" (a workload that gates many later workloads, each of which gates more, should land high). Bind the score as Workload.gating_score.
```

**Response**

Reverse-PageRank on the 110-node, 138-edge directed graph. Frontier pretrains land at the top (GPT-Next pretrain shard 02 ≈ 0.031, Grok-Next pretrain shard 04 ≈ 0.027, Claude-Next pretrain shard 02 ≈ 0.023) because they root 4-5-deep dependency chains; isolated inference workloads sit at the baseline ≈1/110. The score will enter the MIP objective as a per-workload multiplier so the optimizer favors decisions whose downstream impact is large.

### 8. Allocate GPU capacity under the 3D scenario sweep

**Prompt**

```
/rai-prescriptive-problem-formulation Assign each eligible workload to at most one (DC, GPU pool) under the following constraints, indexed by the 3D scenario product (PowerEnvelopeLevel × MarginFloor × DiversityCap) so we get one optimal assignment per cell in a single solve. Constraints: (C1) each P0 workload must be assigned wherever feasible (soft, with priority_weight = 100 driving it from the objective); (C2) each P1/P2 workload assigned to at most one pool; (C3) total GPUs assigned per pool ≤ available_gpu_count; (C4) per-DC power draw (Σ workload GPUs × power_per_gpu_kw × DC pue) ≤ approved_mw × envelope_multiplier × 1000; (C5) gross margin = (revenue − energy_cost − depreciation_cost) / revenue ≥ margin_floor whenever the floor is set; (C6) anchor-share = anchor_revenue / total_revenue ≤ anchor_cap whenever the cap is set; (C7) workload-type floor when the diversity cap includes a type-floor variant (at least N% inference or eval workloads must be among assigned). Maximize Σ over assigned workloads of priority_weight × gating_score × projected_demand_growth × strategic_value_usd. Treat per-cell INFEASIBLE as diagnostic signal — the global solve should not fail when one cell can't be satisfied.
```

**Response**

HiGHS solve over the 48-cell sweep returns 33 OPTIMAL + 15 INFEASIBLE cells. At `time_limit_sec = 900` the solve hits the wall and returns a feasible-but-not-proven-optimal solution; per-cell results remain valid (TIME_LIMIT is signal, not error, per `/rai-prescriptive-results-interpretation`). Baseline cell (100pct / unconstrained / none): 110 assigned workloads, $25,277,811 revenue, 83% realized margin, 95% anchor share. Pareto frontiers: at 85% margin only 18 of 110 workloads survive ($22M, 100% anchor); at `anchor_max_50pct` only 97 fit (revenue $2.6M, 49% anchor — CoreWeave-target shape); the `anchor_max_40pct_with_type_floor` variant returns INFEASIBLE at every envelope because the type-floor wants inference/eval mix but the anchor cap forbids the pretrain volume that supplies the margin.

### 9. Interpret the plan

**Prompt**

```
/rai-prescriptive-results-interpretation Summarize the headline cell (100pct envelope, unconstrained margin, no diversity cap): revenue, total cost, realized margin, anchor share, n_assigned, and which axis would be the first to bind if we tightened it. Then read the two Pareto frontiers (margin × revenue and diversity × revenue) and identify the cliff points.
```

**Response**

Baseline cell: 110 workloads assigned, $25.28M revenue, ~$4.19M total cost (energy + depreciation), 83% realized margin, 95% anchor share. The binding axis is the power envelope (no margin floor or diversity cap is active in this cell). Margin frontier: revenue holds at $25.3M for floors 75–80% but collapses to $22.0M at 85% (89 workloads dropped, 100% anchor); the cliff is 80→85%. Diversity frontier: revenue holds at $25.3M with no cap and at $4.4M / $2.6M at 70% / 50% anchor caps; the 50% cap is the CoreWeave-target shape. A 10–20% envelope relaxation (e.g., contracted-curtailment headroom at 110%) would allow more frontier pretrain shards but does not change the baseline cell unless paired with a tighter margin or diversity setting.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Materialize the headline plan and its decision rows as queryable ontology. Add an AllocationPlan singleton holding the baseline-cell summary (chosen_envelope, chosen_margin, chosen_diversity, revenue_usd, total_cost_usd, realized_margin, anchor_share, n_assigned, status, binding_axis) and an Assignment.is_chosen unary Relationship narrowing Assignment to the 110 rows in the chosen cell.
```

**Response**

Ontology gains a singleton `AllocationPlan` Concept (id = `DCCA_BASELINE`) with `chosen_envelope` = "100pct", `chosen_margin` = "unconstrained", `chosen_diversity` = "none", `revenue_usd` ≈ $25.28M, `total_cost_usd` ≈ $4.19M, `realized_margin` ≈ 0.83, `anchor_share` ≈ 0.95, `n_assigned` = 110, `status` = "OPTIMAL", `binding_axis` = "power_envelope"; plus `Assignment.is_chosen` (110 rows). The headline plan + chosen decisions are now first-class ontology — a downstream analyst (or Cortex Agent) can query `AllocationPlan` and `Assignment.is_chosen` directly without re-running the chain.

## Data

Bundled CSVs in `data/`: 5 `data_centers` (the upstream $300M-approved set + standalone-mode snapshot), 28 `gpu_pools` (H100 / H200 / GB200 mix across 5 DCs), 6 `ai_labs` (3 frontier + 2 applied + 1 research), 110 `workloads` (15 P0 pretrain / 30 P1 finetune / 50 P1 inference / 15 P2 eval), 138 `workload_dependencies` (~130 blocks + ~10 informs), 2,190 `lab_metrics` rows (365 days × 6 labs) split into train / val / test, 6 `lab_growth_forecasts` (`--no-gnn` fallback), plus 3 / 4 / 4 scenario rows. All stages run end-to-end via `datacenter_compute_allocation.py` (see `README.md` Quickstart for run modes and prerequisites).
