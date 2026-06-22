# Runbook: Energy Grid Planning — Multi-Reasoner Walkthrough

ERCOT processes 10 hyperscaler interconnection requests (2,930 MW) against a 12-substation Texas grid. The chain forecasts substation load, finds structural bottlenecks, screens compliance, and produces a Pareto frontier across 5 budget levels — no single reasoner can answer this end-to-end.

## The chain

```
ERCOT has 10 hyperscaler interconnection requests totalling 2,930 MW
on a 12-substation grid where DFW is the binding capacity bottleneck.
The chain produces a Pareto frontier across 5 budget levels — the knee at
$300M unlocks 5 DCs (1,500 MW, $264M net value) including xAI Colossus.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  Substation.predicted_load        (12)
                              DFW: 1,100 → 1,700 MW (+54.6%) ── breaches
                              1,600 MW capacity at 24mo. The only
                              substation predicted to breach.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Graph        ──►  Substation.betweenness          (12)
                 (WCC/      Substation.grid_community         (3 regions)
                 Louvain/   Substation.is_structurally_critical (3)
                 centrality) DFW, Houston, San Antonio dominate. 7 of 10
                              DC requests target critical substations.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Rules        ──►  DataCenterRequest.is_compliant    (2)
                              fails_capacity / fails_structural /
                              fails_low_carbon flags written back.
                              Only Crusoe (Midland) and Oracle
                              (Corpus Christi) pass all three.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Prescriptive ──►  DataCenterRequest.x_approve  (per InvestmentLevel)
                              SubstationUpgrade.x_upgrade  (per InvestmentLevel)
                              OPTIMAL across 5 budget levels in one solve.
                              Knee $300M · 5 DCs · 1,500 MW · $264M net.
                              Google + Lambda never approved — DFW full.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build an ontology for grid infrastructure planning from the CSVs in data/.
```

**Response**

Concepts: `Substation`, `Generator`, `TransmissionLine`, `LoadZone`, `DemandPeriod`, `RenewableProfile`, `MaintenanceWindow`, `Customer`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast`, `LoadHistory`, `DCAnnouncement` — bound to the bundled CSVs (12 substations, 10 DC requests, 18 transmission lines).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

13 concepts: 12 `Substation`, 15 `Generator`, 18 `TransmissionLine`, 5 `LoadZone`, 120 `DemandPeriod`, 120 `RenewableProfile`, 5 `MaintenanceWindow`, 10 `Customer`, 10 `DataCenterRequest` (2,930 MW total), 10 `SubstationUpgrade` ($630M total), historical `LoadHistory` and forward `DemandForecast` rows backing the predictive stage.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have 10 hyperscaler interconnection requests against a 12-substation grid. Which to approve, which substation upgrades to fund, at what budget level?
```

**Response**

Plan routing sub-questions to predictive, graph, rules, and prescriptive reasoners.

### 4. Forecast substation load

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training What's each substation's predicted peak load over the next 24 months, given historical demand, planned generator additions, and the DC request pipeline? Bind the predictions back to the ontology so the rules engine and optimizer can read them. Use the pre-trained model from the DemandForecast table if available, or train fresh.
```

**Response**

`Substation.predicted_load` for all 12; DFW breaches at 1,700 MW vs 1,600 MW cap at 24 months (+54.6%).

### 5. Find structural bottlenecks

**Prompt**

```
/rai-graph-analysis Which substations are most structurally critical to power flow — combining whether many paths route through them, how many direct connections they have, and how connected they are to other influential substations? Flag the top 3 by combined criticality, surface any regional clustering, and persist the scores back to the ontology.
```

**Response**

1 connected component, 3 Louvain communities (North Texas, West Texas, Gulf Coast); DFW, Houston, San Antonio flagged `is_structurally_critical`; 7 of 10 DC requests target critical nodes.

### 5b. Trace fragile transmission corridors (PREVIEW, requires `relationalai>=1.15`)

**Prompt**

```
/rai-graph-analysis For each data-center substation, what is the most fragile transmission corridor from a generator substation — the route running through the greatest total structural criticality across its substations, where a substation's criticality reflects how many power-flow paths route through it? Consider corridors up to about six hops that don't revisit a substation. Then, if the single most critical substation goes offline, which data-center substations reroute and which lose every corridor?
```

**Response**

421 generator-substation to DC-substation corridors. The most fragile carries a betweenness-load of 99.833, routing through the Dallas-Fort Worth / Abilene Central / Houston Ship Channel hubs. Taking the top substation (Dallas-Fort Worth) offline reroutes the other DC substations' corridors; the meshed grid stays connected (no full isolation). Persists `Substation.fragility_load`.

### 6. Screen DC requests

**Prompt**

```
/rai-rules-authoring Screen each data center request against three criteria: (1) substation must have enough capacity after predicted load, (2) substation's low-carbon (renewable + nuclear) generation share must meet the DC's low-carbon requirement, (3) substation shouldn't be one of the top-3 structurally critical. Which requests pass all three?
```

**Response**

`fails_capacity` / `fails_structural` / `fails_low_carbon` + `is_compliant`; 2 pass (Crusoe, Oracle), 8 flagged.

### 7. Approve DCs and fund upgrades

**Prompt**

```
/rai-prescriptive-problem-formulation Which data center requests should we approve and which substation upgrades should we fund at each of the five investment levels ($200M, $300M, $400M, $500M, $600M), maximizing annual revenue across all five in a single solve? A request can only be approved if its substation has enough capacity after upgrades, and total upgrade spend at each level must stay within budget. Consider all 10 requests — the compliance flags from the rules screen are informational, not hard filters.
```

**Response**

OPTIMAL MIP across 5 `InvestmentLevel` values in one solve; `x_approve` and `x_upgrade` written back per level.

### 8. Read the frontier

**Prompt**

```
/rai-prescriptive-results-interpretation Which data centers get approved and which upgrades are selected at each budget level, and where's the knee — the budget where the marginal net value per added dollar starts to drop sharply?
```

**Response**

Pareto frontier with knee at $300M (5 DCs, 1,500 MW, $264M net); marginal $995K/$M at knee, declining to $400K/$M by $600M; Google + Lambda never approved (DFW full).

### 9. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Add an InvestmentPortfolio concept indexed by InvestmentLevel that materializes the per-budget aggregates (approved-DC count, total MW, annual revenue, upgrade cost, net value, marginal value per added $M) and flags the knee point.
```

**Response**

Ontology gains an `InvestmentPortfolio(InvestmentLevel)` Concept (5 rows, one per budget) with `dc_count`, `total_mw`, `annual_revenue`, `upgrade_cost`, `net_value`, `marginal_per_m_to_next_level`, `is_knee_point`. All five frontier rows — $200M ($165M net) → $300M ($264M net, knee) → $600M ($395M net) — are queryable as ontology rather than stdout.

## Data

Bundled CSVs in `data/`: 12 substations, 15 generators, 18 transmission lines, 10 DC requests (2,930 MW), 10 substation upgrades ($630M total), plus historical load and forecast tables. Full chain implemented in `energy_grid_planning.py`.
