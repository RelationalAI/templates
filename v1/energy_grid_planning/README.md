---
title: "Energy Grid Planning"
description: "Multi-reasoner template: demand forecasting, grid vulnerability analysis, compliance rules, and multi-objective optimization for AI data center interconnection planning."
featured: true
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Predictive
  - Graph
  - Rules
  - Prescriptive
tags:
  - Multi-Reasoner
  - Chained Reasoning
  - Multi-Objective
  - Energy
  - Grid Infrastructure
  - Data Centers
  - Capacity Planning
---

# Energy Grid Planning

## What this template is for

Utility planners face a queue of AI data center interconnection requests from hyperscalers (Microsoft, Google, Amazon, Meta, xAI) competing for scarce grid capacity. They must decide which requests to approve, what substation upgrades to invest in, and how to keep the grid reliable -- all under budget constraints and renewable energy mandates.

This template uses RelationalAI's **predictive reasoning**, **graph analysis**, **rules-based classification**, and **prescriptive reasoning (multi-objective optimization)** in a chained multi-reasoner workflow:

1. **Predictive** forecasts substation load growth from historical demand data, identifying which substations will exceed capacity as data center demand accelerates.
2. **Graph analysis** maps the grid topology (substations + transmission lines), computes structural vulnerability (bridges, articulation points, N-1 contingency), and ranks substations by centrality.
3. **Rules** check each data center request against interconnection compliance: capacity limits (using predicted load from Stage 1), renewable energy mandates, and N-1 reliability (using articulation points from Stage 2).
4. **Prescriptive optimization** jointly decides which data centers to approve and which substation upgrades to build across multiple investment levels ($200M-$600M). An InvestmentLevel Scenario Concept traces the Pareto frontier in a single solve, with results queryable in the ontology.

Each stage enriches the shared ontology; downstream stages consume those enrichments. The Pareto frontier shows how revenue scales with infrastructure investment, revealing the knee point where marginal returns diminish.

## Why this problem matters

AI data center buildout is the largest source of new electricity demand in a generation. Hyperscalers are requesting multi-hundred-megawatt interconnections at substations that were designed for decades of 2-3% organic growth. Utility planners face a combinatorial decision: which requests to approve, what infrastructure to upgrade, and how to maintain grid reliability -- all under capital budget constraints and renewable energy mandates.

This is not a single-reasoner problem. Approving a data center at a structurally critical substation (graph) without sufficient capacity headroom (predictive) violates reliability rules (rules) and may not be economically justified at lower budget levels (prescriptive). The value of the multi-reasoner approach is that each stage's output constrains the next -- predictions inform rules, rules inform optimization, and the optimizer respects all upstream signals.

## Reasoner overview: inputs, outputs, and role

| Stage | Reasoner | Inputs | Outputs (enriched on ontology) | Role |
|-------|----------|--------|-------------------------------|------|
| 1. Predict | **Predictive** | `DemandForecast` table (historical load + DC announcements) | `Substation.predicted_load` (derived Property) | Forecast which substations hit capacity limits and when. DC-targeted substations show 5x growth acceleration. |
| 2. Graph | **Graph** (WCC, centrality) + NetworkX (bridges) | `Substation` nodes, `TransmissionLine` edges | `Substation.betweenness` (Property), `Substation.is_articulation_point` (Relationship) | Map grid topology, identify structural bottlenecks and single points of failure. |
| 3. Rules | **Rules** (declarative) | Predicted load (Stage 1), articulation points (Stage 2), DC request properties | `DataCenterRequest.fails_capacity`, `.fails_n1`, `.fails_renewable`, `.is_compliant` (Relationships) | Check each request against interconnection compliance. Every flag is a derived Relationship consuming upstream enrichments. |
| 4. Prescriptive | **Prescriptive** (MIP, Scenario Concept) | All upstream enrichments + `InvestmentLevel` budget scenarios | `DataCenterRequest.x_approve`, `SubstationUpgrade.x_upgrade` per InvestmentLevel (Properties) | Jointly optimize approvals + upgrades across budget levels. One solve produces the Pareto frontier. Results written to ontology. |

