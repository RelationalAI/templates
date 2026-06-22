---
title: "Energy Grid Planning"
description: "AI data center interconnection planning on the ERCOT (Texas) grid: demand forecasting, grid-vulnerability analysis, compliance rules, and multi-objective optimization."
featured: true
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Multi-Objective
  - Energy
  - Grid Infrastructure
  - Data Centers
  - Capacity Planning
  - ERCOT
---

# Energy Grid Planning

## What this template is for

ERCOT's interconnection planning team faces a queue of 10 AI data center requests from hyperscalers (Microsoft, Google, Amazon, Meta, xAI, Oracle, CoreWeave, Lambda Labs, Crusoe Energy, Apple) competing for scarce grid capacity across the Texas grid. They must decide which requests to approve, what substation upgrades to invest in, and how to keep the grid reliable -- all under budget constraints and renewable energy mandates.

This template uses RelationalAI's **predictive reasoning**, **graph analysis**, **rules-based classification**, and **prescriptive reasoning (multi-objective optimization)** in a chained multi-reasoner workflow:

1. **Predictive** forecasts substation load growth from historical demand data, identifying which substations will exceed capacity as data center demand accelerates. Dallas-Fort Worth is the only substation predicted to breach capacity -- at 24 months with 54.6% growth.
2. **Graph analysis** maps the ERCOT grid topology (12 substations + 18 transmission lines), detects community structure (Louvain) across 3 regions (North Texas, West Texas, Gulf Coast), and ranks substations by betweenness centrality to identify structurally critical bottlenecks. 7 of 10 DC requests target structurally critical substations.
3. **Rules** check each data center request against interconnection compliance: capacity limits (using predicted load from Stage 1), low-carbon energy mandates, and structural risk (using centrality-based criticality from Stage 2). Only 2 of 10 requests pass (Crusoe and Oracle); 8 are flagged.
4. **Prescriptive optimization** jointly decides which data centers to approve and which substation upgrades to build across multiple investment levels ($200M-$600M). An InvestmentLevel Scenario Concept traces the Pareto frontier in a single solve, with results queryable in the ontology. The knee point at $300M unlocks 5 DCs (1,500 MW) including xAI Colossus -- the highest-revenue single request at $105M/yr.

Each stage enriches the shared ontology, and downstream stages consume those enrichments -- this is the **accretive ontology enrichment** pattern. No Python dicts or DataFrames carry state between stages; the ontology is the single source of truth:

- **Stage 1 writes** `Substation.predicted_load` -- consumed by Stage 3's capacity rule AND Stage 4's capacity constraint. Both downstream reasoners see the same forecasted headroom.
- **Stage 2 writes** `Substation.betweenness`, `Substation.grid_community`, `Substation.is_structurally_critical` -- consumed by Stage 3's structural risk rule (Rule 2) and by Stage 2.5's corridor ranking.
- **Stage 2.5 writes** `Substation.fragility_load` (PREVIEW) -- the most-fragile generator-to-DC corridor's betweenness load per data-center substation, consuming Stage 2's betweenness along enumerated routes.
- **Stage 3 writes** `DataCenterRequest.fails_capacity`, `.fails_structural`, `.fails_low_carbon`, `.is_compliant` -- queryable compliance flags that document why each request was flagged.
- **Stage 4 writes** `DataCenterRequest.x_approve` and `SubstationUpgrade.x_upgrade` per `InvestmentLevel` -- queried from the ontology via `model.select()`, not parsed from solver output.

The ontology is accretive: each stage enriches it with derived properties, and downstream stages consume those enrichments as first-class attributes. This means changing Stage 1's demand forecast automatically propagates through the rules engine and optimizer without any code changes.

The optimization is **multi-scenario and multi-objective**: `InvestmentLevel` is a Scenario Concept -- 5 budget entities ($200M-$600M) that parameterize the optimization. One MIP solve produces the entire Pareto frontier simultaneously (not a re-solve loop). The frontier reveals the knee point at $300M (5 DCs, 1,500 MW, $264M net value), where xAI Colossus ($105M/yr) unlocks -- the highest marginal return per dollar. Beyond $300M, marginal returns diminish: $995K/$M at the knee vs $400K/$M at $600M. Because the optimizer uses `predicted_load` from Stage 1 (not raw historical load), the capacity constraints reflect forecasted growth -- the same signal the rules engine uses.

