---
title: "Demand Planning Temporal"
description: "Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Multi-Period
  - Temporal-Filtering
  - Inventory
  - LP
---

# Demand Planning Temporal

## What this template is for

Manufacturing and distribution companies must decide how much to produce at each site every week to satisfy customer demand while keeping production and inventory holding costs low. When demand spans many months but the planning team only wants to optimize over a specific window, temporal filtering becomes essential: scope the data to a planning horizon before building the optimization model.

This template solves a multi-period production and inventory planning problem across three warehouse sites and three product SKUs. It demonstrates how to filter demand orders by date range, map dates to integer week periods, and enforce inventory flow conservation constraints so that ending inventory each week equals beginning inventory plus production minus demand.

Prescriptive reasoning makes this practical because the solver simultaneously balances production costs, holding costs, and service-level requirements across all sites, SKUs, and weeks, finding the cost-minimizing plan that a manual planner could not feasibly compute.

## Who this is for

- **Intermediate users** comfortable with linear programming concepts like decision variables, constraints, and objectives
- **Supply chain analysts** building production or inventory planning models
- **Data scientists** who need to scope optimization to a configurable date window
- **Operations researchers** looking for a multi-period flow-conservation pattern in RelationalAI

## What you'll build

- Load sites, SKUs, demand orders, production capacity, and initial inventory from CSV files
- Filter demand orders to a configurable planning horizon using date comparisons
- Map due dates to integer week numbers for use with `std.common.range()`
- Define continuous decision variables for production quantities, inventory levels, and unmet demand
- Enforce inventory flow conservation: `inv[t] = inv[t-1] + production[t] - demand[t]`
- Set a 95% minimum service level constraint on total demand fulfillment
- Minimize total cost (production + holding + unmet-demand penalty) using `model.union()` to combine per-entity costs
- Solve with HiGHS and inspect the production plan, inventory levels, and unmet demand

## What's included

- **Script**: `demand_planning_temporal.py` -- end-to-end model, solve, and results
- **Data**: `data/sites.csv`, `data/skus.csv`, `data/demand_orders.csv`, `data/production_capacity.csv`, `data/initial_inventory.csv`
- **Config**: `pyproject.toml`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

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

6. Expected output:
   ```text
   Status: OPTIMAL
   Total cost: $134,250.75
   Planning horizon: 2025-11-01 to 2026-02-28 (18 weeks)
   Demand orders in scope: 18 (of 25 total)

   === Production Plan (non-zero weeks) ===
     name                  value
     prod_1_1_1           400.0
     prod_1_2_2           350.0
     ...

   === Inventory Levels (selected weeks) ===
     name                  value
     inv_1_1_0           2000.0
     inv_1_2_0           1500.0
     ...

   === Unmet Demand ===
   All demand fulfilled!
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── demand_planning_temporal.py
└── data/
    ├── sites.csv
    ├── skus.csv
    ├── demand_orders.csv
    ├── production_capacity.csv
    └── initial_inventory.csv
```

## How it works

### 1. Date filtering -- scope demand to the planning horizon

The demand orders CSV spans October 2025 through March 2026 (25 orders). The script filters to only the planning window before loading data into the model:

```python
planning_start = "2025-11-01"
planning_end = "2026-02-28"

orders_df["due_date"] = pd.to_datetime(orders_df["due_date"])
filtered_orders = orders_df[
    (orders_df["due_date"] >= planning_start) &
    (orders_df["due_date"] <= planning_end)
].copy()
```

This removes orders outside the horizon so the solver only sees relevant demand.

### 2. Date-to-period mapping -- convert dates to integer weeks

`std.common.range()` requires integer periods. The script converts each order's due date into a week number relative to the planning start:

```python
start_date = datetime.strptime(planning_start, "%Y-%m-%d")
end_date = datetime.strptime(planning_end, "%Y-%m-%d")
num_weeks = int((end_date - start_date).days / 7) + 1

filtered_orders["week_num"] = (
    (filtered_orders["due_date"] - pd.Timestamp(planning_start)).dt.days // 7 + 1
).astype(int)
```

