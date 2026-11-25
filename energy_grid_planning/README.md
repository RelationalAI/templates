---
title: "Energy Grid Planning"
description: "Plan how to connect AI data centers to the Electric Reliability Council of Texas (ERCOT) power grid. Forecasts demand, finds vulnerable parts of the grid, applies compliance rules, and balances competing objectives to recommend where to interconnect."
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

## What this template is for

ERCOT's interconnection planning team faces a queue of 10 AI data center requests from hyperscalers (Microsoft, Google, Amazon, Meta, xAI, Oracle, CoreWeave, Lambda Labs, Crusoe Energy, Apple) competing for scarce grid capacity across the Texas grid. They must decide which requests to approve, what substation upgrades to invest in, and how to keep the grid reliable -- all under budget constraints and renewable energy mandates.

A defensible answer needs all four signals at once: which substations will run out of headroom, which are structurally critical to keep the grid connected, which requests clear interconnection compliance, and which approval-and-upgrade portfolio maximizes value at each budget. **The template chains load forecasts, RelationalAI's graph topology and centrality analysis, rules-based interconnection compliance, and prescriptive multi-objective optimization on a single, accretively-enriched ontology** -- each reasoner writes derived properties the next consumes, so capacity, criticality, and compliance signals stay consistent end to end without DataFrame hand-offs between stages.

## Why this problem matters

ERCOT -- the Electric Reliability Council of Texas -- operates an isolated grid not interconnected with the Eastern or Western Interconnections, so Texas cannot import power during demand spikes. That makes capacity planning uniquely consequential, as Winter Storm Uri (2021) showed when grid failures cascaded without external relief.

Texas is now the fastest-growing market for AI data center development. Hyperscalers are requesting multi-hundred-megawatt interconnections at substations designed for decades of steady organic growth. The ERCOT grid must absorb 2,930 MW of new data center load -- equivalent to roughly 3 nuclear reactors -- while maintaining reliability for 30 million existing customers.

## Who this is for

- Utility planners and grid operators managing interconnection queues (especially ERCOT)
- Energy infrastructure investors evaluating capacity expansion portfolios
- Operations researchers exploring multi-reasoner pipelines in RelationalAI
- Developers learning how to chain graph, rules, and optimization in a single model

## What you'll build

- A substation load forecast derived from the bundled demand forecasts
- Grid topology analysis with WCC, Louvain community detection, and multi-metric centrality ranking
- Three declarative compliance rules consuming upstream reasoner outputs
- Binary decision variables for DC approval and substation upgrades, indexed by InvestmentLevel (Scenario Concept)
- Substation capacity and budget constraints scoped per investment level (the compliance flags are informational and do not constrain the solve)
- A revenue-maximizing objective producing the Pareto frontier across budget scenarios
- Ontology-native result extraction -- no variable parsing, all queryable via `model.select()`

## What's included

- `model/` -- the deployed model: `schema.py` declares the concepts, `source.py` loads the sample data and the investment levels, and one module per stage states the forecast (`load_forecast.py`), graph (`grid_topology.py`), corridors (`corridor_fragility.py`), rules (`interconnection_compliance.py`), and decision problem (`investment_solve.py`, with the per-level portfolios and knee point in `investment_frontier.py`)
- `queries/energy_grid_report.py` -- Prints the five-stage report from the deployed model
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself
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
- `data/train_forecasts.csv`, `data/val_forecasts.csv`, `data/test_forecasts.csv` -- graph neural network (GNN) training splits (not read by the model)

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports).
- RelationalAI Python SDK (`relationalai == 2.3.0`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.ENERGY_GRID_PLANNING_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.ENERGY_GRID_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/energy_grid_planning.zip), unzip it, and enter the template directory:

   ```bash
   unzip energy_grid_planning.zip
   cd energy_grid_planning
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: energy_grid_planning_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.ENERGY_GRID_PLANNING               # published views and tables
     identity:
       internal_schema: <DB>.ENERGY_GRID_PLANNING_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the graph analysis, the corridor search, and the solve. Each refresh of the deployed model runs all three again.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.energy_grid_report
   ```

   ```text
   ============================================================
   STAGE 5: OPTIMIZE -- Joint Interconnection + Upgrade
   ============================================================

     Solved across 5 investment levels ($200M-$600M)
     Status: OPTIMAL
     Objective: 1,562,600,000.00
   ...

     KNEE POINT: $300M -- $300M budget, $252,450,000 net value, 6 DCs, 1,530 MW
     Diminishing returns beyond this investment level.

   ================================================================================
     PIPELINE COMPLETE: 5 stages executed on shared Energy Grid ontology
   ```

   The report prints all five stages; the lines above are the end of Stage 5. `runbook.md` walks through each stage.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.ENERGY_GRID_PLANNING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