## Why this problem matters

ERCOT -- the Electric Reliability Council of Texas -- operates an isolated grid that is not interconnected with the Eastern or Western Interconnections. This isolation means Texas cannot import power from neighboring grids during demand spikes, making capacity planning uniquely consequential. Winter Storm Uri (2021) demonstrated the vulnerability: grid failures cascaded without external relief, causing widespread blackouts.

Texas is now the fastest-growing market for AI data center development. Hyperscalers are requesting multi-hundred-megawatt interconnections at substations designed for decades of steady organic growth. The ERCOT grid must absorb 2,930 MW of new data center load -- equivalent to roughly 3 nuclear reactors -- while maintaining reliability for 30 million existing customers.

This is not a single-reasoner problem. Approving a data center at a structurally critical substation like Dallas-Fort Worth (graph) without sufficient capacity headroom (predictive) violates reliability rules (rules) and may not be economically justified at lower budget levels (prescriptive). The value of the multi-reasoner approach is that each stage's output constrains the next -- predictions inform rules, rules inform optimization, and the optimizer respects all upstream signals.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|--------------------|--------------------|------|
| 1. Predict | **Predictive** | `DemandForecast` table (historical load + DC announcements) | `Substation.predicted_load` (derived Property) | Forecast which substations hit capacity limits. DFW breaches at 24 months (54.6% growth); Houston, San Antonio, Austin grow 32-44% but remain within capacity. |
| 2. Graph | **Graph** (WCC, Louvain, centrality) | `Substation` nodes, `TransmissionLine` edges | `Substation.betweenness`, `.grid_community` (Properties), `Substation.is_structurally_critical` (Relationship) | Map ERCOT grid topology into 3 regions (North Texas, West Texas, Gulf Coast). DFW and Houston are the top structural bottlenecks. 7 of 10 DC requests target critical substations. |
| 3. Rules | **Rules** (declarative) | `predicted_load` (Stage 1), `is_structurally_critical` (Stage 2), DC request properties | `DataCenterRequest.fails_capacity`, `.fails_structural`, `.fails_low_carbon`, `.is_compliant` (Relationships) | Check each request against interconnection compliance. 2 compliant (Crusoe, Oracle), 8 flagged. Every flag is a derived Relationship consuming upstream enrichments. |
| 4. Prescriptive | **Prescriptive** (MIP, Scenario Concept) | `predicted_load` (Stage 1), `InvestmentLevel` budget scenarios, upgrade costs/capacities | `DataCenterRequest.x_approve`, `SubstationUpgrade.x_upgrade` per InvestmentLevel (Properties) | Jointly optimize approvals + upgrades across budget levels. One solve produces the full Pareto frontier. Knee at $300M (5 DCs, $264M net value). All results queryable via `model.select()`. |

**Key design patterns demonstrated:**
- **Accretive ontology enrichment** -- each stage writes derived properties that downstream stages consume as first-class ontology attributes. Stage 1's `predicted_load` flows into both Stage 3 rules and Stage 4 optimization constraints, ensuring consistent capacity signals across the pipeline.
- **Multi-scenario / multi-objective via Scenario Concept** -- `InvestmentLevel` is a Scenario Concept: 5 budget entities ($200M-$600M) that parameterize the optimization. One MIP solve produces the entire Pareto frontier simultaneously (not a re-solve loop). Decision variables `x_approve` and `x_upgrade` are indexed per InvestmentLevel, and results are queryable ontology properties -- not parsed from solver output.
- **Ontology as shared state** -- each stage writes derived properties/relationships that downstream stages read; no Python dicts or DataFrames carry state between stages
- **Graph directly on domain concept** -- the Graph reasoner uses `Substation` as its node concept, so centrality and community results are stored as native Substation properties with no mirror concept or enrichment rules
- **Marginal analysis from ontology queries** -- the per-level DC approvals, upgrade selections, and net value are all queried from the ontology via `model.select(...).where(x_approve > 0.5)` per InvestmentLevel, enabling marginal return analysis across the frontier

## Who this is for

- Utility planners and grid operators managing interconnection queues (especially ERCOT)
- Energy infrastructure investors evaluating capacity expansion portfolios
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain predictive, graph, rules, and optimization in a single model

