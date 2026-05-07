---
title: "Telco Network Recovery"
description: "Multi-reasoner template: GNN demand forecasting, declarative critical-tower rules, call-graph blast radius, and tower-upgrade optimization on a shared telco ontology."
featured: false
private: true
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
  - PageRank
  - Network Operations
  - Capacity Planning
  - Telco
---

## What this template is for

A regional telco operator is missing revenue targets in one part of its footprint while every other region grows. Network availability, churn, and support volume all point at the same area. The operations team needs to find the towers driving the bleed, weight them by who actually depends on them, factor in where demand is heading, and produce a defensible upgrade plan inside a fixed capital and crew budget.

A single reasoner cannot answer this. Description alone identifies the broken region but no plan. Rules alone flag the broken towers but cannot rank them. Graph alone ranks subscribers but does not pick the towers. Predictive alone forecasts demand but does not act. Prescriptive alone has no flagged set, no impact weights, and no forecast to weight upgrades by.

This template uses RelationalAI's **predictive reasoning**, **rules-based classification**, **graph analysis**, and **prescriptive reasoning (MIP)** in a chained workflow on a shared ontology:

1. **Predictive (GNN)** trains a regression GNN on per-region daily KPIs (subscriber growth, network availability, churn, ticket volume, ...) over 365 days x 9 regions, with same-region 1-day-lag temporal edges. The per-region predicted growth becomes a per-tower demand multiplier consumed by Stage 4.
2. **Rules** derive per-tower averages from `NetworkPerformance` measurements and per-tower equipment health from a two-hop `EquipmentHealth -> NetworkEquipment -> CellTower` aggregation, then flag `CellTower.is_critical_restore` for WEST DEGRADED towers with low health.
3. **Graph** builds a directed `Subscriber -> Subscriber` call graph from `CallDetailRecord` (caller -> callee), runs PageRank, and aggregates per critical tower the distinct subscribers routing through it plus the sum of their PageRank scores -- the social blast radius if that tower fails.
4. **Prescriptive** picks one upgrade tier (BRONZE / SILVER / GOLD) per critical tower under a $5M budget and a 200 crew-week install cap. The objective multiplies three coefficients, one from each prior stage: capacity boost x weighted impact (Stage 3) x demand multiplier (Stage 1).

Each stage writes derived properties back to the same ontology that downstream stages read. Stage 2's `is_critical_restore` scopes Stage 3's aggregations and Stage 4's decision variable. Stage 3's `weighted_impact` and Stage 1's `projected_demand_growth` are both objective coefficients in Stage 4. There is no DataFrame ping-pong between stages -- the ontology is the single source of truth, and changing any upstream signal automatically propagates through the rules engine and the optimizer.

## Why this problem matters

A network upgrade decision touches the operator's entire customer base. Picking the wrong tower wastes capex on a low-traffic site; picking too few leaves enterprise customers exposed to repeated outages and accelerates churn at exactly the moment the operator is trying to recover. The chained-reasoner approach grounds each decision in evidence: rules classify which towers are technically broken, graph quantifies who actually routes through them, predictive forecasts whether demand at those sites is growing or contracting, and prescriptive picks the tier mix that maximizes the right combined signal.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1. Predictive | **GNN regression** | `RegionMetric` (composite key date+region), `TemporalEdge` (same-region 1-day-lag pairs) | `RegionGrowth.multiplier` per region; `CellTower.projected_demand_growth` joined via region | Forecast per-region subscriber growth on the Dec test horizon. WEST contracts; eight other regions sit positive (~+0.5 to +0.9%/day in our reference run). |
| 2. Rules | **Rules** (declarative) | `NetworkPerformance` (per-tower measurements), `EquipmentHealth` via `NetworkEquipment` | `CellTower.avg_packet_loss`, `.avg_latency_ms`, `.avg_error_rate`, `.avg_health_score` (Properties), `CellTower.is_critical_restore` (Relationship) | Flag the 15 WEST DEGRADED towers with health < 0.85 -- the upgrade scope for Stage 4. |
| 3. Graph | **Graph** (PageRank) | `Subscriber` nodes, `CallDetailRecord` edges (caller -> callee), `CDR.routed_through(CellTower)` | `Subscriber.influence_score`, `CellTower.impact_count`, `CellTower.weighted_impact` (Properties) | Score subscriber social influence; aggregate per critical tower the distinct callers routing through it and the sum of their PageRank. |
| 4. Prescriptive | **MIP** (gurobi) | `is_critical_restore` (Stage 2), `weighted_impact` (Stage 3), `projected_demand_growth` (Stage 1), `TowerUpgradeOption` cost / capacity / install_weeks | `TowerUpgradeOption.selected` (binary decision Property) | Pick one tier per critical tower under cost + crew-week budgets. Maximize three-factor weighted capacity gain. |