energy_grid_planning/
  model/
    __init__.py              # Exports of the deployed model
    schema.py                # Concepts and properties
    source.py                # Sample data and investment levels
    load_forecast.py         # Stage 1: predicted load, growth, capacity breach
    grid_topology.py         # Stage 2: components, communities, centrality, criticality
    corridor_fragility.py    # Stage 3: corridors, most fragile routes, contingency
    interconnection_compliance.py  # Stage 4: compliance rules and counts
    investment_solve.py      # Stage 5: the approval and upgrade solve
    investment_frontier.py   # Stage 5: portfolios, marginal value, knee point
  queries/
    energy_grid_report.py    # Five-stage report from the deployed model
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
    train_forecasts.csv      # GNN training split (not read by the model)
    val_forecasts.csv        # GNN validation split (not read by the model)
    test_forecasts.csv       # GNN test split (not read by the model)
  README.md                  # This file
  runbook.md                 # Step-by-step analyst walkthrough
  pyproject.toml             # Dependencies
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.energy_grid_report` for the full five-stage chain end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is **synthetic and illustrative** — modeled on the public shape of the ERCOT (Texas) grid and the wave of hyperscaler AI data center announcements, not a specific operator's network export. It is sized to teach the five-stage reasoning flow on a Snowflake-connected RAI account; production attributes a real interconnection study carries (sub-hourly SCADA telemetry, nodal pricing, contingency sets, protection settings) are extension points (see *Customize this template*), not gaps in the reasoning pattern.

The model loads thirteen CSVs from `data/` into the ontology (`model/source.py`). Three additional GNN-split files ship with the template and are **not** read by the model.

- **`substations.csv`** (12 rows) — Texas grid nodes (Houston Ship Channel, Dallas-Fort Worth, San Antonio Metro, …) with `VOLTAGE_KV`, `MAX_CAPACITY_MW`, `CURRENT_LOAD_MW`, and lat/long coordinates.
- **`generators.csv`** (15 rows) — generation units across 7 types (2 nuclear — STP + Comanche Peak — plus gas, coal, wind, solar, battery, hydro), each linked to a substation, with capacity, ramp, cost, emissions, and a renewable flag.
- **`transmission_lines.csv`** (18 rows) — directed `FROM_SUBSTATION_ID -> TO_SUBSTATION_ID` edges forming a single connected ERCOT grid, with capacity, length, impedance, an `IS_ACTIVE` flag, and maintenance priority.
- **`load_zones.csv`** (5 rows) — ERCOT load zones with peak and base demand.
- **`demand_periods.csv`** (120 rows) — 24-hour demand-and-price profiles per load zone.
- **`renewable_profiles.csv`** (120 rows) — hourly solar/wind capacity factors per generator.
- **`maintenance_windows.csv`** (5 rows) — planned generator/line outage windows.
- **`customers.csv`** (10 rows) — end-use customers with contracted demand, flexibility, and curtailment cost.
- **`data_center_requests.csv`** (10 rows) — hyperscaler interconnection requests (Microsoft, Google, Amazon, Meta, xAI, Oracle, CoreWeave, Lambda Labs, Crusoe Energy, Apple), 2,930 MW total, each targeting one substation with a requested MW, annual revenue per MW, power usage effectiveness (PUE), cooling type, low-carbon requirement, and queue position.
- **`substation_upgrades.csv`** (10 rows) — candidate capacity upgrades, each on one substation, with `CAPACITY_INCREASE_MW`, `COST_MILLION`, lead time, and a low-carbon-enablement flag.
- **`demand_forecasts.csv`** (96 rows) — pre-computed substation load forecasts at 6/12/18/24-month horizons, with confidence and a DC-growth-included flag. Stage 1 reads this directly.
- **`load_history.csv`** (576 rows) — 4 years of monthly per-substation load readings with temperature and a peak-season flag.
- **`dc_announcements.csv`** (8 rows) — hyperscaler announcement events (date, MW, target substation).

GNN training splits, **not loaded by the model**: `train_forecasts.csv` (360 rows), `val_forecasts.csv` (108 rows), `test_forecasts.csv` (108 rows) — `substation_id` / `timestamp` / `target_load_mw` series for training a load forecaster of your own.

## Model overview

One shared ontology threads all five stages. Each stage reads concepts and properties earlier stages wrote, and writes new ones for downstream stages — the accretive-enrichment pattern described above.

- **Key entities**: `Substation`, `Generator`, `TransmissionLine`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast`; plus the Stage 5 Scenario Concept `InvestmentLevel` and the results concept `InvestmentPortfolio`. Supporting concepts (`LoadZone`, `DemandPeriod`, `RenewableProfile`, `MaintenanceWindow`, `Customer`, `LoadHistory`, `DCAnnouncement`) mirror their CSVs and back the aggregations.
- **Primary identifiers**: string `id` on the base entities (e.g. `SUB-001`, `TL-001`); `name` on `InvestmentLevel` (e.g. `"$300M"`); `investment_level_name` on `InvestmentPortfolio`.
- **Important invariants**: `predicted_load`, `max_capacity_mw`, `current_load_mw`, `requested_mw`, and `capacity_increase_mw` are non-negative MW; `low_carbon_requirement_pct` is a fraction of the substation's generation capacity (`0.60` means 60%); a generator is low-carbon when `emissions_rate == 0`; Stage 5 decision variables (`x_approve`, `x_upgrade`) are binary.

