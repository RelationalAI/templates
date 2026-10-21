# Partner Demo Runbook: Telco Network Recovery

Audience: AE and SE implementation partners  
Demo goal: show how RelationalAI turns raw operational data into a deployed semantic model, then uses that model as the stable input layer for predictive, graph/path, and optimization workflows.

## Core Story

A regional telco has a fixed capex budget and limited install capacity. Some towers are visibly degraded, but others are at risk because their installed equipment shares models with vendor advisories. Customer impact also varies sharply by tower because enterprise subscribers and high-churn accounts are not distributed evenly.

The demo answer is not just "run an optimizer." The implementation pattern is:

1. Model the business domain as an ontology.
2. Deploy the stable ontology into Snowflake as queryable semantic tables.
3. Use Modeler UI to inspect and explain the deployed schema.
4. Run advanced reasoners and scripts against the deployed semantic tables, not raw CSV/source tables.
5. Write reasoner outputs back as result tables that can feed the next step or be surfaced to applications.

## What to Emphasize

RelationalAI is useful when the customer problem has multiple forms of reasoning over the same connected data:

- **Ontology/modeling:** translate raw tables into business concepts and relationships.
- **Rules:** encode explainable operational logic, such as "WEST degraded towers with poor health are critical restore."
- **Predictive:** learn equipment failure risk from equipment health, tower context, and manufacturer advisories.
- **Graph/path analysis:** reason over subscriber call topology and customer impact.
- **Prescriptive optimization:** decide which tower upgrades to fund under budget and crew constraints.
- **Deployment:** materialize the semantic model into Snowflake so downstream work reads stable concept tables instead of fragile raw feeds.

## Current Architecture

```text
BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE
  Raw Snowflake source tables loaded from the bundled CSV data
        |
        | telco_base_ontology.py
        | rai models deploy --wait
        v
BERTOLANI.TELCO_NETWORK_RECOVERY
  Deployed semantic tables:
  CELLTOWER, NETWORKEQUIPMENT, EQUIPMENTHEALTH, MODELADVISORY,
  NETWORKPERFORMANCE, SUBSCRIBER, CALLDETAILRECORD, TOWERUPGRADEOPTION,
  CELLTOWER_OPERATIONAL_CRITICAL_RESTORE, ...
        |
        | standalone reasoner jobs
        v
BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS
  SUBSCRIBER_INFLUENCE
  TOWER_CUSTOMER_IMPACT
  TOP_CALL_PATH
  TOWER_FAILURE_SCORE
  EQUIPMENT_FAILURE_PREDICTION
  SELECTED_UPGRADES
  RESTORE_PLAN
```

Use [raiconfig.yaml](raiconfig.yaml) for deploy mode. It intentionally has `oplog.enabled: true`, `deployment.outputs.type: table`, and a deployment schema of `BERTOLANI.TELCO_NETWORK_RECOVERY`.

Use [raiconfig_reasoners.yaml](raiconfig_reasoners.yaml) for standalone reasoner execution. It intentionally has no `deployment` or `oplog` section. This matters because predictive and eager prescriptive jobs should execute outside deploy mode while reading the deployed semantic tables.

## Base Ontology

The deployed ontology lives in [telco_base_ontology.py](telco_base_ontology.py). It is deliberately limited to stable domain facts and rules that should be shared across applications:

- `CellTower`: tower identity, location, region, status, capacity, performance rollups.
- `NetworkEquipment`: installed equipment, model, manufacturer, firmware, status, link to tower.
- `EquipmentHealth`: per-equipment health measurements linked to equipment.
- `ModelAdvisory`: vendor recalls, defect notices, EOL, firmware/security advisories linked to affected equipment models.
- `NetworkPerformance`: tower performance events and quality metrics.
- `Subscriber`: customer account, segment, LTV, churn risk, status, derived `customer_value`.
- `CallDetailRecord`: caller, callee, routed-through tower.
- `TowerUpgradeOption`: tower/tier choices with cost, install weeks, and capacity increase.

The base ontology also deploys operational rules:

- `CellTower.avg_packet_loss`
- `CellTower.avg_latency_ms`
- `CellTower.avg_error_rate`
- `CellTower.avg_health_score`
- `CellTower.operational_critical_restore`

Talk track: "The ontology is where we stop thinking in raw table names and start thinking in business nouns. It also makes relationships explicit: equipment is installed on towers, health is measured for equipment, advisories apply to equipment models, and calls route through towers."

## Demo Agenda

Plan for 60 minutes with 10 minutes of buffer.

