---
title: "Memory Supply Allocation"
description: "Monthly rolling-horizon allocation of constrained memory-chip supply across customers with strategic supplier dependencies, named foundries, and raw-material inputs. Four-reasoner chain: predicted supplier capability feeds the optimization, customer-customer paths surface single points of failure, and two what-if scenarios trace supplier-offline and input-shortage cascades."
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
- **Runner**: a single Python script (`python memory_supply_allocation.py`); `runbook.md` gives an analyst-facing, paste-testable walkthrough with one prompt per stage
- **Sample data**: 13 CSVs under `data/` (customers, products, periods, demand, suppliers, capacity, inputs, dependencies, and the disruption schedule)
- **Outputs**: per-iteration LP status and margin, plan-diffs, service levels, dependency chains, and what-if rankings — all printed and persisted back to the ontology for later querying

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed
- A Snowflake user with permissions to access the RAI Native App

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai[gnn]==1.5.0`)

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

**Start here**: `python memory_supply_allocation.py` runs all four reasoners end-to-end.

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

- **Key entities**: `Customer`, `Product`, `Period`, `Supplier`, `Input`, and the junction concepts `Demand`, `SupplierProductCapacity`, `InputUsage`, and `Dependency`.
- **Primary identifiers**: single-column integer ids for the base entities; composite keys for the junctions (e.g. `Demand` is keyed by `(customer_id, product_id, period_id)`).
- **Important invariants**: demand and capacity are non-negative USD; `base_service_floor_pct`, `elevated_floor_pct`, `declared_yield_pct`, `intensity`, and `capability_pct` are fractions in `[0, 1]`; each customer's allocation must lie between its service floor and its yield-adjusted demand.

### Concepts

**`Customer`** — a chip buyer. The first four properties are loaded from CSV; the rest are **rules-authored** in Stage 1 and queryable after the run.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/customers.csv` |
| `name` | string | No | Human-readable name |
| `industry` | string | No | Buyer segment (e.g. Hyperscaler, Foundry Equipment, Precision Optics) |
| `base_service_floor_pct` | float | No | Minimum share of demand the customer must receive |
| `max_declared_yield_pct` | float | No | Derived: max share this customer will yield to upstream |
| `elevated_floor_pct` | float | No | Derived: lifted floor from incoming dependencies |
| `n_incoming_dependencies` | int | No | Derived: count of protecting edges |
| `has_elevated_floor` | bool | No | Derived: effective floor exceeds base |
| `is_dependency_spof` | bool | No | Derived: single protecting edge → single point of failure |

**`Product`** — a memory SKU.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/products.csv` |
| `name` | string | No | e.g. `HBM3E` |
| `family` | string | No | Product family (HBM / DDR / LPDDR / NAND) |
| `unit_price_usd_per_gb` | float | No | List price |
| `margin_pct` | float | No | Objective weight in the LP |

**`Period`** — a monthly bucket in the horizon.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/periods.csv` |
| `month_num` | int | No | 1…36 |
| `label` | string | No | e.g. `2026-01` |

**`Supplier`** — a foundry/fab. Base properties load from `suppliers.csv`; static features load from `supplier_features.csv`; the last two are what-if outputs persisted in Stage 4.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/suppliers.csv` |
| `name` | string | No | e.g. `Orion Foundry` |
| `type` | string | No | Foundry / Memory Fab / NAND Fab |
| `equipment_age_months` | int | No | GNN feature |
| `geopolitical_exposure_score` | float | No | GNN feature |
| `region` | string | No | GNN feature (categorical) |
| `process_node_nm` | int | No | GNN feature |
| `workforce_size_k` | int | No | GNN feature |
| `offline_impact_cells` | int | No | What-if output: cells affected if offline |
| `offline_max_cap_drop_pct` | float | No | What-if output: max capacity drop |

**`Demand`** — requested USD per customer/product/period; also carries the LP decision variable.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `customer_id` | int | Yes | Loaded from `data/demand.csv` |
| `product_id` | int | Yes | Loaded from `data/demand.csv` |
| `period_id` | int | Yes | Loaded from `data/demand.csv` |
| `demand_usd` | float | No | Requested USD |
| `x_alloc` | float | No | Decision variable: allocated USD |

**`SupplierProductCapacity`** — nominal monthly capacity per supplier/product/period.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `supplier_id` | int | Yes | Loaded from `data/supplier_product_capacity.csv` |
| `product_id` | int | Yes | Loaded from `data/supplier_product_capacity.csv` |
| `period_id` | int | Yes | Loaded from `data/supplier_product_capacity.csv` |
| `nominal_capacity_usd` | float | No | Capacity before capability/input scaling |

**`Input`** — a raw material. `shortage_impact_cells` is a Stage-4 what-if output.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | int | Yes | Loaded from `data/inputs.csv` |
| `name` | string | No | Helium / Neon / Palladium |
| `description` | string | No | What the material is used for |
| `shortage_impact_cells` | int | No | What-if output: cells affected by a shortage |

**`InputUsage`** — how exposed each SKU is to each input.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `product_id` | int | Yes | Loaded from `data/input_usage.csv` |
| `input_id` | int | Yes | Loaded from `data/input_usage.csv` |
| `intensity` | float | No | Exposure fraction (0 = none, 1 = full) |

**`Dependency`** — a directed customer-customer protection edge that Stage 1 turns into derived floors and the `Customer.depends_on` graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `downstream_id` | int | Yes | Customer that yields (loaded from `data/dependencies.csv`) |
| `upstream_id` | int | Yes | Customer that is protected |
| `declared_yield_pct` | float | No | Share the downstream customer will give up |
| `elevated_floor_pct` | float | No | Floor the upstream customer is lifted to |

### Relationships

| Relationship | Schema | Notes |
|---|---|---|
| `Customer.depends_on(downstream, upstream)` | `Customer`, `Customer` | Materialized from `Dependency`; traversed in Stage 4 with the paths library |

Stages 2–4 also create intermediate/output concepts — `SupplierCapabilityForecast` `(supplier_id, period_id) → capability_pct`, `EffectiveCapacity` `(iter_id, product_id, period_id) → effective_capacity_usd`, and `ScenarioOutcome` `(iter_id) → total_margin_usd` — all of which persist in the ontology for later querying.

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
- **Reproducibility**: pin `relationalai[gnn]==1.5.0`, set `GNN_SEED`, and prefer `USE_PRECOMPUTED_FORECAST = True` for deterministic, offline reruns.
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
</content>
</invoke>
