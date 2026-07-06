---
title: "Demand Planning Temporal"
description: "Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Multi-Period
  - Temporal-Filtering
  - Inventory
  - LP (linear programming)
---

## What this template is for

Manufacturing and distribution companies must decide how much to produce at each site every week to satisfy customer demand while keeping production and inventory holding costs low. When demand spans many months but the planning team only wants to optimize over a specific window, temporal filtering becomes essential: scope the data to a planning horizon before building the optimization model.

This template solves a multi-period production and inventory planning problem across three warehouse sites and three product SKUs. It demonstrates how to filter demand orders by date range, map dates to integer week periods, and enforce inventory flow conservation constraints so that ending inventory each week equals beginning inventory plus production minus demand.

Prescriptive reasoning makes this practical because the solver simultaneously balances production costs, holding costs, and service-level requirements across all sites, SKUs, and weeks, finding the cost-minimizing plan that a manual planner could not feasibly compute.

## Who this is for

- **Intermediate users** comfortable with linear programming concepts like decision variables, constraints, and objectives
- **Supply chain analysts** building production or inventory planning models
- **Data scientists** who need to scope optimization to a configurable date window
- **Operations researchers** looking for a multi-period flow-conservation pattern in RelationalAI

- A cost-minimizing weekly production plan per (site, SKU, week), produced by **prescriptive** decision variables and a HiGHS solve.
- A date-filtered planning horizon: only demand orders inside the configured window enter the model, with due dates mapped to integer week periods via `std.common.range()`.
- An inventory schedule that satisfies flow conservation (`inv[t] = inv[t-1] + production[t] - demand[t]`) enforced as prescriptive constraints.
- A service-level guarantee (a 95% minimum-fulfillment constraint) plus an unmet-demand report showing whether any demand went unserved.
- A three-scenario what-if sweep that shows how total cost changes as the planning horizon extends, all sharing one model.

Built using **prescriptive reasoning**: continuous decision variables for production, inventory, and unmet demand; a multi-period flow-conservation constraint; and a total-cost objective assembled with `model.union()`.

## What's included

- **Script**: `demand_planning_temporal.py` -- end-to-end model, solve, and results
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Data**: `data/sites.csv`, `data/skus.csv`, `data/demand_orders.csv`, `data/production_capacity.csv`, `data/initial_inventory.csv`
- **Config**: `pyproject.toml`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/demand_planning_temporal.zip
   unzip demand_planning_temporal.zip
   cd demand_planning_temporal
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python demand_planning_temporal.py
   ```

6. Expected output. Each scenario prints its status, cost, and plan; the run ends with a summary sweep. A few representative lines confirm a successful run:

   ```text
   Running scenario: planning_end = 2026-01-31
     Status: OPTIMAL
     Total cost: $26,137.50
     Planning horizon: 2025-11-01 to 2026-01-31 (14 weeks)
     Demand orders in scope: 14 (of 25 total)
     All demand fulfilled!
   ...
   ==================================================
   Scenario Analysis Summary
   ==================================================
     planning_end=2026-01-31: OPTIMAL, cost=$26,137.50
     planning_end=2026-02-28: OPTIMAL, cost=$30,863.50
     planning_end=2026-03-31: OPTIMAL, cost=$34,768.00
   ```

   Extending the planning horizon from January to March increases cost from
   $26,138 to $34,768 as the horizon lengthens (14 to 22 weeks, 14 to 20
   demand orders); demand is met entirely from opening inventory, so the
   increase is holding cost accrued over the longer horizon.
   All demand is fulfilled in every scenario -- no unmet demand penalties.

## Template structure

```text
.
├── README.md                     # this file
├── pyproject.toml                # dependencies
├── demand_planning_temporal.py   # end-to-end model, scenario sweep, solve, results
└── data/
    ├── sites.csv                 # warehouse/distribution sites
    ├── skus.csv                  # products with unit and holding costs
    ├── demand_orders.csv         # dated demand orders (Oct 2025 - Mar 2026)
    ├── production_capacity.csv    # per-(site, SKU) weekly capacity and production cost
    └── initial_inventory.csv     # per-(site, SKU) starting inventory
```

**Start here**: run `python demand_planning_temporal.py` to solve all three horizon scenarios end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is a small, illustrative multi-site production dataset covering three warehouse sites and two SKUs, with demand orders spanning October 2025 through March 2026. It is synthetic and sized to run the temporal-filtering and multi-period optimization pattern quickly, not to match any real plant.

- **`sites.csv`** — warehouse/distribution sites (`Chicago_DC`, `Atlanta_DC`, …) with a weekly throughput capacity.
- **`skus.csv`** — products (`Widget_A`, `Widget_B`) with a unit cost and a weekly holding cost.
- **`demand_orders.csv`** — dated demand orders (`id`, `sku_id`, `site_id`, `quantity`, `due_date`); only orders inside the configured horizon enter each scenario.
- **`production_capacity.csv`** — per-(site, SKU) maximum weekly production and production cost.
- **`initial_inventory.csv`** — per-(site, SKU) starting inventory, used as the week-0 condition.

## Model overview

The model is a multi-period production and inventory ontology. Sites and SKUs are reference entities; demand orders are the dated event table that temporal filtering scopes; production capacity carries the pre-joined data the solver's decision variables attach to.

- **Key entities**: `Site`, `SKU`, `DemandOrder`, `ProdCapacity`, and `WeeklyDemand` (a per-scenario concept that pre-aggregates orders into weekly buckets, including zero-demand weeks).
- **Primary identifiers**: `Site.id` and `SKU.id` (integers); `DemandOrder.id` (integer); the composite key `ProdCapacity(site_id, sku_id)`; the composite key `WeeklyDemand(wk_site_id, wk_sku_id, wk_week_num)`.
- **Important invariants**: quantities, costs, production, and inventory are non-negative; inventory obeys flow conservation (`inv[t] = inv[t-1] + production[t] - demand[t]`); week 0 inventory equals the initial inventory; unmet demand per order is bounded by the order quantity; total unmet demand is capped by the 95% service level.

For the full concept and property definitions — including the time-indexed `x_production` / `x_inventory` decision variables on `ProdCapacity` and the relationships linking orders and capacity to their `Site` and `SKU` — see `demand_planning_temporal.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