**Key design patterns demonstrated:**

- **Accretive ontology enrichment** -- each stage writes derived properties that downstream stages consume as first-class attributes. No glue code, no DataFrame round-trips between stages.
- **Heterogeneous graph for the GNN** -- `RegionMetric` nodes connected by same-region 1-day-lag `TemporalEdge` pairs, plus `region` as a category feature. Three lag features (prev-day, prev-week, 7-day mean) are computed in pandas before the rows are loaded.
- **Edge-concept call graph** -- `CallDetailRecord` IS the edge concept, with `caller -> callee` as the directed edge. PageRank lands on `Subscriber.influence_score` because `node_concept=Subscriber`.
- **Rule with two branches** -- `CellTower.is_critical_restore` defined twice (DEGRADED-status branch and high-packet-loss branch). RAI semantics: a tower is critical if any branch fires.
- **Three-factor MIP objective** -- the optimizer's coefficient is `capacity_increase x weighted_impact x projected_demand_growth`. Each factor comes from a different reasoner upstream.

## Who this is for

- Telco network operations and capital planning teams
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain GNN, rules, graph, and optimization on a shared ontology

## What you'll build

- A regression GNN on a 365-day x 9-region daily KPI series, with temporal edges and lag features
- A two-branch declarative rule that consumes performance and equipment-health aggregations
- A PageRank computation on a directed call graph plus per-tower blast-radius aggregation
- A binary tower-upgrade MIP whose objective coefficients are the upstream reasoners' outputs
- Ontology-native result extraction -- every reasoner output is a queryable property of the model

## What's included

- `telco_network_recovery.py` -- main script with four chained reasoning stages
- `data/cell_towers.csv` -- 250 cell towers across five regions (15 WEST DEGRADED in scope)
- `data/network_equipment.csv` -- 544 equipment installs (radios, baseband units, antennas)
- `data/equipment_health.csv` -- per-equipment health snapshots (failure rate, MTBF, health score)
- `data/network_performance.csv` -- ~5,000 per-tower performance measurements (packet loss, latency, error rate)
- `data/subscribers.csv` -- 1,200 subscribers (consumer + enterprise)
- `data/call_detail_records.csv` -- 6,000 directed call records (caller, callee, tower)
- `data/tower_upgrade_options.csv` -- 360 upgrade options (3 tiers x 120 in-scope towers)
- `data/time_series_metrics.csv` -- 3,285 daily KPI rows (365 days x 9 regions)

## Prerequisites

### Access

- A Snowflake account with the RelationalAI native app installed
- A Snowflake user with permissions on the RAI native app and on `EXP_DATABASE` (the schema for GNN experiment artifacts)
- A gurobi-enabled prescriptive engine for Stage 4

### Tools

- Python >= 3.10
- RelationalAI Python SDK `relationalai==1.0.14`

### One-time Snowflake setup for GNN experiment artifacts

The predictive reasoner writes training artifacts (model checkpoints, metrics, predictions) to a Snowflake schema that the `RELATIONALAI` native app must own. Pick a database you control (for example a personal sandbox), then grant ownership of the experiments schema to the native app:

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

