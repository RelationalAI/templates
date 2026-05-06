# Runbook: Energy Grid Planning — Multi-Reasoner Walkthrough

Walk-through of the chained-reasoner pattern this template is built on. One realistic business thread — **ERCOT processes 10 hyperscaler interconnection requests against the 12-substation Texas grid** — traced across four RAI reasoner families, each stage writing properties back to the same ontology that downstream stages consume.

The template's combined script (`energy_grid_planning.py`) implements stages 1–4 directly; this runbook walks through how an agent would derive the same pipeline prompt-by-prompt, skill-by-skill, so a non-OR reader can follow the full reasoning thread end-to-end.

---

## TL;DR — the chain in one screen

```
ERCOT has 10 hyperscaler interconnection requests totalling 2,930 MW
on a 12-substation grid with one structurally constrained bottleneck (DFW).
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

A single-reasoner approach can't answer this. Predictive alone forecasts demand but doesn't decide. Graph alone finds bottlenecks but doesn't weigh revenue. Rules alone flag noncompliance but can't optimize. Prescriptive alone has no way to weigh "critical" without graph + predictive upstream.

---

## How to read this runbook

This runbook serves two audiences:

- **Reading top-to-bottom**: the narrative + ASCII visualizations show what
  the chain produces stage-by-stage, with the same business framing the
  stakeholder would see.
- **Per-stage skill blocks**: the boxed `Skill / Prompt` callout at the
  start of each stage is the recipe — load that RAI agent skill, give it
  that prompt against the bundled demo data, and the agent will reproduce
  the stage.

---

## Step 0 — Scope the question with `rai-discovery`

> **Skill:** `rai-discovery` ·
> **Prompt:** "We have 10 hyperscaler interconnection requests totalling 2,930 MW queued against a 12-substation ERCOT-style Texas grid. Classify the sub-questions we need to answer to decide which to approve, which substation upgrades to fund, and at what budget level — map each sub-question to the reasoner family that should handle it."

Discovery classifies the question by reasoner family and tells you which
downstream skills to load:

| Sub-question | Reasoner | Skill |
|---|---|---|
| Which substations are losing headroom fastest and will breach capacity? | Predictive | _no public skill yet — see `v1/subscriber_retention/` and `v1/demand_forecasting/` as worked-example references_ |
| Which substations are structural bottlenecks on the transmission grid? Which communities? | Graph | `rai-graph-analysis` |
| Which DC requests fail capacity, structural-risk, or low-carbon compliance? | Rules | `rai-rules-authoring` |
| Across budget levels, which DCs should we approve and which upgrades should we fund? | Prescriptive | `rai-prescriptive-problem-formulation` |
| What does the Pareto frontier tell us about the knee, marginal value, and binding constraints? | Prescriptive (post-solve) | `rai-prescriptive-results-interpretation` |

Discovery's output is a *plan*, not code. Everything that follows
materializes that plan.

---

## Prerequisites

The template ships everything needed to run the chain end-to-end:

- Bundled CSVs in `../data/` (12 substations, 15 generators, 18 transmission lines, 10 DC requests, 10 substation upgrades, and supporting load/forecast tables). To run against your own Snowflake schema, swap CSV loaders for `model.Table(...)` references.
- `raiconfig.yaml` pointed at your RAI-enabled Snowflake account.
- The combined script `../energy_grid_planning.py` runs the full chain.

The narrative below follows the actual stage outputs of `energy_grid_planning.py`. Steps 1–3 below are an agent-style walk-through of how the ontology would be built from scratch via skills like `/rai-build-starter-ontology` and `/rai-discovery`; the template ships a pre-built ontology in `energy_grid_planning.py` for users who want to skip ahead to the reasoner stages.

---

## Walk-through (agent-style)

Steps are sequential — each depends on prior steps. Steps without a skill are presentation-only.

| # | Step | Skill | Prompt | Expected Output |
|---|------|-------|--------|-----------------|
| 1 | Ontology | `/rai-build-starter-ontology` | "Build an ontology for ERCOT grid infrastructure planning from the bundled CSVs (or your Snowflake schema)." | 13 concepts: `Substation`, `Generator`, `TransmissionLine`, `LoadZone`, `DemandPeriod`, `RenewableProfile`, `MaintenanceWindow`, `Customer`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast`, `LoadHistory`, `DCAnnouncement`. 12 substations, 15 generators, 18 transmission lines, 10 DC requests (2,930 MW). |
| 2 | Visualize | — | "Show the ontology as an ASCII diagram." | Concept map with `Substation` as central hub — `Generator`, `TransmissionLine`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast` all relate to it. |
| 3 | Discovery | `/rai-discovery` | "What questions can we answer with this ontology? We're evaluating data center interconnection requests." | 4 reasoning paths: substation load forecast (predictive), grid topology + structural criticality (graph), interconnection compliance (rules), joint approval + upgrade investment (prescriptive). |
| 4 | Explore: generation mix | `/rai-querying` | "What's our current generation mix by fuel type? How much renewable capacity vs fossil?" | 15 generators, 8,135 MW total. Nuclear leads (2,560 MW, 31.5%), then gas (2,290 MW, 28.1%), wind (1,250 MW, 15.4%), coal (1,020 MW, 12.5%), solar (630 MW, 7.7%), battery (300 MW), hydro (85 MW). Renewable: 2,265 MW (28%). Requests with 100% low-carbon mandates (Google, Crusoe) face a structural constraint. |
| 5 | Explore: capacity headroom | `/rai-querying` | "Which substations have the most and least spare capacity right now, before any new DC load?" | Tightest: Houston Ship Channel (69.4% utilized, 550 MW headroom), Austin Energy (68.9%, 280 MW), DFW (68.8%, 500 MW). Most spare: Midland-Permian (38.2%, 680 MW headroom), Lubbock (44.3%, 390 MW). DFW has only 500 MW headroom but 1,100 MW of DC requests stacked on it. |
| 6 | Explore: DC request landscape | `/rai-querying` | "Summarize the 10 DC requests — total MW per substation, revenue per MW, low-carbon requirements." | 2,930 MW total, $528M/yr revenue across 6 substations. DFW most stacked (1,100 MW, 3 requests: Google $195K/MW, xAI $210K/MW, Lambda $150K/MW). xAI is highest revenue ($210K/MW/yr, $105M/yr total). Google and Crusoe require 100% low-carbon. Top 3 substations (DFW, Houston, San Antonio) account for 78% of requested MW. |
| 7 | Stage 1 — Predict | `/rai-querying` (or GNN) | "Forecast which substations are losing headroom fastest and which will breach capacity." | `Substation.predicted_load` written for all 12. DFW: 1,700 MW predicted vs 1,600 MW capacity at 24 months (+54.6% growth). Houston Ship Channel: 1,797 MW (+43.8%, within capacity). The only substation predicted to breach. |
| 8 | Stage 2 — Graph | `/rai-graph-analysis` | "Build a graph on the transmission grid. Find structurally critical substations using betweenness, degree, and eigenvector centrality. Identify connected components and Louvain communities." | 1 connected component, 3 communities (North Texas, West Texas, Gulf Coast). Top 3 by combined centrality rank: DFW, Houston, San Antonio — all flagged `is_structurally_critical`. 7 of 10 DC requests target critical substations. |
| 9 | Stage 3 — Rules | `/rai-rules-authoring` | "Check each request against capacity (using `predicted_load`), low-carbon mandate, and structural risk (using `is_structurally_critical`)." | 3 declarative `Relationship` rules (`fails_capacity`, `fails_structural`, `fails_low_carbon`) + composite `is_compliant`. All 10 pass low-carbon. 2 compliant: Crusoe (Midland) and Oracle (Corpus Christi). 8 flagged on capacity + structural risk. |
| 10 | Stage 4 — Optimize | `/rai-prescriptive-problem-formulation` | "Which DCs to approve and which upgrades to fund across 5 budget levels ($200M-$600M)? Use `predicted_load` for capacity. Show the Pareto frontier — DCs, MW, revenue, net value at each level." | Pareto frontier across `InvestmentLevel` Scenario Concept. Knee at $300M (5 DCs, 1,500 MW, $264M net value). xAI Colossus unlocks at $300M. Google and Lambda never approved (DFW full). |
| 11 | Results | `/rai-prescriptive-results-interpretation` | "How do approvals and upgrades vary by investment level? Where's the knee? What's marginal return per $M?" | Per-level DC list + selected upgrades, queried via `model.select(...).where(x_approve > 0.5)`. Marginal: $200→$300M = $995K/$M (knee); declines to $400K/$M by $600M. |

---

## Stage 1 — Predictive: substation load forecasting

> **Skill:** _no public skill yet — see `v1/subscriber_retention/` and `v1/demand_forecasting/` as worked-example references_ ·
> **Prompt:** "Forecast each substation's future peak load by aggregating the maximum predicted load across the 6/12/18/24-month forecast horizons in the demand-forecast table, and write the result back to every substation as a derived load-projection property. The downstream rules engine and optimizer both need to read this same forecasted headroom — fall back to the substation's current load only when no forecast row exists. Flag substations whose predicted load exceeds their nameplate capacity within the horizon and report which one breaches first."

**Method:** load max forecasted load per substation as `Substation.predicted_load`. The template aggregates `DemandForecast.predicted_load_mw` over forecast horizons (6/12/18/24 months) and writes the max back to the substation. A pre-trained GNN can replace the table lookup; the script falls back gracefully when the GNN model registry is unavailable.

```
Substation load forecast (max across 6/12/18/24-month horizons)

  Houston Ship Channel  ────  pred 1,797 MW  ████████████  +43.8%   safe
  Dallas-Fort Worth     ────  pred 1,700 MW  ██████████    +54.6%   ▲ breach 24mo
  San Antonio Metro     ────  pred 1,069 MW  ███████       +37.1%   safe
  Austin Energy         ────  pred   819 MW  █████         +32.1%   safe
  Waco Gateway          ────  pred   600 MW  ████          +22.4%   safe
  Corpus Christi Coast  ────  pred   600 MW  ████          +11.1%   safe
  Midland-Permian       ────  pred   520 MW  ███           +23.8%   safe
  El Paso Border        ────  pred   470 MW  ███           +14.6%   safe
  Abilene Central       ────  pred   400 MW  ███           +14.3%   safe
  Lubbock West Texas    ────  pred   360 MW  ██            +16.1%   safe
  Brownsville Valley    ────  pred   355 MW  ██            +10.9%   safe
  Amarillo Panhandle    ────  pred   315 MW  ██            +12.5%   safe
                                            ▲
  ──────────────────────────────────────────│──────────────────────
  DFW is the only substation predicted to   │
  breach capacity (1,700 vs 1,600 MW cap).  │
  Stage 3 rules and Stage 4 capacity        │
  constraint both consume this property.    │
  ──────────────────────────────────────────────────────────────────

