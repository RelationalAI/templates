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

A defensible answer needs all four signals at once: which substations will run out of headroom, which are structurally critical to keep the grid connected, which requests clear interconnection compliance, and which approval-and-upgrade portfolio maximizes value at each budget. **The template chains RelationalAI's predictive load forecasting, graph topology and centrality analysis, rules-based interconnection compliance, and prescriptive multi-objective optimization on a single, accretively-enriched ontology** -- each reasoner writes derived properties the next consumes, so capacity, criticality, and compliance signals stay consistent end to end without DataFrame hand-offs between stages.

## Why this problem matters

ERCOT -- the Electric Reliability Council of Texas -- operates an isolated grid not interconnected with the Eastern or Western Interconnections, so Texas cannot import power during demand spikes. That makes capacity planning uniquely consequential, as Winter Storm Uri (2021) showed when grid failures cascaded without external relief.

Texas is now the fastest-growing market for AI data center development. Hyperscalers are requesting multi-hundred-megawatt interconnections at substations designed for decades of steady organic growth. The ERCOT grid must absorb 2,930 MW of new data center load -- equivalent to roughly 3 nuclear reactors -- while maintaining reliability for 30 million existing customers.

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

- `energy_grid_planning.py` -- Main script with five chained reasoning stages
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
- `data/train_forecasts.csv`, `data/val_forecasts.csv`, `data/test_forecasts.csv` -- graph neural network (GNN) training splits (used by optional GNN training workflow, not by the main script)

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

6. Expected output (a few lines confirm a successful run):

   ```text
   STAGE 5: OPTIMIZE -- Joint Interconnection + Upgrade
     Status: OPTIMAL | Objective: 1,579,200,000

     KNEE POINT: $300M -- 5 DCs, 1,500 MW, $264M net value
     xAI Colossus ($105M/yr) unlocks at $300M -- highest-revenue single request

   PIPELINE COMPLETE: 5 stages executed on shared Energy Grid ontology
   ```

   See `runbook.md` for the full log.

## Template structure

```text
energy_grid_planning/
  energy_grid_planning.py    # Main script (5 chained reasoning stages)
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

**Start here**: run `python energy_grid_planning.py` for the full five-stage chain end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is **synthetic and illustrative** — modeled on the public shape of the ERCOT (Texas) grid and the wave of hyperscaler AI data center announcements, not a specific operator's network export. It is sized to teach the five-stage reasoning flow on a Snowflake-connected RAI account; production attributes a real interconnection study carries (sub-hourly SCADA telemetry, nodal pricing, contingency sets, protection settings) are extension points (see *Customize this template*), not gaps in the reasoning pattern.

The script loads thirteen CSVs from `data/` into the ontology (`energy_grid_planning.py` lines 77-89). Three additional GNN-split files ship for the optional training workflow and are **not** read by the main script.

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
- **`demand_forecasts.csv`** (96 rows) — pre-computed substation load forecasts at 6/12/18/24-month horizons, with confidence and a DC-growth-included flag. Stage 1 reads this directly (the GNN fallback path).
- **`load_history.csv`** (576 rows) — 4 years of monthly per-substation load readings with temperature and a peak-season flag.
- **`dc_announcements.csv`** (8 rows) — hyperscaler announcement events (date, MW, target substation).

Optional GNN training splits, **not loaded by the main script**: `train_forecasts.csv` (360 rows), `val_forecasts.csv` (108 rows), `test_forecasts.csv` (108 rows) — `substation_id` / `timestamp` / `target_load_mw` series for the optional predictive-training workflow.

## Model overview

One shared ontology threads all five stages. Each stage reads concepts and properties earlier stages wrote, and writes new ones for downstream stages — the accretive-enrichment pattern described above.

- **Key entities**: `Substation`, `Generator`, `TransmissionLine`, `DataCenterRequest`, `SubstationUpgrade`, `DemandForecast`; plus the Stage 5 Scenario Concept `InvestmentLevel` and the results concept `InvestmentPortfolio`. Supporting concepts (`LoadZone`, `DemandPeriod`, `RenewableProfile`, `MaintenanceWindow`, `Customer`, `LoadHistory`, `DCAnnouncement`) mirror their CSVs and back the aggregations.
- **Primary identifiers**: string `id` on the base entities (e.g. `SUB-001`, `TL-001`); `name` on `InvestmentLevel` (e.g. `"$300M"`); `investment_level_name` on `InvestmentPortfolio`.
- **Important invariants**: `predicted_load`, `max_capacity_mw`, `current_load_mw`, `requested_mw`, and `capacity_increase_mw` are non-negative MW; `low_carbon_requirement_pct` is a percentage; a generator is low-carbon when `emissions_rate == 0`; Stage 5 decision variables (`x_approve`, `x_upgrade`) are binary.

`Substation` is the hub: Stages 1-3 enrich it with forecast, topology, and corridor-fragility properties that Stages 4-5 consume. The Stage 3 paths analysis also derives two transient sub-concepts, `GeneratorSubstation` and `DCSubstation` (both `extends=[Substation]`), to type the corridor endpoints. For the full concept and property definitions, see `energy_grid_planning.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