## What you'll build

- A substation load forecasting pipeline (predictive or pre-baked fallback)
- Grid topology analysis with WCC, Louvain community detection, and multi-metric centrality ranking
- Three declarative compliance rules consuming upstream reasoner outputs
- Binary decision variables for DC approval and substation upgrades, indexed by InvestmentLevel (Scenario Concept)
- Substation capacity, budget, and low-carbon mandate constraints scoped per investment level
- A revenue-maximizing objective producing the Pareto frontier across budget scenarios
- Ontology-native result extraction -- no variable parsing, all queryable via `model.select()`

## What's included

- `energy_grid_planning.py` -- Main script with four chained reasoning stages
- `data/substations.csv` -- 12 Texas substations with capacity, load, and coordinates
- `data/generators.csv` -- 15 generators (2 nuclear: STP + Comanche Peak, plus gas, coal, wind, solar, battery)
- `data/transmission_lines.csv` -- 18 transmission lines forming a connected ERCOT grid
- `data/load_zones.csv` -- 5 ERCOT load zones
- `data/demand_periods.csv` -- 24-hour demand profiles per zone
- `data/renewable_profiles.csv` -- Solar/wind capacity factors by hour
- `data/maintenance_windows.csv` -- Planned generator/line outages
- `data/customers.csv` -- 10 end-use customers with flexibility profiles
- `data/data_center_requests.csv` -- 10 hyperscaler interconnection requests (2,930 MW total)
- `data/substation_upgrades.csv` -- 10 possible substation capacity upgrades
- `data/demand_forecasts.csv` -- Pre-computed substation load forecasts (6/12/18/24 month horizons)
- `data/load_history.csv` -- 4 years of monthly substation load readings
- `data/dc_announcements.csv` -- Hyperscaler announcement events
- `data/train_forecasts.csv`, `data/val_forecasts.csv`, `data/test_forecasts.csv` -- GNN training splits (used by optional GNN training workflow, not by the main script)

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.15.0

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/energy_grid_planning.zip
   unzip energy_grid_planning.zip
   cd energy_grid_planning
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

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
   python energy_grid_planning.py
   ```

6. Expected output:

   ```text
   STAGE 1: PREDICT -- Substation Load Forecasting
     GNN model not available, falling back to DEMAND_FORECASTS table
     Substations at risk of capacity breach:
       Dallas-Fort Worth: 1100 MW current → 1700 MW predicted vs 1600 MW capacity (breach at 24mo, 54.6% growth)
     All substation forecasts:
       Houston Ship Channel      pred=1797.1 MW  growth=43.8%  breach=safe
       Dallas-Fort Worth         pred=1700.2 MW  growth=54.6%  breach=24mo
       San Antonio Metro         pred=1069.1 MW  growth=37.1%  breach=safe
       Austin Energy             pred=818.8 MW  growth=32.1%  breach=safe
       ...

   STAGE 2: GRAPH -- Grid Topology & Structural Vulnerability
     Grid connectivity: 12 substations, 1 component(s) -- CONNECTED
     Grid community structure (Louvain): 3 region(s)
       Region 1 (North Texas): Dallas-Fort Worth, Austin Energy, Waco Gateway
       Region 2 (West Texas): Midland-Permian, Lubbock, El Paso, Amarillo, Abilene
       Region 3 (Gulf Coast): Houston, San Antonio, Corpus Christi, Brownsville
     Top 3 structurally critical substations:
       #1: Dallas-Fort Worth (betw=31.67) [CRITICAL]
       #2: Houston Ship Channel (betw=15.83) [CRITICAL]
       #3: San Antonio Metro (betw=4.33) [CRITICAL]
     KEY INSIGHT: 7 of 10 DC requests target structurally critical substations

   STAGE 3: RULES -- Interconnection Queue Compliance
     DC Request                Hyper         Q#     MW   Cap  LowC  Crit  OK?
     Microsoft Horizon Campus  Microsoft      1    350  FAIL  PASS  FAIL    N
     Meta Bayou DC             Meta           2    300  FAIL  PASS  FAIL    N
     Google Metroplex DC       Google         3    400  FAIL  PASS  FAIL    N
     xAI Colossus Texas        xAI            4    500  FAIL  PASS  FAIL    N
     Lambda Labs DFW           Lambda Labs    5    200  FAIL  PASS  FAIL    N
     Amazon SA Cloud           Amazon         6    280  FAIL  PASS  FAIL    N
     Apple iCloud Texas        Apple          7    250  FAIL  PASS  FAIL    N
     CoreWeave Austin GPU      CoreWeave      8    320  FAIL  PASS  PASS    N
     Crusoe Permian DC         Crusoe Energy   9    180  PASS  PASS  PASS    Y
     Oracle Coastal DC         Oracle        10    150  PASS  PASS  PASS    Y
     Summary: 2 compliant, 8 flagged

   STAGE 4: OPTIMIZE -- Joint Interconnection + Upgrade
     Status: OPTIMAL | Objective: 1,579,200,000

     Pareto frontier:
       #    Level   DCs    DC MW   Revenue $/yr   Upg $M     Net Value
       1    $200M     4    1,000    174,350,000    190.0    164,850,000
       2    $300M     5    1,500    279,350,000    300.0    264,350,000
       3    $400M     6    1,800    328,850,000    385.0    309,600,000
       4    $500M     7    2,080    376,450,000    430.0    354,950,000
       5    $600M     8    2,330    420,200,000    505.0    394,950,000

     KNEE POINT: $300M -- 5 DCs, 1,500 MW, $264M net value
     xAI Colossus ($105M/yr) unlocks at $300M -- highest-revenue single request

     Per-level (abbreviated):
     $200M: Microsoft, CoreWeave, Crusoe, Oracle (1,000 MW)
     $300M: + xAI (500 MW)
     $400M: + Meta (300 MW)
     $500M: + Amazon (280 MW)
     $600M: + Apple (250 MW)
     Never approved: Google (400 MW), Lambda Labs (200 MW) -- DFW is full

     Marginal: $200->$300M = $995K/$M | $300->$400M = $453K/$M | $400->$500M = $454K/$M | $500->$600M = $400K/$M

   PIPELINE COMPLETE: 4 stages executed on shared Energy Grid ontology
   ```

## Template structure

```text
energy_grid_planning/
  energy_grid_planning.py    # Main script (4 chained reasoning stages)
  data/
    substations.csv          # 12 Texas grid nodes
    generators.csv           # 15 generators (nuclear, gas, coal, wind, solar, battery)
    transmission_lines.csv   # 18 ERCOT grid edges
    load_zones.csv           # 5 ERCOT load zones
    demand_periods.csv       # 24-hour demand profiles
    renewable_profiles.csv   # Solar/wind capacity factors
    maintenance_windows.csv  # Planned outages
    customers.csv            # End-use customers
    data_center_requests.csv # 10 hyperscaler interconnection requests (2,930 MW)
    substation_upgrades.csv  # 10 upgrade options
    demand_forecasts.csv     # Pre-computed load forecasts
    load_history.csv         # Historical load readings
    dc_announcements.csv     # Hyperscaler announcements
    train_forecasts.csv      # GNN training split (optional, not used by main script)
    val_forecasts.csv        # GNN validation split (optional, not used by main script)
    test_forecasts.csv       # GNN test split (optional, not used by main script)
  README.md                  # This file
  pyproject.toml             # Dependencies