✓ Substation.predicted_load written back to all 12 substations
```

**Stage 3 rule and Stage 4 constraint with the predictive term:**

```python
# Both reuse the same effective_load expression
effective_load = Substation.predicted_load | Substation.current_load_mw
```

**Caveats:**
- The bundled forecasts are pre-computed in `data/demand_forecasts.csv` to keep the template self-contained. To wire in a live GNN, point `GNN(...)` at your model registry — the template's `try` block already handles both paths.
- DFW's projected breach partially encodes the stacked DC request itself ("we expect demand to keep rising at the substation everyone is targeting"). For an independent baseline, train on a pre-announcement slice and compare.

---

## Stage 2 — Graph: grid topology & structural vulnerability

> **Skill:** `rai-graph-analysis` ·
> **Prompt:** "Build an undirected, unweighted graph using `Substation` directly as the node concept and active transmission lines as edges. Run weakly connected components to confirm grid connectivity, Louvain community detection to surface ERCOT regional clusters, and the betweenness/degree/eigenvector centrality trio. Combine the three centrality ranks into a composite rank and flag the top 3 substations as structurally critical, writing the centrality scores, community label, and criticality flag back to each substation."

**Construction** — `Substation` as the node concept directly (no mirror concept):
- Node concept: `Substation` (12 nodes)
- Edges: active `TransmissionLine` rows, `from_substation` → `to_substation`
- Direction: undirected, unweighted

**Algorithms:** weakly connected components, Louvain community detection, betweenness/degree/eigenvector centrality. Combined rank picks the top-3 as `is_structurally_critical`.

```
Connectivity                ──►  1 component   (12 of 12 reachable)

