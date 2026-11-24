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

This template models that allocation as a scenario sweep across three axes (power envelope, margin floor, and anchor-diversity cap, for 24 combinations in all), tracing the trade-off frontiers the operator actually reasons about: how much revenue a tighter margin floor costs, and how much a tighter anchor cap costs. The strictest combinations come back infeasible, which is itself the answer — a signal that those constraints cannot all be met at once. A follow-on demand overlay then replays the chosen plan under softening-demand scenarios so the operator can see stranded-capacity exposure before committing. It picks up where the [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/energy_grid_planning) template leaves off: that upstream template decides which campuses get built and energized, and the bundled `data_centers.csv` here is a snapshot of its approved campus set.

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
- Per-cell results queryable directly from the ontology — realized revenue, energy + depreciation cost, anchor share, per-workload-type counts, binding-constraint signal (OPTIMAL vs INFEASIBLE, or FEASIBLE vs UNSOLVED when the solve stops at its time limit)

## What's included

- `model/` — the deployed model: `schema.py` declares the concepts and the GNN task relationships, `source.py` loads the bundled CSVs, `reasoning.py` states the GNN, the rules, the PageRank, the 24-cell allocation MIP, and the rules that summarize its solution
- `train.py` — trains the utilization GNN over the deployed splits and registers its version
- `queries/allocation_report.py` — prints the per-stage diagnostics, the per-cell summary, the Pareto frontiers, the plan, and the demand overlay from the deployed model
- `data/data_centers.csv` — 5 DCs (snapshot of the upstream $300M-approved set)
- `data/gpu_pools.csv` — 28 pools across 5 DCs (H100 / H200 / GB200 mix), with per-GPU `hourly_depreciation_rate` ($1.14 H100, $1.52 H200, $2.66 GB200; capex/3-year amortization)
- `data/ai_labs.csv` — 6 labs: 3 frontier anchors (Anthropic, OpenAI, xAI Internal) + 2 applied (Cohere Inference, Together AI Multi-Lab) + 1 research (Stability Open)
- `data/workloads.csv` — 110 workloads: 15 P0 pretrains (frontier labs, 256-1024 GPUs each, GB200/H200/H100 mix), 30 P1 finetune (Together AI + Cohere), 50 P1 inference (Cohere + Together), 15 P2 eval (Stability)
- `data/workload_gpu_compatibility.csv` — per-workload GPU-type allowlist
- `data/workload_dependencies.csv` — 138 edges (~130 blocks + ~10 informs), DAG depth 4-5 rooted at frontier pretrains
- `data/lab_metrics.csv` — 365 days × 6 labs = 2,190 rows with cross-lab co-movement
- `data/workload_utilization_train.csv`, `_val.csv`, `_test.csv` — GNN temporal binary-classification splits. **Train**: 7 historical months × 110 workloads = 770 `(workload, observation_date, is_high_utilization)` observations. **Val**: 1 month × 110 = 110. **Test**: the current month × 110 = 110 observations with no label (every workload gets a probability for the upcoming period).
- `data/power_envelope_levels.csv` — 2 scenario rows (0.85 / 1.00)
- `data/margin_floors.csv` — 3 scenario rows (unconstrained / 80% / 85% gross margin post-depreciation)
- `data/diversity_caps.csv` — 4 scenario rows (none / anchor_max_70pct / anchor_max_50pct CoreWeave-target / anchor_max_40pct_with_type_floor)
- `runbook.md` — analyst paste-test walkthrough mapping each stage to its RAI agent skill + prompt

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schemas). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.
- The predictive reasoner's compute pool added to the compute-pool network rule that admits the PAT user (the rule from the prescriptive reasoner setup), because the deployed model runs this template's GNN training, scoring, and registration jobs as the PAT user. Check the pool names in your account with `SHOW COMPUTE POOLS` (for example `RELATIONAL_AI_HIGHMEM_X64_S_ML`), and have an administrator run `ALTER NETWORK RULE <PAT_POOL_NETWORK_RULE> SET VALUE_LIST = (...)`, listing the pools already in the rule plus the predictive one.

Those jobs need grants for the PAT user's role (`<PAT_ROLE>`) and matching caller grants for the RAI Native App. Once the SQL at the start of the Quickstart has created this template's schemas, have an administrator run:

