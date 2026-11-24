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
- A date-filtered planning horizon: each horizon's problem uses only the demand orders inside its window; `model/source.py` maps due dates to integer week numbers, and `std.common.range()` builds each horizon's weeks.
- An inventory schedule that satisfies flow conservation (`inv[t] = inv[t-1] + production[t] - demand[t]`) enforced as prescriptive constraints.
- A service-level guarantee (a 95% minimum-fulfillment constraint) plus an unmet-demand report showing whether any demand went unserved.
- A three-scenario what-if sweep that shows how total cost changes as the planning horizon extends, with each horizon solved as its own problem in one deployed model.

Built using **prescriptive reasoning**: continuous decision variables for production, inventory, and unmet demand; a multi-period flow-conservation constraint; and a total-cost objective that adds separately summed cost terms.

## What's included

- **Model**: concepts for sites, SKUs, demand orders, production capacity, and weekly demand, time-indexed production and inventory variables, and one cost-minimizing problem per planning horizon, in the `model/` package (`schema.py` declares the concepts, `source.py` loads the sample data and scopes the orders to each horizon, `reasoning.py` states the decision problems), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs the solves.
- **Query**: `queries/demand_planning.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code in `model/`.
- **Data**: `data/sites.csv`, `data/skus.csv`, `data/demand_orders.csv`, `data/production_capacity.csv`, `data/initial_inventory.csv`
- **Config**: `pyproject.toml`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)
- RelationalAI Python SDK (`relationalai`) == 2.3.0

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.DEMAND_PLANNING_TEMPORAL_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.DEMAND_PLANNING_TEMPORAL_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/demand_planning_temporal.zip), unzip it, and enter the template directory:

   ```bash
   unzip demand_planning_temporal.zip
   cd demand_planning_temporal
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
       name: demand_planning_temporal_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.DEMAND_PLANNING_TEMPORAL               # published views and tables
     identity:
       internal_schema: <DB>.DEMAND_PLANNING_TEMPORAL_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solves. Each refresh of the deployed model runs the solves again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.demand_planning
   ```

   ```text
   Running scenario: planning_end = 2026-01-31

   Solve result:
   • status: OPTIMAL
   • objective: 26137.5

     Status: OPTIMAL
     Total cost: $26,137.50
     Planning horizon: 2025-11-01 to 2026-01-31 (14 weeks)
     Demand orders in scope: 14 (of 25 total)
     ...
     === Unmet Demand ===
     All demand fulfilled!
   ...
   ==================================================
   Scenario Analysis Summary
   ==================================================
     planning_end=2026-01-31: OPTIMAL, cost=$26,137.50
     planning_end=2026-02-28: OPTIMAL, cost=$30,863.50
     planning_end=2026-03-31: OPTIMAL, cost=$34,768.00
   ```

   Each scenario prints its status, objective, plan, inventory levels, and unmet demand (trimmed here); the report ends with a summary sweep. Extending the planning horizon from January to March increases cost from $26,138 to $34,768 as the horizon lengthens (14 to 22 weeks, 14 to 20 demand orders); demand is met entirely from opening inventory, so the increase is holding cost accrued over the longer horizon. All demand is fulfilled in every scenario -- no unmet demand penalties. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.DEMAND_PLANNING_TEMPORAL_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                     # this file
├── runbook.md                    # step-by-step analyst walkthrough
├── pyproject.toml                # dependencies
├── model/
│   ├── __init__.py               # exports of the deployed model
│   ├── schema.py                 # concepts and properties
│   ├── source.py                 # sample data, planning horizons, and order scoping
│   └── reasoning.py              # decision variables, constraints, objective, one problem per horizon
├── queries/
│   └── demand_planning.py        # report from the deployed model
└── data/
    ├── sites.csv                 # warehouse/distribution sites
    ├── skus.csv                  # products with unit and holding costs
    ├── demand_orders.csv         # dated demand orders (Oct 2025 - Mar 2026)
    ├── production_capacity.csv   # per-(site, SKU) weekly capacity and production cost
    └── initial_inventory.csv     # per-(site, SKU) starting inventory
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.demand_planning` to solve all three horizon scenarios end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is a small, illustrative multi-site production dataset covering three warehouse sites and three SKUs, with demand orders spanning October 2025 through March 2026. It is synthetic and sized to run the temporal-filtering and multi-period optimization pattern quickly, not to match any real plant.

- **`sites.csv`** — warehouse/distribution sites (`Chicago_DC`, `Atlanta_DC`, …) with a weekly throughput capacity.
- **`skus.csv`** — products (`Widget_A`, `Widget_B`, `Gadget_C`) with a unit cost and a weekly holding cost.
- **`demand_orders.csv`** — dated demand orders (`id`, `sku_id`, `site_id`, `quantity`, `due_date`); only orders inside the configured horizon enter each scenario.
- **`production_capacity.csv`** — per-(site, SKU) maximum weekly production and production cost.
- **`initial_inventory.csv`** — per-(site, SKU) starting inventory, used as the week-0 condition.

## Model overview

The model is a multi-period production and inventory ontology. Sites and SKUs are reference entities; demand orders are the dated event table that temporal filtering scopes; production capacity carries the pre-joined data the solver's decision variables attach to.

