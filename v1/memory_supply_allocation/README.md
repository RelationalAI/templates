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

- **Model**: `memory_supply_allocation.py` — the four-reasoner chain end-to-end on one ontology
- **Runner**: a single Python script (`python memory_supply_allocation.py`)
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills, one prompt per stage; as important a reference as the script itself.
- **Sample data**: 13 CSVs under `data/` (customers, products, periods, demand, suppliers, capacity, inputs, dependencies, and the disruption schedule)
- **Outputs**: per-iteration LP status and margin, plan-diffs, service levels, dependency chains, and what-if rankings — all printed and persisted back to the ontology for later querying

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed
- A Snowflake user with permissions to access the RAI Native App

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai[gnn]==1.11.0`)

### One-time Snowflake setup (predictive GNN)

The default run trains an actual GNN regression model in Stage 2. The predictive reasoner needs an experiment database and schema with four grants, plus a GPU-sized predictive reasoner. Run once as `ACCOUNTADMIN`:

```sql
CREATE DATABASE IF NOT EXISTS MEMORY_SUPPLY;
CREATE SCHEMA   IF NOT EXISTS MEMORY_SUPPLY.EXPERIMENTS;

GRANT USAGE             ON DATABASE MEMORY_SUPPLY             TO APPLICATION RELATIONALAI;
GRANT USAGE             ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL      ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

