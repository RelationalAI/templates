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

- Prompt: `/rai-build-starter-ontology Build an ontology for grid infrastructure planning from the CSVs in data/ covering substations, generators, transmission lines, demand forecasts, data center requests, and substation upgrades.`
- Response: Concepts: `Substation`, `Generator`, `TransmissionLine`, `LoadZone`, `DemandPeriod`, `RenewableProfile`, `MaintenanceWindow`, `Customer`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast`, `LoadHistory`, `DCAnnouncement` — bound to the bundled CSVs (12 substations, 10 DC requests, 18 transmission lines).

### 2. Discover reasoner questions

- Prompt: `/rai-discovery We have 10 hyperscaler interconnection requests against a 12-substation grid. Which to approve, which substation upgrades to fund, at what budget level?`
- Response: Plan routing sub-questions to predictive, graph, rules, and prescriptive reasoners.

### 3. Forecast substation load

- Prompt: `/rai-predictive-modeling + /rai-predictive-training Can we forecast substation load growth over the next 24 months based on historical demand, planned generator additions, and the data center request pipeline? Bind each substation's predicted peak load back to the ontology so the rules engine and optimizer can read it.`
- Response: `Substation.predicted_load` for all 12; DFW breaches at 1,700 MW vs 1,600 MW cap at 24 months (+54.6%).

### 4. Find structural bottlenecks

- Prompt: `/rai-graph-analysis Which substations are most critical to power flow based on grid topology? Check connectivity (WCC), regional structure (Louvain communities), and centrality (betweenness/degree/eigenvector); then flag the top 3 by combined centrality rank as structurally critical and persist the scores back to the ontology.`
- Response: 1 connected component, 3 Louvain communities (North Texas, West Texas, Gulf Coast); DFW, Houston, San Antonio flagged `is_structurally_critical`; 7 of 10 DC requests target critical nodes.

### 5. Screen DC requests

- Prompt: `/rai-rules-authoring Screen each data center request against three criteria: (1) substation must have enough capacity after predicted load, (2) substation's low-carbon (renewable + nuclear) generation share must meet the DC's low-carbon requirement, (3) substation shouldn't be one of the top-3 structurally critical. Which requests pass all three?`
- Response: `fails_capacity` / `fails_structural` / `fails_low_carbon` + `is_compliant`; 2 pass (Crusoe, Oracle), 8 flagged.

### 6. Approve DCs and fund upgrades

- Prompt: `/rai-prescriptive-problem-formulation Decide which data center requests to approve and which substation upgrades to fund at $200M, $300M, $400M, $500M, and $600M investment levels. Maximize annual revenue. A request can only be approved if its substation has enough capacity after upgrades.`
- Response: OPTIMAL MIP across 5 `InvestmentLevel` values in one solve; `x_approve` and `x_upgrade` written back per level.

### 7. Read the frontier

- Prompt: `/rai-prescriptive-results-interpretation Which data centers get approved, which upgrades are selected, and where's the biggest return on investment at each budget level?`
- Response: Pareto frontier with knee at $300M (5 DCs, 1,500 MW, $264M net); marginal $995K/$M at knee, declining to $400K/$M by $600M; Google + Lambda never approved (DFW full).

## Data

Bundled CSVs in `data/`: 12 substations, 15 generators, 18 transmission lines, 10 DC requests (2,930 MW), 10 substation upgrades ($630M total), plus historical load and forecast tables. Full chain implemented in `energy_grid_planning.py`.
