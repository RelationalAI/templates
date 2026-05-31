---
title: "Memory Supply Allocation"
description: "Monthly rolling-horizon allocation of constrained memory-chip supply across customers with strategic supplier dependencies, named foundries, and raw-material inputs. Four-reasoner chain: predicted supplier capability feeds the LP, customer-customer paths surface single points of failure, and two what-if scenarios trace supplier-offline and input-shortage cascades."
featured: false
experience_level: intermediate
industry: "Semiconductors"
reasoning_types:
  - Predictive
  - Rules
  - Prescriptive
  - Graph
tags:
  - Multi-Period
  - Multi-SKU
  - Rolling-Horizon
  - Service-Level
  - LP
  - Allocation
  - Paths
  - Root-Cause-Analysis
  - Supplier-Risk
---

# Memory Supply Allocation

## What this template is for

Memory-chip manufacturers replan allocations every planning cycle as new orders, supplier disruptions, and raw-material shocks land. The hard version of the problem has four moving pieces simultaneously: demand structurally exceeds supply on advanced SKUs (HBM3E today), capacity itself is the product of multiple foundries' health, raw-material availability (helium, neon, palladium) modulates effective output, and customers sit in a strategic dependency graph where some buyers will yield part of their allocation so their own equipment suppliers stay supplied.

This template chains **Predictive**, **Rules**, **Prescriptive**, and **Graph** reasoning on one ontology to walk a planner through a monthly 36-month horizon with two disruption reveals along the way:

1. *What will supplier health look like?* — A pre-computed `SupplierCapabilityForecast` (regression target) per (supplier, month) loaded as ontology, with a clean upgrade path to a `rai-predictive-modeling` GNN for richer feature-based node classification.
2. *Who depends on whom, and how do floors lift?* — Rules-authored derived properties turn the dependency relation into a customer-customer graph plus per-customer yield and elevated-floor numbers, all queryable.
3. *What should we allocate, and what changes when disruption surfaces?* — A three-step rolling-horizon LP. Solve at month 1, reveal an Orion Foundry downtime at month 5, re-forecast and solve months 5-36, then reveal a helium shortage at month 13 and solve months 13-36. Plan-diff between iterations exposes who absorbs the disruption.
4. *Which suppliers and inputs are the cascade hotspots?* — Path traversal enumerates customer-customer chains (RCA + SPOF detection); two what-if branches ablate one supplier at a time and one input at a time, ranking the broadest blast radius.

## Who this is for

- **Intermediate users** comfortable with LP plus graph traversal concepts
- **Strategic procurement / S&OP teams** weighing supplier-risk scenarios under monthly replan cadence
- **Operations researchers** exploring multi-reasoner pipelines (predictive feeding prescriptive feeding graph) in RelationalAI
- **Supply-chain analysts** modeling raw-material exposure (helium, neon, etc.) alongside capacity-by-supplier

## What you'll build

- Load 11 customers, 5 SKUs, 36 monthly periods, 6 named suppliers (foundries/fabs), 3 raw-material inputs, and customer-customer dependencies from CSV
- Derive five **rules-authored** Customer attributes — `max_declared_yield_pct`, `elevated_floor_pct`, `n_incoming_dependencies`, `has_elevated_floor`, `is_dependency_spof` — plus the `Customer.depends_on` graph edge
- Bind a pre-computed **supplier capability forecast** as a first-class ontology Concept (one row per supplier-month), ready to be replaced by a GNN regression in production
- Compose effective capacity per (product, period) as `Σ_suppliers (nominal × capability_pct) × Π_inputs (1 − intensity × (1 − availability))` — sums and products that follow the dependency surface
- Run a 3-step **rolling-horizon LP**: baseline solve at month 1, then disruption reveals at months 5 and 13 trigger re-forecast + re-solve. Plan-diff between consecutive solves surfaces who absorbs each shock
- Enumerate customer-customer dependency chains with `model.path(Customer.depends_on.repeat(1, 3)).all_paths()` and produce a root-cause table + SPOF flag
- Two what-if scenario branches (no re-solve): supplier-offline cascade impact and input-shortage cascade impact, each surfacing affected (product, period) cells

## What's included

