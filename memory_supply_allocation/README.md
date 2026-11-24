---
title: "Memory Supply Allocation"
description: "Allocate limited memory-chip supply across customers month by month to maximize margin while protecting key accounts. Also surfaces which suppliers and raw materials put the plan most at risk."
featured: false
experience_level: intermediate
industry: "Technology & Telecom"
reasoning_types:
  - Predictive
  - Rules-based
  - Prescriptive
  - Graph
tags:
  - Multi-Period
  - Multi-SKU
  - Rolling-Horizon
  - Service-Level
  - Linear-Programming
  - Allocation
  - Paths
  - Root-Cause-Analysis
  - Supplier-Risk
---

## What this template is for

When advanced memory chips are scarce, every manufacturer faces the same monthly question: who gets how much? Demand outstrips supply, foundry health swings month to month, raw-material shocks ripple through production, and strategic customers expect to be protected even when others are cut. Replanning this by spreadsheet is slow, opaque, and hard to defend.

This template shows how RelationalAI answers that question on a single shared model of the business. Forecasting, business rules, optimization, and graph analysis all read and write the same ontology, so a planner can predict supplier health, encode who-protects-whom policies, compute the revenue-maximizing allocation, and trace which suppliers and materials put the plan most at risk — then re-run the whole chain the moment a disruption surfaces.

## Who this is for

- **Intermediate users** comfortable with optimization and graph-traversal concepts
- **Strategic procurement / S&OP teams** weighing supplier-risk scenarios under a monthly replan cadence
- **Operations researchers** exploring multi-reasoner pipelines (predictive feeding prescriptive feeding graph) in RelationalAI

## What you'll build

- A monthly allocation plan across a 36-month horizon that maximizes margin while honoring each customer's service floor — produced by the **prescriptive** (linear-programming) reasoner
- A supplier-capability forecast that feeds the plan, produced by the **predictive** (GNN regression) reasoner
- Customer-protection policies — yield limits, elevated service floors, and single-point-of-failure flags — derived as queryable model attributes with the **rules** reasoner
- A rolling-horizon replan that re-solves as two disruptions surface, surfacing exactly who absorbs each shock
- A risk view that ranks which foundries and raw materials most threaten the plan, using **graph** path traversal plus two what-if scenarios

## What's included

- `model/` -- the deployed model: `schema.py` declares the concepts and the forecast task relationships, `source.py` loads the bundled CSVs and the rolling-horizon disruption data, `reasoning.py` states the rules, the supplier-capability GNN, the three rolling-horizon problems with the rules that publish their results, the dependency-chain paths, and the two what-ifs
- `train.py` -- trains the supplier-capability GNN over the deployed splits and registers its version
- `queries/allocation_report.py` -- prints the forecast summary, each rolling-horizon solve with its plan diff and service levels, the dependency chains, the what-if rankings, and a headline from the deployed model
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills, one prompt per stage
- Sample data: 13 CSVs under `data/` (customers, products, periods, demand, suppliers, capacity, inputs, dependencies, and the disruption schedule)
- Outputs: per-iteration LP status and margin, plan diffs, service levels, dependency chains, and what-if rankings, all queryable from the deployed ontology

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schemas). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.
- The predictive reasoner's compute pool added to the compute-pool network rule that admits the PAT user (the rule from the prescriptive reasoner setup), because the deployed model runs this template's GNN training, scoring, and registration jobs as the PAT user. Check the pool names in your account with `SHOW COMPUTE POOLS` (for example `RELATIONAL_AI_HIGHMEM_X64_S_ML`), and have an administrator run `ALTER NETWORK RULE <PAT_POOL_NETWORK_RULE> SET VALUE_LIST = (...)`, listing the pools already in the rule plus the predictive one.

Those jobs need grants for the PAT user's role (`<PAT_ROLE>`) and matching caller grants for the RAI Native App. Once the Quickstart's first step has created this template's schemas, have an administrator run:

