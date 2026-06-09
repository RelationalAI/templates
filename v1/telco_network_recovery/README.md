---
title: "Telco Network Recovery"
description: "Multi-reasoner template: equipment-failure GNN over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, customer-impact analysis (revenue × churn, with PageRank alongside), and tower-upgrade optimization on a shared telco ontology."
featured: false
experience_level: advanced
industry: "Telecommunications"
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

## What you'll build

- A funded tower-upgrade plan that maximizes restored capacity weighted by customer impact and predicted failure risk, within a fixed capex envelope and crew-week cap.
- A per-tower selection rationale (`operational` / `advisory/predicted` / `high-value`) explaining why each chosen tower made the cut.
- A shared ontology that grows accretively — every stage's output becomes a queryable property the next stage reads, with no DataFrame ping-pong between reasoners.
- A `RestorePlan` singleton plus an `is_selected_upgrade` view, both queryable as ontology after the run.

Built using **predictive reasoning** (GNN on a heterogeneous graph), **rules-based classification** (multi-branch derived flag), **graph analysis** (PageRank + per-tower aggregation), and **prescriptive reasoning** (mixed-integer programming).

## What's included

- **Model**: a 4-stage pipeline (predictive → rules → graph → prescriptive) on a single shared ontology — 8 source-data concepts wired to the bundled CSVs, plus the enrichments each stage writes back.
- **Runner**: `telco_network_recovery.py` — a single Python script with four module-scope stages, runs end-to-end against a Snowflake-connected RAI account.
- **Sample data**: 250 cell towers, 1,500 equipment items, 8 manufacturer advisories on 7 MODELs, 1,200 subscribers, 6,000 call records, 750 upgrade options. See *Sample data* below.
- **Outputs**: per-stage stdout diagnostics plus an ontology-resident `RestorePlan` singleton holding cost, capacity, install-weeks, tier mix, towers covered, and binding constraint.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI native app installed.
- A Snowflake user with permissions on the RAI native app and on `EXP_DATABASE` (the schema for GNN experiment artifacts).
- A gurobi-enabled prescriptive engine for Stage 4 (the script automatically falls back to the bundled HiGHS solver if gurobi is not configured).

### Tools

- Python ≥ 3.10.
- RelationalAI Python SDK (`relationalai == 1.11.0`).

### One-time Snowflake setup for GNN experiment artifacts

Grant the RelationalAI Native App access to a schema for experiment artifacts. The local script uses `TELCO_ENRICHMENT.EXPERIMENTS` by default (or change the constants at the top of the script). Update the SET statements below to match your database, schema, and Native App name, then run the following in a Snowflake SQL worksheet:

```sql
SET db_name            = 'TELCO_ENRICHMENT';
SET schema_experiments = 'TELCO_ENRICHMENT.EXPERIMENTS';
SET app_name           = 'RELATIONALAI';   -- replace with your app name

CREATE DATABASE IF NOT EXISTS identifier($db_name);
CREATE SCHEMA   IF NOT EXISTS identifier($schema_experiments);

GRANT USAGE             ON DATABASE identifier($db_name)            TO APPLICATION identifier($app_name);
GRANT USAGE             ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
GRANT CREATE EXPERIMENT ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
GRANT CREATE MODEL      ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
```

Set `EXP_DATABASE` at the top of `telco_network_recovery.py` to that database (default: `TELCO_ENRICHMENT`).

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/telco_network_recovery.zip
   unzip telco_network_recovery.zip
   cd telco_network_recovery
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

4. Configure:

   ```bash
   rai init
   ```

   After `rai init` generates the config file, add the following to your `raiconfig.yaml`:

   ```yaml
   data:
       ensure_change_tracking: true
   ```

5. (Optional) Regenerate the synthetic data corpus with a fresh seed:

   ```bash
   cd data && python _synthesize_advisory_data.py && cd ..
   ```

