# Runbook: Telco WEST Recovery — Multi-Reasoner Walkthrough

A regional telco is bleeding $791K/quarter from WEST while every other region grows. No single reasoner can answer where to spend a $5M recovery budget: descriptive scopes the crisis, rules flag broken towers, graph weights them by social blast radius, predictive forecasts forward demand, and prescriptive composes all three signals into the upgrade plan. Each stage writes derived properties back to the same ontology that downstream stages consume.

## The chain

```
WEST is bleeding $791K/quarter from a network operations crisis.
The chain produces a $5M plan that recovers 122 Gbps capacity
across all 15 critical towers, prioritized by social blast radius.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Descriptive  ──►  WEST: Q3-Q4 revenue −22% to −26%,
                              avail 94.6 vs 99.5, 15 of 81 DEGRADED.
                              Retention angle? No — 0 high-risk
                              subs; this is operational.
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
  STAGE 4  Predictive   ──►  CellTower.projected_demand_growth (15)
                 (GNN)        WEST: 0.993×  ── shrinking ~0.7%/yr
                              while 8 other regions sit at +0.59 to +0.75%/day.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  TowerUpgradeOption.selected  (15)
                              OPTIMAL · 12 GOLD · 2 SILVER · 1 BRONZE
                              $4.96M of $5M (binding) · 122 Gbps
                              164 of 200 install-weeks (slack)
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 0. Discovery

- Prompt: `/rai-discovery WEST is missing revenue while every other region grows. What questions do we need to answer to figure out where to spend $5M to fix it?`
- Response: Routes sub-questions to descriptive (revenue diagnosis), rules (critical-tower flag), graph (PageRank blast radius), predictive (demand forecast), prescriptive (tier-selection MIP + post-solve interpretation).

### 1. Diagnose WEST

- Prompt: `/rai-querying Where are we missing revenue targets? Which 10 cell towers have the worst average packet loss over 2024, and which region has the worst Q4 network availability?`
- Response: WEST avail 94.6 vs 99.5 elsewhere; Q3-Q4 revenue −22% to −26% ($791K gap); 15 of 81 WEST towers DEGRADED at 8.1–8.9% packet loss; zero high-risk subs — operational, not retention.

### 2. Flag critical-restore towers

- Prompt: `/rai-rules-authoring Flag CellTowers as 'critical-restore' if region is WEST AND status is DEGRADED AND avg equipment health is below 0.85, OR if avg packet loss > 5% with health below 0.85.`
- Response: `CellTower.is_critical_restore` fires on 15 WEST DEGRADED towers; 4 derived health metrics (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) written to all 250 towers.

### 3. Score subscriber blast radius

- Prompt: `/rai-graph-analysis Who are our most socially influential subscribers based on call patterns? For each critical-restore tower, count the distinct subscribers whose calls route through it and rank by total PageRank influence — that's the blast radius if it fails.`
- Response: `Subscriber.influence_score` (PageRank) on all 1,200 subs; `CellTower.weighted_impact` on 15 critical towers; 404 distinct subs (33% of base) route through a critical tower; TWR-0014 has the largest footprint (61 subs, 0.0502).

### 4. Forecast regional demand

- Prompt: `/rai-predictive-modeling + /rai-predictive-training Predict next-quarter subscriber-growth-rate per region using TimeSeriesMetric history. Bind each region's forecast back to its towers as a demand multiplier.`
- Response: GNN node regression on 365d × 9 regions with 1-day-lag temporal edges; WEST multiplier 0.993× (contracting ~0.7%); 8 other regions +0.59 to +0.75%/day; written to `CellTower.projected_demand_growth` for 15 critical towers.

### 5. Optimize tier selection

- Prompt: `/rai-prescriptive-problem-formulation Recover WEST capacity within $5M and 200 install-weeks, prioritizing towers by social blast radius and forward-looking demand. From TowerUpgradeOption, pick at most one upgrade tier (BRONZE/SILVER/GOLD) per critical-restore tower, maximizing Σ capacity_increase × weighted_impact × projected_demand_growth.`
- Response: OPTIMAL · 12 GOLD / 2 SILVER / 1 BRONZE · 122 Gbps restored · $4.96M of $5M (binding) · 164 of 200 install-weeks (slack) · all 15 towers covered.

### 6. Interpret the plan

- Prompt: `/rai-prescriptive-results-interpretation Summarize the plan: total cost, capacity restored, tier mix, towers covered. Which constraint is binding, and what would relaxing it by 10-20% unlock?`
- Response: Budget binds at $4.96M/$5M; flexing to $6M would promote TWR-0009 BRONZE→GOLD (+9 Gbps); install-weeks have 36-week slack; 404 service-affected subs drop to ~0 over the 4-month rollout.

## Data

Bundled CSVs in `../data/`: 250 cell towers (15 WEST DEGRADED), 1,200 subscribers, 6,000 directed CDRs, ~5,000 NetworkPerformance measurements, 544 NetworkEquipment + EquipmentHealth rows, 360 TowerUpgradeOptions (3 tiers × 120 in-scope towers), 3,285 daily KPI rows (365 days × 9 regions). All stages run end-to-end via `../telco_network_recovery.py`.