| Time | Segment | Purpose |
|---:|---|---|
| 0-5 | Business setup | Establish the telco capex recovery problem. |
| 5-15 | Source data to ontology | Show raw tables, then concepts and relationships in `telco_base_ontology.py`. |
| 15-25 | Deploy and Modeler UI | Show deployed semantic tables and the model visualization. |
| 25-40 | Reasoner chain | Run/explain GNN, PageRank/customer impact, paths, optimization. |
| 40-50 | Results | Inspect selected upgrades and restore plan. |
| 50-60 | Partner implementation pattern | Generalize the method partners can use with customers. |

## Measured Code Timings

Measured with `/usr/bin/time -p` in `/Users/stevebertolani/software/templates/v1/telco_network_recovery`.

| Code step | Command | Measured wall time | Notes |
|---|---|---:|---|
| Source table load | `../../.venv/bin/python load_raw_tables.py` | 5.68s | Warm/no-op run; all source tables already existed and were skipped. |
| Base ontology deploy | `env -u DEBUG ../../.venv/bin/rai models deploy --wait` | 12.03s | Warm/no-change deploy; refresh completed and no oplog changes were recorded. |
| Graph/PageRank | `run_graph_impact.py` | 12.00s | Wrote 1,200 `SUBSCRIBER_INFLUENCE` rows and 120 `TOWER_CUSTOMER_IMPACT` rows. |
| Paths | `run_paths.py` | 5.40s | Wrote 1 `TOP_CALL_PATH` row. |
| Predictive GNN | `run_predictive_failure.py` | 366.61s | Cold-ish reasoner readiness dominated: readiness was 214.56s; GNN prediction block reported 91.83s. Wrote 190 tower scores and 1,500 equipment predictions. |
| Optimization | `run_optimization.py` | 227.48s | Parallel init was 1m23s; HiGHS solve time was 0.17s after Gurobi license fallback. Wrote 26 selected upgrades and 1 restore plan. |
| Result SQL inspection | four result queries in this runbook | 2.76s | Returned 1 restore plan row, 26 selected upgrades, and two top-10 result sets. |

If everything is run live, budget about **10m32s of wall-clock code time** in this environment. For a smoother 60-minute partner demo, pre-run GNN and optimization, then rerun only deploy, graph/path, and result queries live. That keeps live code execution to roughly **30-40 seconds** while still showing the long-running scripts and their materialized outputs.

Recommended live pacing:

| Segment | Recommended live time | Live-code stance |
|---|---:|---|
| Business setup | 5 min | No code. |
| Source data and ontology | 8 min | Show source tables and `telco_base_ontology.py`; do not reload unless needed. |
| Deploy and Modeler UI | 10 min | Run deploy live if the environment is ready; measured warm deploy is 12s. |
| Standalone architecture | 5 min | Show `raiconfig.yaml` vs `raiconfig_reasoners.yaml`. |
| Graph/PageRank and paths | 7 min | Safe to run live; measured combined time is 17.40s. |
| GNN | 8 min | Prefer pre-run. Explain script and show result tables; live run measured 6m07s. |
| Optimization | 7 min | Pre-run if time is tight; live run measured 3m47s, mostly init. |
| Results and implementation pattern | 10 min | Run result SQL live; measured 2.76s. |

## Demo Prep

Run this before the live session so Snowflake objects and result tables are already warm.

```bash
cd /Users/stevebertolani/software/templates/v1/telco_network_recovery

# Optional if source tables need to be rebuilt.
../../.venv/bin/python load_raw_tables.py

# Deploy the base ontology as Snowflake tables.
../../.venv/bin/rai models deploy --wait

# Run standalone jobs over the deployed schema.
RAI_CONFIG_FILE_PATH=$PWD/raiconfig_reasoners.yaml env -u DEBUG ../../.venv/bin/python run_graph_impact.py
RAI_CONFIG_FILE_PATH=$PWD/raiconfig_reasoners.yaml env -u DEBUG ../../.venv/bin/python run_paths.py
RAI_CONFIG_FILE_PATH=$PWD/raiconfig_reasoners.yaml env -u DEBUG ../../.venv/bin/python run_predictive_failure.py
RAI_CONFIG_FILE_PATH=$PWD/raiconfig_reasoners.yaml env -u DEBUG ../../.venv/bin/python run_optimization.py
```

Expected result-table counts from the current run:

```text
SUBSCRIBER_INFLUENCE: 1200
TOWER_CUSTOMER_IMPACT: 120
TOP_CALL_PATH: 1
TOWER_FAILURE_SCORE: 190
EQUIPMENT_FAILURE_PREDICTION: 1500
SELECTED_UPGRADES: 26
RESTORE_PLAN: 1
```

If deploy type issues appear after a Snowflake schema change, remove the cached schema under `./build` and rerun deploy. That forces a fresh Snowflake schema read.