6. Run the template end-to-end:

   ```bash
   python telco_network_recovery.py
   ```

   You should see the four stages print diagnostics and then a final plan as queryable ontology. Tail of a successful run:

   ```text
   STAGE 4: PRESCRIPTIVE -- tower upgrade selection MIP
     Selected upgrades: 27 across 5 regions
     Total cost:               $4,992,276  (budget $5,000,000, binding)
     Capacity restored:        180 Gbps
     Rationale tally: operational=2, advisory/predicted=27, high-value=17

   PIPELINE COMPLETE: 4 stages executed on the shared Telco ontology
   ```

   Exact numbers shift run-to-run with the stochastic GNN; the structural outcome — all 5 regions covered, budget binding, ~180-210 Gbps restored across ~25-40 towers — reproduces.

## Template structure

```text
telco_network_recovery/
  telco_network_recovery.py       # Main script (4 chained reasoning stages)
  data/
    cell_towers.csv               # 250 towers across 5 regions (15 WEST DEGRADED)
    network_equipment.csv         # 1,500 equipment installs, 18 MODELs
    equipment_health.csv          # 1,500 per-equipment health snapshots
    network_performance.csv       # 5,000 per-tower measurements
    subscribers.csv               # 1,200 subscribers (consumer + enterprise)
    call_detail_records.csv       # 6,000 directed CDRs
    tower_upgrade_options.csv     # 750 (tower, tier) options
    model_advisories.csv          # 8 manufacturer advisories on 7 MODELs
    _synthesize_advisory_data.py  # reproducibility script for the synthetic data
  README.md                       # this file
  runbook.md                      # analyst-facing paste-testable walkthrough
  pyproject.toml                  # dependencies
```

## Sample data

The bundled data is **synthetic and illustrative** — designed to teach the reasoning flow on a Snowflake-connected RAI account, not to match a specific operator's network. The data does not yet model site / sector / band / radio-unit / vendor / backhaul attributes that a production network catalog carries; those are extension points (see *Customize this template*), not gaps in the reasoning pattern.

- **`cell_towers.csv`** (250 rows) — towers across 5 regions; 15 WEST towers are explicitly `DEGRADED`.
- **`network_equipment.csv`** (1,500 rows) — equipment installs across 18 consolidated MODELs (manufacturer × model name); each links to one tower.
- **`equipment_health.csv`** (1,500 rows) — per-equipment health snapshot (MTBF hours, failure rate, temperature, power, health score).
- **`network_performance.csv`** (5,000 rows) — per-tower performance measurements (latency, throughput, packet loss, jitter, signal strength, utilization).
- **`subscribers.csv`** (1,200 rows) — 1,150 `CONSUMER` + 50 `ENTERPRISE` accounts with `LIFETIME_VALUE_USD`, `CHURN_RISK_SCORE`, `SEGMENT`, `STATUS`. Enterprise LTV averages ~130× consumer, so the customer-impact aggregation in Stage 3 weights heavily toward enterprise-bearing towers — realistic for capex prioritization.
- **`call_detail_records.csv`** (6,000 rows) — directed call records (`caller → callee`), each routed through a specific tower.
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

One shared ontology threads all four stages. Each stage reads concepts and properties earlier stages wrote, and writes new ones for downstream stages.

- **Key entities**: `CellTower`, `NetworkEquipment`, `EquipmentHealth`, `NetworkPerformance`, `ModelAdvisory`, `Subscriber`, `CallDetailRecord`, `TowerUpgradeOption`; plus the derived `TowerFailureScore` (bridge for the GNN output) and `RestorePlan` (singleton plan headline).
- **Primary identifiers**: string ids on the base entities (e.g. `TOWER_ID`, `EQUIPMENT_ID`, `SUB_ID`); composite key on `TowerUpgradeOption` (`tower_id` + `tier`); MODEL string on `ModelAdvisory`.
- **Important invariants**: `severity`, `churn_risk_score`, and `health_score` are fractions in `[0, 1]`; `capacity_gbps` and `cost` are non-negative; the GNN's `at_risk` label is `1` if `STATUS` is `FAILING` or `WARNING`; Stage 4 decision variables are binary.

