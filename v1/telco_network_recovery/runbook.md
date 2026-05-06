# Runbook: Telco WEST Recovery — Multi-Reasoner Walkthrough

WEST revenue collapsed ~29% in Q4 2024 (a ~$2.7M shortfall vs the other-regions average) while every other region held flat or grew. No single reasoner can answer where to spend a $5M recovery budget: descriptive scopes the crisis, rules flag broken towers, graph weights them by social blast radius, predictive forecasts forward demand, and prescriptive composes all four signals into the upgrade plan. Each stage writes derived properties back to the same ontology that downstream stages consume.

## The chain

```
WEST Q4 revenue is down ~29% (~$2.7M gap vs the other-regions avg).
The chain produces a $5M plan that recovers 122 Gbps capacity
across all 15 critical towers, prioritized by social blast radius.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Descriptive  ──►  WEST: Q4 revenue −29% vs H1 baseline,
                              avail 94.6 vs 99.5, 15 of 81 DEGRADED.
                              Retention angle? No — this is
                              operational, not subscriber churn.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  CellTower.is_critical_restore  (15)
                              4 derived health metrics + a compound
                              flag: WEST + DEGRADED + health < 0.85.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Subscriber.influence_score  (PageRank)
                              CellTower.weighted_impact  (15)
                              404 distinct subs (33% of base) route
                              calls through a critical tower.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Predictive   ──►  CellTower.projected_demand_growth (250)
                 (GNN)        WEST: 0.9998×  ── flat/slightly contracting
                              while 8 other regions sit at +0.45 to +0.91%/day.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  TowerUpgradeOption.selected  (15)
                              OPTIMAL · 12 GOLD · 2 SILVER · 1 BRONZE
                              $4.96M of $5M (binding) · 122 Gbps
                              164 of 200 install-weeks (slack)
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a telco network ontology from the eight CSVs in data/: cell_towers, network_equipment, equipment_health, network_performance, subscribers, call_detail_records, tower_upgrade_options, time_series_metrics. The time-series file has one row per (date, region); make sure that's modelled as a composite-key concept since we'll want to forecast region-level trends later.
```

**Response**

Concepts: `CellTower`, `NetworkEquipment`, `EquipmentHealth`, `NetworkPerformance`, `Subscriber`, `CallDetailRecord` (edge concept: caller → callee, routed_through tower), `TowerUpgradeOption` (composite key tower_id+tier), `RegionMetric` (composite key metric_date+region) — all bound to the bundled CSVs. Step 7 (predictive) introduces a same-region 1-day-lag `TemporalEdge` concept derived from `RegionMetric` for GNN message passing.

### 2. Examine ontology

**Prompt**

```
/rai-querying Show the ontology as a concept-relationship diagram and report row counts per concept and the data range covered.
```

**Response**

9 concepts wired to the bundled CSVs: 250 `CellTower`, 1,200 `Subscriber`, 6,000 `CallDetailRecord`, ~5,000 `NetworkPerformance`, 544 `NetworkEquipment`, 544 `EquipmentHealth`, 360 `TowerUpgradeOption`, 3,285 `RegionMetric` (365d × 9 regions), plus same-region 1-day-lag `TemporalEdge` rows for the GNN.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery WEST is missing revenue targets while every other region grows. We have a $5M capex budget and 200 install crew-weeks to allocate to tower upgrades. Which RAI reasoners do we need, in what order, to land on a defensible upgrade plan grounded in the available data (towers, subscribers, calls, equipment health, performance, daily KPIs, and tiered upgrade options)?
```

**Response**

Plans the 4-reasoner chain on the shared ontology — descriptive (`/rai-querying`) to scope the WEST crisis and rule out a retention angle; rules (`/rai-rules-authoring`) to flag critical-restore towers; graph (`/rai-graph-analysis`) to score subscriber influence and aggregate per-tower blast radius; predictive (`/rai-predictive-modeling` + `/rai-predictive-training`) to forecast per-region growth and bind it as a per-tower demand multiplier; prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to compose all three signals into the tier-selection MIP and explain the binding constraint.

### 4. Diagnose WEST

**Prompt**

```
/rai-querying Where are we missing revenue targets, and which region has the worst Q4 2024 network availability? For the worst region, show the cell tower fleet by status and how bad the degraded towers look on packet loss.
```

**Response**

WEST Q4 avail 94.6% vs 99.5% in every other region; WEST Q4 revenue $6.6M vs ~$9.0–9.5M everywhere else (≈$2.7M Q4 deficit, −29% vs WEST's own H1 baseline); 81 WEST towers split into 49 ACTIVE / 17 MAINTENANCE / 15 DEGRADED, with the 15 DEGRADED towers averaging 7.6–10.3% packet loss (median ~8.2%). Subscriber-churn signals stay flat — this is an operational network failure, not retention.

### 5. Flag critical-restore towers

**Prompt**

```
/rai-rules-authoring Flag towers as critical-restore if they're in WEST and either (a) DEGRADED with poor average equipment health (below 0.85), or (b) showing high average packet loss (above 5%) with poor health — the second branch catches ACTIVE-but-failing towers.
```

**Response**

4 derived health properties (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) computed for all 250 towers via `aggs.avg(...).per(CellTower)`. The two-branch `CellTower.is_critical_restore` relationship fires on 15 towers — all 15 are WEST + DEGRADED + health < 0.85, so Branch 1 alone produces the same set, but Branch 2 is kept as a guard against ACTIVE-but-failing failure modes.

### 6. Score subscriber blast radius

**Prompt**

```
/rai-graph-analysis Who are our most socially influential subscribers based on call patterns? For each critical-restore tower, score its blast radius — how many distinct subscribers route calls through it, weighted by their influence.
```

**Response**

`Subscriber.influence_score` (PageRank) on all 1,200 subs; `CellTower.weighted_impact` on 15 critical towers; 404 distinct subs (33% of base) route through a critical tower; TWR-0014 has the largest footprint (61 subs, 0.0502).

### 7. Forecast regional demand

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Predict next-quarter subscriber growth per region from the daily KPI history (train on data through October, validate Nov, test Dec). Bind each region's forecast back to its towers as a demand multiplier.
```