Louvain communities         ──►  3 regions

  Region 1 — North Texas      Dallas-Fort Worth, Austin Energy, Waco Gateway
  Region 2 — West Texas       Midland-Permian, Lubbock, El Paso, Amarillo, Abilene
  Region 3 — Gulf Coast       Houston Ship Channel, San Antonio Metro,
                              Corpus Christi Coast, Brownsville Valley

Centrality (top-3 marked is_structurally_critical)

  #1  Dallas-Fort Worth      betw 31.67  ████████████   [CRITICAL]
  #2  Houston Ship Channel   betw 15.83  ██████         [CRITICAL]
  #3  San Antonio Metro      betw  4.33  ██             [CRITICAL]
  #4  Austin Energy          betw  ~3.0
  …
  #12 Brownsville Valley     betw  0.00

  ──────────────────────────────────────────────────────────────────
  DC requests targeting structurally critical substations:
    Microsoft Horizon Campus  (350 MW) ─►  Houston    [CRITICAL]
    Meta Bayou DC             (300 MW) ─►  Houston    [CRITICAL]
    Google Metroplex DC       (400 MW) ─►  DFW        [CRITICAL]
    xAI Colossus Texas        (500 MW) ─►  DFW        [CRITICAL]
    Lambda Labs DFW           (200 MW) ─►  DFW        [CRITICAL]
    Amazon SA Cloud           (280 MW) ─►  San Antonio [CRITICAL]
    Apple iCloud Texas        (250 MW) ─►  San Antonio [CRITICAL]
                                                       ────────────
  7 of 10 DC requests sit on the 3 most structurally critical nodes.
  ──────────────────────────────────────────────────────────────────

