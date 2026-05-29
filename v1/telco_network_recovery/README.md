---
title: "Telco Network Recovery"
description: "Multi-reasoner template: equipment-failure GNN over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, call-graph blast radius, and tower-upgrade optimization on a shared telco ontology."
featured: false
private: false
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

A regional telco operator must allocate a fixed capex budget across cell towers in the face of two distinct risk signals. Some towers are visibly broken — degraded status, high packet loss, low equipment health — and a declarative rule can find them. Others have equipment that **looks operationally fine on its own measurements** but sits on a manufacturer's MODEL that just received a recall, a defect-batch notice, or an EOL advisory; those towers won't fail today, but they will fail soon. The chain integrates both signals into an optimizable plan.

This template uses RelationalAI's **predictive reasoning**, **rules-based classification**, **graph analysis**, and **prescriptive reasoning (MIP)** in a chained workflow on a shared ontology:

1. **Predictive (GNN)** trains a binary classifier on `NetworkEquipment.STATUS` over a heterogeneous graph that links each equipment to its `EquipmentHealth` snapshot, its `CellTower`, and any `ModelAdvisory` on its MODEL. Advisory severity propagates to every fleet sibling through shared-MODEL message passing, and 2-hop paths via `CellTower` let the GNN reach tower-mate equipment too. Per-equipment predicted-failure probability is summed per tower into `CellTower.failure_intensity`.
2. **Rules** derive per-tower averages from `NetworkPerformance` measurements and equipment health (two-hop join via FK property equality), then flag `CellTower.is_critical_restore` via three branches: WEST + DEGRADED + low equipment health; WEST + high packet loss + low health; or `failure_intensity > threshold` (any region). The third branch broadens upgrade scope beyond WEST when the GNN flags concentrated predicted failure elsewhere.
3. **Graph** builds a directed `Subscriber → Subscriber` call graph from `CallDetailRecord`, runs PageRank, and aggregates per critical tower the subscribers routing through it weighted by their influence — the social blast radius if that tower fails.
4. **Prescriptive** picks one upgrade tier (BRONZE / SILVER / GOLD) per critical tower under a $5M budget and a 200 crew-week install cap. The objective multiplies three coefficients, one from each upstream stage: capacity boost × weighted impact (Stage 3) × failure intensity (Stage 1).

Each stage writes derived properties back to the same ontology that downstream stages read. There is no DataFrame ping-pong between stages — the ontology is the single source of truth, and changing any upstream signal automatically propagates through the rules engine and the optimizer.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1. Predictive | **GNN binary classification** | `NetworkEquipment` (nodes), `EquipmentHealth`, `CellTower`, `ModelAdvisory` (all node concepts); three FK / shared-MODEL edges | `NetworkEquipment.predictions.probs`; `CellTower.failure_intensity` (per-tower SUM via bridge concept) | Predict which equipment is at risk by propagating advisory severity through shared-MODEL message passing. Output is a continuous per-tower risk score the optimizer can prioritize against. |
| 2. Rules | **Rules** (declarative) | `NetworkPerformance`, `EquipmentHealth`, `CellTower.failure_intensity` | `CellTower.avg_packet_loss`, `.avg_latency_ms`, `.avg_error_rate`, `.avg_health_score` (Properties); `CellTower.is_critical_restore` (Relationship) | Flag critical-restore towers via three branches (two WEST-scoped operational rules + one predictive branch firing on `failure_intensity > threshold`). |
| 3. Graph | **Graph** (PageRank) | `Subscriber` nodes, `CallDetailRecord` edges, `routed_through(CellTower)` | `Subscriber.influence_score`, `CellTower.impact_count`, `CellTower.weighted_impact` | Score subscriber social influence; aggregate per critical tower the callers routing through it and the sum of their PageRank. |
| 4. Prescriptive | **MIP** (gurobi) | `is_critical_restore` (Stage 2), `weighted_impact` (Stage 3), `failure_intensity` (Stage 1), `TowerUpgradeOption` | `TowerUpgradeOption.selected` (binary decision Property) | Pick one tier per critical tower under cost + crew-week budgets. Maximize three-factor weighted capacity gain. |

**Key design patterns demonstrated:**