**Response**

GNN node regression on 365d × 9 regions with same-region 1-day-lag temporal edges; per-region mean of the Dec test predictions yields WEST multiplier ≈0.9998× (flat/slightly contracting) while the 8 other regions sit at +0.45% to +0.91%/day. The multiplier is loaded into a `RegionGrowth` concept and joined to `CellTower.projected_demand_growth` via region — populating all 250 towers (CellTower covers 5 regions; the other 4 RegionMetric regions are forecast but have no towers to bind to).

### 8. Optimize tier selection

**Prompt**

```
/rai-prescriptive-problem-formulation Recover WEST capacity within $5M and 200 install-weeks. For each critical-restore tower, pick at most one upgrade tier (BRONZE, SILVER, or GOLD) that maximizes capacity restored, weighted by each tower's blast radius and the regional demand forecast.
```

**Response**

Status OPTIMAL with all 15 critical towers covered (one tier each). Tier mix: 12 GOLD / 2 SILVER / 1 BRONZE. Total capacity restored 122 Gbps. Total cost $4,956,843 of the $5M budget (binding). Total install crew-weeks 164 of 200 (slack). The tier mix skews toward GOLD because the per-Gbps cost on GOLD is competitive once it is multiplied by `weighted_impact` and `projected_demand_growth` in the objective.

### 9. Interpret the plan

**Prompt**

```
/rai-prescriptive-results-interpretation Summarize the plan: total cost, capacity restored, tier mix, towers covered. Which constraint is binding, and what would relaxing it by 10-20% unlock?
```

**Response**

Budget is binding at $4.96M/$5M (only $43K of headroom); a re-solve at higher budget would quantify which BRONZE/SILVER swaps unlock — TWR-0009 BRONZE → GOLD is the next-cheapest tier upgrade in the candidate set. Install-weeks have 36 weeks of slack (164/200) so crew capacity is not the bottleneck. All 15 critical towers are covered, so the 404 service-affected subscribers identified by the graph stage are addressed within the rollout window.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Materialize the optimal plan and the 15 selected upgrades as queryable ontology. Add a RestorePlan concept holding the plan summary (total cost, install-weeks, capacity restored, tier-mix counts, towers covered, binding constraint) and a SelectedUpgrade view restricted to the chosen tower-tier rows.
```

**Response**

Ontology gains a singleton `RestorePlan` Concept with `total_cost`, `total_install_weeks`, `capacity_restored_gbps`, `gold_count`, `silver_count`, `bronze_count`, `towers_covered`, `binding_constraint`; plus `SelectedUpgrade` (a view over the 15 chosen rows of `TowerUpgradeOption`). All headline plan numbers — $4,956,843 / 164 weeks / 122 Gbps / 12 GOLD / 2 SILVER / 1 BRONZE / 15 covered — are now queryable as ontology, not stdout.

## Data

Bundled CSVs in `data/`: 250 cell towers (15 WEST DEGRADED), 1,200 subscribers, 6,000 directed CDRs, ~5,000 NetworkPerformance measurements, 544 NetworkEquipment + EquipmentHealth rows, 360 TowerUpgradeOptions (3 tiers × 120 in-scope towers), 3,285 daily KPI rows (365 days × 9 regions). All stages run end-to-end via `telco_network_recovery.py`.