- **Script**: `memory_supply_allocation.py` — four-stage chain end-to-end
- **Runbook**: `runbook.md` — analyst-facing paste-testable walkthrough, one prompt per stage
- **Data**: `data/customers.csv`, `data/products.csv`, `data/periods.csv`, `data/demand.csv`, `data/suppliers.csv`, `data/supplier_features.csv`, `data/supplier_observations_historical.csv`, `data/supplier_product_capacity.csv`, `data/inputs.csv`, `data/input_usage.csv`, `data/supplier_capability_forecast.csv`, `data/dependencies.csv`, `data/disruption_reveal.csv`
- **Config**: `pyproject.toml`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

### Stage 2 (Predictive GNN) — one-time Snowflake setup

The default run trains an actual GNN regression model for Stage 2. The predictive reasoner needs an experiment database + schema with four grants, and a GPU-sized predictive reasoner provisioned. Run once as `ACCOUNTADMIN`:

```sql
CREATE DATABASE IF NOT EXISTS MEMORY_SUPPLY;
CREATE SCHEMA   IF NOT EXISTS MEMORY_SUPPLY.EXPERIMENTS;

GRANT USAGE             ON DATABASE MEMORY_SUPPLY            TO APPLICATION RELATIONALAI;
GRANT USAGE             ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL      ON SCHEMA   MEMORY_SUPPLY.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

Then provision a GPU-sized predictive reasoner (`GPU_NV_S`) and reference it in `raiconfig.yaml` under `reasoners.predictive`. The script's `EXP_DATABASE` and `EXP_SCHEMA` constants default to `MEMORY_SUPPLY` / `EXPERIMENTS`; change them if you used different names.

If you don't need to demonstrate the GNN training step (e.g. for fast iteration or offline reproducibility), set `USE_PRECOMPUTED_FORECAST = True` at the top of the script — it skips training entirely and loads `data/supplier_capability_forecast.csv` directly. The Stage-3 LP and Stage-4 paths analysis run identically either way.

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/memory_supply_allocation.zip
   unzip memory_supply_allocation.zip
   cd memory_supply_allocation
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
   python memory_supply_allocation.py
   ```