### Concepts

**`CellTower`** — a cell tower with location, status, and region. Stages 1-3 enrich it with predicted-failure, operational, and customer-impact properties.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `TOWER_ID` from `data/cell_towers.csv` |
| `name`, `tower_type`, `status`, `region` | String | No | Loaded from CSV |
| `capacity_gbps` | Integer | No | Baseline backhaul capacity |
| `install_date` | DateTime | No | When the tower came online |
| `failure_intensity` | Float | No | **Stage 1** GNN sum (per-tower) |
| `avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score` | Float | No | **Stage 2** rule-stage averages |
| `is_critical_restore` | Relationship | — | **Stage 2** three-branch flag |
| `impact_count`, `weighted_impact`, `weighted_pagerank` | Float | No | **Stage 3** customer-impact aggregates |

**`NetworkEquipment`** — an equipment install on a tower. The GNN's prediction target.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `EQUIPMENT_ID` |
| `tower_id_fk` | String | No | Explicit FK column for GNN edge construction |
| `equipment_type`, `manufacturer`, `eqp_model`, `firmware_version`, `status` | String | No | Categorical features |
| `at_risk` | Integer | No | Binary label (1 if `STATUS in {FAILING, WARNING}`) |
| `install_date` | DateTime | No | When installed |

**`Subscriber`** — a customer account that places calls. Stage 3 reads `customer_value` and `status` to weight the per-tower aggregation.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | String | Yes | `SUB_ID` |
| `subscriber_type`, `segment`, `status` | String | No | `CONSUMER`/`ENTERPRISE`; segment tier; `ACTIVE`/`SUSPENDED` |
| `lifetime_value` | Float | No | `LIFETIME_VALUE_USD` |
| `churn_risk_score` | Float | No | `[0, 1]` — probability of churn |
| `customer_value` | Float | No | Precomputed: `lifetime_value × (1 + churn_risk_score)` — the per-subscriber weight Stage 3 sums into `weighted_impact` |
| `influence_score` | Float | No | **Stage 3** PageRank on the call graph |

**`TowerUpgradeOption`** — a (tower, tier) candidate upgrade. The MIP's decision space.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `tower_id`, `tier` | String | Yes | Composite key |
| `capacity_increase_gbps` | Integer | No | Capacity restored if selected |
| `cost` | Float | No | USD |
| `install_weeks` | Integer | No | Crew weeks required |
| `for_tower` | Relationship | — | Link back to `CellTower` |
| `selected` | Float | No | **Stage 4** binary decision (0/1) |
| `is_selected_upgrade` | Relationship | — | **Stage 4** narrowed view of `selected == 1` |

**`ModelAdvisory`** — a manufacturer advisory on an equipment MODEL.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `model` | String | Yes | Identifies the affected MODEL |
| `advisory_type` | String | No | `RECALL` / `DEFECT_BATCH` / `EOL` / `FIRMWARE_BUG` / `SECURITY_PATCH` |
| `severity` | Float | No | `[0, 1]` — manufacturer-stated severity |
| `issued_date` | DateTime | No | When issued |

`EquipmentHealth`, `NetworkPerformance`, and `CallDetailRecord` are also Concepts (snapshots / metric rows / call edges); they serve as join sources for the aggregations and edges Stages 1-3 build. Their properties mirror their CSV columns.

**`RestorePlan`** — singleton holding the plan headline.

| Property | Type | Notes |
|---|---|---|
| `total_cost`, `capacity_restored_gbps`, `total_install_weeks` | Float / Integer | Headline metrics |
| `gold_count`, `silver_count`, `bronze_count`, `towers_covered` | Integer | Tier mix and reach |
| `binding_constraint` | String | `"budget"`, `"install_weeks"`, or `"none"` |