One shared ontology threads all five stages. Each stage reads properties earlier stages wrote and writes new ones for downstream stages — the accretive-enrichment pattern, so capacity, criticality, and compliance signals stay consistent end to end without DataFrame hand-offs.

```text
demand forecasts → predicted_load → grid topology + centrality → corridor fragility
   → compliance rules → multi-objective MIP → Pareto frontier
```

### Stage 1: Predict -- Substation Load Forecasting

Derives `Substation.predicted_load` as an ontology property by taking the max `DemandForecast` per substation. Substations near announced data center projects show 32-55% growth; Dallas-Fort Worth is the only substation predicted to breach capacity (1,700 MW predicted vs 1,600 MW capacity at 24 months, 54.6% growth), while Houston Ship Channel shows the highest absolute load (1,797 MW) but stays within its larger capacity. Because both downstream reasoners read `predicted_load` as a first-class attribute, changing the forecast propagates through the rules engine and optimizer without code changes — the first link in the accretive chain.

### Stage 2: Graph -- Grid Topology & Structural Vulnerability

The Graph reasoner uses `Substation` directly as its node concept, with edges between substations that share an active transmission line, and stores results back as native `Substation` properties. It computes weakly connected components (confirming all 12 substations are reachable), Louvain community detection (3 ERCOT regions), and betweenness/degree/eigenvector centrality combined into a critical rank. 7 of 10 DC requests target structurally critical substations — a key input to the rules engine.

### Stage 3: Paths -- Transmission Corridors & Contingency

> PREVIEW capability; requires `relationalai>=1.15`.

Where Stage 2 scores a *substation*, the paths capability scores the *corridor* feeding each data center. It derives a bidirectional substation-to-substation edge from active transmission lines, enumerates generator-substation to DC-substation routes, and ranks each by the Stage 2 betweenness summed along its hops — the most fragile corridor carries the greatest through-traffic exposure. A contingency pass removes the highest-betweenness substation and re-enumerates to show which data centers reroute; the most-fragile load is persisted as `Substation.fragility_load`. On the bundled grid this enumerates 421 generator-to-DC corridors; the most fragile carries a betweenness-load of 99.833 through the Dallas-Fort Worth, Abilene Central, and Houston Ship Channel hubs.

### Stage 4: Rules -- Interconnection Queue Compliance

Three declarative rules consume upstream outputs, then a composite flag combines them:
- **Capacity check**: `requested_mw + predicted_load > max_capacity_mw` (uses Stage 1, with a `current_load_mw` fallback). Most requests fail — the existing grid lacks headroom for new AI load without upgrades.
- **Structural risk**: request targets a structurally critical substation (uses Stage 2 centrality). 7 of 10 requests fail.
- **Low-carbon mandate**: substation's low-carbon generation fraction below the DC's requirement. All requests pass — ERCOT's nuclear plants (STP, Comanche Peak) and wind/solar fleet supply enough low-carbon generation.
- **Composite**: `is_compliant` passes all checks. Only Crusoe Permian DC and Oracle Coastal DC are fully compliant.