5. Run the template:

   ```bash
   python telco_network_recovery.py
   ```

6. Expected output (abbreviated):

   ```text
   RegionMetric rows: 3,285  (9 regions x 365 days)
   Cell towers: 250  Subscribers: 1200  CDRs: 6,000
   NetworkPerformance: 5,000  NetworkEquipment: 544  EquipmentHealth: 544
   TowerUpgradeOptions: 360  (3 tiers per tower)
   GNN splits: train=2,745 (<2024-11-01)  val=270 (Nov)  test=270 (Dec)

   STAGE 1: PREDICTIVE -- per-region subscriber-growth GNN
     Per-region GNN-predicted SUBSCRIBER_GROWTH_RATE (Dec 2024 test horizon):
       REGION_ID  MEAN_PREDICTED_GROWTH  MULTIPLIER
            WEST                -0.0002      0.9998
           SOUTH                 0.0045      1.0045
       SOUTHWEST                 0.0051      1.0051
       SOUTHEAST                 0.0053      1.0053
       NORTHEAST                 0.0061      1.0061
         CENTRAL                 0.0070      1.0070
       NORTHWEST                 0.0077      1.0077
            EAST                 0.0083      1.0083
           NORTH                 0.0091      1.0091

   STAGE 2: RULES -- flag is_critical_restore towers
     Flagged critical_restore towers: 15
       TWR-0010 DEGRADED  avg_health 0.48  avg_loss 8.57%  cap_gbps 18
       TWR-0015 DEGRADED  avg_health 0.60  avg_loss 8.59%  cap_gbps 60
       TWR-0009 DEGRADED  avg_health 0.62  avg_loss 9.28%  cap_gbps 17
       ...

   STAGE 3: GRAPH -- PageRank + per-critical-tower blast radius
     Top 10 subscribers by PageRank:
       SUB-CON-00900  CONSUMER     $3,794 LTV   influence 0.0030
       SUB-CON-00723  CONSUMER     $3,049 LTV   influence 0.0030
       SUB-ENT-0038   ENTERPRISE  $283,233 LTV  influence 0.0026
       ...
     Per-critical-tower blast radius:
       TWR-0014  impact_count 61  weighted_impact 0.0502  growth 0.9998
       TWR-0008  impact_count 56  weighted_impact 0.0430  growth 0.9998
       ...

   STAGE 4: PRESCRIPTIVE -- tower upgrade selection MIP
     OPTIMAL plan -- selected upgrades:
       TWR-0014   GOLD  +6 Gbps   $350,864
       TWR-0008   GOLD +10 Gbps   $416,455
       TWR-0011   GOLD  +9 Gbps   $481,914
       ...
       TWR-0005 SILVER  +3 Gbps   $220,435
       TWR-0009 BRONZE  +3 Gbps    $97,784
       ...

     Total cost:               $4,956,843  (budget $5,000,000)
     Total install crew-weeks: 164  (budget 200)
     Capacity restored:        122 Gbps
     Tier mix:                 {'GOLD': 12, 'SILVER': 2, 'BRONZE': 1}
     Towers covered:           15 of 15 critical

   PIPELINE COMPLETE: 4 stages executed on the shared Telco ontology
   ```

## Template structure

```text
telco_network_recovery/
  telco_network_recovery.py   # Main script (4 chained reasoning stages)
  data/
    cell_towers.csv           # 250 towers across 5 regions (15 WEST DEGRADED)
    network_equipment.csv     # 544 equipment installs
    equipment_health.csv      # 544 per-equipment health snapshots
    network_performance.csv   # ~5,000 per-tower measurements
    subscribers.csv           # 1,200 subscribers
    call_detail_records.csv   # 6,000 directed CDRs
    tower_upgrade_options.csv # 360 (tower, tier) options
    time_series_metrics.csv   # 3,285 daily KPI rows (365 x 9 regions)
  README.md                   # this file
  pyproject.toml              # dependencies
```