## Live Walkthrough

### 1. Open With the Business Problem

Say:

"We are a regional telco. We need to decide which towers to upgrade under a fixed capex budget and install-week constraint. We have operational health, network performance, subscriber value, call routing, tower upgrade options, and vendor advisories. The interesting part is that no single table answers the question."

Show the source systems:

- Network inventory: towers and equipment.
- EMS/NMS: health and performance.
- Vendor portals: model advisories.
- CRM/billing: subscribers.
- Mediation: call detail records.
- CAPEX planning: upgrade options.

Partner point: real customer projects start here. Do not start by asking "which algorithm?" Start by asking "what decisions must the customer make, and what concepts support that decision?"

### 2. Show the Ontology

Open [telco_base_ontology.py](telco_base_ontology.py) and show:

- Concept declarations.
- Identity choices.
- Functional relationships such as `NetworkEquipment.tower`, `EquipmentHealth.equipment`, and `CallDetailRecord.routed_through`.
- Derived business properties such as `Subscriber.customer_value`.
- Operational critical-restore rules.

Say:

"The ontology gives us a shared language. `CellTower`, `NetworkEquipment`, `Subscriber`, and `CallDetailRecord` are not just table aliases. They are typed business concepts with relationships the reasoners can use."

Implementation partner lesson:

- Keep the base ontology stable and explainable.
- Put durable business rules in the base model.
- Put experimental or heavy reasoner calculations in separate jobs that read the deployed tables.

### 3. Deploy and Show Modeler UI

Use deploy mode:

```bash
../../.venv/bin/rai models deploy --wait
```

Then show `BERTOLANI.TELCO_NETWORK_RECOVERY` in Snowflake or Modeler UI.

Suggested Modeler UI path:

1. Open the deployed model/schema visualization.
2. Point to `CellTower` as the central operational entity.
3. Follow `NetworkEquipment -> CellTower`.
4. Follow `EquipmentHealth -> NetworkEquipment`.
5. Follow `ModelAdvisory -> NetworkEquipment`.
6. Follow `CallDetailRecord -> Subscriber` and `CallDetailRecord -> CellTower`.
7. Show `TowerUpgradeOption -> CellTower`.

Say:

"This visualization is the implementation handoff artifact. Partners can use it with business users to validate that the model says what they think the business says."

Partner point:

"The deployed schema is also the contract for downstream apps and reasoners. From this point forward, we stop reading raw CSV/source tables for reasoning workflows."

### 4. Explain the Standalone Reasoner Pattern

Show [reasoner_common.py](reasoner_common.py), [raiconfig_reasoners.yaml](raiconfig_reasoners.yaml), and the four standalone scripts.

Say:

"The base ontology is deployed. The standalone jobs use the deployed semantic tables as inputs. This is the path we want partners to internalize: model once, deploy the business layer, then run reasoners on top of that layer."

Important distinction:

- `raiconfig.yaml`: deploy config, includes `deployment` and `oplog`.
- `raiconfig_reasoners.yaml`: eager reasoner config, no `deployment`, no `oplog`.

### 5. Predictive Stage: Equipment Failure GNN

Script: [run_predictive_failure.py](run_predictive_failure.py)

Inputs:

- `CELLTOWER`
- `NETWORKEQUIPMENT`
- `EQUIPMENTHEALTH`
- `MODELADVISORY`

Outputs:

- `TOWER_FAILURE_SCORE`
- `EQUIPMENT_FAILURE_PREDICTION`

Talk track:

"The GNN answers: which equipment items are likely at risk, using both local health metrics and graph context. Equipment on the same tower can influence one another, and vendor advisories propagate through shared equipment models."

Show:

- Undirected graph edges: health to equipment, equipment to tower, advisory to equipment.
- `PropertyTransformer` feature groups.
- Per-equipment predictions rolled up to tower-level `failure_intensity`.

Partner point:

"Prediction output becomes operational data. Once written back as `TOWER_FAILURE_SCORE`, optimization does not need to know how the GNN worked. It just consumes failure intensity."

### 6. Graph/PageRank and Customer Impact

Script: [run_graph_impact.py](run_graph_impact.py)

Inputs:

- `SUBSCRIBER`
- `CALLDETAILRECORD`

Outputs:

- `SUBSCRIBER_INFLUENCE`
- `TOWER_CUSTOMER_IMPACT`

Talk track:

"The graph question is: which subscribers are structurally important in the call network, and which towers carry high customer impact? The business measure is not just number of callers. It is active subscribers weighted by customer value, with PageRank-style influence available as a network signal."

Show:

- `SUBSCRIBER_INFLUENCE`: one row per subscriber.
- `TOWER_CUSTOMER_IMPACT`: tower-level `WEIGHTED_IMPACT` and `WEIGHTED_PAGERANK`.

