# Runbook: Telco Network Recovery — Multi-Reasoner Walkthrough

A regional telco operator must allocate a fixed $5M capex budget and 200 crew-weeks across cell towers in the face of two distinct risk signals — visible operational degradation (some towers are already DEGRADED with elevated packet loss) and predicted equipment failure driven by manufacturer recall/defect advisories on specific equipment MODELs. The chain integrates both signals plus a customer-impact weighting (revenue × churn), then prescriptively chooses upgrade tiers within the capex envelope.

> **Headline figures below** are from a real Snowflake-backed run. The GNN is stochastic, so they shift run-to-run; the *structural* outcome reproduces — multi-region coverage, budget binding, ~180-210 Gbps across ~25-40 towers, tier mix tilting toward GOLD on high-value enterprise towers. See the template README's *Customize this template* > *Tune parameters* for the impact-measure knobs.

## The chain

```
Ontology: 8 source-data concepts including Advisory, which the model reduces to
ModelAdvisory; 1,500 equipment items, 8 advisories on 7 MODELs. The chain produces a multi-region preventive-
maintenance plan within the $5M / 200-week envelope, restoring ~180 Gbps
of capacity across ~27 selected towers (out of 142 flagged
critical-restore) in all 5 regions. (The GNN is stochastic — exact
figures shift run to run; the structural outcome holds.)

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  NetworkEquipment.predictions (1,500)
   /rai-predictive-           TowerFailureScore.failure_intensity (190)
   modeling                   Per-tower SUM of equipment failure
                              probabilities; range 0.02-10.47.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  CellTower.is_critical_restore  (142)
   /rai-pyrel                 Three-branch flag: 2 WEST operational
                              branches + 1 predictive branch.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Subscriber.influence_score  (PageRank,
   /rai-graph-analysis        graph-reasoner signal); CellTower.
                              weighted_impact = sum of caller
                              customer_value (LTV x churn, ACTIVE
                              only) — headline; weighted_pagerank
                              kept as secondary network-effect view.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Paths        ──►  Subscriber.top_call_path_influence
   /rai-graph-analysis        198 simple call paths (≤ 3 hops) from
                              the top-PageRank hub; 54 routing towers
                              recovered; top influence load kept.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  TowerUpgradeOption.selected  (27)
   /rai-prescriptive-problem  OPTIMAL · 12 BRONZE · 7 SILVER · 8 GOLD
                              $4,992,276 of $5M (binding) · 180 Gbps
                              161 of 200 install-weeks (slack)
                              Region: SOUTH 7, EAST 6, WEST 6,
                              CENTRAL 4, NORTH 4.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-ontology Build a telco network ontology from the CSVs in data/. Include a ModelAdvisory concept so manufacturer recall/defect/EOL/firmware notices can be linked to every equipment item of the affected model.
```

**Response**

Concepts: `CellTower`, `NetworkEquipment` (with `tower_id_fk` FK property), `EquipmentHealth` (with `equipment_id_fk` FK property), `NetworkPerformance`, `Subscriber`, `CallDetailRecord` (edge concept: caller → callee, routed_through tower), `TowerUpgradeOption` (composite key tower_id+tier), `ModelAdvisory` (PK: MODEL) — all bound to the bundled CSVs. The FK properties on `NetworkEquipment` and `EquipmentHealth` carry the join keys explicitly so the GNN can define heterogeneous edges via property equality.

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, how many rows are in each, and what's the advisory coverage — how many MODELs are advised, what are the severities, and what fraction of equipment sits on an advised MODEL?
```

**Response**

8 source-data concepts wired to the bundled CSVs: 250 `CellTower`, 1,500 `NetworkEquipment`, 1,500 `EquipmentHealth`, 5,000 `NetworkPerformance`, 1,200 `Subscriber`, 6,000 `CallDetailRecord`, 750 `TowerUpgradeOption` (3 tiers × 250 towers), 8 `Advisory` rows on 7 distinct MODELs (severities `0.50–0.95`), which the model keeps as 7 `ModelAdvisory` rows, the most severe per MODEL. 572 of 1,500 equipment items (38.1%) sit on an advised MODEL — the relational-neighbor signal the GNN's `ModelAdvisory → NetworkEquipment` edge propagates; 597 (39.8%) carry the binary `AT_RISK` label (`STATUS in FAILING / WARNING`) — the GNN's prediction target, distinct from advised-MODEL coverage.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have $5M of capex and 200 install crew-weeks for tower upgrades. Two distinct risk signals are visible -- operational degradation (already-broken towers in one region) and manufacturer advisories on specific MODELs of equipment. Which RAI reasoners do we need, in what order, to land on a defensible upgrade plan that integrates both signals?
```