`Substation` is the hub: Stages 1-2 enrich it with forecast and topology properties that Stages 4-5 consume, and Stage 3 adds corridor fragility and the contingency routes. The Stage 3 paths analysis also derives two transient sub-concepts, `GeneratorSubstation` and `DCSubstation` (both `extends=[Substation]`), to type the corridor endpoints. For the full concept and property definitions, see `model/schema.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

One shared ontology threads all five stages. Each stage reads properties earlier stages wrote and writes new ones for downstream stages — the accretive-enrichment pattern, so capacity, criticality, and compliance signals stay consistent end to end without DataFrame hand-offs.

```text
demand forecasts → predicted_load ───────────────┬→ compliance rules (with generation mix)
grid topology + centrality → structural flags ───┘
                           └→ corridor fragility and contingency
predicted_load + upgrade costs + revenue → one MIP across the budget levels → Pareto frontier
```

### Stage 1: Predict -- Substation Load Forecasting

Derives `Substation.predicted_load` as an ontology property by taking the max `DemandForecast` per substation, with `growth_rate` (growth over the current load, floored at 0.1 MW) and `breach_period` (the first month a forecast exceeds capacity) alongside. Substations near announced data center projects show 32-55% growth; Dallas-Fort Worth is the only substation predicted to breach capacity (1,700 MW predicted vs 1,600 MW capacity at 24 months, 54.6% growth), while Houston Ship Channel shows the highest absolute load (1,797 MW) but stays within its larger capacity. Because both downstream reasoners read `predicted_load` as a first-class attribute, changing the forecast propagates through the rules engine and optimizer without code changes — the first link in the accretive chain.

### Stage 2: Graph -- Grid Topology & Structural Vulnerability

The Graph reasoner uses `Substation` directly as its node concept, with edges between substations that share an active transmission line, and stores results back as native `Substation` properties. It computes weakly connected components (confirming all 12 substations are reachable), Louvain community detection (3 ERCOT regions), and betweenness/degree/eigenvector centrality combined into a critical rank. 7 of 10 DC requests target structurally critical substations — a key input to the rules engine.

### Stage 3: Paths -- Transmission Corridors & Contingency

> PREVIEW capability; requires `relationalai>=1.15`.

Where Stage 2 scores a *substation*, the paths capability scores the *corridor* feeding each data center. It derives a bidirectional substation-to-substation edge from active transmission lines, enumerates generator-substation to DC-substation routes, and ranks each by the Stage 2 betweenness summed along its hops — the most fragile corridor carries the greatest through-traffic exposure. A contingency pass removes the highest-betweenness substation and re-enumerates to show which data centers reroute; the model persists each data center substation's most fragile load (`Substation.fragility_load`), its rank, its most fragile route (`Substation.fragile_route`), and its route with the offline substation removed (`Substation.contingency_route`), with the corridor and reroute counts in `CorridorSummary`. On the bundled grid this enumerates 421 generator-to-DC corridors; the most fragile carries a betweenness-load of 99.833 through the Dallas-Fort Worth, Abilene Central, and Houston Ship Channel hubs.

### Stage 4: Rules -- Interconnection Queue Compliance

Three declarative rules consume upstream outputs, then a composite flag combines them:
- **Capacity check**: `requested_mw + predicted_load > max_capacity_mw` (uses Stage 1, with a `current_load_mw` fallback). Most requests fail — the existing grid lacks headroom for new AI load without upgrades.
- **Structural risk**: request targets a structurally critical substation (uses Stage 2 centrality). 7 of 10 requests fail.
- **Low-carbon mandate**: the substation's zero-emission share of generation capacity is below the DC's required fraction; a substation with no generating capacity fails any positive requirement. Only Oracle Coastal DC passes: its substation's generation is entirely zero-emission, while the other requested substations have no zero-emission generation, no generation at all, or about 53% against requirements of 60-100%.
- **Composite**: `is_compliant` passes all checks. Only Oracle Coastal DC is fully compliant.

### Stage 5: Prescriptive -- Multi-Objective Optimization

An `InvestmentLevel` Scenario Concept holds 5 budget levels ($200M-$600M), each parameterizing one MIP solve into a Pareto frontier. Binary variables `x_approve` (per DC request) and `x_upgrade` (per substation upgrade) are indexed by investment level; substation-capacity constraints use `predicted_load` from Stage 1 so the optimizer sees the same forecasted headroom as the rules engine, and budget constraints are scoped `.per(InvestmentLevel)`. Revenue reflects annual interconnection capacity revenue ($145K-$210K per MW/yr), not energy revenue.

One solve produces the entire frontier. The knee point at $300M (6 DCs, 1,530 MW, $252M net value) is the budget level where the marginal net value per added $M falls the most from the step into it to the step out of it (on a tie, the smaller budget; if the marginal value never falls, the report names no knee): both DFW upgrades fit the budget, and Google Metroplex DC and Lambda Labs DFW join. At $200M, 4 DCs are approved (Microsoft, Amazon SA, Crusoe, Oracle); beyond the knee each additional $100M adds one more DC with diminishing returns ($1,013K/$M into the knee vs $439K/$M from $400M to $500M). Revenue is the objective, so where several upgrade sets earn the same revenue (as at $500M), the net value depends on which set the solver returns. xAI Colossus (500 MW) is never approved at any budget — DFW headroom goes to Google and Lambda. Per-level results (approvals, upgrades, MW) are all queried from the ontology via `model.select()` rather than parsed from solver output.

See the modules in `model/` for the implementation of the five stages and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own substation/transmission-line topology; keep the column names listed in *Sample data* above.
- For Snowflake-backed runs, swap the `load_csv(...)` calls in `model/source.py` for `model.data(snowflake_table)` calls.

### Tune parameters

- **Investment levels** — the budget scenarios (`$200M-$600M`) are `InvestmentLevel` rows; add rows for finer Pareto resolution or shift the budget caps to match your capex envelope.
- **Corridor hop bound** — `MAX_CORRIDOR_HOPS` in `model/corridor_fragility.py` caps the Stage 3 path enumeration; raise it to trace longer generator-to-DC corridors.
- **Structural-criticality cutoff** — `CRITICAL_THRESHOLD` in `model/grid_topology.py` sets how many substations Stage 2 flags critical, ranked by the sum of their betweenness, degree, and eigenvector centrality ranks, feeding Stage 4's structural rule.
- **Objective weights** — Stage 5 maximizes annual interconnection revenue; adjust `annual_revenue_per_mw` to reweight which requests clear at each budget; the net-value amortization changes only the reported net value, marginal value per budget step and knee, not the approvals.

### Extend the model

- **Add demand scenarios** — create a `DemandScenario` concept as a second Scenario axis alongside `InvestmentLevel`.
- **Add generation dispatch** — extend with a `GeneratorPeriod` cross-product and dispatch variables (increases problem size significantly).
- **Adjust the low-carbon target** — modify the `fails_low_carbon` rule (e.g., exclude nuclear to use a renewable-only mandate).

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from your grid systems; the ontology shape is independent of the load pipeline.
- The synthetic grid is sized at 12 substations / 18 lines; the chain scales to whatever fits the prescriptive engine's solve budget. Size the engine up for larger grids or finer investment grids, since the MIP grows with substations × investment levels.
- Pin `relationalai` (this template targets `2.3.0`) and schedule the run as a pipeline step for reproducible, deterministic re-runs.

## Troubleshooting

<details>
<summary>Most DCs fail the capacity check</summary>

- This is expected -- the existing ERCOT grid doesn't have headroom for 2,930 MW of new AI load without upgrades.
- Crusoe (Midland-Permian) and Oracle (Corpus Christi) target substations with spare capacity and low structural criticality; Oracle is the only request that also meets its low-carbon requirement.
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
<summary>xAI Colossus is never approved at any budget level</summary>

- It targets the Dallas-Fort Worth substation, the only substation predicted to breach capacity (54.6% growth). Even with both DFW upgrades, DFW has 699.8 MW of headroom.
- That fits Google Metroplex DC and Lambda Labs DFW together (600 MW, $108M/yr) or xAI alone (500 MW, $105M/yr); xAI with Lambda would need 700 MW.
- The optimizer correctly prioritizes the revenue-maximizing allocation at the constrained substation.

</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chained reasoner patterns and ontology enrichment.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `aggs` / `.define()`.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — node-concept and edge-concept patterns, PageRank and centrality.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.

## Support

- File issues at the RelationalAI templates repository.