- **Key entities**: `Site`, `SKU`, `DemandOrder`, `ProdCapacity`, and `WeeklyDemand` (pre-aggregated demand per planning horizon, site, SKU, and week, including zero-demand weeks).
- **Primary identifiers**: `Site.id` and `SKU.id` (integers); `DemandOrder.id` (integer); the composite key `ProdCapacity(site_id, sku_id)`; the composite key `WeeklyDemand(wk_planning_end, wk_site_id, wk_sku_id, wk_week_num)`.
- **Important invariants**: quantities, costs, production, and inventory are non-negative; inventory obeys flow conservation (`inv[t] = inv[t-1] + production[t] - demand[t]`); week 0 inventory equals the initial inventory; unmet demand per order is bounded by the order quantity; total unmet demand is capped by the 95% service level. Unmet demand is not subtracted from the inventory withdrawal: inventory must cover all demand, and `x_unmet` counts only toward the service level and the penalty.

For the full concept and property definitions, see `model/schema.py`; the time-indexed `x_production` / `x_inventory` decision variables on `ProdCapacity` are declared in `model/reasoning.py`, and the relationships linking orders and capacity to their `Site` and `SKU` in `model/source.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

**Sweep planning horizons.** `model/source.py` lists three `planning_end` dates to analyze how the horizon length affects cost. For each, it selects the demand orders inside the window (so each problem sees only relevant demand) and builds the weekly demand over the horizon's weeks. `model/reasoning.py` defines one problem per horizon, so an infeasible horizon never affects the others.

**Map dates to integer weeks.** `std.common.range()` requires integer periods, so each order's due date is converted into a week number relative to the planning start, and the number of weeks is derived from the horizon length. The week count varies by scenario (14 weeks for January, 18 for February, 22 for March).

**Index decision variables by time.** Production and inventory variables are indexed by both concept (site × SKU) and time period via a multi-arity property pattern, creating one continuous variable per (site, SKU, week) combination, bounded by the per-line weekly capacity.

**Enforce flow conservation.** The core multi-period constraint ties adjacent weeks together: inventory at the end of week `t` equals inventory at the end of week `t-1` plus production in week `t` minus demand in week `t`. A `WeeklyDemand` concept pre-aggregates orders into weekly buckets — including zero-demand weeks — so the constraint covers every period.

**Minimize total cost.** The objective adds production cost, holding cost, and an unmet-demand penalty, each summed over its own concept, and the solver minimizes the total subject to the flow-conservation and service-level constraints.

`model/source.py` also includes a commented-out Pattern B for data that carries Unix epoch-second timestamps instead of date strings: convert the horizon boundaries to epochs and filter identically.

See `model/reasoning.py` for the implementation and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- **Add more sites or SKUs**: Append rows to `sites.csv`, `skus.csv`, `production_capacity.csv`, and `initial_inventory.csv`. The model generalizes to any number of site-SKU combinations.
- **Switch to epoch timestamps**: Follow the commented Pattern B code to adapt the template for data with Unix epoch integer columns.

### Tune parameters

- **Change the planning horizon**: Edit `planning_start` and the `SCENARIO_VALUES` list in `model/source.py` to shift the optimization window. Each value becomes its own problem, and the week count and date filter update automatically per scenario.
- **Adjust service level**: Change `min_service_level` in `model/reasoning.py` (default 0.95) to require higher or lower demand fulfillment.
- **Adjust safety stock**: The `safety_stock_weeks` parameter in `model/reasoning.py` (default 1) requires inventory at the end of each week to be at least `safety_stock_weeks × average weekly demand` per site-SKU pair. Set to 0 to disable, or increase for more conservative buffering.

### Extend the model

- Add new cost components (for example a per-site fixed operating cost) as another summed term in the objective in `build_plan`, following the `prod_cost` / `hold_cost` / `unmet_cost` pattern.
- Add new constraints (for example a per-site total-capacity cap across SKUs) with additional `problem.satisfy(...)` calls alongside the flow-conservation constraint in `build_plan`.

### Scale up / productionize

- The scenario sweep shares one model across horizons; for production, read your Snowflake tables into DataFrames (for example with Snowpark's `to_pandas()`) in place of the CSV loads in `model/source.py`, so its week-number and weekly-demand preparation still runs. That preparation happens at deploy time, so new order data needs a redeploy, not only a refresh.
- Solve time is controlled by `time_limit_sec` on `problem.configure("highs", ...)` in `model/reasoning.py`; raise it if larger site/SKU/week grids need more time.

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
<summary>A horizon's solve status is INFEASIBLE</summary>

Inventory balance withdraws every unit of weekly demand, so initial inventory plus production must cover all demand plus safety stock; lowering `min_service_level` does not relieve a stock shortage. Check that production capacities in `production_capacity.csv` are large enough to cover weekly demand. Also verify that `initial_inventory.csv` has entries for every site-SKU pair. If you increased `safety_stock_weeks`, try setting it to 0 to check whether the safety stock floor is causing infeasibility.
</details>

<details>
<summary>No demand orders in scope after filtering</summary>

Verify that `planning_start` and the `SCENARIO_VALUES` dates in `model/source.py` overlap with the `due_date` values in `demand_orders.csv`. The default data covers October 2025 through March 2026; the default scenarios span January through March 2026.
</details>

<details>
<summary>Connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — concepts, properties, `model.define(...)`, and `model.where(...)`, used to load and link the entities.
- [Temporal periods with `std.common.range()`](https://docs.relational.ai/) — building the integer week ranges the multi-period variables and constraints index over.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem`, `solve_for` decision variables, `satisfy` constraints, and `minimize` objectives.
- [Solver management](https://docs.relational.ai/) — configuring the HiGHS solve and `time_limit_sec`.

## Support

- File issues at the RelationalAI templates repository.