- **Accretive ontology enrichment** — each stage writes derived properties that downstream stages consume as first-class attributes. No glue code, no DataFrame round-trips between stages (except where the GNN's prediction shape needs a one-step pandas aggregation before binding back).
- **Heterogeneous-graph GNN** — three FK / shared-MODEL edges (`EquipmentHealth → NetworkEquipment`, `NetworkEquipment → CellTower`, `ModelAdvisory → NetworkEquipment`) so advisory severity propagates to every fleet sibling AND reaches tower-mate equipment via 2-hop paths.
- **Property-equality edges** — the GNN graph defines edges via `==` between FK columns instead of `model.Relationship` traversal. FK properties on `NetworkEquipment` and `EquipmentHealth` carry the join keys explicitly so heterogeneous edges read as property-level equality conditions.
- **Bridge concept** — per-equipment predictions are aggregated in pandas (`sum`) and loaded back as a `CellTower.failure_intensity` property via a small `TowerFailureScore` concept. Same pattern as in `retail_planning`.
- **Three-branch rule** — `CellTower.is_critical_restore` is defined three times (OR semantics). A tower is critical if any branch fires; the third branch lets the GNN broaden scope beyond WEST.
- **Three-factor MIP objective** — `capacity_increase × weighted_impact × failure_intensity`. Each factor comes from a different reasoner upstream.

## Who this is for

- Telco network operations and capital planning teams.
- Operations researchers exploring multi-reasoner pipelines in RelationalAI.
- Developers learning how to model heterogeneous-graph GNN inputs (FK property-equality edges, shared-key edges, undirected message passing) on a multi-concept ontology.

## What you'll build

- A heterogeneous-graph GNN that predicts equipment-level risk by message-passing from `ModelAdvisory` (the recall / defect signal) through shared MODEL to every fleet sibling.
- A three-branch declarative rule that combines operational degradation (Stage 2 / Stage 3) with the GNN's predicted-failure intensity.
- A PageRank computation on a directed call graph plus per-tower blast-radius aggregation.
- A binary tower-upgrade MIP whose objective coefficients are the upstream reasoners' outputs.
- Ontology-native result extraction — every reasoner output is a queryable property of the model.

## What's included

- `telco_network_recovery.py` — main script with four chained reasoning stages.
- `data/cell_towers.csv` — 250 cell towers across five regions (15 WEST DEGRADED).
- `data/network_equipment.csv` — 1,500 equipment installs across 18 consolidated MODELs.
- `data/equipment_health.csv` — per-equipment health snapshots (1:1 with equipment).
- `data/network_performance.csv` — 5,000 per-tower performance measurements.
- `data/subscribers.csv` — 1,200 subscribers (consumer + enterprise).
- `data/call_detail_records.csv` — 6,000 directed call records.
- `data/tower_upgrade_options.csv` — 750 upgrade options (3 tiers × 250 towers).
- `data/model_advisories.csv` — 8 manufacturer advisories (recall / defect / EOL / firmware bug / security patch) covering 7 MODELs.
- `data/_synthesize_advisory_data.py` — reproducibility script for the synthetic data corpus.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI native app installed.
- A Snowflake user with permissions on the RAI native app and on `EXP_DATABASE` (the schema for GNN experiment artifacts).
- A gurobi-enabled prescriptive engine for Stage 4.

### Tools

- Python ≥ 3.10.
- RelationalAI Python SDK with the predictive extra (`relationalai[gnn] == 1.4.2`).

### One-time Snowflake setup for GNN experiment artifacts

The predictive reasoner writes training artifacts (model checkpoints, metrics, predictions) to a Snowflake schema that the `RELATIONALAI` native app must own. Pick a database you control, then grant ownership of the experiments schema to the native app:

```sql
USE DATABASE <YOUR_DATABASE>;
CREATE SCHEMA IF NOT EXISTS EXPERIMENTS;
GRANT OWNERSHIP ON SCHEMA EXPERIMENTS TO APPLICATION RELATIONALAI;
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

4. Configure your RAI connection:

   ```bash
   rai init
   ```

5. (Optional) Regenerate the synthetic data corpus with a fresh seed:

   ```bash
   cd data && python _synthesize_advisory_data.py && cd ..
   ```

6. Run the template:

   ```bash
   python telco_network_recovery.py
   ```

7. Representative output (one run on RAI 1.4.2):

   > The equipment-failure GNN is stochastic — exact figures (failure_intensity, flagged-tower count, tier mix, Gbps) shift run to run. The structural outcome reproduces: all 5 regions covered, budget binding, ~200 Gbps restored across ~36 towers.

   ```text
   Equipment split: train=1050 val=225 test=1500 (all)
   Label distribution: at_risk=1 597 / 1500 (39.8%)
   Advisories: 8 on 7 distinct models

   STAGE 1: PREDICTIVE -- equipment-failure binary classification GNN
     failure_intensity distribution: min=0.02, median=2.92, max=10.47
     Towers with failure_intensity > 1.5: 139 / 190
     GNN recall on 597 true at-risk items:
       Argmax (predicted_label == 1):                         0 ( 0.0%)
       p>=0.5 (probabilistic threshold):                    547 (91.6%)
     GNN per-equipment positive-prob distribution: min=0.006,
       median=0.021, max=0.977; items with pos_prob>=0.5: 576 / 1500

   STAGE 2: RULES -- flag is_critical_restore towers
     Flagged critical_restore towers: 142
     Region breakdown:  WEST 43, EAST 32, SOUTH 25, NORTH 23, CENTRAL 19
     Branch 1 (WEST + DEGRADED + low health):                  12 towers
     Branch 2 (WEST + high packet loss + low health):          12 towers
     Branch 3 (failure_intensity > 1.5, any region):          139 towers
     Towers flagged ONLY by the predictive branch:            130 (92%)

   STAGE 3: GRAPH -- PageRank + per-critical-tower blast radius

   STAGE 4: PRESCRIPTIVE -- tower upgrade selection MIP
     Selected upgrades: 36 across 5 regions
     Total cost:               $4,997,992  (budget $5,000,000, binding)
     Total install crew-weeks: 194         (budget 200, near binding)
     Capacity restored:        207 Gbps
     Tier mix:                 {'BRONZE': 17, 'SILVER': 15, 'GOLD': 4}
     Region breakdown:         {'EAST': 10, 'SOUTH': 9, 'CENTRAL': 7, 'WEST': 6, 'NORTH': 4}

     Plan (queryable as ontology):
       plan_id              total_cost install_weeks capacity_gbps gold silver bronze towers binding
       TELCO_RECOVERY_2024Q4 4997992.0           194           207    4     15     17     36  budget

   PIPELINE COMPLETE: 4 stages executed on the shared Telco ontology
   Plan headline + 36-row SelectedUpgrade view are now queryable as ontology
   -- RestorePlan and TowerUpgradeOption.is_selected_upgrade.
   ```

   Exact numbers depend on the synthesis seed and the GNN training run.

## Template structure

```text
telco_network_recovery/
  telco_network_recovery.py       # Main script (4 chained reasoning stages)
  data/
    cell_towers.csv               # 250 towers across 5 regions (15 WEST DEGRADED)
    network_equipment.csv         # 1,500 equipment installs, 18 MODELs
    equipment_health.csv          # 1,500 per-equipment health snapshots
    network_performance.csv       # 5,000 per-tower measurements
    subscribers.csv               # 1,200 subscribers
    call_detail_records.csv       # 6,000 directed CDRs
    tower_upgrade_options.csv     # 750 (tower, tier) options
    model_advisories.csv          # 8 manufacturer advisories on 7 MODELs
    _synthesize_advisory_data.py  # reproducibility script for the synthetic data
  README.md                       # this file
  runbook.md                      # multi-reasoner agent-skill walkthrough
  pyproject.toml                  # dependencies
```

## How it works

### Stage 1: Predictive — equipment-failure binary GNN

The GNN learns a binary `at_risk` label (1 if `STATUS in {FAILING, WARNING}`, else 0) by message-passing over three heterogeneous edges on an **undirected** graph (`directed=False`), so signal can flow both ways and reach equipment via 2-hop paths through their towers:

```python
gnn_graph = Graph(model, directed=False, weighted=False)

# Edge 1: EquipmentHealth <-> NetworkEquipment (per-equipment health features)
model.define(gnn_graph.Edge.new(src=EquipmentHealth, dst=NetworkEquipment)).where(
    EquipmentHealth.equipment_id_fk == NetworkEquipment.id,
)
# Edge 2: NetworkEquipment <-> CellTower (tower-context features; also
# the 2-hop path that lets advisory signal reach tower-mates)
model.define(gnn_graph.Edge.new(src=NetworkEquipment, dst=CellTower)).where(
    NetworkEquipment.tower_id_fk == CellTower.id,
)
# Edge 3: ModelAdvisory <-> NetworkEquipment (recall/defect signal via MODEL)
model.define(gnn_graph.Edge.new(src=ModelAdvisory, dst=NetworkEquipment)).where(
    ModelAdvisory.model == NetworkEquipment.eqp_model,
)
```

The undirected setting matters: with directed edges, the advisory signal would absorb into an advised equipment item but couldn't propagate to its tower-mates. Bidirectional message passing lets the GNN learn the 2-hop *"my tower-mate has a known-bad model, so I'm at elevated risk too"* pattern that's the multi-hop case in the latent-risk model.

`PropertyTransformer` annotates features by type — categorical (manufacturer, MODEL, firmware version, tower type / status / region, advisory type), continuous (failure rate, temperature, power consumption, health score, advisory severity), integer (MTBF hours, tower capacity), and datetime (install dates, last failure date, measurement date, advisory issued date).

Per-equipment predicted-failure probabilities are summed per tower and loaded back as a `CellTower.failure_intensity` property via a small `TowerFailureScore` bridge concept. Sum (not max) preserves per-tower differentiation — a tower with 4 confidently-at-risk pieces weighs ~4× a tower with 1.

### Stage 2: Rules — three-branch is_critical_restore

The rule consumes two derived aggregations — average packet loss from `NetworkPerformance` and average equipment health from the two-hop `EquipmentHealth → NetworkEquipment → CellTower` join — and the GNN's `failure_intensity`:

```python
# Branch 1: WEST + DEGRADED status + low equipment health (operational)
model.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())