```sql
GRANT USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO ROLE <PAT_ROLE>;
GRANT USAGE ON DATABASE <DB> TO ROLE <PAT_ROLE>;
GRANT USAGE ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON ALL VIEWS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO ROLE <PAT_ROLE>;
GRANT USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO ROLE <PAT_ROLE>;
GRANT CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO ROLE <PAT_ROLE>;
GRANT CALLER USAGE, CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT, INSERT ON ALL TABLES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE ON ALL FILE FORMATS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE EXPERIMENT, CREATE MODEL ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER USAGE, MODIFY ON ALL EXPERIMENTS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER OWNERSHIP ON ALL MODELS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
```

The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python >= 3.10.
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.MEMORY_SUPPLY_ALLOCATION;
CREATE SCHEMA IF NOT EXISTS <DB>.MEMORY_SUPPLY_ALLOCATION_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.MEMORY_SUPPLY_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;

```

Use this sequence to deploy the model, train the GNN, and query the rolling-horizon plans:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/memory_supply_allocation.zip), unzip it, and enter the template directory:

   ```bash
   unzip memory_supply_allocation.zip
   cd memory_supply_allocation
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

   Set the connection `role` to the model role, then add the predictive and prescriptive reasoners, the registered version the GNN predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: memory_supply_gnn          # created on first use if it doesn't exist
       gnns:
         supplier_capability:           # the GNN's name in model/reasoning.py
           registry: <DB>.MEMORY_SUPPLY_ALLOCATION
           model: SUPPLIER_CAPABILITY
           version: V1                  # train.py registers this version
     prescriptive:
       name: memory_supply_solver       # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.MEMORY_SUPPLY_ALLOCATION          # published views and tables
     identity:
       internal_schema: <DB>.MEMORY_SUPPLY_ALLOCATION_META # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>           # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the reasoners and the public schema named in `raiconfig.yaml` if they don't exist and waits for the model's first refresh, which loads the data and sets up the three rolling-horizon problems. No version of the GNN is registered yet, so this refresh makes no capability forecast and the problems have no capacity to allocate.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it forecasts supplier capability with this version and solves the three problems over it: `CALL DB.MEMORY_SUPPLY_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `DB`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the forecast, the plans, and the risk analyses from the deployed model:

   ```bash
   python -m queries.allocation_report
   ```

   ```text
   GNN predictions: 216 rows for periods 1..36

   Per-supplier capability_pct summary (post-Stage 2):
                mean  min  max              supplier
   supplier_id
   1            0.93 0.93 0.93         Orion Foundry
   2            0.93 0.93 0.93        Helios Foundry
   3            0.93 0.93 0.93        Nimbus Foundry
   4            0.92 0.92 0.92  Pelican Memory Works
   5            0.93 0.93 0.93   Stellar Memory Corp
   6            0.93 0.93 0.93    Vega Flash Systems

   ============================================================
   Stage 3 iteration 0: Baseline (month 1, no disruption revealed)
   ============================================================
     Horizon: months 1-36, effective-capacity cells loaded: 180
   Solve result:
   • status: OPTIMAL
   • objective: 45672092437.4948

     Status: OPTIMAL
     Total margin over horizon (months 1-36): $45,672,092,437.49
     ...

   ============================================================
   Rolling-horizon summary
   ============================================================
     iter=0 months=1-36: OPTIMAL      margin=$45,672,092,437.49
     iter=1 months=5-36: OPTIMAL      margin=$40,685,982,461.43
     iter=2 months=13-36: OPTIMAL      margin=$29,100,819,663.45
     ...

   ============================================================
   Headline
   ============================================================
     Customer-graph SPOF(s): Apex Photonic Components
     Multi-hop dependency chains:
       Aether Cloud -> Photonic Lithography -> Apex Photonic Components
       Hyperion Compute -> Photonic Lithography -> Apex Photonic Components
     Supplier with widest offline impact: Orion Foundry (72 affected cells, max cap drop 60.1%)
     Input with widest shortage impact: Helium (180 affected cells)
     Margin erosion across rolling horizon (iter 0 -> iter 2): $16,571,272,774.04
   ```

   The report prints more than shown here: each iteration's plan diff and per-customer service levels, the dependency chains, and both what-if tables. The GNN's forecast, and with it the margins and the plan diffs, shifts from one training run to the next; the structure is stable: three OPTIMAL solves with margin eroding as each disruption is revealed, Apex Photonic Components as the dependency SPOF, Orion Foundry and Helium as the widest supplier and input impacts. Alternative optimal allocations can differ between refreshes at the same margin.

   To forecast and solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.MEMORY_SUPPLY_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

8. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas, with the GNN's experiments and registered versions in the public schema.

## Template structure

```text
.
├── README.md
├── runbook.md
├── pyproject.toml
├── train.py                      # trains and registers the GNN
├── model/
│   ├── __init__.py               # exports for train.py and the query
│   ├── schema.py                 # concepts and the forecast task relationships
│   ├── source.py                 # loads the CSVs, the GNN splits, and the disruption data
│   └── reasoning.py              # rules, GNN, rolling-horizon problems, paths, what-ifs
├── queries/
│   └── allocation_report.py      # prints the forecast, plans, chains, and what-ifs
└── data/                         # sample input CSVs
    ├── customers.csv
    ├── products.csv
    ├── periods.csv
    ├── demand.csv
    ├── suppliers.csv
    ├── supplier_features.csv
    ├── supplier_observations_historical.csv
    ├── supplier_product_capacity.csv
    ├── inputs.csv
    ├── input_usage.csv
    ├── supplier_capability_forecast.csv
    ├── dependencies.csv
    └── disruption_reveal.csv
```

**Start here**: follow the Quickstart to deploy the model, train the GNN, and query the results, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The sample data models a memory-chip maker allocating constrained supply across 11 customers and 5 SKUs over a 36-month horizon. All files live in `data/` and are loaded as ontology concepts at startup.

- **`customers.csv`** (11 rows) — buyers across several industries (e.g. hyperscaler, consumer OEM, automotive, foundry equipment, precision optics), each with a `base_service_floor_pct` (the minimum share of demand they must receive).
- **`products.csv`** (5 rows) — memory SKUs (HBM3E, HBM3, DDR5-6400, LPDDR5X, NAND-TLC-512Gb) with unit price and margin. HBM3E is the scarce, high-margin SKU.
- **`periods.csv`** (36 rows) — monthly buckets (`2026-01` … `2028-12`).
- **`demand.csv`** (1,476 rows) — demand in USD per `(customer, product, period)`. Demand structurally exceeds supply on advanced SKUs.
- **`suppliers.csv`** (6 rows) — named foundries and memory/NAND fabs (Orion Foundry, Helios Foundry, Nimbus Foundry, Pelican Memory Works, Stellar Memory Corp, Vega Flash Systems).
- **`supplier_features.csv`** (6 rows) — per-supplier static features for the GNN (equipment age, geopolitical exposure, region, process node, workforce size).
- **`supplier_observations_historical.csv`** (144 rows) — 24 months of past `capability_pct` per supplier (periods −23…0), the GNN's training labels.
- **`supplier_product_capacity.csv`** (360 rows) — nominal monthly USD capacity per `(supplier, product, period)`.
- **`inputs.csv`** (3 rows) and **`input_usage.csv`** (10 rows) — raw materials (helium, neon, palladium) and each SKU's exposure (`intensity`, 0–1) to them.
- **`supplier_capability_forecast.csv`** (216 rows) — a checked-in snapshot of the GNN's output, used only when `USE_PRECOMPUTED_FORECAST = True`. Both paths produce bit-identical downstream results.
- **`dependencies.csv`** (7 rows) — directed customer-customer protection edges with `declared_yield_pct` and `elevated_floor_pct`.
- **`disruption_reveal.csv`** (2 rows) — the rolling-horizon disruption schedule (Orion downtime at month 5, helium shortage at month 13).

## Model overview

The model is one shared ontology that all four reasoners read and write.