### Relationships

- `NetworkEquipment.tower_id_fk == CellTower.id` — equipment install on a tower (also a Stage 1 GNN edge).
- `EquipmentHealth.equipment_id_fk == NetworkEquipment.id` — per-equipment health snapshot (GNN edge).
- `ModelAdvisory.model == NetworkEquipment.eqp_model` — advisory ↔ every equipment item on the affected MODEL (GNN edge — propagates advisory severity across fleet siblings).
- `CallDetailRecord.caller` and `.callee` ⟶ `Subscriber` — directed edges of the Stage 3 PageRank call graph.
- `CallDetailRecord.routed_through` ⟶ `CellTower` — links each call to the tower it routed through; the per-tower customer-impact aggregation reads this.
- `TowerUpgradeOption.for_tower` ⟶ `CellTower` — Stage 4 scopes the decision space to options on critical-restore towers.

## How it works

**Stage 1 — Predictive (GNN).** A binary `at_risk` classifier message-passes over three heterogeneous edges on an undirected graph (`EquipmentHealth ↔ NetworkEquipment ↔ CellTower`, plus `ModelAdvisory ↔ NetworkEquipment` via shared MODEL). The undirected setting matters: bidirectional message passing lets the GNN reach tower-mate equipment via 2-hop paths through `CellTower`, so the *"my tower-mate sits on a recalled MODEL"* pattern is learnable. Per-equipment positive probabilities are summed per tower into `CellTower.failure_intensity` via a `TowerFailureScore` bridge concept.

**Stage 2 — Rules.** A three-branch `CellTower.is_critical_restore` flag fires when (1) `region == "WEST"` + `status == "DEGRADED"` + low avg equipment health, (2) WEST + high packet loss + low health, or (3) `failure_intensity > 1.5` (any region). Per-tower averages (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) are derived first from `NetworkPerformance` and a two-hop `EquipmentHealth → NetworkEquipment → CellTower` join.