```

## How it works

### Stage 1: Predict -- Substation Load Forecasting

Derives `Substation.predicted_load` as an ontology property from the `DemandForecast` table using `aggs.max().per(Substation)`. Substations near announced data center projects show 32-55% growth depending on location and announced capacity. Dallas-Fort Worth is the only substation predicted to breach capacity (1,700 MW predicted vs 1,600 MW capacity at 24 months, 54.6% growth). Houston Ship Channel shows the highest absolute load (1,797 MW) but remains within its larger capacity. This predicted load feeds the capacity constraint in Stage 4.

The `predicted_load` derived property aggregates the max forecasted load per substation:

```python
Substation.predicted_load = model.Property(f"{Substation} has {Float:predicted_load}")
model.define(
    Substation.predicted_load(
        aggs.max(DemandForecast.predicted_load_mw)
        .where(DemandForecast.substation(Substation))
        .per(Substation)
    )
)
```

### Stage 2: Graph -- Grid Topology & Structural Vulnerability

The Graph reasoner uses `Substation` directly as its node concept — no mirror concept needed. Edges connect substations that share an active transmission line. Centrality and community results are stored as native Substation properties. Computes:
- Weakly connected components (grid connectivity -- confirms all 12 substations are reachable)
- Louvain community detection (3 ERCOT regions: North Texas, West Texas, Gulf Coast)
- Betweenness, degree, and eigenvector centrality combined into a critical rank
- 7 of 10 DC requests target structurally critical substations -- a key input to the rules engine

```python
grid_graph = Graph(
    model, directed=False, weighted=False, node_concept=Substation, aggregator="sum"
)