Week 1 is the first week of the horizon; week 18 is the last.

### 3. Multi-arity decision variables indexed by time

Production and inventory variables are indexed by both concept (site x SKU) and time period. The `x_production` variable uses a multi-arity property pattern:

```python
ProdCapacity.x_production = Property(
    f"{ProdCapacity} in week {{t:int}} produces {{production:float}}"
)
x_prod = Float.ref()
s.solve_for(
    ProdCapacity.x_production(t, x_prod),
    type="cont",
    lower=0,
    upper=ProdCapacity.max_production_per_week,
    name=["prod", ProdCapacity.site_id, ProdCapacity.sku_id, t],
    where=[t == weeks]
)
```

This creates one continuous variable per (site, SKU, week) combination.

### 4. Flow conservation constraint

The core multi-period pattern ties adjacent weeks together. Inventory at the end of week `t` must equal inventory at the end of week `t-1` plus production in week `t` minus demand in week `t`:

```python
s.satisfy(model.where(
    ProdCapacity.x_inventory(t, x_inv_curr),
    ProdCapacity.x_inventory(t - 1, x_inv_prev),
    ProdCapacity.x_production(t, x_prod),
    WeeklyDemand.wk_site_id == ProdCapacity.site_id,
    WeeklyDemand.wk_sku_id == ProdCapacity.sku_id,
    WeeklyDemand.wk_week_num == t,
    t >= 1,
).require(
    x_inv_curr == x_inv_prev + x_prod - WeeklyDemand.wk_quantity
))
```

A `WeeklyDemand` concept pre-aggregates orders into weekly buckets (including zero-demand weeks) so the constraint covers every period.

### 5. Cost objective with model.union()

The objective combines three cost components from different concepts using `model.union()`:

```python
prod_cost = ProdCapacity.production_cost * sum(x_prod).per(ProdCapacity).where(...)
hold_cost = ProdCapacity.holding_cost_per_week * sum(x_inv).per(ProdCapacity).where(...)
unmet_cost = unmet_penalty * DemandOrder.x_unmet

s.minimize(sum(model.union(prod_cost, hold_cost, unmet_cost)))
```

### Epoch timestamp alternative

The script includes commented-out examples of Pattern B (epoch integer timestamps). If your data uses Unix epoch seconds instead of date strings, convert the planning horizon to epochs and filter identically:

```python
start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp()) + 86399
filtered_orders = orders_df[
    (orders_df["created_at"] >= start_epoch) &
    (orders_df["created_at"] <= end_epoch)
].copy()
```

## Customize this template

- **Change the planning horizon**: Edit `planning_start` and `planning_end` to shift the optimization window. The week count and date filter update automatically.
- **Add more sites or SKUs**: Append rows to `sites.csv`, `skus.csv`, `production_capacity.csv`, and `initial_inventory.csv`. The model generalizes to any number of site-SKU combinations.
- **Adjust service level**: Change `min_service_level` (default 0.95) to require higher or lower demand fulfillment.
- **Add safety stock constraints**: Use the `safety_stock_weeks` parameter to require minimum inventory levels at each period.
- **Switch to epoch timestamps**: Follow the commented Pattern B code to adapt the template for data with Unix epoch integer columns.

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

The 95% service level constraint may be too strict for your data. Try lowering `min_service_level` to 0.90, or check that production capacities in `production_capacity.csv` are large enough to cover weekly demand. Also verify that `initial_inventory.csv` has entries for every site-SKU pair.
</details>

<details>
<summary>No demand orders in scope after filtering</summary>

Verify that `planning_start` and `planning_end` overlap with the `due_date` values in `demand_orders.csv`. The default data covers October 2025 through March 2026; the default horizon is November 2025 through February 2026.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Run `rai init` to configure your connection profile. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>
