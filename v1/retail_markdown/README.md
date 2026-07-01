---
title: "Retail Markdown"
description: "Set discount levels across weeks to maximize revenue while clearing inventory."
featured: false
experience_level: intermediate
industry: "Retail & Consumer"
reasoning_types:
  - Prescriptive
tags:
  - Mixed-Integer Programming
  - Revenue Maximization
  - Inventory Management
  - Pricing Optimization
---

## What this template is for

Retailers often face the challenge of clearing seasonal inventory before it loses value. Markdown optimization determines the best discount schedule across a planning horizon to maximize total revenue -- including both sales revenue and the salvage value of any remaining stock. Discounts stimulate demand but reduce per-unit revenue, so the trade-off must be carefully balanced.

This template finds the discount schedule that maximizes revenue across a multi-week horizon, respecting a price ladder (discounts only deepen over time) and finite inventory, and crediting the salvage value of whatever is left at the end. It captures the full trade-off between aggressive discounting to drive volume and preserving margin on high-value items.

**The reasoning approach uses prescriptive optimization: a mixed-integer program that picks one discount level per product-week and tracks the resulting sales and cumulative inventory.**

## Who this is for

- Retail pricing and merchandising analysts optimizing markdown schedules
- Operations researchers working with mixed-integer programming
- Data scientists exploring multi-period optimization with binary decisions
- **Assumed knowledge**: comfortable reading Python; the pricing and optimization terms are explained as they come up

## What you'll build

- A revenue-maximizing markdown schedule (one discount level per product per week), produced by **prescriptive reasoning** (mixed-integer program)
- A price ladder that prevents discounts from reversing week to week
- A demand model combining base demand, discount lift, and weekly seasonal multipliers
- Per-week sales and cumulative-inventory tracking, bounded so cumulative sales never exceed initial stock
- A total-revenue figure that credits end-of-horizon salvage value on unsold units

## What's included

- `retail_markdown.py` -- Main script defining the MIP model with discount selection, sales tracking, and revenue optimization
- `data/products.csv` -- Products with initial price, cost, inventory, base demand, and salvage rate
- `data/discounts.csv` -- Discount levels with percentage and demand lift factor
- `data/weeks.csv` -- Planning weeks with seasonal demand multipliers
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/retail_markdown.zip
   unzip retail_markdown.zip
   cd retail_markdown
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
   python retail_markdown.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total revenue (sales + salvage): $18432.50

   === Selected Discounts by Product-Week ===
    product  week  discount_pct
    Sweater     1           0.0
    Sweater     2          10.0
    Sweater     3          20.0
    Sweater     4          30.0
     Jacket     1           0.0
     Jacket     2           0.0
     Jacket     3          10.0
     Jacket     4          20.0
      Pants     1           0.0
      Pants     2          10.0
      Pants     3          20.0
      Pants     4          30.0
      Shirt     1           0.0
      Shirt     2           0.0
      Shirt     3          10.0
      Shirt     4          20.0

   === Sales by Product-Week ===
    product  week  discount_pct  units_sold
    Sweater     1           0.0       20.00
    Sweater     2          10.0       20.70
    Sweater     3          20.0       21.60
    Sweater     4          30.0       22.40
     Jacket     1           0.0       12.00
     Jacket     2           0.0       10.80
     Jacket     3          10.0       11.04
     Jacket     4          20.0       11.34
      Pants     1           0.0       25.00
      Pants     2          10.0       25.88
      Pants     3          20.0       27.00
      Pants     4          30.0       28.00
      Shirt     1           0.0       30.00
      Shirt     2           0.0       27.00
      Shirt     3          10.0       27.60
      Shirt     4          20.0       28.35

   === Cumulative Sales by Product-Week ===
    product  week  cumulative_sold
    Sweater     1            20.00
    Sweater     2            40.70
    Sweater     3            62.30
    Sweater     4            84.70
     Jacket     1            12.00
     Jacket     2            22.80
     Jacket     3            33.84
     Jacket     4            45.18
      Pants     1            25.00
      Pants     2            50.88
      Pants     3            77.88
      Pants     4           105.88
      Shirt     1            30.00
      Shirt     2            57.00
      Shirt     3            84.60
      Shirt     4           112.95
   ```

## Template structure

```text
retail_markdown/
├── README.md            # this file
├── pyproject.toml       # dependencies
├── retail_markdown.py   # main script (MIP model, solve, result tables)
├── runbook.md           # analyst-facing walkthrough
└── data/
    ├── products.csv     # products with price, cost, inventory, base demand, salvage rate
    ├── discounts.csv    # discount levels with percentage and demand lift
    └── weeks.csv        # planning weeks with seasonal demand multipliers
