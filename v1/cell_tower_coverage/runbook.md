# Cell Tower Coverage — Analyst Runbook

A network planner wants to know which new cell tower sites to build, and which demand zone each one serves, to cover the most people under a fixed capital budget and a cap on how many towers can be built this cycle. The dataset is 6 candidate sites (each with a build cost and a serving capacity), 10 population zones, and 19 feasible site-to-zone coverage links. The analysis solves a maximum-coverage mixed-integer program that picks the build plan and the single tower assignment for each covered zone.

```text
6 candidate sites (build cost, capacity) · 10 demand zones (population) · 19 feasible coverage links
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: build site? · zone covered? · tower serves zone?  (all binary)
   • constraints: ≤ 3 towers; total build cost ≤ $650k; each covered zone served by exactly
     one built tower; each tower's served population ≤ its capacity
   • objective: maximize covered population
   • HiGHS mixed-integer program                 -> OPTIMAL, 90,000 covered
      │
      ▼
/rai-prescriptive-results-interpretation
   • build T02, T04, T06 ($610k of $650k) → 8 of 10 zones, 87.5% of population
   • the 3-tower cap binds (budget has $40k slack); Riverfront + Lakeside stay uncovered
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `TowerSite`/`DemandZone`/`CoveragePair` concepts the build step created, and the interpret step reads the selection decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/tower_sites.csv` (each candidate site has a build cost and a serving capacity), `data/demand_zones.csv` (each zone has a population), and `data/coverage_pairs.csv` (the feasible site-to-zone links a tower could serve). Model the coverage pair as a relationship linking a tower site to a demand zone.

**Response:** Loads `TowerSite` (6, with `build_cost` and `capacity`), `DemandZone` (10, with `population` — 102,900 total), and `CoveragePair` (19 feasible site-zone links, each with `distance_km` and `signal_score`), linked back to their site and zone.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 6 `TowerSite` (build cost, capacity), 10 `DemandZone` (population, 102,900 total), and 19 `CoveragePair` (the only allowed site-to-zone service links) — so not every zone can be served by every tower.

## 3. Maximize covered population

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Which sites should we build and which tower should serve each zone to cover the most people, building at most 3 towers within a $650,000 budget? Use a binary build decision per site, a binary covered decision per zone, and a binary serve decision per feasible site-zone pair. A zone counts as covered only if it's assigned to exactly one built tower, a tower can only serve zones if it's built, and the population a tower serves can't exceed its capacity. Maximize total covered population and persist the decisions to the ontology.

**Response:** OPTIMAL (HiGHS), covered population **90,000 of 102,900** (relative gap 0.0). The model has 3 binary decision families and 5 constraint families; build, cover, and serve decisions are written back as `TowerSite.x_selected`, `DemandZone.y_covered`, and `CoveragePair.z_assigned`.

## 4. Read the build plan

**Prompt:** /rai-prescriptive-results-interpretation Which towers get built, which zones do they serve, and what's the coverage rate — and is the budget or the tower count the binding limit?

**Response:** Build **T02 (North Water Tank), T04 (Campus Microcell), and T06 (Airport Perimeter)** for **$610,000 of the $650,000 budget**, covering **8 of 10 zones — 90,000 people, an 87.5% coverage rate**. All three towers run above 90% of capacity. The **3-tower cap is the binding limit** in this solve — 0 towers to spare, versus $40k of budget headroom; Riverfront (7,200) and Lakeside (5,700) are left uncovered. Reaching them would take both another tower and more budget: the only sites that can serve those two zones push the cheapest fully-covering plan to a 4th tower at about $850k, past both the count cap and the budget.

## Data

Bundled CSVs in `data/`: 6 tower sites, 10 demand zones, 19 coverage pairs. The budget ($650k) and tower cap (3) are constants in the script. Full model in `cell_tower_coverage.py`.