### Stage 5: Prescriptive -- Multi-Objective Optimization

An `InvestmentLevel` Scenario Concept holds 5 budget levels ($200M-$600M), each parameterizing one MIP solve into a Pareto frontier. Binary variables `x_approve` (per DC request) and `x_upgrade` (per substation upgrade) are indexed by investment level; substation-capacity constraints use `predicted_load` from Stage 1 so the optimizer sees the same forecasted headroom as the rules engine, and budget constraints are scoped `.per(InvestmentLevel)`. Revenue reflects annual interconnection capacity revenue ($145K-$210K per MW/yr), not energy revenue.

One solve produces the entire frontier. The knee point at $300M (5 DCs, 1,500 MW, $264M net value) shows the highest marginal return, unlocking xAI Colossus ($105M/yr). At $200M, 4 DCs are approved (Microsoft, CoreWeave, Crusoe, Oracle); each additional $100M adds one more DC with diminishing returns ($995K/$M at the knee vs $400K/$M at $600M). Google Metroplex DC (400 MW) and Lambda Labs DFW (200 MW) are never approved at any budget — DFW capacity is fully consumed. Per-level results (approvals, upgrades, MW) are all queried from the ontology via `model.select()` rather than parsed from solver output.

See `energy_grid_planning.py` for the implementation of all five stages and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own substation/transmission-line topology; keep the column names listed in *Sample data* above.
- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `model.data(snowflake_table)` calls.
- Use real GNN predictions by installing the predictive reasoner and training on `load_history.csv` (the GNN training splits ship in `data/` for this), then let Stage 1 read the trained model instead of the `demand_forecasts.csv` fallback.

### Tune parameters

- **Investment levels** — the budget scenarios (`$200M-$600M`) are `InvestmentLevel` rows; add rows for finer Pareto resolution or shift the budget caps to match your capex envelope.
- **Corridor hop bound** — `MAX_CORRIDOR_HOPS` caps the Stage 3 path enumeration; raise it to trace longer generator-to-DC corridors.
- **Structural-criticality cutoff** — `CRITICAL_THRESHOLD` sets how many top-betweenness substations Stage 2 flags critical, feeding Stage 4's structural rule.
- **Objective weights** — Stage 5 maximizes annual interconnection revenue; adjust `annual_revenue_per_mw` or the net-value amortization to reweight which requests clear at each budget.

### Extend the model

- **Add demand scenarios** — create a `DemandScenario` concept as a second Scenario axis alongside `InvestmentLevel`.
- **Add generation dispatch** — extend with a `GeneratorPeriod` cross-product and dispatch variables (increases problem size significantly).
- **Adjust the low-carbon target** — modify the `fails_low_carbon` rule (e.g., exclude nuclear to use a renewable-only mandate).

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from your grid systems; the ontology shape is independent of the load pipeline.
- The synthetic grid is sized at 12 substations / 18 lines; the chain scales to whatever fits the prescriptive engine's solve budget. Size the engine up for larger grids or finer investment grids, since the MIP grows with substations × investment levels.
- Pin `relationalai` (this template targets `1.15.0`) and schedule the run as a pipeline step for reproducible, deterministic re-runs.

## Troubleshooting

<details>
<summary>Stage 2 graph queries work but Stage 5 fails with <code>UnsupportedRecursionError</code></summary>

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

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chained reasoner patterns and ontology enrichment.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `aggs` / `.define()`.

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) — heterogeneous-graph classification, PropertyTransformer, edge patterns.
- [Graph reasoner](https://docs.relational.ai/) — node-concept and edge-concept patterns, PageRank and centrality.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.

## Support

- File issues at the RelationalAI templates repository.