- **Key entities**: `Customer` — a chip buyer; `Product` — a memory SKU; `Period` — a monthly bucket in the horizon; `Supplier` — a foundry/fab; `Input` — a raw material; plus junction concepts `Demand` (requested USD per customer/product/period, carrying the LP decision variable), `SupplierProductCapacity` (monthly capacity per supplier/product/period), `InputUsage` (each SKU's exposure to each input), and `Dependency` (a customer-to-customer protection edge).
- **Primary identifiers**: single-column integer ids for the base entities; composite keys for the junctions (e.g. `Demand` is keyed by `(customer_id, product_id, period_id)`).
- **Important invariants**: demand and capacity are non-negative USD; `base_service_floor_pct`, `elevated_floor_pct`, `declared_yield_pct`, `intensity`, and `capability_pct` are fractions in `[0, 1]`; each customer's allocation must lie between its service floor and its yield-adjusted demand.

Alongside the base entities, Stage 1 rules-authors several derived `Customer` attributes (yield limits, elevated floors, single-point-of-failure flags), and Stages 2–4 create intermediate and output concepts — a supplier-capability forecast, per-iteration effective capacity, and per-scenario margin — that persist in the ontology for later querying. For the full concept and property definitions, see `model/schema.py`; `model/reasoning.py` holds the rules, the GNN, and the problems, and `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV inputs → load → Stage 1 rules → Stage 2 forecast → Stage 3 rolling-horizon LP → Stage 4 paths + what-if → outputs
```

**Stage 1 (Rules)** turns the `Dependency` rows into per-customer attributes the LP consumes. Declarative aggregations derive each customer's `max_declared_yield_pct` and `elevated_floor_pct`, a `Customer.depends_on` graph edge is materialized from the same rows, and a `Customer.is_dependency_spof` flag fires when exactly one incoming edge keeps a customer above its base floor. Every output is first-class ontology, so an analyst can `model.where(Customer.is_dependency_spof()).select(Customer.name).to_df()` without re-running the pipeline.

**Stage 2 (Predictive)** forecasts `capability_pct` per `(supplier, month)`. By default it trains a `task_type="regression"` GNN over a heterogeneous graph (each `SupplierObservation → Supplier`, plus `Supplier → Supplier` edges within a region) using the static supplier features, with 24 months of history as labels (20 months train, 4 validation). Each observation is identified by its own `id`, with `supplier_id` and `period_id` as properties: a deployed GNN reads node concepts identified by one field. Predictions, clipped to `[0.85, 1.0]` and rounded, land in the `SupplierCapabilityForecast` concept. Setting `USE_PRECOMPUTED_FORECAST = True` loads a checked-in snapshot of that output instead — both paths feed identical numbers downstream.

**Stage 3 (Prescriptive)** runs a margin-maximizing LP three times as a rolling horizon: a baseline solve at month 1, a re-solve at month 5 once Orion Foundry downtime is revealed, and a re-solve at month 13 once a helium shortage is revealed. Effective capacity per `(product, period)` combines supplier capability and input availability:

```text
effective_capacity = Σ_suppliers (nominal × capability_pct) × Π_inputs (1 − intensity × (1 − availability))
```

Each solve is its own named `Problem` (`memory_supply_allocation_iter_0` to `_2`), constrained by capacity, a yield-aware demand cap, and the base and elevated service floors; the model computes each iteration's effective capacity with rules and publishes each solve's status, total margin, and allocations as relationships the report reads. A per-customer plan-diff against the previous solve is the headline: hyperscalers absorb the disruption while equipment-maker customers stay pinned at their elevated floors.

**Stage 4 (Graph)** enumerates variable-length dependency chains with `model.path(Customer.depends_on.repeat(1, 3)).all().paths()` for root-cause analysis, then runs two what-if branches as rules over the same baseline forecast capacity that Stage 3 uses, so impact stays consistent with the optimization: one takes each supplier offline, the other drops each input to 30% availability, ranking the widest blast radius. The supplier-offline results live on a separate `SupplierOfflineImpact` concept rather than on `Supplier`: the GNN reads `Supplier`, and these results derive from its forecast.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the headers documented in [Sample data](#sample-data).
- Add suppliers or inputs by appending rows to `suppliers.csv` + `supplier_product_capacity.csv`, or `inputs.csv` + `input_usage.csv`; the LP picks up new entities automatically.
- Extend the dependency graph by adding rows to `dependencies.csv`. For chains longer than 3 hops, raise the `repeat(1, 3)` bound in Stage 4. Avoid cycles — `.all().paths()` returns walks, which can blow up enumeration.

### Tune parameters

- **`USE_PRECOMPUTED_FORECAST`** (`model/reasoning.py`): `True` deploys no GNN and loads the bundled forecast snapshot instead — the fastest path for iteration; skip the Train step.
- **`HORIZON_END_PERIOD`** (`model/source.py`) and `data/periods.csv`: change the horizon length (keep the two in sync).
- **`data/disruption_reveal.csv`**: edit the rolling-horizon disruption schedule. Each row is `(reveal_period, target_type, target_id, parameter_name, parameter_value, start_period, end_period, narrative)`; lower `parameter_value` to increase severity.
- **GNN knobs** (`GNN_N_EPOCHS`, `GNN_LR`, `GNN_SEED` in `model/reasoning.py`): training depth, learning rate, and reproducibility seed. The predictive reasoner's size in `raiconfig.yaml` decides the device.

### Extend the model

- **Adjust floors and yields**: edit `base_service_floor_pct` in `customers.csv` and `declared_yield_pct` / `elevated_floor_pct` in `dependencies.csv`; the Stage-1 rules pick up new values without code changes.
- **Change the objective**: swap `Product.margin_pct` in the Stage-3 objective for `unit_price_usd_per_gb * margin_pct` (or a new derived net-revenue property) to optimize revenue instead of margin.
- **Add constraints or outputs**: add a `problem.satisfy(...)` block in Stage 3 of `model/reasoning.py`, or persist a new derived property back to the ontology as Stages 1 and 4 do.

### Scale up / productionize

- **Engine sizing**: the GNN trains on the predictive reasoner named in `raiconfig.yaml` (`reasoners.predictive.size` sets its size); the LPs solve on the default `highs` solver.
- **Reproducibility**: pin `relationalai[gnn]==2.3.0`, set `GNN_SEED`, and prefer `USE_PRECOMPUTED_FORECAST = True` for deterministic reruns.
- **Scheduling**: the deployed model refreshes on its schedule in `raiconfig.yaml` (`interval_s: 0` refreshes only on deploy or on demand); each refresh forecasts with the registered version and re-solves the three problems.

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
<summary>Solver returns INFEASIBLE on a rolling-horizon iteration</summary>

The base + elevated service floors define a minimum amount of supply each customer must receive. If a disruption combination pushes the total floor obligation above effective capacity, the LP returns INFEASIBLE. Tune `data/disruption_reveal.csv` to less severe `parameter_value` settings, lower hyperscaler base floors in `customers.csv`, or lower elevated floors in `dependencies.csv`.
</details>

<details>
<summary>Warning: <code>Dependency does not have a upstream_id property declared</code></summary>

This is a known false-positive of RAI's static typo-detection check that fires during model construction when same-typed `identify_by` fields are processed. The property is correctly auto-created (confirm by checking that Photonic Lithography reaches its 95% elevated floor in the output). The warning has no effect on results.
</details>

<details>
<summary>Plan-diff shows zero delta for every equipment-maker customer</summary>

This is expected and is the headline narrative of the template. Equipment-maker customers have elevated floors of 88–95% driven by the dependency graph, so their LP allocations are pinned at the floor and disruptions land on the hyperscalers (whose base floor is 55%) instead. To see plan diffs across equipment makers too, remove rows from `dependencies.csv` or raise hyperscaler base floors above 0.85.
</details>

<details>
<summary>No multi-hop chains in the output</summary>

Multi-hop chains require dependency rows that chain together (A depends on B and B depends on C). The sample data has `Photonic → Apex` plus inbound `Hyperion → Photonic` and `Aether → Photonic`, yielding two 2-hop chains. Add rows to `dependencies.csv` to build longer chains and raise the `repeat(1, 3)` bound.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Run `rai init` to configure your connection profile. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chaining predictive, rules, prescriptive, and graph reasoning on one ontology, as this template does.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, aggregates, and `.define()` for derived properties.

### Reasoner reference

- [Predictive reasoner (GNN)](https://docs.relational.ai/) — heterogeneous-graph regression, PropertyTransformer, and edge patterns (Stage 2).
- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives (Stage 3).
- [Graph reasoner / paths](https://docs.relational.ai/) — variable-length path traversal with `.repeat(...).all().paths()` (Stage 4).

## Support

- File issues at the RelationalAI templates repository.