**Stage 3 — Graph (customer impact analysis).** PageRank on the directed `Subscriber → Subscriber` call graph lands on `Subscriber.influence_score` (the graph reasoner's network-effect signal). The headline per-tower measure is `CellTower.weighted_impact` — sum of `Subscriber.customer_value` (= `lifetime_value × (1 + churn_risk_score)`) across the ACTIVE callers whose calls route through each tower. `weighted_pagerank` is the parallel PageRank-weighted view, exposed as a secondary signal queryable alongside the revenue-based headline.

**Stage 4 — Prescriptive (MIP).** Binary `TowerUpgradeOption.selected`, scoped to critical-restore towers, with three constraints (at most one tier per tower, total cost ≤ $5M, total install-weeks ≤ 200) and a three-factor objective:

```python
problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps
        * CellTower.weighted_impact      # Stage 3: revenue × churn
        * CellTower.failure_intensity    # Stage 1: GNN-predicted
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
)
```

After the solve, a `RestorePlan` singleton is populated and each selected option is tagged `is_selected_upgrade`. Every selected tower carries a `rationale` tag in the printed plan noting which upstream signal(s) drove its inclusion (`operational` / `advisory/predicted` / `high-value`).

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `model.data(snowflake_table)` calls and adjust `EXP_DATABASE` / `EXP_SCHEMA` at the top of the script.
- If your subscriber feed lacks `LIFETIME_VALUE_USD` or `CHURN_RISK_SCORE`, supply a `CUSTOMER_VALUE` column directly and skip the pandas precompute.

### Tune parameters

- **Budget envelope** — `BUDGET_USD` (default `$5,000,000`), `INSTALL_WEEKS_BUDGET` (default `200`).
- **Predictive threshold** — `FAILURE_INTENSITY_THRESHOLD` (default `1.5`) is Branch 3's cutoff for *"the GNN is confident multiple pieces are at risk."*
- **Customer-value formula** — the bundled formula is `LTV × (1 + churn_risk_score)`. Use `log1p(LTV) × (1 + churn)` to compress the enterprise-vs-consumer gap; multiply by an `NPS_SCORE`-derived factor for retention fragility; or add SLA-tier and emergency-service multipliers once those fields land on `subscribers.csv`.

### Extend the model

- **Add more advisories** — extend `data/model_advisories.csv` with new advisory types and severities; the GNN picks them up on the next training run.
- **Add a fourth GNN edge** — e.g., `NetworkEquipment → SimilarEquipment` via shared `FIRMWARE_VERSION` or `MANUFACTURER` to test other heterogeneous-neighborhood patterns.
- **Add SLA-tier weighting** — add `SLA_TIER` / `is_emergency_service` columns to `subscribers.csv` and fold them into the `customer_value` precompute; the rest of the chain is unchanged.
- **Add backhaul coupling** — model `BackhaulPath` / `AggregationNode` as Concepts and add a per-node capacity constraint to Stage 4 (`aggs.sum(selected × capacity).per(AggregationNode) <= node_headroom`).
- **Swap PageRank for another graph algorithm** — `weighted_pagerank` is the secondary network-effect signal; replace `call_graph.pagerank()` with `betweenness_centrality()` or `eigenvector_centrality()` to surface different structural roles without changing the optimizer.

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from the operator's upstream systems (see *Source-system mapping* under *Sample data* for the typical sources and cadences).
- The synthetic data assumes 250 towers / 1,500 equipment; the chain scales to whatever fits the prescriptive engine's solve budget. Tier mix and capacity numbers move roughly linearly with the budget envelope.

## Troubleshooting

<details>
<summary>GNN training fails with permission errors on <code>EXP_DATABASE</code></summary>

The `RELATIONALAI` native app must own the `EXPERIMENTS` schema. Run the one-time setup DDL from the Prerequisites section.

Verify with `SHOW GRANTS ON SCHEMA <DB>.EXPERIMENTS` — you should see `OWNERSHIP` granted to `APPLICATION RELATIONALAI`.

</details>

<details>
<summary>Stage 4 returns an infeasible status</summary>

Stage 4 is feasible whenever the flagged-tower set has at least one BRONZE option that fits under the remaining budget. The bundled data has BRONZE options on every tower; tightening `BUDGET_USD` below the minimum total cost of one BRONZE per flagged tower will produce infeasibility.

</details>

<details>
<summary>The 15 WEST DEGRADED towers don't show up in Stage 4 selections</summary>

The Stage 2 rule still fires on them (Branches 1 and 2) — they're in the flagged set. Whether they're picked by Stage 4 depends on the multiplicative objective: a WEST tower with low `failure_intensity` (healthy equipment) and low `weighted_impact` (few high-value callers) gets a small objective contribution and may be deprioritized vs. higher-risk, higher-value towers elsewhere. This is the intended behavior of the chain.

</details>

<details>
<summary>The plan looks enterprise-heavy</summary>

The bundled subscriber data has 50 enterprise (~$300K LTV avg) vs. 1,150 consumer (~$3K LTV avg) accounts, so `weighted_impact` concentrates heavily on enterprise-bearing towers. This matches operator reality (enterprise SLAs drive capex). For a more balanced spread, swap the `customer_value` formula for `log1p(LTV) × (1 + churn)` or add a per-region minimum-coverage constraint to Stage 4 — both are tuning knobs, not redesigns.

</details>

<details>
<summary>Gurobi unavailable / unlicensed</summary>

The script requests gurobi first. If gurobi errors at runtime (license, integration), it catches the failure and retries with `solver="highs"` — no edit needed. To always use HiGHS, change `problem.solve("gurobi")` to `problem.solve("highs")`.

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