**Response**

Plans the 5-reasoner chain on the shared ontology — descriptive (`/rai-pyrel`) to scope the ontology and advisory landscape; predictive (`/rai-predictive-modeling` + `/rai-predictive-training`) to train an equipment-failure binary classification GNN with a `ModelAdvisory → NetworkEquipment` edge and sum the predictions per tower into `TowerFailureScore.failure_intensity`; rules (`/rai-pyrel`) to flag critical-restore towers via a three-branch rule combining operational degradation with the predictive intensity; graph (`/rai-graph-analysis`) to compute subscriber PageRank and aggregate per-tower customer impact (revenue × churn across ACTIVE callers); prescriptive (`/rai-prescriptive-problem` + `/rai-prescriptive-results`) to compose all three signals into the tier-selection MIP and explain the binding constraint.

### 4. Train the equipment-failure GNN

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Which equipment items are at risk of failure, factoring in not just each item's own health metrics but the broader fleet context — manufacturer advisories on the same model, and the health of other equipment on the same tower? Roll the per-equipment predictions up to a per-tower failure-intensity score so downstream reasoners can use it for prioritization.
```

**Response**

GNN binary classification with `eval_metric=roc_auc`, 80 epochs, three FK / shared-MODEL edges on an **undirected** graph (`directed=False`) so signal flows both ways across `Equipment ↔ Tower ↔ Equipment` and propagates the 2-hop neighbor-advisory pattern. PropertyTransformer pulls equipment / health / tower / advisory features (category, continuous, integer, datetime). Train/val/test split is 1050/225/1500 (test = all equipment so every item gets a prediction). A rule sums the per-equipment positive-class probabilities per tower into `TowerFailureScore.failure_intensity`, a concept keyed by tower id: a `CellTower` property derived from the predictions would make the predictions depend on themselves, because the GNN reads the `CellTower` table. Per-tower `failure_intensity` distribution: min 0.02, median 2.92, max 10.47 — graded enough to give the prescriptive objective a real priority signal.

### 5. Flag critical-restore towers

**Prompt**

```
/rai-pyrel Which towers should we flag as critical-restore? Any tower fitting one of three cases: (1) in WEST and DEGRADED with poor equipment health (avg health below 0.85); (2) in WEST and showing high packet loss (above 5%) with poor health — catches ACTIVE-but-failing towers operations would otherwise miss; (3) predicted equipment-failure intensity above 1.5 (any region) — catches towers where multiple equipment items are at risk before they fail. Compute the per-tower health average by joining EquipmentHealth through NetworkEquipment to CellTower.
```

**Response**

Four derived health properties (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) computed for all 250 towers; the equipment-health aggregation joins from EquipmentHealth through NetworkEquipment to CellTower. The three-branch `CellTower.is_critical_restore` relationship fires on 142 towers spanning all five regions, distributed: WEST 43, EAST 32, SOUTH 25, NORTH 23, CENTRAL 19. Per-branch contribution: Branch 1 fires on 12 towers, Branch 2 fires on 12 towers, Branch 3 (`failure_intensity > 1.5`) fires on 139 towers — 130 of which are flagged ONLY by the predictive branch (92% of the flagged set). 3 of the 15 WEST DEGRADED towers happen to have avg_health ≥ 0.85 in the augmented data and don't trip Branch 1 (though all 15 still fire on Branch 3 via their predicted failure_intensity).

### 6. Score per-tower customer impact

**Prompt**

```
/rai-graph-analysis For each critical-restore tower, what is the customer impact at stake if the tower fails — the total revenue at risk, weighted by churn urgency? For each tower, give us two summed scores across the ACTIVE subscribers routed through it: one weights each subscriber by `lifetime_value × (1 + churn_risk_score)`, and the other weights each by their structural importance on the call graph, where importance flows along incoming directed call edges so subscribers receiving calls from other heavily-called subscribers score high.
```

**Response**

`Subscriber.influence_score` (PageRank, 1,200 subs) plus two per-tower properties on the 142 critical towers: `CellTower.weighted_impact` (headline — sum of `Subscriber.customer_value = LTV × (1 + churn_risk_score)` over the distinct ACTIVE callers routed through, each counted once per tower) and `CellTower.weighted_pagerank` (secondary — sum of PageRank influence over the same set). The prescriptive MIP consumes `weighted_impact` in its objective.

### 7. Trace the most-influential call paths (PREVIEW)

**Prompt**

```
/rai-graph-analysis Starting from our most influential subscriber, how many call paths of up to three hops run through the network, how many distinct cell towers carry them, and how much social influence does the strongest path carry — the path running through the subscribers with the highest combined importance, where a subscriber is influential when influential subscribers call them? Don't revisit a subscriber.
```

**Response**

Where PageRank scores a *subscriber*, paths scores the *route*. From the top-PageRank hub (SUB-CON-00900), 198 simple call paths (≤ 3 hops) are enumerated over an arity-3 caller-via-tower-callee edge, recovering 54 distinct routing towers; each path is ranked by summed PageRank, rounded to six decimals. The highest influence load is 0.009041, persisted for the hub as `Subscriber.top_call_path_influence`, and the winning route is published hop by hop, with its routing towers, as `TopCallPathStep` and `TopCallPathHop`. (Scoped to a seed hub — the full call graph is large and cyclic.)

### 8. Optimize tier selection

**Prompt**

```
/rai-prescriptive-problem Which tower upgrade plan maximizes weighted capacity restored within our $5M capex and 200 install-week envelope? For each critical-restore tower, pick at most one upgrade tier — BRONZE, SILVER, or GOLD. Each option's contribution to the objective is its `capacity_increase_gbps` multiplied by the tower's `weighted_impact` and its `failure_intensity` — a three-factor product so a high-failure-intensity tower serving high-revenue, churn-fragile accounts outscores a low-risk one.
```

**Response**

Status OPTIMAL; 27 towers covered (selected from the 142 flagged) across all five regions (SOUTH 7, EAST 6, WEST 6, CENTRAL 4, NORTH 4). Tier mix 12 BRONZE / 7 SILVER / 8 GOLD — the customer-value × failure-intensity objective rewards concentrating spend on high-revenue, high-risk towers. Total capacity restored 180 Gbps; budget binding ($4,992,276 / $5,000,000); install-weeks have slack (161 / 200). Each selected tower carries a `rationale` tag (`operational` / `advisory/predicted` / `high-value`): in this run, all 27 fired on `advisory/predicted`, 17 also on `high-value`, 2 on `operational` (towers can fire on multiple signals).

### 9. Interpret the plan

**Prompt**

```
/rai-prescriptive-results What is the final plan we ended up with — total cost, capacity restored, tier mix, towers covered? Which constraints are binding, and what would relaxing them unlock?
```

**Response**

Budget is the binding constraint ($4,992,276 of $5M); install-weeks have ~20% slack (161 of 200) because the objective concentrates spend on fewer, higher-value GOLD upgrades. The ~115 flagged-but-not-selected towers would unlock primarily with more capex, not more crews. A sensitivity sweep would show the marginal-Gbps-per-dollar curve flattening as the optimizer moves down the `customer-value × failure-intensity` ranking.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology Materialize the optimal plan and the selected upgrades as queryable ontology. Add a RestorePlan concept holding the plan summary (total cost, install-weeks, capacity restored, tier-mix counts, towers covered, binding constraint) and mark the chosen tower-tier rows on TowerUpgradeOption.
```