Then provision a GPU-sized predictive reasoner (`GPU_NV_S`) and reference it in `raiconfig.yaml` under `reasoners.predictive`. To skip GNN training entirely (fast iteration / offline reproducibility), set `USE_PRECOMPUTED_FORECAST = True` at the top of the script — see [Tune parameters](#tune-parameters).

## Quickstart

1. **Download the template**

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/memory_supply_allocation.zip
   unzip memory_supply_allocation.zip
   cd memory_supply_allocation
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure credentials**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python memory_supply_allocation.py
   ```

6. **Expected output**

   The run ends with a rolling-horizon summary like this — three optimal solves with margin eroding as each disruption is revealed:

   ```text
   Rolling-horizon summary
     iter=0 months=1-36:  OPTIMAL  margin=$45,488,032,436.79
     iter=1 months=5-36:  OPTIMAL  margin=$40,523,678,803.86
     iter=2 months=13-36: OPTIMAL  margin=$28,972,506,958.58
   ```

## Template structure

```text
.
├── README.md
├── runbook.md
├── pyproject.toml
├── memory_supply_allocation.py   # main runner / entrypoint
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

**Start here**: run `python memory_supply_allocation.py` for all four reasoners end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

Alongside the base entities, Stage 1 rules-authors several derived `Customer` attributes (yield limits, elevated floors, single-point-of-failure flags), and Stages 2–4 create intermediate and output concepts — a supplier-capability forecast, per-iteration effective capacity, and per-scenario margin — that persist in the ontology for later querying. For the full concept and property definitions, see `memory_supply_allocation.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV inputs → load → Stage 1 rules → Stage 2 forecast → Stage 3 rolling-horizon LP → Stage 4 paths + what-if → outputs
```

**Stage 1 (Rules)** turns the `Dependency` rows into per-customer attributes the LP consumes. Declarative aggregations derive each customer's `max_declared_yield_pct` and `elevated_floor_pct`, a `Customer.depends_on` graph edge is materialized from the same rows, and a `Customer.is_dependency_spof` flag fires when exactly one incoming edge keeps a customer above its base floor. Every output is first-class ontology, so an analyst can `model.where(Customer.is_dependency_spof()).select(Customer.name).to_df()` without re-running the pipeline.

**Stage 2 (Predictive)** forecasts `capability_pct` per `(supplier, month)`. By default it trains a `task_type="regression"` GNN over a heterogeneous graph (each `SupplierObservation → Supplier`, plus `Supplier → Supplier` edges within a region) using the static supplier features, with 24 months of history as labels (20 months train, 4 validation). Predictions land in the `SupplierCapabilityForecast` concept. Setting `USE_PRECOMPUTED_FORECAST = True` loads a checked-in snapshot of that output instead — both paths feed identical numbers downstream.

**Stage 3 (Prescriptive)** runs a margin-maximizing LP three times as a rolling horizon: a baseline solve at month 1, a re-solve at month 5 once Orion Foundry downtime is revealed, and a re-solve at month 13 once a helium shortage is revealed. Effective capacity per `(product, period)` combines supplier capability and input availability:

```text
effective_capacity = Σ_suppliers (nominal × capability_pct) × Π_inputs (1 − intensity × (1 − availability))
```

Each solve is constrained by capacity, a yield-aware demand cap, and the base and elevated service floors. A per-customer plan-diff against the previous solve is the headline: hyperscalers absorb the disruption while equipment-maker customers stay pinned at their elevated floors.

**Stage 4 (Graph)** enumerates variable-length dependency chains with `model.path(Customer.depends_on.repeat(1, 3)).all_paths()` for root-cause analysis, then runs two what-if branches that reuse Stage 3's capacity helper so impact stays consistent with the optimization: one takes each supplier offline, the other drops each input to 30% availability, ranking the widest blast radius.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the headers documented in [Sample data](#sample-data).
- Add suppliers or inputs by appending rows to `suppliers.csv` + `supplier_product_capacity.csv`, or `inputs.csv` + `input_usage.csv`; the LP picks up new entities automatically.
- Extend the dependency graph by adding rows to `dependencies.csv`. For chains longer than 3 hops, raise the `repeat(1, 3)` bound in Stage 4. Avoid cycles — `.all_paths()` returns walks, which can blow up enumeration.

### Tune parameters

- **`USE_PRECOMPUTED_FORECAST`** (top of script): `True` skips GNN training and loads the bundled forecast snapshot — fastest path for iteration or offline runs.
- **`HORIZON_END_PERIOD`** and `data/periods.csv`: change the horizon length (keep the two in sync).
- **`data/disruption_reveal.csv`**: edit the rolling-horizon disruption schedule. Each row is `(reveal_period, target_type, target_id, parameter_name, parameter_value, start_period, end_period, narrative)`; lower `parameter_value` to increase severity.
- **GNN knobs** (`GNN_N_EPOCHS`, `GNN_LR`, `GNN_SEED`, `GNN_DEVICE`): training depth, learning rate, reproducibility seed, and `cpu`/`cuda`.

### Extend the model

- **Adjust floors and yields**: edit `base_service_floor_pct` in `customers.csv` and `declared_yield_pct` / `elevated_floor_pct` in `dependencies.csv`; the Stage-1 rules pick up new values without code changes.
- **Change the objective**: swap `Product.margin_pct` in the Stage-3 objective for `unit_price_usd_per_gb * margin_pct` (or a new derived net-revenue property) to optimize revenue instead of margin.
- **Add constraints or outputs**: add a `problem.satisfy(...)` block in Stage 3, or persist a new derived property back to the ontology as Stages 1 and 4 do.

### Scale up / productionize

- **Engine sizing**: the GNN path needs a GPU-sized predictive reasoner (`GPU_NV_S`); the LP solves on the default `highs` solver.
- **Reproducibility**: pin `relationalai[gnn]==1.11.0`, set `GNN_SEED`, and prefer `USE_PRECOMPUTED_FORECAST = True` for deterministic, offline reruns.
- **Scheduling**: the script is a single entrypoint, so it drops into any scheduler or pipeline that can run `python memory_supply_allocation.py`.

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
<summary><code>TypeError: '&gt;' not supported between instances of 'Int128Array' and 'int'</code></summary>

`PathTraversal.length` returns an `Int128Array` column. Cast it with `.astype(int)` before comparing or filtering in pandas. The template already does this for the `hops` and `step` columns — if you add more columns from path query results, cast them too.
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
- [Graph reasoner / paths](https://docs.relational.ai/) — variable-length path traversal with `.repeat(...).all_paths()` (Stage 4).

## Support

- File issues at the RelationalAI templates repository.
