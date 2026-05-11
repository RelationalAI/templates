# Runbook: Telco Network Recovery — Multi-Reasoner Walkthrough

A regional telco operator must allocate a fixed $5M capex budget and 200 crew-weeks across cell towers in the face of two distinct risk signals — visible operational degradation (some towers are already DEGRADED with elevated packet loss) and predicted equipment failure driven by manufacturer recall/defect advisories. The first signal a SQL query can catch; the second sits on a separate concept (`ModelAdvisory`) and requires the GNN to propagate severity through shared-MODEL message passing. The chain integrates both, then prescriptively chooses upgrade tiers.

## The chain

```
Two distinct risk signals -- operational degradation and predicted
equipment failure -- combined via a multi-hop GNN. Naive SQL catches
6.5% of the true at-risk; a sophisticated join-aware SQL gets to
~85%; the GNN closes the remaining ~15% via 2-hop tower-mate
propagation and a smooth three-way interaction no threshold isolates.
The chain produces a multi-region preventive-maintenance plan within
the $5M / 200-week envelope, restoring 214 Gbps (75% more capacity
than a rules-only plan on the same data).

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Descriptive  ──►  Ontology = 9 concepts incl. ModelAdvisory
                              1,500 equipment, 8 advisories on 7 MODELs
                              (RECALL / DEFECT_BATCH / EOL /
                              FIRMWARE_BUG / SECURITY_PATCH).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Predictive   ──►  NetworkEquipment.predictions (1,500)
                 (GNN)        CellTower.failure_intensity (190)
                              Naive SQL catches 6.5%, join-aware SQL
                              ~85%, GNN-only ~15% (2-hop + smooth).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Rules        ──►  CellTower.is_critical_restore  (166)
                              Three-branch flag: 2 WEST operational
                              branches + 1 predictive branch.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Graph        ──►  Subscriber.influence_score  (PageRank)
                              CellTower.weighted_impact  (166)
                              Distinct subscribers routing through
                              each critical tower, weighted by PageRank.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  TowerUpgradeOption.selected  (39)
                              OPTIMAL · 22 BRONZE · 13 SILVER · 4 GOLD
                              $4,999,671 of $5M (binding) · 214 Gbps
                              195 of 200 install-weeks (near binding)
                              Region: EAST 11, WEST 9, SOUTH 8,
                              CENTRAL 7, NORTH 4.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a telco network ontology from the CSVs in data/. Include a ModelAdvisory concept keyed by MODEL so manufacturer recall/defect/EOL/firmware notices can be linked to every equipment item of the affected model -- the predictive stage will message-pass advisory severity through that edge.
```

**Response**

Concepts: `CellTower`, `NetworkEquipment` (with `tower_id_fk` FK property), `EquipmentHealth` (with `equipment_id_fk` FK property), `NetworkPerformance`, `Subscriber`, `CallDetailRecord` (edge concept: caller → callee, routed_through tower), `TowerUpgradeOption` (composite key tower_id+tier), `ModelAdvisory` (PK: MODEL) — all bound to the bundled CSVs. The FK properties on NetworkEquipment and EquipmentHealth carry the join keys explicitly so Stage 2's GNN can define heterogeneous edges via property equality (the workaround for an SDK iteration-mutation bug when GNN-node concepts also carry `model.Relationship` cross-pointers).

### 2. Examine ontology

**Prompt**

```
/rai-querying Show the ontology as a concept-relationship diagram and report row counts per concept. Cover the advisory coverage too: how many MODELs are advised, what severities, and what fraction of equipment sits on an advised model.
```

**Response**

