---
title: "Telco Network Recovery"
description: "Tower-upgrade planning on a shared telco ontology: an equipment-failure graph neural network (GNN) over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, and customer-impact analysis (revenue times churn, with PageRank)."
featured: false
experience_level: advanced
industry: "Technology & Telecom"
reasoning_types:
  - Predictive
  - Rules-based
  - Graph
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - GNN
  - Heterogeneous Graph
  - PageRank
  - Network Operations
  - Capacity Planning
  - Telco
---

## What this template is for

A regional telco operator must allocate a fixed capex budget across cell towers in the face of two distinct risk signals. Some towers are visibly broken (degraded status, packet loss, equipment health), and a declarative rule can find them. Others look fine on their own measurements but sit on equipment models that just received a manufacturer recall, defect-batch notice, or end-of-life advisory — they won't fail today, but they will fail soon. Neither signal alone gives a defensible spending plan.

This template chains RelationalAI's reasoners — predictive, rules-based, graph, and prescriptive — through a shared ontology to produce that plan: which towers to upgrade at which tier, within budget and crew constraints, weighted by the revenue and churn risk that sits behind each tower. The result is operator-credible (it answers *"how much revenue at risk would relaxing this constraint protect?"*) without leaving the ontology.

## Who this is for

- Telco network operations and capital planning teams.
- Operations researchers exploring multi-reasoner pipelines in RelationalAI.
- Developers learning heterogeneous-graph graph-neural-network (GNN) modeling on a multi-concept ontology.
- **Assumed knowledge**: comfortable reading Python; the telco, GNN, graph, and optimization terms are explained as they come up. As an advanced multi-reasoner template, it goes faster if you have followed a single-reasoner template first, but no deep RelationalAI experience is required to run it.

## What you'll build

- A funded tower-upgrade plan that maximizes restored capacity weighted by customer impact and predicted failure risk, within a fixed capex envelope and crew-week cap.
- A per-tower selection rationale (`operational` / `advisory/predicted` / `high-value`) explaining why each chosen tower made the cut.
- A shared ontology that grows accretively — every stage's output becomes a queryable property the next stage reads, with no DataFrame ping-pong between reasoners.
- A `RestorePlan` singleton plus an `is_selected_upgrade` view, both queryable as ontology after the run.

Built using **predictive reasoning** (GNN on a heterogeneous graph), **rules-based classification** (multi-branch derived flag), **graph analysis** (PageRank + per-tower aggregation), and **prescriptive reasoning** (mixed-integer programming).

## What's included

- **Model**: a 5-stage pipeline (predictive, then rules, then graph, then paths, then prescriptive) on a single shared ontology, in the `model/` package (`schema.py` declares the 8 source-data concepts and the GNN task relationships, `source.py` loads the bundled CSVs, the equipment split and the most severe advisory per MODEL, and a module per stage states its rules: `equipment_failure.py` the GNN (with `advisory_signals.py` for the advisory coverage figures), `critical_towers.py` the critical-tower rules, `customer_impact.py` the PageRank and customer impact, `call_paths.py` the call paths, and `tower_upgrades.py` the upgrade MIP). `rai models deploy --path model` deploys it to your Snowflake account, where each refresh scores the equipment, derives the critical towers, and solves the upgrade MIP.
- **Training**: `train.py` — trains the equipment-failure GNN over the deployed splits and registers its version.
- **Query**: `queries/recovery_report.py` — prints the per-stage diagnostics and the plan from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code itself.
- **Sample data**: 250 cell towers, 1,500 equipment items, 8 manufacturer advisories on 7 MODELs, 1,200 subscribers, 6,000 call records, 750 upgrade options. See *Sample data* below.
- **Outputs**: per-stage stdout diagnostics plus an ontology-resident `RestorePlan` singleton holding cost, capacity, install-weeks, tier mix, towers covered, and binding constraint.

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
GRANT USAGE ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON ALL VIEWS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO ROLE <PAT_ROLE>;
GRANT USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO ROLE <PAT_ROLE>;
GRANT CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO ROLE <PAT_ROLE>;
GRANT CALLER USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT, INSERT ON ALL TABLES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE ON ALL FILE FORMATS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE, MODIFY ON ALL EXPERIMENTS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER OWNERSHIP ON ALL MODELS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
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
CREATE SCHEMA IF NOT EXISTS <DB>.TELCO_NETWORK_RECOVERY;
CREATE SCHEMA IF NOT EXISTS <DB>.TELCO_NETWORK_RECOVERY_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.TELCO_NETWORK_RECOVERY_META TO APPLICATION <RAI_APP_NAME>;

