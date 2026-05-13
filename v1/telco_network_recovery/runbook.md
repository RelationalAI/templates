# Runbook: Telco Network Recovery — Multi-Reasoner Walkthrough

A regional telco operator must allocate a fixed $5M capex budget and 200 crew-weeks across cell towers in the face of two distinct risk signals — visible operational degradation (some towers are already DEGRADED with elevated packet loss) and predicted equipment failure driven by manufacturer recall/defect advisories on specific equipment MODELs. The chain integrates both signals, then prescriptively chooses upgrade tiers within the capex envelope.

## The chain

```
Ontology: 8 concepts including ModelAdvisory; 1,500 equipment items,
8 advisories on 7 MODELs (RECALL / DEFECT_BATCH / EOL / FIRMWARE_BUG
/ SECURITY_PATCH). The chain produces a multi-region preventive-
maintenance plan within the $5M / 200-week envelope, restoring 214
Gbps of capacity across 39 selected towers (out of 166 flagged
critical-restore) in all 5 regions.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  NetworkEquipment.predictions (1,500)
                 (GNN)        CellTower.failure_intensity (190)
                              Per-tower SUM of equipment failure
                              probabilities; range 0.09-8.67.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  CellTower.is_critical_restore  (166)
                              Three-branch flag: 2 WEST operational
                              branches + 1 predictive branch.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Subscriber.influence_score  (PageRank)
                              CellTower.weighted_impact  (166)
                              Distinct subscribers routing through
                              each critical tower, weighted by PageRank.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Prescriptive ──►  TowerUpgradeOption.selected  (39)
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
/rai-build-starter-ontology Build a telco network ontology from the CSVs in data/. Include a ModelAdvisory concept so manufacturer recall/defect/EOL/firmware notices can be linked to every equipment item of the affected model.
```

**Response**

Concepts: `CellTower`, `NetworkEquipment` (with `tower_id_fk` FK property), `EquipmentHealth` (with `equipment_id_fk` FK property), `NetworkPerformance`, `Subscriber`, `CallDetailRecord` (edge concept: caller → callee, routed_through tower), `TowerUpgradeOption` (composite key tower_id+tier), `ModelAdvisory` (PK: MODEL) — all bound to the bundled CSVs. The FK properties on NetworkEquipment and EquipmentHealth carry the join keys explicitly so Stage 2's GNN can define heterogeneous edges via property equality (the workaround for an SDK iteration-mutation bug when GNN-node concepts also carry `model.Relationship` cross-pointers).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows are in each, and what's the advisory coverage (how many MODELs are advised, what severities, and what fraction of equipment sits on an advised model)?
```

**Response**

8 concepts wired to the bundled CSVs: 250 `CellTower`, 1,500 `NetworkEquipment`, 1,500 `EquipmentHealth`, 5,000 `NetworkPerformance`, 1,200 `Subscriber`, 6,000 `CallDetailRecord`, 750 `TowerUpgradeOption` (3 tiers × 250 towers), 8 `ModelAdvisory` rows on 7 distinct MODELs. Advisory severities span 0.50–0.95 (RECALL / DEFECT_BATCH / FIRMWARE_BUG / EOL / SECURITY_PATCH). 572 of the 1,500 equipment items (38.1 %) sit on an advised MODEL — these are the items the GNN's ModelAdvisory edge will surface as elevated-risk.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have $5M of capex and 200 install crew-weeks for tower upgrades. Two distinct risk signals are visible -- operational degradation (already-broken towers in one region) and manufacturer advisories on specific MODELs of equipment. Which RAI reasoners do we need, in what order, to land on a defensible upgrade plan that integrates both signals?
```

**Response**

Plans the 5-reasoner chain on the shared ontology — descriptive (`/rai-querying`) to scope the ontology and advisory landscape; predictive (`/rai-predictive-modeling` + `/rai-predictive-training`) to train an equipment-failure binary classification GNN with a `ModelAdvisory → NetworkEquipment` edge and bind the per-tower `failure_intensity` back to `CellTower`; rules (`/rai-rules-authoring`) to flag critical-restore towers via a three-branch rule combining operational degradation with the predictive intensity; graph (`/rai-graph-analysis`) to score subscriber influence and aggregate per-tower blast radius; prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to compose all three signals into the tier-selection MIP and explain the binding constraint.