Partner point:

"Graph outputs are often not the final answer. They become weights, filters, or explanations for downstream decisions."

### 7. Paths Stage

Script: [run_paths.py](run_paths.py)

Inputs:

- `CALLDETAILRECORD`
- `SUBSCRIBER_INFLUENCE`

Output:

- `TOP_CALL_PATH`

Talk track:

"PageRank scores nodes. Paths explain routes. Starting from the most influential subscriber, we trace simple call paths up to three hops and preserve which towers carried each hop."

Partner point:

"Path reasoning is useful when the route itself is the answer: dependency chains, fraud paths, service paths, logistics routes, escalation paths."

### 8. Optimization Stage

Script: [run_optimization.py](run_optimization.py)

Inputs:

- `CELLTOWER`
- `CELLTOWER_OPERATIONAL_CRITICAL_RESTORE`
- `TOWERUPGRADEOPTION`
- `TOWER_FAILURE_SCORE`
- `TOWER_CUSTOMER_IMPACT`

Outputs:

- `SELECTED_UPGRADES`
- `RESTORE_PLAN`

Talk track:

"The optimization asks: given the towers we care about, the risk scores, customer impact, and upgrade options, what should we actually fund?"

Formulation:

- Decision variable: select a tower/tier upgrade option.
- Constraint: at most one tier per tower.
- Constraint: total cost <= $5M.
- Constraint: install weeks <= 200.
- Objective: maximize capacity restored weighted by customer impact and failure risk.

Show the fallback:

- Gurobi is attempted first.
- HiGHS is used when Gurobi is not licensed/configured.

Partner point:

"Optimization is where the prior reasoners become action. The output is not a score; it is a constrained plan."

### 9. Inspect Results

Useful Snowflake queries:

```sql
SELECT * FROM BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.RESTORE_PLAN;

SELECT *
FROM BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SELECTED_UPGRADES
ORDER BY WEIGHTED_IMPACT DESC, FAILURE_INTENSITY DESC;

SELECT *
FROM BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_CUSTOMER_IMPACT
ORDER BY WEIGHTED_IMPACT DESC
LIMIT 10;

SELECT *
FROM BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_FAILURE_SCORE
ORDER BY FAILURE_INTENSITY DESC
LIMIT 10;
```

Say:

"The final answer is explainable because every selected tower can be traced back to the ontology: tower health, equipment risk, customer impact, and the cost/capacity tradeoff."

## Partner Implementation Pattern

Use this as the high-level methodology for customer engagements:

1. **Frame the decision.** What decision or insight changes action?
2. **Inventory source data.** Identify entities, relationships, measures, and update cadence.
3. **Build the base ontology.** Map tables into concepts, properties, and relationships.
4. **Validate with the business.** Use Modeler UI to inspect the deployed schema with SMEs.
5. **Deploy the stable model.** Materialize semantic tables with deploy mode and op log.
6. **Discover reasoner opportunities.** Classify questions as rules, graph, predictive, prescriptive, or chained.
7. **Run reasoners on semantic tables.** Treat deployed concepts as the input contract.
8. **Persist outputs.** Write predictions, scores, paths, and decisions into result tables or ontology enrichments.
9. **Operationalize.** Schedule refreshes, expose result tables, branch/merge model changes, and connect apps or agents.

## Suggested Whiteboard Framing

Draw this left to right:

```text
Raw data -> Ontology -> Deployed semantic schema -> Reasoner outputs -> Decision/application
```

Then add the reasoner chain:

```text
Operational rules
       |
Predictive GNN -> failure intensity
       |
Graph/PageRank -> customer impact
       |
Paths -> route explanation
       |
Prescriptive optimization -> funded upgrade plan
```

The important message:

"RelationalAI lets you keep the business model stable while composing multiple reasoning techniques over it. Partners do not have to build a one-off pipeline for every question."

## Demo Risks and Backup Plan

- If GNN runtime is too long, pre-run it and show `TOWER_FAILURE_SCORE` plus the script.
- If Gurobi is unavailable, use the built-in HiGHS fallback. This already worked in the current environment.
- If Modeler UI is slow, show Snowflake deployed tables first, then return to Modeler UI when it loads.
- If a deploy type mismatch appears, remove `./build` and redeploy to force a fresh Snowflake schema read.
- If a live run fails, continue the narrative from the precomputed result tables in `BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS`.

## Close

End with:

"The implementation partner takeaway is that RelationalAI is not only a reasoner runtime. It is a modeling and deployment workflow. You model the problem once, validate it visually, deploy it as semantic tables, and then layer reasoning on top to produce decisions that remain explainable."
