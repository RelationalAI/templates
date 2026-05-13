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

## Prerequisites and chain context

This template is a follow-up to **[energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning)**. Where the upstream template decides which AI campuses get built and energized at what MW envelope (a multi-year capex / interconnect decision over ~50 binaries), this template zooms into the energized campus and decides which AI lab's individual training, fine-tune, inference, and eval workloads get which GPUs in which pool right now. The two share a single ontology -- `DataCenterRequest` -- and reason at very different scales.

Two run modes are supported:

- **Chain mode (default).** Connects to the same `Model("Energy Grid Infrastructure")` that `energy_grid_planning` populated, reads `DataCenterRequest.x_approve(InvestmentLevel)` at the chosen level, and attaches new properties to the existing concept via a side-table CSV. Requires `energy_grid_planning` to have been run first on the same RAI account/engine.
- **Standalone mode (`--standalone`).** Loads `data/data_centers.csv` directly -- a snapshot of the same 5 DCs the upstream $300M solve approves, with matching names / MWs / hyperscalers / substations. Lets you run this template cold without first running the upstream.

If you have not run `energy_grid_planning` yet, start with `--standalone`. Then return for the chain-mode walk-through to see the ontology compose across templates.

## What this template is for

The 5 hyperscaler campuses approved by the upstream $300M solve -- xAI Colossus, Microsoft Horizon, CoreWeave Austin, Crusoe Permian, Oracle Coastal -- are now energized and stocked with GPU pools. The DC operator (a neocloud / colocation provider, or the hyperscaler operating its own campus) has to allocate that GPU capacity across the AI labs renting time on it. Frontier model labs want long-running training reservations on the largest contiguous H100 / H200 / GB200 pools at preferential anchor-customer rates. Inference customers want a steady slice of right-sized GPUs in low-latency regions. Research orgs want bursty best-effort capacity. They all compete for the same physical pools under the same power envelope.

The decision is **multi-objective and operationally pressing**. Every major hyperscaler now reports AI compute as a binding constraint on growth (Microsoft has disclosed an $80B Azure backlog blocked specifically by power constraints). The operator is accountable on three publicly-discussed dimensions:

1. **Power envelope.** Each campus has a substation-bound MW cap (the upstream-solved `approved_mw`). At 100% the cap is grid-approved; at 85% it is a heat-wave / curtailment day; at 110% it is contracted-curtailment headroom.
2. **Gross-margin discipline.** SemiAnalysis quantifies neocloud BMaaS at 55-65% gross margin pre-depreciation but only **14-16% net** after labor, power, and depreciation, so even a single MWh-cost mis-allocation is meaningful to the P&L.
3. **Anchor concentration.** CoreWeave's Q2 2025 10-Q discloses **71% of revenue from a single customer (Microsoft)** and an $11.9B OpenAI commitment booked through October 2030 -- the canonical example of the concentration risk that caps equity value. Operators win anchors (because they underwrite debt-financed buildouts) AND dilute them (because investor-visible concentration risk caps equity value).

This template combines the upstream-inherited `PowerEnvelopeLevel` with two new Scenario Concepts -- `MarginFloor` and `DiversityCap` -- into a **3D scenario sweep (3 x 4 x 4 = 48 cells)** that traces two Pareto frontiers the operator already discusses publicly: margin-floor vs. achievable revenue, and diversity-cap vs. achievable revenue, with envelope as outer sensitivity. The strictest cells return `INFEASIBLE` -- this is the intended diagnostic signal showing which constraint combinations cannot be satisfied simultaneously.