6. Expected output (abbreviated):
   ```text
   ============================================================
   Stage 2: Predictive forecast loaded
   ============================================================
                 mean    min    max               supplier
   supplier_id
   1            0.965  0.926  0.984          Orion Foundry
   2            0.952  0.910  0.985         Helios Foundry
   ...

   ============================================================
   Stage 3 iteration 0: Baseline (month 1, no disruption revealed)
   ============================================================
     Status: OPTIMAL
     Total margin over horizon (months 1-36): $45,488,032,436.79

     === Per-customer service level (over current horizon) ===
                       name          industry  demand_$B  alloc_$B  service_%
           Hyperion Compute       Hyperscaler      74.25     56.45      76.00
               Aether Cloud       Hyperscaler      33.75     28.24      83.70
       Photonic Lithography Foundry Equipment       0.24      0.22      95.00
   Apex Photonic Components  Precision Optics       0.07      0.07      97.50
       (... 7 more rows ...)

   ============================================================
   Stage 3 iteration 1: Re-plan at month 5 (Orion downtime revealed)
   ============================================================
     Status: OPTIMAL
     Total margin over horizon (months 5-36): $40,523,678,803.86

     === Plan diff vs prior iteration (months 5-36) ===
                       name  delta_$M
               Aether Cloud   -369.62
           Hyperion Compute   -280.36
     Beacon Memory Holdings    -27.10
             Helios AI Labs    -11.94
       Photonic Lithography      0.00      <- protected by elevated floor
        Vertex Test Systems      0.00
        Crystal Wafer Tools      0.00
   Apex Photonic Components      0.00
       (... rest unchanged ...)

   ============================================================
   Stage 3 iteration 2: Re-plan at month 13 (helium shortage revealed)
   ============================================================
     Status: OPTIMAL
     Total margin over horizon (months 13-36): $28,972,506,958.58

     === Plan diff vs prior iteration (months 13-36) ===
                       name   delta_$M
           Hyperion Compute  -2,149.37
               Aether Cloud  -1,839.17
             Helios AI Labs    -553.37
     Beacon Memory Holdings    -367.45
       Photonic Lithography       0.00   <- still protected

   ============================================================
   Rolling-horizon summary
   ============================================================
     iter=0 months=1-36:  OPTIMAL  margin=$45,488,032,436.79
     iter=1 months=5-36:  OPTIMAL  margin=$40,523,678,803.86
     iter=2 months=13-36: OPTIMAL  margin=$28,972,506,958.58

   ============================================================
   Stage 4: Dependency-chain analysis (PATHS), RCA, and what-if
   ============================================================
     Total customer-customer dependency paths (1-3 hops): 9
     === Dependency chains ===
         1 Hyperion Compute -> Photonic Lithography
         1 Photonic Lithography -> Apex Photonic Components
         2 Aether Cloud -> Photonic Lithography -> Apex Photonic Components
         2 Hyperion Compute -> Photonic Lithography -> Apex Photonic Components
     (... and 5 single-hop chains ...)

     === Customers flagged as dependency SPOFs (ontology query) ===
                spof_customer
     Apex Photonic Components

     === Supplier-offline impact (each supplier in isolation) ===
                 supplier  n_affected_cells  max_cap_drop_%       affected_products
            Orion Foundry                72           60.90             HBM3E, HBM3
     Pelican Memory Works                72           70.90      DDR5-6400, LPDDR5X
            Nimbus Foundry                72           70.50         HBM3, DDR5-6400
      Stellar Memory Corp                72           50.90 LPDDR5X, NAND-TLC-512Gb
       Vega Flash Systems                36           50.90          NAND-TLC-512Gb
           Helios Foundry                36           40.60                   HBM3E

     === Input-shortage impact (each input at 30% availability) ===
         input  n_affected_cells                                       affected_products_avg_drop
        Helium               180 HBM3E=35%, HBM3=28%, DDR5-6400=18%, LPDDR5X=10%, NAND-TLC-512Gb=7%
          Neon               108                                 HBM3E=32%, HBM3=24%, DDR5-6400=14%
     Palladium                72                                                HBM3E=28%, HBM3=14%

   ============================================================
   Headline
   ============================================================
     Customer-graph SPOF(s): Apex Photonic Components
     Multi-hop dependency chains:
       Aether Cloud -> Photonic Lithography -> Apex Photonic Components
       Hyperion Compute -> Photonic Lithography -> Apex Photonic Components
     Supplier with widest offline impact: Orion Foundry (72 affected cells, max cap drop 60.0%)
     Input with widest shortage impact: Helium (180 affected cells)
     Margin erosion across rolling horizon (iter 0 -> iter 2): $16,515,525,478.20
   ```

   Headline read: as disruption surfaces, hyperscalers absorb all of the pain while equipment-maker customers stay pinned at their elevated floors (95%, 92%, 88%) — exactly the strategic dynamic the dependency declarations were designed to enforce. PATHS analysis surfaces Apex Photonic Components as a structural single point of failure: its 90% floor is sustained by exactly one upstream signal (Photonic Lithography). Orion Foundry is the supplier whose offline scenario casts the widest shadow; Helium is the input whose shortage touches every SKU. Numbers shown are from a GNN-default run; switching to `USE_PRECOMPUTED_FORECAST=True` produces slightly higher margins (~$47.1B / $42.0B / $30.2B) because the GNN's feature-driven predictions land slightly below the synthetic forecast values.

## Template structure

```text
.
├── README.md
├── runbook.md
├── pyproject.toml
├── memory_supply_allocation.py
└── data/
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

## How it works

### Stage 1: rules-authored derived properties

Two declarative aggregations turn `Dependency` into per-customer attributes the LP consumes. Both default to `0.0` so customers outside the dependency graph fall through cleanly:

```python
max_yield_expr = (
    aggregates.max(Dependency.declared_yield_pct)
    .per(Customer)
    .where(Dependency.downstream_id == Customer.id)
    | 0.0
)
model.define(Customer.max_declared_yield_pct(max_yield_expr))