```sql
GRANT USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO ROLE <PAT_ROLE>;
GRANT USAGE ON DATABASE <DB> TO ROLE <PAT_ROLE>;
GRANT USAGE ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON ALL VIEWS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO ROLE <PAT_ROLE>;
GRANT CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO ROLE <PAT_ROLE>;
GRANT CALLER USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT, INSERT ON ALL TABLES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE ON ALL FILE FORMATS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE, MODIFY ON ALL EXPERIMENTS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER OWNERSHIP ON ALL MODELS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
```

The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports).
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.DATACENTER_COMPUTE_ALLOCATION;
CREATE SCHEMA IF NOT EXISTS <DB>.DATACENTER_COMPUTE_ALLOCATION_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.DATACENTER_COMPUTE_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;

```

Use this sequence to deploy the model, train the GNN, and query the allocation plan:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/datacenter_compute_allocation.zip), unzip it, and enter the template directory:

   ```bash
   unzip datacenter_compute_allocation.zip
   cd datacenter_compute_allocation
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the predictive and prescriptive reasoners, the registered version the GNN predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: workload_utilization_gnn          # created on first use if it doesn't exist
       gnns:
         workload_utilization:             # the GNN's name in model/reasoning.py
           registry: <DB>.DATACENTER_COMPUTE_ALLOCATION
           model: WORKLOAD_UTILIZATION
           version: V1                  # train.py registers this version
     prescriptive:
       name: datacenter_allocation_solver      # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.DATACENTER_COMPUTE_ALLOCATION          # published views and tables
     identity:
       internal_schema: <DB>.DATACENTER_COMPUTE_ALLOCATION_META # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>           # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the reasoners and the public schema named in `raiconfig.yaml` if they don't exist and waits for the model's first refresh, which loads the data, derives the eligibility rules and the gating scores, and sets up the allocation problem. No version of the GNN is registered yet, so this refresh makes no utilization predictions and assigns no workloads.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts utilization with this version and solves the allocation over those predictions: `CALL <DB>.DATACENTER_COMPUTE_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `<DB>`. The solve runs to its 240-second time limit, so this refresh takes several minutes. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the diagnostics and the plan from the deployed model:

   ```bash
   python -m queries.allocation_report
   ```

   ```text
   ============================================================
   STAGE 1: PREDICT -- per-workload utilization-probability GNN
   ============================================================
     Workload utilization-probability distribution: n_total=110, n>=0.5: 110, n<0.5: 0
     Top 5 (most likely to be high-utilization):
       + Grok-Next pretrain shard 04                   p=0.931
       + GPT-Next pretrain shard 05                    p=0.931
   ...
   ============================================================
   STAGE 3: GRAPH -- workload-dependency PageRank (gating score)
   ============================================================
     Top-10 gating workloads (frontier pretrains expected to dominate):
       GPT-Next pretrain shard 02                    score=0.0310
       Grok-Next pretrain shard 04                   score=0.0266
   ...
   ============================================================
   STAGE 4: PRESCRIPTIVE -- compute allocation MIP (24-cell sweep)
   ============================================================
     Latest refresh's solve of the 24-cell scenario sweep:
     Termination status: TIME_LIMIT
     Solve time:         240.0s
     Objective:          651,852,520.64
     Note: TIME_LIMIT means solver returned a feasible but not proven-optimal solution. Per-cell results below remain valid.

     Per-cell summary (24 cells: 16 feasible, 8 unsolved):
   envelope        margin                        diversity   status  n_assigned   revenue_usd  total_cost_usd  realized_margin  anchor_share ...
     100pct         80pct anchor_max_40pct_with_type_floor UNSOLVED           0          0.00            0.00              NaN           NaN ...
     100pct         80pct                 anchor_max_50pct FEASIBLE          74  2,473,858.46      490,512.99             0.80          0.49 ...
   ...
     100pct unconstrained                             none FEASIBLE         110 25,277,810.94    4,204,733.51             0.83          0.95 ...
   ...
     AllocationPlan singleton (queryable as ontology):
         plan_id envelope        margin diversity   status  n_assigned  revenue_usd  total_cost_usd  realized_margin  anchor_share   binding_axis
   DCCA_BASELINE   100pct unconstrained      none FEASIBLE         110  25277810.94    4.204734e+06         0.833659      0.947251 power_envelope
     Assignment.is_chosen rows: 110 (matches n_assigned above)

     DemandScenario overlay (chosen plan replayed under risk):
             scenario  factor  realized_revenue_usd  stranded_revenue_usd  stranded_pct
             expected    1.00         25,277,810.94                  0.00          0.00
   diffusion_slowdown    0.85         25,077,803.64            200,007.30          0.79
        scaling_break    0.70         24,877,796.35            400,014.59          1.58
        frontier_loss    0.50         24,611,119.95            666,690.99          2.64
   ```

   The report prints all four stages and the demand overlay; the lines above are trimmed. The GNN is stochastic, so the utilization probabilities shift from one training run to the next; the structural outcome reproduces: the frontier pretrains rank first, the baseline cell assigns all 110 workloads, and the margin and diversity cliffs sit at the same cells. The solve above is the open-source HiGHS default, which returns a feasible solution at its `SOLVER_TIME_LIMIT_SEC` of 240 seconds and reports `TIME_LIMIT` (signal, not failure), so each refresh takes about that long and the cells are labelled FEASIBLE or UNSOLVED. With Gurobi, the solve reaches `OPTIMAL` in seconds and the cells are labelled OPTIMAL or INFEASIBLE; set `SOLVER` in `model/reasoning.py` to switch. The full printout and a step-by-step walkthrough are in `runbook.md`.

   To predict and solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.DATACENTER_COMPUTE_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

8. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas, with the GNN's experiments and registered versions in the public schema.

## Template structure

```text
datacenter_compute_allocation/
  model/
    __init__.py                     # exports for train.py and the query
    schema.py                       # concepts, GNN task relationships
    source.py                       # bundled CSVs, demand scenarios, base facts
    reasoning.py                    # GNN, rules, PageRank, allocation MIP, cell outcomes, plan
  train.py                          # trains the GNN and registers its version
  queries/
    allocation_report.py            # per-stage diagnostics, per-cell summary, frontiers, plan, overlay
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
    power_envelope_levels.csv       # 2 scenario rows (envelope multiplier)
    margin_floors.csv               # 3 scenario rows (gross margin floors)
    diversity_caps.csv              # 4 scenario rows (anchor concentration caps)
  README.md                         # this file
  runbook.md                        # multi-reasoner agent-skill walkthrough
  pyproject.toml                    # dependencies
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the four-stage report, or follow `runbook.md` to rebuild it step by step.

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
- **`power_envelope_levels.csv` / `margin_floors.csv` / `diversity_caps.csv`** — the three scenario-axis tables (2 / 3 / 4 rows) that index the 24-cell sweep.

## Model overview

One shared ontology threads all four stages: each stage reads concepts and properties earlier stages wrote and writes new ones for downstream stages.

- **Key entities**: `DataCenterRequest` (a campus), `GpuPool`, `AILab`, `Workload`, `WorkloadGpuCompat` and `WorkloadDependency` (workload relationships as their own concepts), the three scenario concepts `PowerEnvelopeLevel` / `MarginFloor` / `DiversityCap`, plus the derived `WorkloadForecast` (the GNN's probability), `Compatibility` and `Assignment` (decision space), `ScenarioCell` (one row per scenario cell), the `AllocationPlan` singleton, and the `DemandScenario` overlay.
- **Primary identifiers**: string ids on `DataCenterRequest`, `GpuPool`, `AILab`, and `Workload`; the scenario concepts are identified by `name`; `WorkloadForecast` by workload id; `WorkloadGpuCompat`, `WorkloadDependency`, `Compatibility`, `Assignment`, and `ScenarioCell` carry composite keys.
- **Important invariants**: `envelope_multiplier`, `fraction`, and `anchor_max_share` are fractions; a negative sentinel on `MarginFloor.fraction` / `DiversityCap.anchor_max_share` marks the unconstrained row (its constraint is skipped); the `is_high_utilization` label is binary; `Assignment.x_assign` decision variables are binary; power / cost / GPU counts are non-negative.

For the full concept and property definitions — the entity concepts and the three scenario concepts in `model/schema.py`, and the derived `WorkloadForecast` / `Compatibility` / `Assignment` / `ScenarioCell` / `AllocationPlan` / `DemandScenarioOutlook` concepts each stage writes in `model/reasoning.py` — `runbook.md` builds them step by step with the RAI skills.

## How it works

### Stage 1: Predictive — per-workload utilization-probability GNN

Binary node classification on `Workload`: predict the probability that each workload will be high-utilization (actually use its allocated capacity at high duty cycle) vs stall or be repaced. Stranded capacity (depreciation accruing without offsetting revenue) is the operator's biggest economic exposure, so this is the chain's load-bearing forward-looking signal.

The graph is heterogeneous with three cross-concept edge types: a `LabMetric → Workload` edge that carries lab-side recent activity into a workload's prediction neighborhood (a workload owned by a fast-ramping lab inherits its signal); the `WorkloadDependency.blocks` DAG shared with Stage 3, so a workload downstream of a high-utilization gating pretrain inherits signal through the dependency chain; and a load-bearing `LabMetric → LabMetric` edge between cross-lab same-date pairs sharing a workload type, which carries cross-lab co-movement (funding waves, supply shocks).

The task tables carry per-`(workload, observation_date)` historical labels. Each row is one monthly utilization observation, so the same workload appears in 7 training rows (one per historical month), giving the GNN per-period variety to learn from instead of a single label per entity — Train (7 months × 110 = 770) / Val (1 month × 110 = 110) / Test (current month × 110, no label, so every workload gets a probability for the upcoming period). The task relationships use `at` time slots and the GNN runs with `has_time_column=True` so LabMetric features are time-aligned with each (workload, month) prediction. The positive-class probability is written to the ontology as `WorkloadForecast.utilization_probability`, on a concept of its own because the GNN reads the `Workload` table, and consumed by Stage 4's objective.

### Stage 2: Rules — eligibility + priority tiers + Compatibility precompute

Two rule families run on the workload-pool product. The eligibility rule joins through the `WorkloadGpuCompat(workload, gpu_type)` composite-key concept (per the GNN-node FD trap: multi-valued allowlists on a GNN-node concept must live as their own concept, not as a Workload Relationship) and enforces both the memory check and the GPU-type allowlist. Eligible pairs are then materialized into a `Compatibility(workload, gpu_pool)` concept — a precompute that keeps the Stage 4 MIP linear and small. Priority tier classification reads `AILab.contract_tier` and writes both `Workload.priority_tier` (string) and `Workload.priority_weight` (100 / 10 / 1) — the numeric form is what Stage 4's objective consumes.

### Stage 3: Graph — reverse-PageRank for downstream gating

A directed `Workload` graph is built with edge reversal (successor → predecessor) so a node's PageRank accumulates flow from everything it gates downstream. The resulting score lands on `Workload.gating_score`.

### Stage 4: Prescriptive — assignment MIP under a 3D Scenario sweep

The decision variable `Assignment.x_assign` is a binary variable indexed by the three scenario concepts (`PowerEnvelopeLevel`, `MarginFloor`, `DiversityCap`), so the MIP solves all 24 cells in a single pass. Constraint families run one per scenario axis:

- **C1+C2** at-most-one per workload per cell (soft P0; priority_weight = 100 drives P0 from the objective).
- **C3** per-pool GPU-count capacity.
- **C4** per-DC power envelope: `Σ gpu_count × power_per_gpu × pue ≤ approved_mw × 1000 × envelope_multiplier`.
- **C5** linearized gross-margin floor (skipped when `MarginFloor.fraction < 0` for the unconstrained row).
- **C6** anchor-concentration cap (skipped when `DiversityCap.anchor_max_share < 0`).
- **C7** workload-type floor (skipped unless `DiversityCap.workload_type_floor >= 0`).

The objective is what makes this a real chain rather than four disjoint reasoners: it maximizes the sum over chosen assignments of `priority_weight` (Stage 2) × `gating_score` (Stage 3) × `WorkloadForecast.utilization_probability` (Stage 1) × `strategic_value_usd` (raw $ baseline) — every prior stage's signal enters the same product. Only workloads with a forecast are assignable, so a refresh before a GNN version exists assigns nothing. The deployed model derives the per-cell summary from the solved values with ontology-side aggregation: one `ScenarioCell` row per cell, with its revenue, cost, margin, anchor share, and per-type and per-tier counts, and a status that is OPTIMAL or INFEASIBLE when the solve proved optimality and FEASIBLE or UNSOLVED when it stopped at its time limit. The chosen baseline cell (`100pct / unconstrained / none`) is persisted as a singleton `AllocationPlan` concept with revenue / total_cost / margin / anchor_share / n_assigned / status / binding_axis, plus an `Assignment.is_chosen` flag over its decision rows.

Finally, a `DemandScenario` overlay replays the locked-in plan under four risk scenarios. Anchor (P0) revenue is treated as contractual (factor 1.0) — the operator gets paid for the seat regardless of utilization — while opportunistic (P1/P2) seats realize only the scenario factor of their assigned revenue. The overlay reports realized and stranded revenue per scenario and persists each as a `DemandScenarioOutlook(scenario)` concept row, so the stranded-capacity exposure of the chosen plan is queryable as ontology, not just printed.

See `model/reasoning.py` for the implementation and `runbook.md` to reproduce each stage step by step with the RAI skills.

## Customize this template

### Use your own data

- Add or remove campuses by editing `data_centers.csv`. The bundled set is a snapshot of the upstream $300M-approved campuses; re-running `energy_grid_planning` at a different `InvestmentLevel` produces a different approved set you can copy in.
- Adjust the lab roster in `ai_labs.csv`. The anchor flag drives the `DiversityCap` constraint.

### Tune parameters

- Tune the scenario axes: edit `power_envelope_levels.csv`, `margin_floors.csv`, and `diversity_caps.csv`. Adding rows scales the cell count multiplicatively.
- Change the priority spread by editing the weights in the Stage 2 rules of `model/reasoning.py` (default 100 / 10 / 1).

### Extend the model

- Add a fourth GNN edge type, a new dependency relation, or extra scenario axes; the accretive-ontology pattern means downstream stages pick up new signals without restructuring.

### Scale up / productionize

- Tune the Stage 4 solve by adjusting `SOLVER` or `SOLVER_TIME_LIMIT_SEC` in `model/reasoning.py`. The default works on any prescriptive engine; faster commercial solvers (when licensed) can reach OPTIMAL in a fraction of the time.
- Replace the bundled CSVs with CDC ingestion from the operator's inventory, telemetry, and contract systems; the ontology shape is independent of the load pipeline.

## Troubleshooting

<details>
<summary><code>Experiment tracking database ... does not exist or is not accessible</code> when training</summary>

The GNN keeps its experiments and registered versions in the public schema named in `raiconfig.yaml`, and the RAI Native App needs USAGE on its database and schema plus CREATE EXPERIMENT and CREATE MODEL on the schema. Run the setup grants from the [Quickstart](#quickstart) as an administrator, then run `python train.py` again.
</details>

<details>
<summary>The report prints <code>(no predictions returned)</code></summary>

The deployed model has not refreshed since a version was registered: the refresh that `rai models deploy` waits for runs before `python train.py`. Run `python train.py` if you haven't, then the refresh call from step 6 of the Quickstart, and query again.
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

Expected at the default `time_limit_sec=240`. Per-cell numbers remain valid with `TIME_LIMIT` (`rai-prescriptive-results`: `TIME_LIMIT` is signal, not error). Raise `SOLVER_TIME_LIMIT_SEC` or switch to a faster solver in `model/reasoning.py` if you need a tighter MIP gap.
</details>

<details>
<summary>Per-cell summary shows all cells <code>INFEASIBLE</code></summary>

Likely an upstream constraint (C5 / C6 / C7) firing at unintended cells. Check that the `-1.0` NULL-handling sentinels are filtered correctly in C5 / C6 / C7's `model.where(... .fraction >= 0.0 ...)` clauses.
</details>

<details>
<summary>Per-workload utilization probabilities do not match the README's distribution</summary>

The GNN is stochastic, so the probabilities shift from one training run to the next, and a different `seed` or `n_epochs` in `model/reasoning.py` changes them too. The structural outcome (frontier pretrains near the top, evals near the bottom) reproduces.
</details>

## What this template abstracts

This is a snapshot allocator, not a production scheduler. Workloads are assigned to a single `(Workload, GpuPool)` slot — gang scheduling, topology-aware placement, time-block reservations, and elastic sizing are out of scope. Utilization is modeled as a per-workload point estimate; per-workload (p10, p50, p90) bands would be a natural extension, with the scenario sweep providing the aggregate-level approximation today.

## Learn more

- Upstream template: [energy_grid_planning](https://github.com/RelationalAI/templates/tree/main/energy_grid_planning) — the multi-year capex / interconnect decision that approves which campuses get built and energized.
- Peer multi-reasoner: [telco_network_recovery](https://github.com/RelationalAI/templates/tree/main/telco_network_recovery) — same accretive-chain pattern in a tower-upgrade context, using a binary-classification GNN + three-branch rule + PageRank + MIP.
- RelationalAI documentation: <https://docs.relational.ai>

## Support

- File issues at <https://github.com/RelationalAI/templates/issues>.
- Reach the RAI team via the support channels listed at <https://relational.ai>.