✓ Substation.betweenness / degree_centrality / eigenvector_centrality
✓ Substation.grid_community              written back (12 rows)
✓ Substation.is_structurally_critical    written back (3 rows)
```

---

## Stage 3 — Rules: interconnection queue compliance

> **Skill:** `rai-rules-authoring` ·
> **Prompt:** "Author three declarative compliance rules per data-center request, each consuming an upstream enrichment. Rule 1 fails capacity when the request's MW plus the substation's forecasted load (with current load as fallback) exceeds the substation's nameplate capacity. Rule 2 fails structural risk when the target substation is flagged structurally critical from Stage 2. Rule 3 fails the low-carbon mandate when the substation's zero-emission generation share is below the request's required percentage; sum capacity for generators with emissions rate of zero. Add a composite `is_compliant` flag that fires only when none of the three failure flags fire."

Three declarative `Relationship` rules consume Stages 1–2 enrichments. Each is written as a `model.where(...).define(...)` block; a composite `is_compliant` fires only when none of the three failure flags fire.

**Rule 1 — Capacity** (consumes `Substation.predicted_load` from Stage 1):

```python
DataCenterRequest.fails_capacity = model.Relationship(...)
effective_load = SubRef.predicted_load | SubRef.current_load_mw
model.where(
    DataCenterRequest.substation(SubRef),
    DataCenterRequest.requested_mw + effective_load > SubRef.max_capacity_mw,
).define(DataCenterRequest.fails_capacity())
```

**Rule 2 — Structural risk** (consumes `Substation.is_structurally_critical` from Stage 2):

```python
model.where(
    DataCenterRequest.substation(SubRef),
    SubRef.is_structurally_critical(),
).define(DataCenterRequest.fails_structural())
```

**Rule 3 — Low-carbon mandate** (zero-emission share at the substation must meet the request's requirement; nuclear + renewable count):

```python
model.where(
    DataCenterRequest.substation(SubRef),
    (SubRef.low_carbon_gen_mw | 0.0) * 100
        < DataCenterRequest.low_carbon_requirement_pct * (SubRef.total_gen_mw | 0.001),
).define(DataCenterRequest.fails_low_carbon())
```

```
  DC Request                Hyper          Q#    MW   Cap  LowC  Crit  OK?
  ──────────────────────────────────────────────────────────────────────
  Microsoft Horizon Campus  Microsoft       1   350  FAIL  PASS  FAIL    N
  Meta Bayou DC             Meta            2   300  FAIL  PASS  FAIL    N
  Google Metroplex DC       Google          3   400  FAIL  PASS  FAIL    N
  xAI Colossus Texas        xAI             4   500  FAIL  PASS  FAIL    N
  Lambda Labs DFW           Lambda Labs     5   200  FAIL  PASS  FAIL    N
  Amazon SA Cloud           Amazon          6   280  FAIL  PASS  FAIL    N
  Apple iCloud Texas        Apple           7   250  FAIL  PASS  FAIL    N
  CoreWeave Austin GPU      CoreWeave       8   320  FAIL  PASS  PASS    N
  Crusoe Permian DC         Crusoe Energy   9   180  PASS  PASS  PASS    Y
  Oracle Coastal DC         Oracle         10   150  PASS  PASS  PASS    Y
  ──────────────────────────────────────────────────────────────────────
  Summary: 2 compliant, 8 flagged
