---
title: "Retail Markdown"
description: "Set discount levels across weeks to maximize revenue while clearing inventory."
featured: false
experience_level: intermediate
industry: "Retail"
reasoning_types:
  - Prescriptive
tags:
  - Mixed-Integer Programming
  - Revenue Maximization
  - Inventory Management
  - Pricing Optimization
---

# Retail Markdown

## What this template is for

Retailers often face the challenge of clearing seasonal inventory before it loses value. Markdown optimization determines the best discount schedule across a planning horizon to maximize total revenue -- including both sales revenue and the salvage value of any remaining stock. Discounts stimulate demand but reduce per-unit revenue, so the trade-off must be carefully balanced.

This template models the markdown problem as a mixed-integer program. Binary decision variables select which discount level to apply to each product in each week. Continuous variables track units sold and cumulative sales. Constraints enforce that exactly one discount is chosen per product-week, that discounts can only increase over time (a price ladder), and that cumulative sales never exceed initial inventory. Demand depends on a base rate, a discount-specific demand lift, and a weekly seasonal multiplier.

The objective maximizes total revenue from sales plus the salvage value of unsold inventory at the end of the planning horizon. This captures the full trade-off between aggressive discounting to drive volume and preserving margin on high-value items.

## Who this is for

- Retail pricing and merchandising analysts optimizing markdown schedules
- Operations researchers working with mixed-integer programming
- Data scientists exploring multi-period optimization with binary decisions
- Anyone interested in inventory clearance and revenue management

## What you'll build

- A mixed-integer programming model that selects discount levels per product per week
- Price ladder constraints preventing discount reversals
- Demand modeling with base demand, discount lifts, and seasonal multipliers
- Inventory tracking via cumulative sales constraints
- Revenue maximization including end-of-horizon salvage value

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
   curl -L -O https://docs.relational.ai/templates/zips/v1/retail_markdown.zip
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
.
├── README.md
├── pyproject.toml
├── retail_markdown.py
└── data/
    ├── products.csv
    ├── discounts.csv
    └── weeks.csv
```

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
s.solve_for(Product.x_select(w, d, x), type="bin", ...)
s.solve_for(Product.x_sales(w, d, y), type="cont", lower=0, ...)
s.solve_for(Product.x_cuml_sales(w, z), type="cont", lower=0, ...)
```

### 3. Key constraints

The one-hot constraint ensures exactly one discount level is active per product-week. The price ladder constraint prevents discount reversals:

```python
# One discount per product-week
s.satisfy(model.where(Product.x_select(w, d, x)).require(
    sum(d, x).per(Product, w) == 1
))

# Discounts can only increase over time
s.satisfy(model.where(
    Product.x_select(w, d, x),
    Product.x_select(w2, d2, x2),
    w2.num == w.num + 1,
    d2.level < d.level,
).require(x + x2 <= 1))
```

### 4. Objective

Revenue combines sales revenue (price after discount times units sold) and salvage value of remaining inventory:

```python
revenue = sum(
    Product.initial_price * (1 - d.discount_pct / 100) * x
).where(Product.x_sales(w, d, x))
salvage = sum(
    Product.initial_price * Product.salvage_rate * (Product.initial_inventory - z)
).where(Product.x_cuml_sales(w, z), w.num == num_weeks)
s.maximize(revenue + salvage)
```

## Customize this template

- **Add more products or weeks**: Extend the CSV files. The model scales with additional products and longer planning horizons.
- **Change discount levels**: Modify `discounts.csv` to add finer or coarser discount tiers with different demand lifts.
- **Minimum margin constraint**: Add a constraint ensuring the discounted price always exceeds the product cost.
- **Category-level constraints**: Group products by category and limit the total discount budget per category.
- **Demand elasticity**: Replace the fixed demand lift with a price-elasticity function for more realistic demand modeling.

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