### 4. Train the equipment-failure GNN

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Which equipment items are at risk of failure, factoring in not just each item's own health metrics but the broader fleet context — manufacturer advisories on the same model, and the health of other equipment on the same tower? Roll the per-equipment predictions up to a per-tower failure-intensity score so downstream reasoners can use it for prioritization.
```

**Response**

GNN binary classification with `eval_metric=roc_auc`, 80 epochs, three FK / shared-MODEL edges on an **undirected** graph (`directed=False`) so signal can flow both ways across `Equipment ↔ Tower ↔ Equipment` and propagate the 2-hop neighbor-advisory pattern. PropertyTransformer pulls equipment / health / tower / advisory features (category, continuous, integer, datetime). Train/val/test split is 1050/225/1500 (test = all equipment so every item gets a prediction). Per-equipment positive-class probabilities are summed per tower in pandas and loaded back as `CellTower.failure_intensity` via a `TowerFailureScore` bridge concept. Per-tower `failure_intensity` distribution: min 0.09, median 3.06, max 8.67 — graded enough that the Stage 4 objective gets a real priority signal.

### 5. Flag critical-restore towers

**Prompt**

```
/rai-rules-authoring Which towers should we flag as critical-restore? Any tower fitting one of three cases: (1) in WEST and DEGRADED with poor equipment health (avg health below 0.85); (2) in WEST and showing high packet loss (above 5%) with poor health — catches ACTIVE-but-failing towers operations would otherwise miss; (3) predicted equipment-failure intensity above 1.5 (any region) — catches towers where multiple equipment items are at risk before they fail. Compute the per-tower health average by joining EquipmentHealth through NetworkEquipment to CellTower.
```

**Response**

Four derived health properties (`avg_packet_loss`, `avg_latency_ms`, `avg_error_rate`, `avg_health_score`) computed for all 250 towers; the equipment-health aggregation joins from EquipmentHealth through NetworkEquipment to CellTower. The three-branch `CellTower.is_critical_restore` relationship fires on 166 towers spanning all five regions, distributed: WEST 47, EAST 37, SOUTH 33, NORTH 29, CENTRAL 20. Per-branch contribution: Branch 1 fires on 12 towers, Branch 2 fires on 12 towers, Branch 3 (`failure_intensity > 1.5`) fires on 165 towers — 154 of which are flagged ONLY by the predictive branch (93% of the flagged set). 3 of the 15 WEST DEGRADED towers happen to have avg_health ≥ 0.85 in the augmented data and don't trip Branch 1 (though all 15 still fire on Branch 3 via their predicted failure_intensity).

### 6. Score subscriber blast radius

**Prompt**

```
/rai-graph-analysis Who are our most socially influential subscribers — subscribers who receive calls from other highly-called subscribers? For each critical-restore tower, score its blast radius — how many distinct subscribers route calls through it, weighted by their influence.
```

**Response**

`Subscriber.influence_score` (PageRank) on all 1,200 subscribers; `CellTower.weighted_impact` and `CellTower.impact_count` on all 166 critical towers. Multi-region scope means the blast-radius story spans the operator's full customer base, not just the WEST cohort.

### 7. Optimize tier selection

**Prompt**

```
/rai-prescriptive-problem-formulation Which tower upgrade plan maximizes weighted capacity restored within our $5M capex and 200 install-week envelope? For each critical-restore tower, pick at most one upgrade tier (BRONZE / SILVER / GOLD). Each option's contribution to the objective is its capacity_increase_gbps multiplied by the tower's weighted_impact (Stage 3) and failure_intensity (Stage 1) — a three-factor product so a high-failure-intensity tower with many influential subscribers outscores a low-risk one.
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

### 9. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Materialize the optimal plan and the selected upgrades as queryable ontology. Add a RestorePlan concept holding the plan summary (total cost, install-weeks, capacity restored, tier-mix counts, towers covered, binding constraints) and a SelectedUpgrade view restricted to the chosen tower-tier rows.
```

**Response**

Ontology gains a singleton `RestorePlan` Concept with `total_cost`, `total_install_weeks`, `capacity_restored_gbps`, `gold_count`, `silver_count`, `bronze_count`, `towers_covered`, `binding_constraints` (now a list); plus `SelectedUpgrade` (a view over the chosen rows of `TowerUpgradeOption`). Headline plan numbers are queryable as ontology, not stdout.

## Data

Bundled CSVs in `data/`: 250 cell towers (15 WEST DEGRADED), 1,500 NetworkEquipment items across 18 consolidated MODELs, 1,500 EquipmentHealth snapshots, 5,000 NetworkPerformance measurements, 1,200 subscribers, 6,000 CDRs, 750 TowerUpgradeOptions (3 tiers × 250 towers), 8 ModelAdvisory rows on 7 distinct MODELs (severities 0.50–0.95). The synthesis script `data/_synthesize_advisory_data.py` regenerates the equipment / health / advisory / upgrade-option CSVs deterministically from a seed. The AT_RISK label is governed by a weighted sum of five signals: own-model advisory severity (0.25), tower-mate's advisory severity (0.45 -- the multi-hop signal), health gap (0.10), outdated-firmware flag (0.05), and a smooth three-way interaction (advisory × health_gap × firmware-outdated, weight 0.10). All four chain stages run end-to-end via `telco_network_recovery.py`.