9 concepts wired to the bundled CSVs: 250 `CellTower`, 1,500 `NetworkEquipment`, 1,500 `EquipmentHealth`, ~5,000 `NetworkPerformance`, 1,200 `Subscriber`, 6,000 `CallDetailRecord`, 750 `TowerUpgradeOption` (3 tiers × 250 towers), 8 `ModelAdvisory` rows on 7 distinct MODELs. Advisory severities span 0.50–0.95 (RECALL / DEFECT_BATCH / FIRMWARE_BUG / EOL / SECURITY_PATCH). About a third of the 1,500 equipment items sit on an advised MODEL — these are the items the GNN's ModelAdvisory edge will surface as elevated-risk.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have $5M of capex and 200 install crew-weeks for tower upgrades. Two distinct risk signals are visible -- operational degradation (already-broken towers in one region) and manufacturer advisories on specific MODELs of equipment. Which RAI reasoners do we need, in what order, to land on a defensible upgrade plan that integrates both signals?
```

**Response**

Plans the 5-reasoner chain on the shared ontology — descriptive (`/rai-querying`) to scope the ontology and advisory landscape; predictive (`/rai-predictive-modeling` + `/rai-predictive-training`) to train an equipment-failure binary classification GNN with a `ModelAdvisory → NetworkEquipment` edge and bind the per-tower `failure_intensity` back to `CellTower`; rules (`/rai-rules-authoring`) to flag critical-restore towers via a three-branch rule combining operational degradation with the predictive intensity; graph (`/rai-graph-analysis`) to score subscriber influence and aggregate per-tower blast radius; prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to compose all three signals into the tier-selection MIP and explain the binding constraint. Discovery flags that this is a canonical GNN-over-SQL case: the advisory signal lives on a separate concept the SQL alternative can't trivially incorporate.

### 4. Train the equipment-failure GNN

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Train a binary classification GNN on NetworkEquipment.STATUS (AT_RISK = STATUS in {FAILING, WARNING}). The graph should include three heterogeneous edges: EquipmentHealth -> NetworkEquipment via equipment_id_fk; NetworkEquipment -> CellTower via tower_id_fk; ModelAdvisory -> NetworkEquipment via shared MODEL. Sum predicted failure probability per tower into CellTower.failure_intensity. Show a side-by-side check: how many at-risk items does a SQL filter on HEALTH_SCORE < 0.5 catch vs the GNN?
```

**Response**

GNN binary classification with `eval_metric=roc_auc`, 80 epochs, three FK / shared-MODEL edges on an **undirected** graph (`directed=False`) so signal can flow both ways across `Equipment ↔ Tower ↔ Equipment` and propagate the 2-hop neighbor-advisory pattern. PropertyTransformer pulls equipment / health / tower / advisory features (category, continuous, integer, datetime). Train/val/test split is 1050/225/1500 (test = all equipment so every item gets a prediction). Per-equipment positive-class probabilities are summed per tower in pandas and loaded back as `CellTower.failure_intensity` via a `TowerFailureScore` bridge concept. The script prints a three-tier SQL-vs-GNN comparison: naive SQL on `HEALTH_SCORE < 0.5` catches 6.5%; join-aware SQL with `OR model IN advised_models` gets to ~85%; the GNN closes the remaining ~15% via 2-hop tower-mate propagation and the smooth three-way interaction term. Per-tower `failure_intensity` distribution: min 0.09, median 3.06, max 8.67 — graded enough that the Stage 4 objective gets a real priority signal.

### 5. Flag critical-restore towers

**Prompt**

```
/rai-rules-authoring Define CellTower.is_critical_restore with three branches: (1) WEST + DEGRADED + avg equipment health below 0.85; (2) WEST + avg packet loss above 5% + low health -- this catches ACTIVE-but-failing in the operational region; (3) failure_intensity above the configurable threshold -- this catches predicted-failure towers in any region. Use FK property-equality for the two-hop equipment-health-to-tower aggregation.
```

**Response**

Four derived health properties (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) computed for all 250 towers; the equipment-health aggregation traverses `EquipmentHealth.equipment_id_fk == NetworkEquipment.id` and `NetworkEquipment.tower_id_fk == CellTower.id`. The three-branch `CellTower.is_critical_restore` relationship fires on 166 towers spanning all five regions. The GNN's third branch contributes almost all of them — the WEST operational branches alone would produce only the 15 in-region cases the rule-only baseline would have caught.

### 6. Score subscriber blast radius

**Prompt**

```
/rai-graph-analysis Who are our most socially influential subscribers based on call patterns? For each critical-restore tower, score its blast radius -- how many distinct subscribers route calls through it, weighted by their influence.
```

**Response**

`Subscriber.influence_score` (PageRank) on all 1,200 subscribers; `CellTower.weighted_impact` and `CellTower.impact_count` on ~125 critical towers. Multi-region scope means the blast-radius story spans the operator's full customer base, not just the WEST cohort.

### 7. Optimize tier selection

**Prompt**