elevated_expr = (
    aggregates.max(Dependency.elevated_floor_pct)
    .per(Customer)
    .where(Dependency.upstream_id == Customer.id)
    | 0.0
)
model.define(Customer.elevated_floor_pct(elevated_expr))
```

A `Customer.depends_on` graph relationship is materialized from the same rows, and a `Customer.is_dependency_spof` boolean flag fires when exactly one incoming dependency is the only thing keeping a customer above its base floor. All Stage-1 outputs are first-class ontology — a downstream analyst can `model.where(Customer.is_dependency_spof()).select(Customer.name).to_df()` and get the answer without re-running the pipeline.

### Stage 2: predictive supplier-capability GNN

The forecast is a regression target per (supplier, month). The default code path trains an actual GNN — a `task_type="regression"` model over a heterogeneous graph (`SupplierObservation → Supplier` for each observation; `Supplier → Supplier` for same-region clustering) using per-supplier static features (equipment_age_months, geopolitical_exposure_score, region, process_node_nm, workforce_size_k). Training labels come from 24 months of past observations in `supplier_observations_historical.csv`; predictions are generated for periods 1–36:

```python
gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    device=GNN_DEVICE,
    n_epochs=GNN_N_EPOCHS,
    lr=GNN_LR,
)
gnn.fit()
SupplierObservation.predictions = gnn.predictions(domain=Test)
```

Predictions are extracted via the standard `Source.predictions.predicted_value` pattern and bound into the `SupplierCapabilityForecast` concept — the same downstream ontology surface either code path produces. Training takes ~60-90 seconds on a GPU-sized predictive reasoner (`GPU_NV_S`).

The pre-computed forecast path (`USE_PRECOMPUTED_FORECAST = True`) skips the GNN entirely and loads `data/supplier_capability_forecast.csv` directly. Use it when iterating on Stage 3 / Stage 4 or running in environments without the experiment-schema setup.

### Stage 3: rolling-horizon prescriptive LP

The LP runs three times. Between solves, a disruption-reveal data table is consulted; any rows whose `reveal_period` has been reached overwrite the working forecast or input-availability state, and effective capacity is recomputed from scratch:

```python
def compute_effective_capacity(forecast_df_state, input_avail_state):
    """Compute effective capacity per (product, period) given current forecast
    and input availability state. Returns a DataFrame with columns
    product_id, period_id, effective_capacity_usd."""
    sp = spc_df.merge(forecast_df_state, on=["supplier_id", "period_id"])
    sp["eff_supply_usd"] = sp["nominal_capacity_usd"] * sp["capability_pct"]
    per_prod_period = (
        sp.groupby(["product_id", "period_id"])["eff_supply_usd"].sum().reset_index()
    )

    # Multiply by input-availability factor per product:
    #   product_multiplier = product over inputs of (1 - intensity * (1 - avail))
    iu = input_usage_df.copy()
    iu["avail"] = iu["input_id"].map(input_avail_state).fillna(1.0)
    iu["mult"] = 1.0 - iu["intensity"] * (1.0 - iu["avail"])
    per_prod_mult = iu.groupby("product_id")["mult"].prod()

    per_prod_period["mult"] = per_prod_period["product_id"].map(per_prod_mult).fillna(1.0)
    per_prod_period["effective_capacity_usd"] = (
        per_prod_period["eff_supply_usd"] * per_prod_period["mult"]
    )
    return per_prod_period[["product_id", "period_id", "effective_capacity_usd"]]