## How it works

### Stage 1: Predictive -- per-region growth GNN

The GNN predicts daily `SUBSCRIBER_GROWTH_RATE` per region from the other 12 KPIs plus three lag features (`PREV_DAY_GROWTH`, `PREV_WEEK_GROWTH`, `GROWTH_7D_MEAN`). The graph topology is sparse and temporal: each `RegionMetric` connects to its same-region predecessor one day earlier. Train < 2024-11-01 (includes the WEST decline onset in Sep-Oct), validate on November, test on December.

The lag features and temporal edges are computed in pandas before the rows are loaded:

```python
tsm_df["PREV_DAY_GROWTH"] = tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"].shift(1).fillna(0.0)
tsm_df["PREV_WEEK_GROWTH"] = tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"].shift(7).fillna(0.0)
tsm_df["GROWTH_7D_MEAN"] = (
    tsm_df.groupby("REGION")["SUBSCRIBER_GROWTH_RATE"]
    .shift(1).rolling(7, min_periods=1).mean().fillna(0.0)
    .reset_index(level=0, drop=True)
)
```

The per-region mean predicted growth from the test horizon is bundled into a small `RegionGrowth` concept and joined to each tower:

```python
RegionGrowth = model.Concept("RegionGrowth", identify_by={"region": String})
RegionGrowth.multiplier = model.Property(f"{RegionGrowth} has {Float:multiplier}")
rg_src = model.data(per_region[["REGION_ID", "MULTIPLIER"]])
model.define(RegionGrowth.new(region=rg_src.REGION_ID))
model.define(RegionGrowth.multiplier(rg_src.MULTIPLIER)).where(
    RegionGrowth.region == rg_src.REGION_ID,
)

CellTower.projected_demand_growth = model.Property(
    f"{CellTower} has {Float:projected_demand_growth}"
)
model.define(CellTower.projected_demand_growth(RegionGrowth.multiplier)).where(
    RegionGrowth.region == CellTower.region,
)
```

### Stage 2: Rules -- flag is_critical_restore towers

The rule consumes two derived aggregations: average packet loss from `NetworkPerformance` (one row per measurement) and average equipment health from `EquipmentHealth` via the two-hop `EquipmentHealth -> NetworkEquipment -> CellTower` join. The flag fires on either of two branches:

```python
# Branch 1: WEST + DEGRADED status + low equipment health
model.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())

# Branch 2: WEST + high packet loss + low health (catches ACTIVE-but-failing)
model.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())
```

### Stage 3: Graph -- PageRank + blast radius

The Graph reasoner uses Pattern 3 (`edge_concept`): `CallDetailRecord` IS the edge, with `caller -> callee` as the directed edge. PageRank lands directly on `Subscriber.influence_score` because the node concept is `Subscriber`. Per critical tower, the blast radius is the distinct count and the PageRank sum of subscribers whose calls route through it:

```python
call_graph = Graph(
    model, directed=True, weighted=False,
    node_concept=Subscriber, edge_concept=CallDetailRecord,
    edge_src_relationship=CallDetailRecord.caller,
    edge_dst_relationship=CallDetailRecord.callee,
    aggregator="sum",
)
call_graph.Node.influence_score = call_graph.pagerank()

model.define(
    CellTower.weighted_impact(
        aggs.sum(Subscriber.influence_score)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
        )
        .per(CellTower)
    )
)
```

### Stage 4: Prescriptive -- tower upgrade MIP

The decision variable `TowerUpgradeOption.selected` is binary, scoped to options on critical towers. Three constraints (one tier per tower, total cost, total install weeks) and a three-factor objective:

```python
problem.solve_for(
    TowerUpgradeOption.selected,
    where=[TowerUpgradeOption.for_tower(CellTower), CellTower.is_critical_restore()],
    name=["tower_id", "tier"], type="bin",
)

problem.maximize(
    aggs.sum(
        TowerUpgradeOption.selected
        * TowerUpgradeOption.capacity_increase_gbps  # raw upgrade attribute
        * CellTower.weighted_impact                   # Stage 3 (graph)
        * CellTower.projected_demand_growth           # Stage 1 (GNN)
    ).where(
        TowerUpgradeOption.for_tower(CellTower),
        CellTower.is_critical_restore(),
    )
)
```

## Customize this template

- **Tighten the rule** -- adjust the health-score threshold (0.85) or add a third branch (e.g., MAINTENANCE-status with high error rate)
- **Swap PageRank for centrality** -- replace `call_graph.pagerank()` with `betweenness_centrality()` or `eigenvector_centrality()` to reweight blast radius
- **Add a budget scenario axis** -- introduce an `InvestmentLevel` Scenario Concept (per the energy_grid_planning template) so one solve produces the Pareto frontier across multiple budgets
- **Per-tower forecast** -- change the GNN target from `SUBSCRIBER_GROWTH_RATE` to a per-tower demand series (would require a separate `TowerMetric` time series table)
- **Replace bundled CSVs** -- point at your own Snowflake tables via `model.Table(...)` instead of `pd.read_csv(...)` for production-scale data

## Troubleshooting

<details>
<summary>GNN training fails with permission errors on <code>EXP_DATABASE</code></summary>

- The `RELATIONALAI` native app must own the `EXPERIMENTS` schema. Run the one-time setup DDL from the Prerequisites section.
- Verify with `SHOW GRANTS ON SCHEMA <DB>.EXPERIMENTS` -- you should see `OWNERSHIP` granted to `APPLICATION RELATIONALAI`.

</details>

<details>
<summary>Stage 4 returns an infeasible status</summary>

- The 15 critical towers each have at least one BRONZE option that fits within $5M; if you tightened the budget below ~$1.5M the problem becomes infeasible because no full coverage is reachable.
- Consider relaxing `INSTALL_WEEKS_BUDGET` or raising `BUDGET_USD`, or drop the at-most-one-per-tower constraint if partial coverage is acceptable.

</details>

<details>
<summary>WEST predicted growth is positive instead of negative</summary>

- The GNN is sensitive to the seed and epoch count. Defaults (`SEED=42`, `n_epochs=80`) reliably produce a contracting WEST in our test runs, but other seeds may not.
- The Sep-Oct WEST decline is in the training window; if you shrink the training window past the decline onset (e.g., move the val cutoff earlier) the model loses the signal.

</details>

<details>
<summary>Stage 3 PageRank top-10 is dominated by enterprise subscribers</summary>

- This is expected if a few enterprise accounts receive a lot of inbound traffic. PageRank captures structural inbound influence regardless of LTV.
- To weight by LTV, switch the graph to `weighted=True` and pass an edge weight relationship; or post-multiply `influence_score * lifetime_value` when computing `weighted_impact`.

</details>

<details>
<summary>The 15 critical towers don't include the towers I expected</summary>

- The flag is scoped to WEST + DEGRADED + health < 0.85 (Branch 1) OR WEST + packet_loss > 5% + health < 0.85 (Branch 2). Towers in other regions or with healthy equipment will not be flagged.
- Inspect `CellTower.avg_health_score` and `CellTower.avg_packet_loss` for individual towers to debug threshold behavior.

</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) -- chained reasoner patterns and ontology enrichment
- [PyRel v1 query language](https://docs.relational.ai/) -- `model.where(...)` / `aggs` / `.define()`

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) -- regression / classification, PropertyTransformer, temporal edges
- [Graph reasoner](https://docs.relational.ai/) -- node-concept and edge-concept patterns, PageRank and centrality
- [Prescriptive reasoner](https://docs.relational.ai/) -- `Problem` API, decision variables, constraints, objective

### CLI / SDK guides

- [`rai init`](https://docs.relational.ai/) -- one-time configuration

## Support

- File issues at the RelationalAI templates repository