A single reasoner cannot answer this. Rules alone classify what is eligible but cannot rank. Graph alone ranks which workloads gate downstream work but does not assign GPUs. Predictive alone forecasts that Anthropic's training intensity will ramp next month but does not act. Prescriptive alone has no eligibility filter, no dependency weights, and no forecast to weight allocations by. The accretive chain produces a defensible plan: each stage's output narrows or scores the next.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 0. Chain bind | **Query** | Upstream `DataCenterRequest.x_approve(InvestmentLevel)` and properties | New properties: `approved_mw`, `dollars_per_mwh` | Bind upstream-approved DCs and attach side-table `dollars_per_mwh` for the energy-cost calculation. Defines all new concepts (`GpuPool`, `AILab`, `Workload`, `WorkloadDependency`, scenario concepts). |
| 1. Predictive | **Heterogeneous-graph GNN** | `LabMetric` time series + four edge types: same-lab temporal, intra-lab `lab_workloads`, `WorkloadDependency.blocks` (shared with Stage 3), cross-lab `co_dated` (LOAD-BEARING) | `LabGrowth.multiplier` per lab; `Workload.projected_demand_growth` joined via lab | Forecast per-lab training intensity using cross-lab co-movement (industry GPU supply shocks, AI funding waves, model-release seasons). The cross-lab `co_dated` edge is what makes this a real GNN problem, not 6 disjoint univariate forecasts. |
| 2. Rules | **Rules** (declarative) | `Workload` requirements, `GpuPool` specs | `Workload.fails_memory`, `.passes_gpu_type`, `.is_eligible` Relationships; `Workload.priority_tier` and `.priority_weight` Properties; `Compatibility(workload, gpu_pool)` precompute | Classify which (Workload, GpuPool) pairs are technically eligible (memory + GPU-type allowlist). Assign priority tier P0/P1/P2 from `contract_tier`. The Compatibility precompute keeps the Stage 4 MIP linear. |
| 3. Graph | **Reverse-PageRank** | `Workload` nodes, `WorkloadDependency.blocks` edges | `Workload.gating_score` | Score how much downstream work each workload unblocks. A frontier pretrain that gates 14 fine-tunes and evals lands high; an isolated inference workload sits at baseline. |
| 4. Prescriptive | **MIP** (HiGHS) | `Compatibility`, `priority_weight`, `gating_score`, `projected_demand_growth`, `dollars_per_mwh`, `hourly_depreciation_rate`, `approved_mw`, `is_strategic_anchor`, the three Scenario Concepts | `Assignment.x_assign` per `(PowerEnvelopeLevel, MarginFloor, DiversityCap)`; `AllocationPlan` singleton; `Assignment.is_chosen` | Assign each workload to one (DC, GpuPool) under power, GPU-count, gross-margin-floor (energy + depreciation cost), and anchor / workload-type-diversity constraints. Maximizes a four-factor strategic value: priority * gating * growth * strategic_value_usd. 48-cell sweep; strictest cells return INFEASIBLE as designed signal. The headline cell (`100pct / unconstrained / none`) is persisted as the `AllocationPlan` singleton, and its decision rows are flagged via `Assignment.is_chosen` so the plan is queryable as ontology after the script exits. |

**Key design patterns demonstrated:**

- **Cross-template ontology extension.** The upstream `DataCenterRequest` concept is extended with new properties (`approved_mw`, `dollars_per_mwh`) via `model.define()` calls that join on the existing identifier. No upstream rewrites; downstream stages query the extended concept uniformly.
- **One ontology relationship, two reasoners.** `WorkloadDependency.blocks` carries information into both the Stage 1 GNN (as a heterogeneous edge) and the Stage 3 PageRank (as the dependency DAG). Defined once in the ontology, consumed without duplication or DataFrame round-trips.
- **Per-cell aggregates queried from the ontology.** Stage 4's per-cell summary table (revenue, energy + depreciation cost, anchor share, workload-type counts) comes from `sum(...).where(Assignment.x_assign(env, mar, div, x), x > 0.5).per(env, mar, div)` aggregate expressions assembled inside a single `model.select()` call -- mirroring `energy_grid_planning`'s `rev_per_level` pattern. No pandas-side groupby of raw assignments.
- **Headline plan persisted as ontology.** After the 48-cell sweep, the chosen baseline cell (`100pct / unconstrained / none`) is written back as a singleton `AllocationPlan` Concept carrying revenue, total_cost, realized_margin, anchor_share, n_assigned, status, and binding_axis -- plus an `Assignment.is_chosen` unary Relationship that flags the decision rows in that cell. The plan is queryable as ontology after the script exits, mirroring the `RestorePlan` / `is_selected_upgrade` pattern in `telco_network_recovery`.
- **Heterogeneous GNN, not time-series-on-rails.** Stage 1 connects `LabMetric` to `Workload`, to other `LabMetric` rows on the same date (when their labs share a workload_type), and reuses `WorkloadDependency` -- in addition to same-lab temporal lags. Pure same-entity temporal-lag topology is a misuse of the GNN reasoner; the cross-concept edges are what give it lift.
- **Three-dimensional Scenario Concept design.** `PowerEnvelopeLevel` (outer capacity sensitivity), `MarginFloor` (primary Pareto axis), `DiversityCap` (primary Pareto axis). Decision variable `Assignment.x_assign` is indexed by all three; the Pareto frontier emerges from constraint relaxation across cells, not from a multi-objective solve.
- **Lex-emulating priority weights.** P0 workloads carry weight 100, P1 carry 10, P2 carry 1, plus a hard P0-must-be-assigned constraint. This mirrors how production cluster schedulers (Borg, Singularity, MAST) balance priority dominance with throughput optimization.
- **Four-factor MIP objective.** `priority_weight * gating_score * projected_demand_growth * strategic_value_usd` -- one factor per upstream reasoner (Stage 2 / Stage 3 / Stage 1) plus the raw dollar baseline. Single-MIP, weighted-sum; the multi-objective Pareto emerges from constraint relaxation, not the objective.