```

**Start here**: run `python retail_markdown.py` for the end-to-end solve, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — a short seasonal clearance across a handful of products, sized so the model solves instantly while showing the full workflow.

- **`products.csv`** — one row per product, with `initial_price`, `cost`, `initial_inventory`, `base_demand` (units per week at full price), and `salvage_rate` (fraction of price recovered on leftovers).
- **`discounts.csv`** — one row per discount tier, with `discount_pct` (percent off) and `demand_lift` (demand multiplier at that discount). Includes a `level` 0 / 0% tier so "no markdown" is always an option.
- **`weeks.csv`** — one row per planning week, with `demand_multiplier` (seasonal factor applied to base demand).

## Model overview

- **Key entities**: `Product`, `Discount`, `Week`.
- **Primary identifiers**: string `name` on `Product`; integer `level` on `Discount`; integer `num` on `Week`.
- **Important invariants**: exactly one discount level is active per product-week; discounts can only deepen over successive weeks (price ladder); cumulative sales never exceed `initial_inventory`; `discount_pct`, `demand_lift`, and `demand_multiplier` are non-negative; the selection variable is binary and sales variables are non-negative.

**`Product`** — an item to mark down, with its price, cost, stock, demand, and salvage economics. The solve writes the discount-selection, sales, and cumulative-sales decision variables onto it.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | Loaded from `data/products.csv` |
| `initial_price` | Float | No | Full price before any markdown |
| `cost` | Float | No | Unit cost |
| `initial_inventory` | Integer | No | Starting stock |
| `base_demand` | Float | No | Units per week at full price |
| `salvage_rate` | Float | No | Fraction of price recovered on unsold units |
| `x_select` | Float (binary decision) | No | 1 if a given `Discount` is active for the product in a given `Week` |
| `x_sales` | Float (continuous decision) | No | Units sold per product-week-discount |
| `x_cuml_sales` | Float (continuous decision) | No | Cumulative units sold through a given `Week` |

**`Discount`** — a discount tier, defining how much price is cut and how much demand rises.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `level` | Integer | Yes | Discount ordering (0 = no discount) |
| `discount_pct` | Float | No | Percent off `initial_price` |
| `demand_lift` | Float | No | Demand multiplier at this discount |

**`Week`** — a period in the planning horizon, with its seasonal demand factor.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `num` | Integer | Yes | Week index (1-based) |
| `demand_multiplier` | Float | No | Seasonal factor on base demand |

The script also defines a `num_weeks` relationship (`count(Week)`) used to identify the last week for the salvage term.

## How it works

### 1. Define concepts and load data

Three concepts are defined: `Product` (with pricing, inventory, and demand info), `Discount` (with percentage and demand lift), and `Week` (with seasonal demand multiplier):

```python
Product = model.Concept("Product", identify_by={"name": String})
Product.initial_price = model.Property(f"{Product} has {Float:initial_price}")
Product.initial_inventory = model.Property(f"{Product} has {Integer:initial_inventory}")
Product.base_demand = model.Property(f"{Product} has {Float:base_demand}")
Product.salvage_rate = model.Property(f"{Product} has {Float:salvage_rate}")

Discount = model.Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")

Week = model.Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")
```

### 2. Decision variables

Three sets of variables model the decisions and state: binary selection of discount level per product-week, continuous sales per product-week-discount, and cumulative sales per product-week:

```python
problem.solve_for(Product.x_select(Week_ref, Discount_ref, selection_ref), type="bin", ...)
problem.solve_for(Product.x_sales(Week_ref, Discount_ref, sales_ref), type="cont", lower=0, ...)
problem.solve_for(Product.x_cuml_sales(Week_ref, cumulative_ref), type="cont", lower=0, ...)
```

### 3. Key constraints

The one-hot constraint ensures exactly one discount level is active per product-week. The price ladder constraint prevents discount reversals:

```python
# One discount per product-week
problem.satisfy(model.where(Product.x_select(Week_ref, Discount_ref, selection_ref)).require(
    sum(Discount_ref, selection_ref).per(Product, Week_ref) == 1
))

# Discounts can only increase over time
problem.satisfy(model.where(
    Product.x_select(Week_ref, Discount_ref, selection_ref),
    Product.x_select(Week_inner, Discount_inner, selection_inner),
    Week_inner.num == Week_ref.num + 1,
    Discount_inner.level < Discount_ref.level,
).require(selection_ref + selection_inner <= 1))
```

### 4. Objective

Revenue combines sales revenue (price after discount times units sold) and salvage value of remaining inventory:

```python
revenue = sum(
    Product.initial_price * (1 - Discount_ref.discount_pct / 100) * sales_ref
).where(Product.x_sales(Week_ref, Discount_ref, sales_ref))
salvage = sum(
    Product.initial_price * Product.salvage_rate * (Product.initial_inventory - cumulative_ref)
).where(Product.x_cuml_sales(Week_ref, cumulative_ref), Week_ref.num == num_weeks)
problem.maximize(revenue + salvage)
```

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the column names listed in *Sample data* above.
- Keep a `level` 0 / 0% row in `discounts.csv` so "no markdown" remains a feasible choice.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)`.

### Tune parameters

- **Discount levels** — modify `discounts.csv` to add finer or coarser tiers with different demand lifts.
- **Planning horizon** — add or remove rows in `weeks.csv`; the model scales with longer horizons.
- **Solver time limit** — `time_limit_sec` (default `60`) on the `problem.solve(...)` call.

### Extend the model

- **Minimum margin constraint** — add a constraint ensuring the discounted price always exceeds the product cost.
- **Category-level constraints** — group products by category and limit the total discount budget per category.
- **Demand elasticity** — replace the fixed demand lift with a price-elasticity function for more realistic demand modeling.

### Scale up / productionize

- Replace the CSV bundle with ingestion from your merchandising or point-of-sale tables.
- Mixed-integer programs grow harder with more products, weeks, and discount tiers; give the solver more time via `time_limit_sec`, or accept a near-optimal solution by checking the MIP gap.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

Check that initial inventory is sufficient for at least one week of base demand. Also verify that the discount levels include a 0% option (no discount) so the model has a feasible starting point.
</details>

<details>
<summary>Solver is slow or times out</summary>

Mixed-integer programs can be computationally expensive. Reduce the number of products, weeks, or discount levels. You can also increase `time_limit_sec` or accept a near-optimal solution by checking the MIP gap.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, `.per(...)`, aggregations, and `model.select(...)`.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.

### Deeper dives

- [Multi-period optimization patterns](https://docs.relational.ai/) — modeling week-over-week state (cumulative sales, price ladders) with indexed decision variables.

## Support

- File issues at the RelationalAI templates repository.