line_ref = TransmissionLine.ref()
model.define(
    grid_graph.Edge.new(src=line_ref.from_substation, dst=line_ref.to_substation)
).where(line_ref.is_active == True)

community = grid_graph.louvain()
betweenness = grid_graph.betweenness_centrality()
```

### Stage 2.5: Paths -- Transmission Corridors & Contingency

> PREVIEW capability; requires `relationalai>=1.15`.

Where Stage 2 scores a *substation*, the **Graph** paths capability scores the *corridor* feeding each data center. It derives a bidirectional substation-to-substation edge from active transmission lines, enumerates generator-substation to DC-substation routes, and ranks each by the Stage 2 betweenness summed along its hops — the most fragile corridor is the one carrying the greatest through-traffic exposure. A contingency pass removes the highest-betweenness substation and re-enumerates to show which data centers reroute. The most-fragile load is persisted as `Substation.fragility_load`.

```python
corridor_df = model.where(
    corridor := model.path(
        corridor_src, Substation.connects_to.repeat(1, MAX_CORRIDOR_HOPS), corridor_dst
    ).all_paths(),
).select(
    corridor.alias("corridor"),
    corridor.nodes["index"].alias("hop"),
    Substation(corridor.nodes).id.alias("substation_id"),
    Substation(corridor.nodes).name.alias("substation_name"),
).to_df()
```

### Stage 3: Rules -- Interconnection Queue Compliance

Three declarative rules (RAI Relationships) consume upstream outputs:
- **Capacity check**: `requested_mw + predicted_load > max_capacity_mw` (uses Stage 1). Most requests fail because the existing grid lacks headroom for new AI load without upgrades.
- **Structural risk**: DC request targets a structurally critical substation (uses Stage 2 centrality). 7 of 10 requests fail this check.
- **Low-carbon mandate**: substation's low-carbon generation fraction < DC's requirement (nuclear + renewable). All requests pass -- ERCOT's nuclear plants (STP, Comanche Peak) and extensive wind/solar fleet provide sufficient low-carbon generation.
- **Composite**: `is_compliant` = passes all checks. Only Crusoe Permian DC and Oracle Coastal DC are fully compliant.

The capacity rule demonstrates the accretive pattern, consuming `predicted_load` from Stage 1 with a fallback to `current_load_mw`:

```python
DataCenterRequest.fails_capacity = model.Relationship(f"{DataCenterRequest} fails capacity check")
SubRef_rule = Substation.ref()
effective_load_rule = SubRef_rule.predicted_load | SubRef_rule.current_load_mw
model.where(
    DataCenterRequest.substation(SubRef_rule),
    DataCenterRequest.requested_mw + effective_load_rule > SubRef_rule.max_capacity_mw,
).define(DataCenterRequest.fails_capacity())
```

### Stage 4: Prescriptive -- Multi-Objective Optimization

Uses the **InvestmentLevel Scenario Concept** pattern:
- 5 budget levels ($200M-$600M) as Scenario entities
- Binary variables `x_approve` and `x_upgrade` indexed by InvestmentLevel
- Substation capacity constraints use `predicted_load` from Stage 1 (not raw historical load), ensuring the optimizer sees the same forecasted headroom as the rules engine
- Budget constraints scoped `.per(InvestmentLevel)`
- Revenue values reflect annual interconnection capacity revenue ($145K-$210K per MW/yr), not energy revenue
- One solve produces the entire Pareto frontier -- the knee point at $300M (5 DCs, 1,500 MW, $264M net value) shows the highest marginal return, unlocking xAI Colossus ($105M/yr) as the single highest-revenue request
- At $200M, 4 DCs are approved (Microsoft, CoreWeave, Crusoe, Oracle); each additional $100M budget increment adds 1 more DC with diminishing marginal returns ($995K/$M at the knee vs $400K/$M at $600M)
- Google Metroplex DC (400 MW) and Lambda Labs DFW (200 MW) are never approved at any budget level -- DFW substation capacity is fully consumed
- Per-level details (which DCs approved, which upgrades selected, upgrade MW) are all queried from the ontology via `model.select()`, not parsed from solver output
- All decision variables (`x_approve`, `x_upgrade`) are ontology properties indexed by InvestmentLevel, making the full Pareto frontier queryable without any output parsing

The `Problem` setup defines the InvestmentLevel Scenario Concept with binary decision variables, and the capacity constraint uses `predicted_load` from Stage 1:

```python
problem = Problem(model, Float)