## Who this is for

- DC operators (neocloud, colo, hyperscaler infra teams) allocating GPU capacity across multi-tenant pools
- Capacity planners deciding when a (margin floor, diversity cap, envelope) point justifies acquiring more megawatts
- Operations researchers exploring multi-reasoner pipelines that compose a heterogeneous GNN, graph centrality, declarative rules, and a scenario-parameterized MIP
- Developers extending RelationalAI templates across decision lineages (capacity planning -> allocation -> scheduling)

## What you'll build

- A 6-lab x 5-DC compute allocation MIP, indexed by a 3D Scenario Concept sweep (3 envelopes x 4 margin floors x 4 diversity caps = 48 cells)
- A heterogeneous-graph GNN for per-lab training-intensity forecasting (with a per-lab gradient-boosted-trees baseline available for the GNN-vs-tabular lift comparison; see `runbook.md`)
- Reverse-PageRank scoring on a workload dependency DAG (4-5 deep chains rooted at frontier pretrains)
- Declarative hardware-compatibility rules + lex-emulating priority weights (P0=100, P1=10, P2=1)
- Two headline Pareto frontiers (margin <-> revenue and diversity <-> revenue) at the 100% envelope, with 85% / 110% drawn as overlay sensitivity bands
- Per-cell results queryable directly from the ontology -- realized revenue, energy + depreciation cost, anchor share, per-workload-type counts, binding-constraint signal (OPTIMAL vs INFEASIBLE)

## What's included

- `datacenter_compute_allocation.py` -- main script: chain bind + 4 reasoner stages + Pareto reporting
- `data/data_centers.csv` -- 5 DCs (snapshot of upstream $300M-approved set; standalone mode only)
- `data/data_center_attrs.csv` -- 5 rows: `dc_id -> dollars_per_mwh` (chain mode side table)
- `data/gpu_pools.csv` -- 28 pools across 5 DCs (H100 / H200 / GB200 mix), with per-GPU `hourly_depreciation_rate` ($1.14 H100, $1.52 H200, $2.66 GB200; capex/3-year amortization)
- `data/ai_labs.csv` -- 6 labs: 3 frontier anchors (Anthropic, OpenAI, xAI Internal) + 2 applied (Cohere Inference, Together AI Multi-Lab) + 1 research (Stability Open)
- `data/workloads.csv` -- 110 workloads: 15 P0 pretrains (frontier labs, 256-1024 GPUs each, GB200/H200/H100 mix), 30 P1 finetune (Together AI + Cohere), 50 P1 inference (Cohere + Together), 15 P2 eval (Stability)
- `data/workload_gpu_compatibility.csv` -- per-workload GPU-type allowlist
- `data/workload_dependencies.csv` -- ~140 edges (~130 blocks + ~10 informs), DAG depth 4-5 rooted at frontier pretrains
- `data/lab_metrics.csv` -- 365 days x 6 labs = 2,190 rows with cross-lab co-movement
- `data/train_metrics.csv`, `val_metrics.csv`, `test_metrics.csv` -- GNN train/val/test splits
- `data/lab_growth_forecasts.csv` -- Stage 1 fallback (lab x multiplier)
- `data/power_envelope_levels.csv` -- 3 scenario rows (0.85 / 1.00 / 1.10)
- `data/margin_floors.csv` -- 4 scenario rows (unconstrained / 75% / 80% / 85% gross margin post-depreciation)
- `data/diversity_caps.csv` -- 4 scenario rows (none / anchor_max_70pct / anchor_max_50pct CoreWeave-target / anchor_max_40pct_with_type_floor)
- `runbook.md` -- end-to-end run instructions for both chain and standalone modes, including the GNN-vs-baseline lift validation cell

## How to run it

### Chain mode (default; assumes upstream has run)

```bash
python datacenter_compute_allocation.py
```