# Branch 2: WEST + high packet loss + low health (ACTIVE-but-failing)
model.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())

# Branch 3: predicted failure intensity high (any region)
model.where(
    CellTower.failure_intensity > FAILURE_INTENSITY_THRESHOLD,
).define(CellTower.is_critical_restore())
```

### Stage 3: Graph — PageRank + blast radius

The Graph reasoner uses Pattern 3 (`edge_concept`): `CallDetailRecord` IS the edge, with `caller → callee` as the directed edge. PageRank lands directly on `Subscriber.influence_score`. Per critical tower, the blast radius is the distinct count and the PageRank sum of subscribers whose calls route through it.

### Stage 4: Prescriptive — tower upgrade MIP

The decision variable `TowerUpgradeOption.selected` is binary, scoped to options on critical towers. Three constraints (one tier per tower, total cost ≤ $5M, total install weeks ≤ 200) and a three-factor objective:

```python
problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps   # raw upgrade attribute
        * CellTower.weighted_impact                   # Stage 3 (graph)
        * CellTower.failure_intensity                 # Stage 1 (GNN)
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
)
```

## Customize this template

- **Tighten the predictive branch** — raise `FAILURE_INTENSITY_THRESHOLD` from 1.5 to require more concentrated predicted failure before flagging a tower.
- **Add more advisories** — extend `data/model_advisories.csv` with new advisory types and severities; the GNN will pick them up on next training run.
- **Add a fourth GNN edge** — e.g., `NetworkEquipment → SimilarEquipment` via shared FIRMWARE_VERSION or shared MANUFACTURER to test other heterogeneous-neighborhood patterns.
- **Swap PageRank for centrality** — replace `call_graph.pagerank()` with `betweenness_centrality()` or `eigenvector_centrality()` to reweight blast radius.
- **Add a budget scenario axis** — introduce an `InvestmentLevel` Scenario Concept (per the energy_grid_planning template) so one solve produces the Pareto frontier across multiple budgets.

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

The Stage 2 rule still fires on them (branches 1 and 2) — they're in the flagged set. Whether they're picked by Stage 4 depends on the multiplicative objective: a WEST tower with low `failure_intensity` (healthy equipment) gets a small objective contribution and may be deprioritized vs higher-failure-intensity towers elsewhere. This is the intended behavior of the GNN-aware chain.

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