**Sweep planning horizons.** The script loops over three `planning_end` dates to analyze how the horizon length affects cost. Each iteration filters demand orders to the window (dropping orders outside it so the solver sees only relevant demand), recomputes the week mapping, and solves a fresh problem.

**Map dates to integer weeks.** `std.common.range()` requires integer periods, so each order's due date is converted into a week number relative to the planning start, and the number of weeks is derived from the horizon length. The week count varies by scenario (14 weeks for January, 18 for February, 22 for March).

**Index decision variables by time.** Production and inventory variables are indexed by both concept (site × SKU) and time period via a multi-arity property pattern, creating one continuous variable per (site, SKU, week) combination, bounded by the per-line weekly capacity.

**Enforce flow conservation.** The core multi-period constraint ties adjacent weeks together: inventory at the end of week `t` equals inventory at the end of week `t-1` plus production in week `t` minus demand in week `t`. A `WeeklyDemand` concept pre-aggregates orders into weekly buckets — including zero-demand weeks — so the constraint covers every period.

**Minimize total cost.** The objective combines production cost, holding cost, and an unmet-demand penalty from different concepts using `model.union()`, and the solver minimizes their sum subject to the flow-conservation and service-level constraints.

The script also includes a commented-out Pattern B for data that carries Unix epoch-second timestamps instead of date strings: convert the horizon boundaries to epochs and filter identically.

See `demand_planning_temporal.py` for the implementation and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- **Add more sites or SKUs**: Append rows to `sites.csv`, `skus.csv`, `production_capacity.csv`, and `initial_inventory.csv`. The model generalizes to any number of site-SKU combinations.
- **Switch to epoch timestamps**: Follow the commented Pattern B code to adapt the template for data with Unix epoch integer columns.

### Tune parameters

- **Change the planning horizon**: Edit `planning_start` and the `SCENARIO_VALUES` list to shift the optimization window. Values must be in increasing date order (each scenario extends the previous horizon). The week count and date filter update automatically per scenario.
- **Adjust service level**: Change `min_service_level` (default 0.95) to require higher or lower demand fulfillment.
- **Adjust safety stock**: The `safety_stock_weeks` parameter (default 1) requires inventory at the end of each week to be at least `safety_stock_weeks × average weekly demand` per site-SKU pair. Set to 0 to disable, or increase for more conservative buffering.

### Extend the model

- Add new cost components (for example a per-site fixed operating cost) as additional terms in the `model.union()` objective, following the `prod_cost` / `hold_cost` / `unmet_cost` pattern.
- Add new constraints (for example a per-site total-capacity cap across SKUs) with additional `problem.satisfy(...)` calls alongside the flow-conservation constraint.

### Scale up / productionize

- The scenario sweep shares one model across horizons; for production, replace the CSV loads with Snowflake-backed `model.data(...)` sources and schedule the run.
- Solve time is controlled by `time_limit_sec` on `problem.solve("highs", ...)`; raise it if larger site/SKU/week grids need more time.

## Troubleshooting

<details>
<summary>ModuleNotFoundError: No module named 'relationalai'</summary>

Make sure you have activated your virtual environment and installed dependencies:

```bash
source .venv/bin/activate
python -m pip install .
```
</details>

<details>
<summary>Solver returns INFEASIBLE</summary>

The 95% service level constraint may be too strict for your data. Try lowering `min_service_level` to 0.90, or check that production capacities in `production_capacity.csv` are large enough to cover weekly demand. Also verify that `initial_inventory.csv` has entries for every site-SKU pair. If you increased `safety_stock_weeks`, try setting it to 0 to check whether the safety stock floor is causing infeasibility.
</details>

<details>
<summary>No demand orders in scope after filtering</summary>

Verify that `planning_start` and the `SCENARIO_VALUES` dates overlap with the `due_date` values in `demand_orders.csv`. The default data covers October 2025 through March 2026; the default scenarios span January through March 2026.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Run `rai init` to configure your connection profile. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — concepts, properties, `model.define(...)`, and `model.where(...)`, used to load and link the entities.
- [Temporal periods with `std.common.range()`](https://docs.relational.ai/) — building the integer week ranges the multi-period variables and constraints index over.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem`, `solve_for` decision variables, `satisfy` constraints, `minimize` objectives, and `model.union()`.
- [Solver management](https://docs.relational.ai/) — configuring the HiGHS solve and `time_limit_sec`.

## Support

- File issues at the RelationalAI templates repository.