```

The result loads into an `EffectiveCapacity` concept tagged with the rolling-horizon `iter_id` discriminator, so the LP at iteration K references only its own rows:

```python
problem.satisfy(
    model.where(EffectiveCapacity.iter_id == iter_id).require(
        sum(Demand.x_alloc).per(EffectiveCapacity).where(
            Demand.product_id == EffectiveCapacity.product_id,
            Demand.period_id == EffectiveCapacity.period_id,
        )
        <= EffectiveCapacity.effective_capacity_usd
    ),
    name=["cap", EffectiveCapacity.iter_id, EffectiveCapacity.product_id, EffectiveCapacity.period_id],
)
```

The decision variable is scoped to the current iteration's horizon via `where=[Demand.period_id >= horizon_start]` so the LP only resolves the unsolved tail of the horizon. After each solve, the script extracts the allocation and computes a per-customer plan-diff vs the prior iteration's allocation — the table that exposes who absorbs the disruption.

### Stage 4: dependency-chain enumeration and what-if scenarios

The paths library handles variable-length traversal of the customer dependency graph. The README example output shows two 2-hop chains both passing through Photonic Lithography to reach Apex Photonic Components — these are the structural reason Apex has no alternative protection. Path enumeration runs once and is independent of the LP solves:

```python
p_pattern = model.path(Customer.depends_on.repeat(1, 3))
paths_df = model.where(
    p := p_pattern.all_paths(),
).select(
    p.alias("path_id"),
    p.length.alias("hops"),
    p.nodes["index"].alias("step"),
    Customer(p.nodes).name.alias("customer"),
).to_df()
```

The two what-if branches use the same `compute_effective_capacity` helper as Stage 3, so the impact analyses stay consistent with the LP's capacity model. **Supplier-offline** zeroes one supplier's `capability_pct` and counts (product, period) cells where capacity drops more than 10%. **Input-shortage** drops one input to 30% availability and reports per-product average capacity drop weighted by intensity.

## Customize this template

- **Change the rolling-horizon disruption schedule**: edit `data/disruption_reveal.csv`. Each row is `(reveal_period, target_type, target_id, parameter_name, parameter_value, start_period, end_period, narrative)`. `target_type` is `supplier` or `input`. Increase severity by lowering `parameter_value`; widen the window by adjusting `start_period`/`end_period`. The script automatically picks them up.
- **Swap pre-computed forecast for a GNN**: replace the load of `supplier_capability_forecast.csv` with a call to `rai-predictive-modeling` and a prediction-extraction step. The `SupplierCapabilityForecast` concept binding stays the same.
- **Add more suppliers or inputs**: append rows to `suppliers.csv` + `supplier_product_capacity.csv`, or `inputs.csv` + `input_usage.csv`. Re-run; the LP picks up the new entities automatically.
- **Adjust base floors and yields**: edit `customers.csv` `base_service_floor_pct` and `dependencies.csv` `declared_yield_pct` / `elevated_floor_pct`. The Stage-1 rules pick up new values without code changes.
- **Extend the dependency graph for longer chains**: add rows to `dependencies.csv`. If you build chains of length > 3, increase `repeat(1, 3)` in Stage 4 accordingly. Avoid cycles — `.all_paths()` returns walks (cycles allowed), which can blow up enumeration.
- **Change the horizon**: edit `data/periods.csv` (rows) and `HORIZON_END_PERIOD` (constant). Update `disruption_reveal.csv` reveal periods accordingly.
- **Use net revenue instead of margin**: replace `Product.margin_pct` in the objective with `Product.unit_price_usd_per_gb * Product.margin_pct` (or a new derived `Product.net_revenue_pct`).

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

The base + elevated service floors define a minimum amount of supply each customer must receive. If a disruption combination pushes the total floor obligation above effective capacity, the LP returns INFEASIBLE. Tune `data/disruption_reveal.csv` to less severe `parameter_value` settings, lower hyperscaler base floors in `customers.csv`, or lower elevated floors in `dependencies.csv`. The script prints a pre-solve feasibility ratio in the disruption_reveal preview when you regenerate data.
</details>

<details>
<summary>Warning: <code>Dependency does not have a upstream_id property declared</code></summary>

This is a known false-positive of RAI's static typo-detection check that fires during model construction when same-typed identify_by fields are processed. The property is correctly auto-created (you can confirm by inspecting that Photonic Lithography reaches its elevated floor of 95% in the output). The warning has no effect on results.
</details>

<details>
<summary><code>TypeError: '&gt;' not supported between instances of 'Int128Array' and 'int'</code></summary>

`PathTraversal.length` returns an `Int128Array` column. Cast it with `.astype(int)` before comparing or filtering in pandas. The template already does this for the `hops` and `step` columns — if you add more columns from path query results, cast them too.
</details>

<details>
<summary>Plan-diff shows zero delta for every equipment-maker customer</summary>

This is expected and is the headline narrative of the template. Equipment-maker customers (Photonic Lithography, Vertex Test Systems, Crystal Wafer Tools, Apex Photonic Components) have elevated floors of 88-95% driven by the dependency graph. Their LP allocations are pinned at the floor, so disruptions land on the hyperscalers (whose base floor is 55%) instead. To see plan diffs across equipment makers too, either remove rows from `dependencies.csv` or raise hyperscaler base floors above 0.85.
</details>

<details>
<summary>No multi-hop chains in the output</summary>

Multi-hop chains require dependency rows that chain together (e.g., A depends on B and B depends on C). The sample data has `Photonic -> Apex` plus the inbound `Hyperion -> Photonic` and `Aether -> Photonic`, which yields two 2-hop chains. Add rows to `dependencies.csv` to build longer chains and bump `repeat(1, 3)` to a higher bound.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Run `rai init` to configure your connection profile. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>