**Response**

Ontology gains a singleton `RestorePlan` Concept with `total_cost`, `total_install_weeks`, `capacity_restored_gbps`, `gold_count`, `silver_count`, `bronze_count`, `towers_covered`, and `binding_constraint` (a single String — `"budget"`, `"install_weeks"`, or `"none"`); plus a `TowerUpgradeOption.is_selected_upgrade` relationship marking the chosen tower-tier rows. Headline plan numbers are queryable as ontology, not stdout.

## Data

Bundled CSVs in `data/`: 250 cell towers (15 WEST DEGRADED), 1,500 `NetworkEquipment` items across 18 consolidated MODELs, 1,500 `EquipmentHealth` snapshots, 5,000 `NetworkPerformance` measurements, 1,200 subscribers, 6,000 CDRs, 750 `TowerUpgradeOption` rows (3 tiers × 250 towers), 8 `Advisory` rows on 7 distinct MODELs (severities 0.50–0.95). `data/_synthesize_advisory_data.py` regenerates the equipment / health / advisory / upgrade-option CSVs deterministically from a seed. The chain's stages are declared in `model/` (`schema.py`, `source.py`, and one module per stage: `equipment_failure.py`, `advisory_signals.py`, `critical_towers.py`, `customer_impact.py`, `call_paths.py`, `tower_upgrades.py`), trained with `train.py`, and read by `queries/recovery_report.py`.