```

Use this sequence to deploy the model, train the GNN, and query the recovery plan:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/telco_network_recovery.zip), unzip it, and enter the template directory:

   ```bash
   unzip telco_network_recovery.zip
   cd telco_network_recovery
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
       name: telco_failure_gnn          # created on first use if it doesn't exist
       gnns:
         equipment_failure:             # the GNN's name in model/equipment_failure.py
           registry: <DB>.TELCO_NETWORK_RECOVERY
           model: EQUIPMENT_FAILURE
           version: V1                  # train.py registers this version
     prescriptive:
       name: telco_recovery_solver      # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.TELCO_NETWORK_RECOVERY          # published views and tables
     identity:
       internal_schema: <DB>.TELCO_NETWORK_RECOVERY_META # solver inputs, results, refresh procedures
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

   The deploy creates the reasoners and the public schema named in `raiconfig.yaml` if they don't exist and waits for the model's first refresh, which loads the data and runs the rules, the graph analysis, and the upgrade solve. No version of the GNN is registered yet, so this refresh makes no failure predictions.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts with this version and solves again over those predictions: `CALL <DB>.TELCO_NETWORK_RECOVERY_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `<DB>`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the diagnostics and the plan from the deployed model:

   ```bash
   python -m queries.recovery_report
   ```

   ```text
   Equipment split: train=1050 val=225 test=1500 (all)
   Label distribution: at_risk=1 597 / 1500 (39.8%)
   Advisories: 7 on 7 distinct models
   ...
   ============================================================
   STAGE 1: PREDICTIVE -- equipment-failure binary classification GNN
   ============================================================

     Top 10 towers by predicted failure intensity (sum of equipment failure probs):
   TOWER_ID  FAILURE_INTENSITY
   TWR-0021             8.9240
   TWR-0159             8.5622
   TWR-0067             7.3455
   ...

     failure_intensity distribution: min=0.05, median=2.93, max=8.92
     Towers with failure_intensity > 1.5: 156 / 190
   ...
   ============================================================
   STAGE 2: RULES -- flag is_critical_restore towers
   ============================================================

     Flagged critical_restore towers: 158
   ...
   ============================================================
   STAGE 4: PATHS -- Call-path enumeration from the seed hub
   ============================================================

     Seed scope: 1 highest-PageRank hub(s) ['SUB-CON-00900']; enumeration <= 3 hops, simple paths only.
     Simple call paths enumerated from the seed hub(s): 198
     Distinct routing towers recovered across those paths: 54
     Top influence-weighted call path (PageRank sum 0.009041): SUB-CON-00900 -> SUB-CON-00814 -> SUB-ENT-0038 -> SUB-CON-00644 via towers [NexusStream-ton-94, NexusStream-borough-113, NexusStream-view-55]

   ============================================================
   STAGE 5: PRESCRIPTIVE -- tower upgrade selection MIP
   ============================================================

   Solve result:
   • status: OPTIMAL
   • objective: 1062056637.585094

     Selected upgrades: 26
   ...
     Total cost:               $4,993,173
     Total install crew-weeks: 168
     Capacity restored:        179 Gbps
     Tier mix:                 {'GOLD': 9, 'SILVER': 5, 'BRONZE': 12}
     Towers covered:           26 of 158 critical
   ...
   PIPELINE COMPLETE: 5 stages read from the deployed Telco ontology
   ```

   The report prints all five stages; the lines above are trimmed. The GNN is stochastic, so the predicted figures, the critical-tower count, and the plan shift from one training run to the next; on the bundled data, runs have ended with status OPTIMAL, the budget binding (about $4.99M of $5M), and all 5 regions covered, though a different trained model can change that. The model keeps the highest-severity advisory for each MODEL, so the data summary counts the eight advisories in the CSV as seven. `runbook.md` walks through each stage.

   To predict and solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.TELCO_NETWORK_RECOVERY_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                       # this file
├── runbook.md                      # analyst-facing paste-testable walkthrough
├── pyproject.toml                  # dependencies
├── model/
│   ├── __init__.py                 # exports for train.py and the query
│   ├── schema.py                   # concepts, GNN task relationships, plan relationships
│   ├── source.py                   # bundled CSVs and the equipment split
│   ├── equipment_failure.py        # at-risk label, GNN, tower failure intensity, training and score figures
│   ├── advisory_signals.py         # advisory counts and the equipment the advised MODELs cover
│   ├── critical_towers.py          # tower averages, the three restore branches, branch and region counts
│   ├── customer_impact.py          # PageRank, customer value, per-tower impact
│   ├── call_paths.py               # call-path enumeration from the seed hub
│   └── tower_upgrades.py           # upgrade MIP, plan summary, and rationale tally
├── train.py                        # trains the GNN and registers its version
├── queries/
│   └── recovery_report.py          # per-stage diagnostics and the plan
└── data/
    ├── cell_towers.csv             # 250 towers across 5 regions (15 WEST DEGRADED)
    ├── network_equipment.csv       # 1,500 equipment installs, 18 MODELs
    ├── equipment_health.csv        # 1,500 per-equipment health snapshots
    ├── network_performance.csv     # 5,000 per-tower measurements
    ├── subscribers.csv             # 1,200 subscribers (consumer + enterprise)
    ├── call_detail_records.csv     # 6,000 directed CDRs
    ├── tower_upgrade_options.csv   # 750 (tower, tier) options
    ├── model_advisories.csv        # 8 manufacturer advisories on 7 MODELs
    └── _synthesize_advisory_data.py  # reproducibility script for the synthetic data
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the five-stage report, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is **synthetic and illustrative** — designed to teach the reasoning flow on a Snowflake-connected RAI account, not to match a specific operator's network. The data does not yet model site / sector / band / radio-unit / vendor / backhaul attributes that a production network catalog carries; those are extension points (see *Customize this template*), not gaps in the reasoning pattern.

- **`cell_towers.csv`** (250 rows) — towers across 5 regions; 15 WEST towers are explicitly `DEGRADED`.
- **`network_equipment.csv`** (1,500 rows) — equipment installs across 18 consolidated MODELs (manufacturer x model name); each links to one tower.
- **`equipment_health.csv`** (1,500 rows) — per-equipment health snapshot (mean time between failures (MTBF) hours, failure rate, temperature, power, health score).
- **`network_performance.csv`** (5,000 rows) — per-tower performance measurements (latency, throughput, packet loss, jitter, signal strength, utilization).
- **`subscribers.csv`** (1,200 rows) — 1,150 `CONSUMER` + 50 `ENTERPRISE` accounts with `LIFETIME_VALUE_USD`, `CHURN_RISK_SCORE`, `SEGMENT`, `STATUS`. Enterprise lifetime value (LTV) averages ~130x consumer, so the customer-impact aggregation in Stage 3 weights heavily toward enterprise-bearing towers — realistic for capex prioritization.
- **`call_detail_records.csv`** (6,000 rows) — directed call records (`caller -> callee`), each routed through a specific tower.
- **`tower_upgrade_options.csv`** (750 rows) — three BRONZE / SILVER / GOLD options per tower with capacity, cost, and install-week deltas.
- **`model_advisories.csv`** (8 rows) — manufacturer advisories (`RECALL` / `DEFECT_BATCH` / `EOL` / `FIRMWARE_BUG` / `SECURITY_PATCH`) on 7 MODELs, with severities `0.50–0.95`.

**Source-system mapping (notional).** In a real operator deployment these tables arrive from different upstream systems via change-data-capture, not a single export:

| Snowflake table         | Notional source system            | Update cadence |
|-------------------------|-----------------------------------|----------------|
| `CELL_TOWERS`           | Network inventory / NEM           | weekly         |
| `NETWORK_EQUIPMENT`     | EMS / asset management            | daily          |
| `EQUIPMENT_HEALTH`      | EMS / NMS performance subsystem   | hourly         |
| `NETWORK_PERFORMANCE`   | NMS / OSS performance probes      | minutes        |
| `MODEL_ADVISORIES`      | Vendor portals (Ericsson, Nokia…) | ad hoc         |
| `CALL_DETAIL_RECORDS`   | Mediation / billing               | hourly         |
| `SUBSCRIBERS`           | CRM / billing                     | daily          |
| `TOWER_UPGRADE_OPTIONS` | CAPEX planning / vendor catalog   | quarterly      |

The ontology shape is independent of the load pipeline.

## Model overview

One shared ontology threads all five stages. Each stage reads concepts and properties earlier stages wrote, and writes new ones for downstream stages.

- **Key entities**: `CellTower`, `NetworkEquipment`, `EquipmentHealth`, `NetworkPerformance`, `ModelAdvisory`, `Subscriber`, `CallDetailRecord`, `TowerUpgradeOption`; plus the derived `TowerFailureScore` (bridge for the GNN output) and `RestorePlan` (singleton plan headline).
- **Primary identifiers**: string ids on the base entities (e.g. `TOWER_ID`, `EQUIPMENT_ID`, `SUB_ID`); composite key on `TowerUpgradeOption` (`tower_id` + `tier`); MODEL string on `ModelAdvisory`.
- **Important invariants**: `severity`, `churn_risk_score`, and `health_score` are fractions in `[0, 1]`; `capacity_gbps` and `cost` are non-negative; the GNN's `at_risk` label is `1` if `STATUS` is `FAILING` or `WARNING`; Stage 5 decision variables are binary.

For the full concept and property definitions, see `model/`; `runbook.md` builds them step by step with the RAI skills.

## How it works

**Stage 1 — Predictive (GNN).** A binary `at_risk` classifier message-passes over three heterogeneous edges on an undirected graph (`EquipmentHealth -> NetworkEquipment -> CellTower`, plus `ModelAdvisory -> NetworkEquipment` via shared MODEL). The undirected setting matters: bidirectional message passing lets the GNN reach tower-mate equipment via 2-hop paths through `CellTower`, so the *"my tower-mate sits on a recalled MODEL"* pattern is learnable. Per-equipment positive probabilities are summed per tower into `TowerFailureScore.failure_intensity`, a concept keyed by tower id.

**Stage 2 — Rules.** A three-branch `CellTower.is_critical_restore` flag fires when (1) `region == "WEST"` + `status == "DEGRADED"` + low avg equipment health, (2) WEST + high packet loss + low health, or (3) `failure_intensity > 1.5` (any region). Per-tower averages (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) are derived first from `NetworkPerformance` and a two-hop `EquipmentHealth -> NetworkEquipment -> CellTower` join.

**Stage 3 — Graph (customer impact analysis).** PageRank on the directed `Subscriber -> Subscriber` call graph lands on `Subscriber.influence_score` (the graph reasoner's network-effect signal). The headline per-tower measure is `CellTower.weighted_impact` — sum of `Subscriber.customer_value` (= `lifetime_value x (1 + churn_risk_score)`) across the distinct active callers (`Subscriber.status == SubscriberStatus.ACTIVE`) whose calls route through each tower; a caller counts once per tower however many calls it routes there. `weighted_pagerank` is the parallel PageRank-weighted view, exposed as a secondary signal queryable alongside the revenue-based headline.

**Stage 4 — Paths (PREVIEW).** Where Stage 3 scores a *subscriber*, the paths capability scores the *route*: from the top-PageRank hub (the smallest subscriber ID on an exact tie) it enumerates the simple call paths (up to three hops) over an arity-3 caller-via-tower-callee edge and ranks them by summed PageRank influence, rounded to six decimals. On the bundled data this is 198 simple call paths recovering 54 distinct routing towers. The model persists the hub's highest influence load as `Subscriber.top_call_path_influence` and publishes the winning route (the smallest path ID among paths with the same rounded load) through `TopCallPathStep` (its subscribers in order) and `TopCallPathHop` (the routing tower on each hop), which the report prints.

**Stage 5 — Prescriptive (MIP).** Binary `TowerUpgradeOption.selected`, scoped to critical-restore towers, with three constraints (at most one tier per tower, total cost at most $5M, total install-weeks at most 200). The objective maximizes restored capacity weighted by two upstream signals per tower — Stage 3's `weighted_impact` (revenue × churn) and Stage 1's `failure_intensity` (GNN-predicted risk) — so capacity spent on high-value, high-risk towers counts most.

After the solve, a `RestorePlan` singleton is populated and each selected option is tagged `is_selected_upgrade`. Every selected tower carries a `rationale` tag in the printed plan noting which upstream signal(s) drove its inclusion: `operational` (Stage 2 Branch 1 or 2 fired), `advisory/predicted` (Branch 3 fired), `high-value` (weighted impact in the top quartile of critical towers).

For the implementation, see the stage modules in `model/`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above.
- Regenerate the synthetic corpus: run `python _synthesize_advisory_data.py` in `data/`, then deploy again and train a new version. The generator uses a fixed seed, so it reproduces the bundled files; change its `SEED` for a different corpus.
- The subscriber `STATUS` column is enum-mapped: values must exactly match the `SubscriberStatus` member names (`ACTIVE` / `SUSPENDED`). `lookup()` cannot validate values that arrive from data columns — unrecognized values silently map to a nonexistent member, and those subscribers drop out of the Stage 3 customer-impact aggregates. Extend the enum if your feed has more statuses.
- For Snowflake-backed runs, replace the CSV reads in `model/source.py` with Snowflake reads that return pandas DataFrames: the seeded train/validation/test split and the advisory selection there run in pandas. The equipment frame needs its `STATUS` column, which the model turns into the `at_risk` label.
- The model derives `Subscriber.customer_value` from `lifetime_value` and `churn_risk_score` in `model/customer_impact.py`, so a subscriber feed needs both `LIFETIME_VALUE_USD` and `CHURN_RISK_SCORE`.

### Tune parameters

- **Budget envelope** — `BUDGET_USD` (default `$5,000,000`), `INSTALL_WEEKS_BUDGET` (default `200`).
- **Predictive threshold** — `FAILURE_INTENSITY_THRESHOLD` (default `1.5`) is Branch 3's cutoff for *"the GNN is confident multiple pieces are at risk."*
- **Customer-value formula** — the bundled formula is `LTV x (1 + churn_risk_score)`. Use `log1p(LTV) x (1 + churn)` to compress the enterprise-vs-consumer gap; multiply by an `NPS_SCORE`-derived factor for retention fragility; or add SLA-tier and emergency-service multipliers once those fields land on `subscribers.csv`.

### Extend the model

- **Add more advisories** — extend `data/model_advisories.csv` with new advisory types and severities; the GNN picks them up on the next training run.
- **Add a fourth GNN edge** — e.g., `NetworkEquipment -> SimilarEquipment` via shared `FIRMWARE_VERSION` or `MANUFACTURER` to test other heterogeneous-neighborhood patterns.
- **Add SLA-tier weighting** — add `SLA_TIER` / `is_emergency_service` columns to `subscribers.csv` and fold them into the `customer_value` rule in `model/customer_impact.py`; the rest of the chain is unchanged.
- **Add backhaul coupling** — model `BackhaulPath` / `AggregationNode` as Concepts and add a per-node capacity constraint to Stage 5 (`aggs.sum(selected * capacity).per(AggregationNode) <= node_headroom`).
- **Swap PageRank for another graph algorithm** — `weighted_pagerank` is the secondary network-effect signal; replace `call_graph.pagerank()` with `betweenness_centrality()` or `eigenvector_centrality()` to surface different structural roles without changing the optimizer.

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from the operator's upstream systems (see *Source-system mapping* under *Sample data* for the typical sources and cadences).
- The synthetic data assumes 250 towers / 1,500 equipment; the chain scales to whatever fits the prescriptive engine's solve budget. Tier mix and capacity numbers move roughly linearly with the budget envelope.

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
<summary>Stage 5 returns an infeasible status</summary>

All three Stage 5 constraints are upper bounds (at most one tier per tower, total cost, total install-weeks), so selecting no upgrades is always feasible with a nonnegative budget: a tight `BUDGET_USD` yields a smaller plan, not infeasibility. An infeasible status points at a constraint you added or at negative budget values.

</details>

<details>
<summary>The 15 WEST DEGRADED towers don't show up in Stage 5 selections</summary>

Only the ones whose average equipment health is below 0.85 fire Branch 1 (12 of the 15 on the bundled data); the others are flagged only if their predicted failure intensity crosses the Branch 3 threshold. Whether they're picked by Stage 5 depends on the multiplicative objective: a WEST tower with low `failure_intensity` (healthy equipment) and low `weighted_impact` (few high-value callers) gets a small objective contribution and may be deprioritized vs. higher-risk, higher-value towers elsewhere. This is the intended behavior of the chain.

</details>

<details>
<summary>The plan looks enterprise-heavy</summary>

The bundled subscriber data has 50 enterprise (~$300K LTV avg) vs. 1,150 consumer (~$3K LTV avg) accounts, so `weighted_impact` concentrates heavily on enterprise-bearing towers. This matches operator reality (enterprise SLAs drive capex). For a more balanced spread, swap the `customer_value` formula for `log1p(LTV) x (1 + churn)` or add a per-region minimum-coverage constraint to Stage 5 — both are tuning knobs, not redesigns.

</details>

<details>
<summary>Using Gurobi instead of HiGHS</summary>

The model solves with HiGHS, an open-source solver that needs no license. Where Gurobi is licensed, change `problem.configure("highs", ...)` in `model/tower_upgrades.py` to `problem.configure("gurobi", ...)` and deploy again.

</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chained reasoner patterns and ontology enrichment.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `aggs` / `.define()`.

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) — heterogeneous-graph classification, PropertyTransformer, edge patterns.
- [Graph reasoner](https://docs.relational.ai/) — node-concept and edge-concept patterns, PageRank and centrality.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.

## Support

- File issues at the RelationalAI templates repository.