**Key design patterns demonstrated:**
- **Scenario Concept** for multi-objective optimization -- InvestmentLevel entities encode budget variations; one solve handles all levels simultaneously (not a re-solve loop)
- **Ontology as shared state** -- each stage writes derived properties/relationships that downstream stages read; no Python dicts or DataFrames as intermediaries
- **Separate graph model** -- Graph and Prescriptive reasoners use independent `Model` instances to avoid SDK recursion, with results transferred via `model.data()` + `filter_by()`
- **Pareto frontier from scenario queries** -- the tradeoff between infrastructure investment and DC revenue emerges from querying `model.select(...).where(x_approve > 0.5)` per InvestmentLevel

## Who this is for

- Utility planners and grid operators managing interconnection queues
- Energy infrastructure investors evaluating capacity expansion portfolios
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain predictive, graph, rules, and optimization in a single model

## What you'll build

- A substation load forecasting pipeline (predictive or pre-baked fallback)
- Grid topology analysis with WCC, centrality, bridges, and N-1 contingency screening
- Three declarative compliance rules consuming upstream reasoner outputs
- Binary decision variables for DC approval and substation upgrades, indexed by InvestmentLevel (Scenario Concept)
- Substation capacity, budget, and renewable mandate constraints scoped per investment level
- A revenue-maximizing objective producing the Pareto frontier across budget scenarios
- Ontology-native result extraction -- no variable parsing, all queryable via `model.select()`

## What's included

- `energy_grid_planning.py` -- Main script with four chained reasoning stages
- `data/substations.csv` -- 12 substations with capacity, load, and coordinates
- `data/generators.csv` -- 15 generators (gas, coal, nuclear, solar, wind, hydro, battery)
- `data/transmission_lines.csv` -- 20 transmission lines forming a connected grid
- `data/load_zones.csv` -- 5 geographic load zones
- `data/demand_periods.csv` -- 24-hour demand profiles per zone
- `data/renewable_profiles.csv` -- Solar/wind capacity factors by hour
- `data/maintenance_windows.csv` -- Planned generator/line outages
- `data/customers.csv` -- 10 end-use customers with flexibility profiles
- `data/data_center_requests.csv` -- 10 hyperscaler interconnection requests (Microsoft, Google, Amazon, Meta, xAI, Oracle, CoreWeave, Lambda Labs, Crusoe Energy, Apple)
- `data/substation_upgrades.csv` -- 8 possible substation capacity upgrades
- `data/demand_forecasts.csv` -- Pre-computed substation load forecasts (6/12/18/24 month horizons)
- `data/load_history.csv` -- 4 years of monthly substation load readings
- `data/dc_announcements.csv` -- Hyperscaler announcement events
- `data/train_forecasts.csv`, `data/val_forecasts.csv`, `data/test_forecasts.csv` -- GNN training splits

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/energy_grid_planning.zip
   unzip energy_grid_planning.zip
   cd energy_grid_planning
   ```

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
   ============================================================
   STAGE 1: PREDICT -- Substation Load Forecasting
   ============================================================
     All substation forecasts:
       Houston East              pred=1387.2 MW  growth=36.0%  breach=safe
       Chicago Loop              pred=1292.0 MW  growth=36.0%  breach=safe
       Phoenix Central           pred=829.6 MW  growth=36.0%  breach=safe
       ...

   ============================================================
   STAGE 2: GRAPH -- Grid Topology & Structural Vulnerability
   ============================================================
     Grid connectivity: 12 substations, 1 component(s)
     CONNECTED: All substations reachable from any other.
     Top 5 critical substations (centrality):
       #1: Kansas City Hub (betw=11.92, deg=0.45, eig=0.45)
       #2: San Antonio Grid (betw=10.50, deg=0.36, eig=0.31)
       ...

   ============================================================
   STAGE 3: RULES -- Interconnection Queue Compliance
   ============================================================
     DC Request                Hyper        MW   Cap Renew  N-1  OK?
     Azure GPU West            Microsoft    300  FAIL  FAIL  PASS  N
     GCP TPU Farm              Google       250  FAIL  FAIL  PASS  N
     AWS Trainium Center       Amazon       400  FAIL  PASS  PASS  N
     ...
     Summary: 0 compliant, 10 flagged (out of 10 requests)

   ============================================================
   STAGE 4: OPTIMIZE -- InvestmentLevel Scenario Concept
   ============================================================
     Solving across 5 investment levels simultaneously...
     Objective: 672,100,000.00

     Approved DCs per investment level:
       $200M: AWS, Apple, xAI (3 DCs, 1,080 MW)
       $300M: + Meta (4 DCs, 1,430 MW)
       $400M: + GCP (5 DCs, 1,680 MW)
       $500M: same as $400M
       $600M: + Crusoe (6 DCs, 1,880 MW)

     Revenue by investment level:
       $200M  $94.9M revenue, $185M upgrades
       $300M  $123.3M revenue, $233M upgrades
       $400M  $146.3M revenue, $353M upgrades  <-- knee point
       $500M  $146.3M revenue, $468M upgrades
       $600M  $161.5M revenue, $533M upgrades

   PIPELINE COMPLETE: Predict -> Graph -> Rules -> Prescriptive
   ```