```

Every request passes low-carbon — ERCOT's nuclear (STP, Comanche Peak) plus its wind/solar fleet provides enough zero-emission generation. The two compliant requests sit on substations that are neither structurally critical (Stage 2) nor predicted to breach (Stage 1). Eight requests need either upgrades, redirection, or both — Stage 4 picks the optimal mix.

```
✓ DataCenterRequest.fails_capacity         written back
✓ DataCenterRequest.fails_structural       written back
✓ DataCenterRequest.fails_low_carbon       written back
✓ DataCenterRequest.is_compliant           written back  (2 rows)
```

---

## Stage 4 — Prescriptive: joint DC approval + upgrade MIP

> **Skill:** `rai-prescriptive-problem-formulation` ·
> **Prompt:** "Formulate a single MIP that picks DC approvals and substation upgrades jointly across five budget scenarios at $200M, $300M, $400M, $500M, and $600M. Model the budget as an `InvestmentLevel` Scenario Concept and index both the binary approve and binary upgrade decision variables by it, so one solve produces the full Pareto frontier — no per-budget re-solve loop. Constrain per substation per scenario that approved DC load fits within nameplate capacity minus forecasted load plus selected upgrade headroom, and per scenario that selected upgrade costs stay within the scenario's budget cap. Maximize total annual interconnection revenue summed across all scenarios."

```
FORMULATION

  Scenario Concept
    InvestmentLevel(name, budget_cap)   5 levels: $200M, $300M, $400M, $500M, $600M

  Decision variables (binary, indexed by InvestmentLevel)
    DataCenterRequest.x_approve(InvestmentLevel)    50 binaries  (10 DCs × 5 levels)
    SubstationUpgrade.x_upgrade(InvestmentLevel)    50 binaries  (10 upgrades × 5 levels)

  Constraints
    1. Substation capacity per InvestmentLevel
         max_capacity − predicted_load + Σ(x_upgrade · capacity_increase)
         ≥  Σ(x_approve · requested_mw)            per (Substation, InvestmentLevel)
    2. Budget per InvestmentLevel
         Σ(x_upgrade · cost_million)  ≤  budget_cap   per InvestmentLevel

  Objective (maximize)
    Σ x_approve · annual_revenue_per_mw · requested_mw           summed over all levels