The script will:
1. Connect to `Model("Energy Grid Infrastructure")` and read `DataCenterRequest.x_approve("$300M")`.
2. Attach `dollars_per_mwh` from `data/data_center_attrs.csv` to the upstream-approved DCs.
3. Define new concepts (`GpuPool`, `AILab`, `Workload`, `WorkloadDependency`, scenarios) on the same model.
4. Run Stage 1 (GNN), Stage 2 (rules), Stage 3 (PageRank), Stage 4 (48-cell MIP).
5. Print per-cell summary + the two Pareto frontiers at the 100% envelope.

If chain mode finds no upstream-approved DCs, it raises a clear error and recommends `--standalone`.

**Expected runtime** (full pipeline, standalone, real GNN):
- Stage 1 (GNN training + prediction): ~90-120s on `GPU_NV_S` predictive engine
- Stages 2-3 (rules + PageRank): a few seconds
- Stage 4 (48-cell MIP): hits the 900s `time_limit_sec` and returns a feasible solution. Per-cell results remain valid; objective is within demo-acceptable gap (rai-prescriptive-results-interpretation: a non-OPTIMAL termination is signal, not failure)

**Expected per-cell behavior:**
- `(*, unconstrained / 75% / 80% margin, none diversity)`: full assignment of all 110 workloads, ~$25M revenue, 83% realized margin, 95% anchor share
- `(*, 85% margin, none)`: tight floor binds — drops 89 lower-margin workloads, retains 14 of 15 frontier P0 pretrains, revenue $22M @ 85% margin / 100% anchor
- `(*, *, anchor_max_70pct)`: anchor cap drops most P0 pretrains, $4-5M revenue @ ~70% anchor
- `(*, *, anchor_max_50pct)`: CoreWeave-target cap, $2.6M @ 49% anchor (only 2 of 15 P0 pretrains fit)
- `(*, *, anchor_max_40pct_with_type_floor)`: INFEASIBLE — too tight to satisfy with this lab roster
- `(*, 85% margin, anchor_max_50pct)`: INFEASIBLE — high margin floor wants pretrain-only, but anchor cap forbids that mix

### Standalone mode (no upstream prerequisite)

```bash
python datacenter_compute_allocation.py --standalone
```

Loads the bundled `data/data_centers.csv` (the same 5 DCs the upstream $300M solve approves) into a fresh `Model("Datacenter Compute Allocation")`. All four reasoner stages run identically.

### Skip GNN (use precomputed forecasts)

```bash
python datacenter_compute_allocation.py --no-gnn
```

Loads `data/lab_growth_forecasts.csv` directly into `LabGrowth` and skips GNN training. Downstream stages are unchanged. Use this for fast iteration on Stages 2-4.

### Pick a different upstream investment level (chain mode)

```bash
python datacenter_compute_allocation.py --investment-level "\$400M"
```

The upstream sweep ($200M to $600M) and this template's 3D scenario sweep compose into a 4D scenario grid without any new constraints in either model.

## Customize this template

- **Add or remove DCs** by editing `data_centers.csv` (standalone) or running `energy_grid_planning` at a different `InvestmentLevel` (chain).
- **Adjust the lab roster** in `ai_labs.csv`. Anchor flag drives the `DiversityCap` constraint.
- **Tune scenario axes**: edit `power_envelope_levels.csv`, `margin_floors.csv`, `diversity_caps.csv`. Adding rows scales the cell count multiplicatively.
- **Change the priority spread** by editing the weights in `stage2_rules` (default 100 / 10 / 1).
- **Replace the GNN with a tabular baseline** by setting `--no-gnn` and editing `lab_growth_forecasts.csv` directly.
- **Use a different solver** by changing `problem.solve("highs", ...)` to `"gurobi"` if any single cell consistently exceeds 60s.

## What this template abstracts

This is a tutorial-grade allocator, not a production scheduler. Several real-world constraints are intentionally simplified -- see the design doc's "Production fidelity" section for the full list, but at a glance:

- **Gang scheduling.** Production training requires all-or-nothing allocation across (e.g.) 256 GPUs with topology-aware placement. We model assignment as a single (Workload, GpuPool) binary; `interconnect` and `reservation_model` are informational, not constraints.
- **Time-block reservations.** Production training is reserved for hours-to-weeks; our snapshot allocation collapses all time into one period.
- **Elastic sizing.** Production schedulers (Pollux, Sia) adjust GPU count mid-training; our `gpu_count_required` is fixed.
- **Per-DC `dollars_per_mwh` is a scalar.** Real wholesale electricity prices vary intraday and seasonally; smart workload scheduling can arbitrage this. The snapshot omits this lever.
- **Anchor designation is binary.** Real concentration risk is a function of contract size and term, not just identity. The Boolean `is_strategic_anchor` is a tutorial simplification.