## Template structure

```
energy_grid_planning/
  energy_grid_planning.py    # Main script (4 chained reasoning stages)
  data/
    substations.csv          # Grid nodes
    generators.csv           # Power plants
    transmission_lines.csv   # Grid edges
    load_zones.csv           # Geographic demand regions
    demand_periods.csv       # 24-hour demand profiles
    renewable_profiles.csv   # Solar/wind capacity factors
    maintenance_windows.csv  # Planned outages
    customers.csv            # End-use customers
    data_center_requests.csv # Hyperscaler interconnection requests
    substation_upgrades.csv  # Upgrade options
    demand_forecasts.csv     # Pre-computed load forecasts
    load_history.csv         # Historical load readings
    dc_announcements.csv     # Hyperscaler announcements
    train_forecasts.csv      # GNN training split
    val_forecasts.csv        # GNN validation split
    test_forecasts.csv       # GNN test split
  README.md                  # This file
  pyproject.toml             # Dependencies
```

## How it works

### Stage 1: Predict -- Substation Load Forecasting

Derives `Substation.predicted_load` as an ontology property from the `DemandForecast` table using `aggs.max().per(Substation)`. Substations near announced data center projects show 36% growth vs 10% organic. This predicted load feeds the capacity constraint in Stage 4.

### Stage 2: Graph -- Grid Topology & Structural Vulnerability

Uses a **separate `graph_model`** (to avoid SDK 1.0.12 recursion with prescriptive) to build a substation-transmission line graph. Computes:
- Weakly connected components (grid connectivity)
- Betweenness, degree, and eigenvector centrality (transfer bottlenecks)
- Bridge detection and N-1 contingency screening (via NetworkX)

Results are loaded back into the main model via `model.data()` + `filter_by()`.

### Stage 3: Rules -- Interconnection Queue Compliance

Three declarative rules (RAI Relationships) consume upstream outputs:
- **Capacity check**: `requested_mw + predicted_load > max_capacity_mw` (uses Stage 1)
- **N-1 reliability**: DC request at an articulation point substation (uses Stage 2)
- **Renewable mandate**: substation's renewable generation fraction < DC's requirement
- **Composite**: `is_compliant` = passes all checks

### Stage 4: Prescriptive -- Multi-Objective Optimization

Uses the **InvestmentLevel Scenario Concept** pattern:
- 5 budget levels ($200M-$600M) as Scenario entities
- Binary variables `x_approve` and `x_upgrade` indexed by InvestmentLevel
- Substation capacity and budget constraints scoped `.per(InvestmentLevel)`
- One solve produces the entire Pareto frontier
- Results populated in the ontology, queryable via `model.select()`

## Customize this template

- **Add investment levels**: Add rows to the InvestmentLevel DataFrame for finer Pareto resolution
- **Add demand scenarios**: Create a DemandScenario concept as a second Scenario axis
- **Add generation dispatch**: Extend with GeneratorPeriod cross-product and dispatch variables (increases problem size significantly)
- **Use real GNN predictions**: Install the predictive reasoner and train on `load_history.csv` via `energy_demand_forecast.py`
- **Adjust renewable target**: Modify the `fails_renewable` rule threshold
- **Add your grid data**: Replace CSVs with your substation/transmission line topology

## Troubleshooting

**Q: Stage 2 graph queries work but Stage 4 fails with UnsupportedRecursionError?**
A: The Graph reasoner's recursive definitions conflict with prescriptive `variable_values()` in SDK 1.0.12. The template uses a separate `graph_model` for Stage 2 to avoid this.

**Q: All DCs fail the capacity check?**
A: This is expected -- the existing grid doesn't have headroom for 2.7 GW of new AI load without upgrades. The optimizer selects which upgrades to build.

**Q: The Pareto frontier shows the same DCs at $400M and $500M?**
A: The knee point is at $400M. Beyond that, additional budget goes to upgrades that don't unlock new DC approvals -- diminishing returns.