```
/rai-prescriptive-problem-formulation Stay within $5M and 200 install-weeks. For each critical-restore tower, pick at most one upgrade tier (BRONZE / SILVER / GOLD) that maximizes capacity restored, weighted by each tower's blast radius (Stage 4) and its predicted failure intensity (Stage 2).
```

**Response**

Status OPTIMAL; 39 towers covered (selected from the 166 flagged) across all five regions (EAST 11, WEST 9, SOUTH 8, CENTRAL 7, NORTH 4). Tier mix is 22 BRONZE / 13 SILVER / 4 GOLD — the predictive-intensity factor lets smaller upgrades on many towers outscore premium upgrades on few; the plan is dominantly preventive-maintenance, not WEST recovery. Total capacity restored 214 Gbps. Budget is binding at $4,999,671 of $5,000,000; install-weeks at 195 of 200 are near-binding, indicating crew capacity is the next constraint to relax if scope expands further.

### 8. Interpret the plan

**Prompt**

```
/rai-prescriptive-results-interpretation Summarize the plan: total cost, capacity restored, tier mix, towers covered. Which constraints are binding, and what would relaxing them unlock?
```

**Response**

Budget is binding ($4,999,671 / $5,000,000); install-weeks at 195 / 200 are near-binding. The two constraints are close enough that the next scope expansion needs both relaxed together — the 127 flagged-but-not-selected towers can't all be reached by relaxing budget alone. A sensitivity sweep would show the marginal-Gbps-per-dollar curve flattening as the optimizer moves down the predicted-failure-intensity ranking.

### 9. Validate against the SQL alternative

**Prompt**

```
/rai-querying Pull the equipment IDs the GNN flagged as positive (predicted_label == 1) and compare against a SQL-equivalent set: equipment with HEALTH_SCORE < 0.5. Report the overlap and what fraction of the GNN-flagged-only set sits on an advised MODEL.
```

**Response**

The comparison surfaces three tiers of at-risk equipment. The naive `WHERE health_score < 0.5` query catches the small "health-driven" tail (~6% of true at-risk). A more sophisticated **join-aware SQL** that also adds `OR model IN advised_models` jumps to ~85% — but it still misses the **2-hop neighbor-driven** cases (equipment on a clean MODEL whose tower-mate is on a recalled one) and the **smooth three-way interaction** cases (moderate advisory + moderate health + outdated firmware compounding into elevated risk that no single threshold isolates). The GNN catches both via its heterogeneous undirected graph -- the remaining ~15% gap is the uniquely GNN-distinctive set.

### 10. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Materialize the optimal plan and the selected upgrades as queryable ontology. Add a RestorePlan concept holding the plan summary (total cost, install-weeks, capacity restored, tier-mix counts, towers covered, binding constraints) and a SelectedUpgrade view restricted to the chosen tower-tier rows.
```

**Response**

Ontology gains a singleton `RestorePlan` Concept with `total_cost`, `total_install_weeks`, `capacity_restored_gbps`, `gold_count`, `silver_count`, `bronze_count`, `towers_covered`, `binding_constraints` (now a list); plus `SelectedUpgrade` (a view over the chosen rows of `TowerUpgradeOption`). Headline plan numbers are queryable as ontology, not stdout.

## Data

Bundled CSVs in `data/`: 250 cell towers (15 WEST DEGRADED), 1,500 NetworkEquipment items across ~20 consolidated MODELs, 1,500 EquipmentHealth snapshots, ~5,000 NetworkPerformance measurements, 1,200 subscribers, 6,000 CDRs, 750 TowerUpgradeOptions (3 tiers × 250 towers), 8 ModelAdvisory rows on 7 distinct MODELs. The synthesis script `data/_synthesize_advisory_data.py` regenerates the equipment / health / advisory / upgrade-option CSVs deterministically from a seed. The AT_RISK label is governed by a weighted sum of five signals: own-model advisory severity (0.25), tower-mate's advisory severity (0.45 -- the multi-hop signal), health gap (0.10), outdated-firmware flag (0.05), and a smooth three-way interaction (advisory × health_gap × firmware-outdated, weight 0.10). This is designed so a SQL query on equipment columns alone misses most of the risk, and even a join-aware SQL on `ModelAdvisory` still leaves a measurable gap the GNN closes via 2-hop neighbor message passing. All five stages run end-to-end via `telco_network_recovery.py`.