problem.solve_for(DataCenterRequest.x_approve(InvestmentLevel, x_a), type="bin",
            name=["approve", InvestmentLevel.name, DataCenterRequest.id])
problem.solve_for(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u), type="bin",
            name=["upgrade", InvestmentLevel.name, SubstationUpgrade.id])

# C1: Substation capacity per investment level
# Uses predicted_load from Stage 1 (with current_load fallback) — the accretive chain.
x_a_c = Float.ref("xa_c")
x_u_c = Float.ref("xu_c")
effective_load = Substation.predicted_load | Substation.current_load_mw

problem.satisfy(model.where(
    DataCenterRequest.x_approve(InvestmentLevel, x_a_c),
    SubstationUpgrade.x_upgrade(InvestmentLevel, x_u_c),
    DataCenterRequest.substation(Substation),
    SubstationUpgrade.substation(Substation),
).require(
    Substation.max_capacity_mw - effective_load
    + sum(x_u_c * UpgRef.capacity_increase_mw).where(
        UpgRef.substation == Substation).per(Substation, InvestmentLevel)
    >= sum(x_a_c * DCRef.requested_mw).where(
        DCRef.substation == Substation).per(Substation, InvestmentLevel)
))
```

## Customize this template

- **Add investment levels**: Add rows to the InvestmentLevel DataFrame for finer Pareto resolution
- **Add demand scenarios**: Create a DemandScenario concept as a second Scenario axis
- **Add generation dispatch**: Extend with GeneratorPeriod cross-product and dispatch variables (increases problem size significantly)
- **Use real GNN predictions**: Install the predictive reasoner and train on `load_history.csv` via `energy_demand_forecast.py`
- **Adjust low-carbon target**: Modify the `fails_low_carbon` rule (e.g., exclude nuclear to use renewable-only)
- **Add your grid data**: Replace CSVs with your substation/transmission line topology

## Troubleshooting

<details>
<summary>Stage 2 graph queries work but Stage 4 fails with <code>UnsupportedRecursionError</code></summary>

- SDK versions before 1.0.13 could hit this when recursive graph rules and
  prescriptive result queries shared one model. Upgrade to >= 1.0.13.

</details>

<details>
<summary>Most DCs fail the capacity check</summary>

- This is expected -- the existing ERCOT grid doesn't have headroom for 2,930 MW of new AI load without upgrades.
- Only Crusoe (Midland-Permian) and Oracle (Corpus Christi) pass all checks because they target substations with sufficient spare capacity and low structural criticality.
- The optimizer selects which upgrades to build to unlock the remaining requests.

</details>

<details>
<summary>Knee point shifts depending on predicted load</summary>

- The optimizer uses `predicted_load` from Stage 1 as the capacity baseline.
- Higher predicted load means less headroom, so fewer DCs fit at each budget level.
- The knee point at $300M reflects forecasted growth (up to 54.6% for DFW), not historical load.
- If you change the demand forecasts, the Pareto frontier and knee point will shift accordingly.

</details>

<details>
<summary>Google and Lambda Labs are never approved at any budget level</summary>

- Both target the Dallas-Fort Worth substation, which is already the only substation predicted to breach capacity (54.6% growth).
- Even with upgrades, DFW capacity is fully consumed by higher-revenue requests (xAI Colossus at 500 MW, $105M/yr).
- The optimizer correctly prioritizes revenue-maximizing allocations at the constrained substation.

</details>