──────────────────────────────────────────────────────────────────────
SOLVE  (HiGHS, single solve, all 5 levels in one MIP)   →   OPTIMAL
──────────────────────────────────────────────────────────────────────
```

```
PARETO FRONTIER (queried directly from ontology)

  Level    Budget    DCs   DC MW    Revenue $/yr    Upg $M    Net Value
  ──────  ────────  ────  ──────  ─────────────   ────────  ───────────
   $200M    $200M     4    1,000     $174,350,000    $190.0   $164,850,000
   $300M    $300M     5    1,500     $279,350,000    $300.0   $264,350,000   ◄ KNEE
   $400M    $400M     6    1,800     $328,850,000    $385.0   $309,600,000
   $500M    $500M     7    2,080     $376,450,000    $430.0   $354,950,000
   $600M    $600M     8    2,330     $420,200,000    $505.0   $394,950,000

  Per-level DC approvals (cumulative as budget increases)

   $200M:  Microsoft (350) · CoreWeave (320) · Crusoe (180) · Oracle (150)   ── 1,000 MW
   $300M:  + xAI Colossus (500)                                              ── 1,500 MW
   $400M:  + Meta Bayou (300)                                                ── 1,800 MW
   $500M:  + Amazon SA (280)                                                 ── 2,080 MW
   $600M:  + Apple iCloud (250)                                              ── 2,330 MW

   Never approved at any level:
     Google Metroplex DC  (400 MW, DFW)
     Lambda Labs DFW      (200 MW, DFW)
     ──────────────────────────────────
     DFW is physically full once xAI takes 500 MW.

  Marginal value per $M added budget

   $200 → $300M    ── $995K / $M   ◄ knee — xAI Colossus unlocks at $300M
   $300 → $400M    ── $453K / $M
   $400 → $500M    ── $454K / $M
   $500 → $600M    ── $400K / $M

✓ DataCenterRequest.x_approve(InvestmentLevel)   written back
✓ SubstationUpgrade.x_upgrade(InvestmentLevel)   written back
  Each variable is now a queryable property of the model — no
  parsing of solver output, no per-level re-solve loops.
```

### Reading the solve

- **Knee at $300M.** xAI Colossus alone delivers $105M/yr ($210K × 500 MW), the single highest-revenue request. Unlocking it requires the $110M UPG-003 upgrade at DFW. Below $300M, xAI doesn't fit; above $300M, the next-best DCs (Meta, Amazon, Apple) deliver $0.4M/$M-ish — diminishing returns.
- **DFW is the binding bottleneck.** With xAI's 500 MW absorbing the post-upgrade headroom, neither Google (400 MW) nor Lambda (200 MW) ever fit — they share DFW. The optimizer correctly prioritizes revenue per MW over queue position.
- **All compliant requests get approved by $200M.** The 2 fully compliant requests from Stage 3 (Crusoe, Oracle) sit on sub-critical substations; they're cheap upgrades and clear the bar at the lowest budget.
- **`predicted_load` propagates the chain.** Capacity slack at every substation reflects Stage 1's forecast, not raw historical load — the same signal the rules engine used.

---

## Stage 5 — Interpretation

> **Skill:** `rai-prescriptive-results-interpretation` ·
> **Prompt:** "Read the per-scenario decision-variable properties straight from the ontology — approved DCs, selected upgrades, total MW, revenue, and amortized upgrade cost — and present the Pareto frontier across the five investment levels. Compute marginal value per added budget dollar between adjacent levels and call out the knee where the marginal jump is largest. Translate the result into business language: which DCs unlock at the knee, which substation is the binding bottleneck, and which requests are infeasible at every budget level."

```
THE PLAN, IN BUSINESS TERMS

  • Recommended budget: $300M (the knee).
    5 DCs, 1,500 MW connected, $279M/yr revenue, $264M net value.
  • Marginal $100M from $200M unlocks xAI Colossus alone — $105M/yr — at
    $995K return per $1M spent. Beyond the knee, marginal return roughly
    halves.
  • Google (400 MW) and Lambda (200 MW) are structurally infeasible at any
    budget level — DFW is full once xAI takes its 500 MW. Either redirect
    them to a different substation, or de-prioritize.
  • Crusoe (Midland) and Oracle (Corpus Christi) approve cheaply at any
    budget — they were the only two that passed all three rules in Stage 3.

ONTOLOGY ENRICHMENT — what each stage contributed back

  Stage 1 (predictive)    Substation.predicted_load                [12]

  Stage 2 (graph)         Substation.betweenness                   [12]
                          Substation.degree_centrality             [12]
                          Substation.eigenvector_centrality        [12]
                          Substation.grid_community                [12]
                          Substation.is_structurally_critical      [3]

  Stage 3 (rules)         DataCenterRequest.fails_capacity         [8]
                          DataCenterRequest.fails_structural       [7]
                          DataCenterRequest.fails_low_carbon       [0]
                          DataCenterRequest.is_compliant           [2]
                          Substation.low_carbon_gen_mw             [12]
                          Substation.total_gen_mw                  [12]

  Stage 4 (prescriptive)  DataCenterRequest.x_approve              [50]
                          SubstationUpgrade.x_upgrade              [50]

  ──────────────────────────────────────────────────────────────────
  Each stage reads what the previous stage wrote.
  Re-running any downstream stage automatically picks up enrichments.
  No glue code, no DataFrame round-trip — same ontology throughout.
  ──────────────────────────────────────────────────────────────────
```

---

## The chain — accretive ontology enrichment

```
THE ENERGY GRID PLANNING CHAIN

  STAGE 1  PREDICTIVE
  "Where is demand growing? Who breaches first?"
  reads:   DemandForecast.predicted_load_mw, Substation.current_load_mw
  writes:  Substation.predicted_load              ── per substation
                         │
                         ▼
  STAGE 2  GRAPH (WCC / Louvain / centrality)
  "How is the grid connected? Which substations are structural bottlenecks?"
  reads:   Substation nodes, TransmissionLine edges (active)
  writes:  Substation.betweenness / degree_centrality / eigenvector_centrality
           Substation.grid_community               ── 3 regions
           Substation.is_structurally_critical     ── 3 substations
                         │
                         ▼
  STAGE 3  RULES (declarative Relationships)
  "Which DC requests pass capacity, structural, low-carbon checks?"
  reads:   Substation.predicted_load        ◄── Stage 1
           Substation.is_structurally_critical ◄── Stage 2
           Generator.emissions_rate, DataCenterRequest.low_carbon_requirement_pct
  writes:  DataCenterRequest.fails_capacity / fails_structural / fails_low_carbon
           DataCenterRequest.is_compliant          ── 2 requests
                         │
                         ▼
  STAGE 4  PRESCRIPTIVE (HiGHS MIP, Scenario Concept)
  "Which DCs to approve and which upgrades to fund across 5 budget levels?"
  reads:   Substation.predicted_load        ◄── Stage 1
           SubstationUpgrade.cost_million / capacity_increase_mw
           DataCenterRequest.requested_mw / annual_revenue_per_mw
           InvestmentLevel.budget_cap              ── 5 levels
  writes:  DataCenterRequest.x_approve(InvestmentLevel)
           SubstationUpgrade.x_upgrade(InvestmentLevel)
                         │
                         ▼
                   Pareto frontier,
                   queryable directly from the ontology.

  ──────────────────────────────────────────────────────────────────
  No glue. No DataFrame ping-pong. No per-level re-solve loop.
  Four reasoners, one ontology, one accretive thread.
  ──────────────────────────────────────────────────────────────────
```

---

## Why the chain matters (vs. any single stage)

| Stage alone | What it tells you | What it doesn't |
|---|---|---|
| Predictive | "DFW will breach in 24 months" | What to do; which requests matter |
| Graph alone | "DFW, Houston, San Antonio are bottlenecks" | Whether they have headroom; what to approve |
| Rules alone | (won't fire — no `predicted_load`, no `is_structurally_critical`) | Pipeline misses |
| Prescriptive alone | (no flagged set, no critical-node info, no forecast) | Whole pipeline misses |

| Combined | Output |
|---|---|
| Predictive → Graph | Forecasted load + structural bottleneck map |
| + Rules | Per-request compliance vs. capacity / structural / low-carbon |
| + Prescriptive | Pareto frontier across 5 budget levels in one solve |

**Multi-reasoner chaining grounded in (and contributing to) the ontology.**

---

## Adapting this recipe to a new domain

The chain pattern transfers cleanly. To rebuild for a different problem:

1. Re-run `rai-discovery` on the new business question — does it actually
   need all 4 reasoner families, or is one or two sufficient?
2. Strip the demo ontology to the concepts the new chain needs (lean is
   better for type inference and solver compile time).
3. Stage 1 (Predictive) is optional — if you have forecast tables already,
   a simple `aggs.max(...).per(...)` derived property is enough; swap in
   a GNN later by pointing the predictive reasoner at your model registry.
4. Stages 2–4 are the load-bearing chain: graph centrality flags
   structurally critical nodes, rules consume both the predictive forecast
   and the criticality flag to fail or pass each request, and the
   prescriptive MIP reads the same forecast as a capacity baseline while
   indexing decision variables by an `InvestmentLevel` Scenario Concept so
   one solve produces the full Pareto frontier.
5. Keep the validation checks at every stage: assert the predicted-load
   write covers all nodes, the top-N critical set looks plausible against
   the topology, the compliance table has at least one PASS and one FAIL,
   and the optimizer reports OPTIMAL with a non-zero objective.

The shape this template demonstrates — *each reasoner writes a property
the next reasoner reads* — is what makes the chain accretive rather than
serial. The agent skills are how you reliably author each link.

---

## Data Reference

**Substations with DC requests:**

| Substation | Location | Capacity | DC Requests | DC MW |
|------------|----------|----------|-------------|-------|
| SUB-001 | Houston Ship Channel | 1,800 MW | Microsoft (350), Meta (300) | 650 MW |
| SUB-002 | Dallas-Fort Worth | 1,600 MW | Google (400), xAI (500), Lambda (200) | 1,100 MW |
| SUB-003 | San Antonio Metro | 1,200 MW | Amazon (280), Apple (250) | 530 MW |
| SUB-004 | Austin Energy | 900 MW | CoreWeave (320) | 320 MW |
| SUB-005 | Midland-Permian | 1,100 MW | Crusoe (180) | 180 MW |
| SUB-007 | Corpus Christi Coast | 800 MW | Oracle (150) | 150 MW |

**ERCOT regions (Louvain):** North Texas (DFW, Austin, Waco) | West Texas (Midland, Lubbock, El Paso, Amarillo, Abilene) | Gulf Coast (Houston, San Antonio, Corpus Christi, Brownsville)

**DFW breach:** 1,600 MW capacity, 1,700 MW predicted (24mo), +54.6% growth, 1,100 MW DC requests stacked on top. Google and Lambda permanently infeasible.

**Upgrades:** 10 available, $630M total, 2,900 MW combined capacity. Only $300M of upgrades are needed at the knee.

- **Source data**: bundled CSVs in `../data/` (12 substations, 15 generators, 18 transmission lines, 10 DC requests, 10 upgrade options, plus historical load and forecast tables).
- **Ontology**: defined in `../energy_grid_planning.py` (13 concepts).
- **Stages**: implemented in `../energy_grid_planning.py` as a single combined script with stage banners.
