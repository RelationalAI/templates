---
title: "Markdown Optimization"
description: "Set discount levels for products across a selling season to maximize revenue while clearing inventory."
featured: false
experience_level: intermediate
industry: "Retail"
reasoning_types:
  - Prescriptive
tags:
  - Pricing
  - MILP
---

# Markdown Optimization

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Retailers often need to clear seasonal inventory over a fixed selling window (for example, a 4-week end-of-season period).
Markdown decisions are tricky because deeper discounts typically increase demand but reduce the price you recover.

This template models a simple markdown strategy problem where you choose a discount tier each week for each product.
Once a product is marked down, it cannot be marked back up later (a “price ladder” constraint).
This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose weekly discounts and sales quantities that maximize total revenue from discounted sales plus salvage value on leftover inventory.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** using the RelationalAI Semantics API.
- You’re comfortable with basic Python and the idea of constraints + objectives.
- You want a concrete example of a MILP with binary selection variables and continuous flow variables.

## What you’ll build

- A semantic model of products and discount options loaded from CSV.
- A MILP that selects exactly one discount per product-week (binary decisions).
- Sales and cumulative-sales variables that enforce demand and inventory limits.
- A price ladder that prevents discount levels from decreasing week over week.
- A solve script that prints the chosen discounts, sales, and cumulative sales.

## What’s included

- **Model + solve script**: `retail_markdown.py`
- **Sample data**: `data/products.csv`, `data/discounts.csv`, `data/weeks.csv`
- **Outputs**: solver status + objective, plus three printed tables (`select`, `sales`, `cum`)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/retail_markdown.zip
   unzip retail_markdown.zip
   cd retail_markdown
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python retail_markdown.py
   ```

6. **Expected output**

   The script prints a status line, an objective value, and three tables.
   You should see output shaped like:

   ```text
   Status: OPTIMAL
   Total revenue (sales + salvage): $23374.65

   === Selected Discounts by Product-Week ===
   ...

   === Sales by Product-Week ===
   ...

   === Cumulative Sales by Product-Week ===
   ...
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ retail_markdown.py          # main runner / entrypoint
└─ data/                       # sample input data
   ├─ products.csv
   ├─ discounts.csv
   └─ weeks.csv
```

**Start here**: `retail_markdown.py`

## Sample data

Data files are in `data/`.

### `products.csv`

Defines the initial state and economics for each product.

| Column | Meaning |
| --- | --- |
| `id` | Product identifier (not used as a key in this template) |
| `name` | Product name (used as the entity key and for printed labels) |
| `initial_price` | Starting price before any markdown |
| `cost` | Unit cost (included in sample data; not used in the objective in this template) |
| `initial_inventory` | Starting inventory available to sell |
| `base_demand` | Base weekly demand at full price |
| `salvage_rate` | Fraction of price recovered for leftover units at the end |

### `discounts.csv`

Defines the allowed discount tiers and how discounting increases demand.

| Column | Meaning |
| --- | --- |
| `id` | Discount identifier (not used as a key in this template) |
| `level` | Ordered tier index used by the price ladder constraint |
| `discount_pct` | Discount percentage (0, 10, 20, 30, 50 in the sample) |
| `demand_lift` | Demand multiplier when using this discount |

### `weeks.csv`

Defines how demand changes over the selling window.

| Column | Meaning |
| --- | --- |
| `id` | Week identifier |
| `week_num` | Week number (used as the time index) |
| `demand_multiplier` | Seasonal demand multiplier (often decreases over time) |

## Model overview

This template models a markdown strategy with two core concepts and a small number of decision variables.

- **Key entities**: `Product`, `Discount`
- **Primary identifiers**:
  - `Product` is keyed by `name`
  - `Discount` is keyed by `level`
- **Important invariants**:
  - Exactly one discount tier is selected per product-week.
  - Discount levels cannot decrease from one week to the next.
  - Cumulative sales cannot exceed initial inventory.

### `Product`

A retail item that has initial inventory and demand/economic parameters.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `name` | string | Yes | Loaded as the key from `data/products.csv` |
| `initial_price` | float | No | Used to compute revenue and salvage value |
| `cost` | float | No | Loaded but not used in the objective in this template |
| `initial_inventory` | int | No | Upper bound on cumulative sales |
| `base_demand` | float | No | Used in the weekly sales upper bound |
| `salvage_rate` | float | No | Used to value leftover inventory |

### `Discount`

A discount tier that has both a percent-off and a demand lift factor.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `level` | int | Yes | Loaded as the key from `data/discounts.csv` |
| `discount_pct` | float | No | Used in revenue computation |
| `demand_lift` | float | No | Used in the weekly sales upper bound |

### Decision variables

The solver creates decision variables using properties on `Product` indexed by week (`t`) and discount (`d`).

| Variable | Type | Meaning |
| --- | --- | --- |
| `Product.selected(t, d, selected)` | binary | 1 if discount `d` is chosen in week `t` |
| `Product.sales(t, d, sales)` | continuous | units sold in week `t` at discount `d` |
| `Product.cum_sales(t, cum_sales)` | continuous | cumulative units sold through week `t` |

## How it works

This section walks through the highlights in `retail_markdown.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs and sets `DATA_DIR` and a pandas option for consistent CSV types:

```python
from pathlib import Path
from time import time_ns

import pandas
from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, data, std, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False
```

### Define concepts and load CSV data

Next, it creates a Semantics `Model` and loads `Product` and `Discount` from CSV using `data(...).into(...)`:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model(
    f"retail_markdown_{time_ns()}",
    config=globals().get("config", None),
    use_lqp=False,
)

# Product concept: products with inventory, pricing, and demand parameters.
Product = model.Concept("Product")
Product.name = model.Property("{Product} has {name:string}")
Product.initial_price = model.Property("{Product} has {initial_price:float}")
Product.cost = model.Property("{Product} has {cost:float}")
Product.initial_inventory = model.Property("{Product} has {initial_inventory:int}")
Product.base_demand = model.Property("{Product} has {base_demand:float}")
Product.salvage_rate = model.Property("{Product} has {salvage_rate:float}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["name"])

# Discount concept: discount levels and their demand lift factors.
Discount = model.Concept("Discount")
Discount.level = model.Property("{Discount} has {level:int}")
Discount.discount_pct = model.Property("{Discount} has {discount_pct:float}")
Discount.demand_lift = model.Property("{Discount} has {demand_lift:float}")

# Load discount data from CSV.
data(read_csv(DATA_DIR / "discounts.csv")).into(Discount, keys=["level"])
```

The weekly demand multipliers are read into a Python dictionary.
This avoids creating a separate `Week` concept inside `s.satisfy(...)` where-clauses (a known pain point in v0.13):

```python
# Week demand multipliers: loaded as a Python dict for use in per-week constraints.
# Note: Week is not defined as a Concept because non-solver concepts in satisfy()
# where clauses can cause "Uninitialized property: error_<concept>" in RAI v0.13.
weeks_df = read_csv(DATA_DIR / "weeks.csv")
demand_multiplier = dict(zip(weeks_df["week_num"], weeks_df["demand_multiplier"]))
```

### Define decision variables, constraints, and objective

With the inputs loaded, the script creates a `SolverModel` and registers three decision-variable families using `solve_for(...)`:

```python
# Create a continuous optimization model with a MILP formulation.
s = SolverModel(model, "cont", use_pb=True)

# Product.selected decision variable: select exactly one discount per product-week.
Product.selected = model.Property("{Product} in week {t:int} at discount {d:Discount} is {selected:float}")
x_sel = Float.ref()
s.solve_for(
    Product.selected(t, d, x_sel),
    type="bin",
    name=["select", Product.name, t, d.discount_pct],
    where=[t == weeks],
)

# Product.sales decision variable: units sold at the chosen discount.
Product.sales = model.Property("{Product} in week {t:int} at discount {d:Discount} has {sales:float}")
x_sales = Float.ref()
s.solve_for(
    Product.sales(t, d, x_sales),
    type="cont",
    lower=0,
    name=["sales", Product.name, t, d.discount_pct],
    where=[t == weeks],
)

# Product.cum_sales decision variable: cumulative sales through each week.
Product.cum_sales = model.Property("{Product} through week {t:int} has {cum_sales:float}")
x_cum = Float.ref()
s.solve_for(
    Product.cum_sales(t, x_cum),
    type="cont",
    lower=0,
    name=["cum", Product.name, t],
    where=[t == weeks],
)
```

Then it enforces the core business rules with `where(...).require(...)` constraints, including one-discount-per-week and the price ladder:

```python
# Constraint: one discount level selected per product per week.
one_discount_per_week = where(
    Product.selected(t, d, x_sel)
).require(
    sum(x_sel).per(Product, t) == 1
)
s.satisfy(one_discount_per_week)

# Constraint: price ladder - discounts can only increase (prices can only decrease).
d1, d2 = Discount.ref(), Discount.ref()
x_sel1, x_sel2 = Float.ref(), Float.ref()
price_ladder = where(
    Product.selected(t, d1, x_sel1),
    Product.selected(t + 1, d2, x_sel2),
    d2.level < d1.level,
    t >= week_start,
    t < week_end
).require(
    x_sel1 + x_sel2 <= 1
)
s.satisfy(price_ladder)
```

Finally, it maximizes revenue from discounted sales plus salvage value at the end of the horizon:

```python
# Objective: maximize revenue from sales plus salvage value of remaining inventory.
revenue = sum(
    x_sales * Product.initial_price * (1 - d.discount_pct / 100)
).where(
    Product.sales(t, d, x_sales)
)

x_cum_final = Float.ref()
salvage = sum(
    (Product.initial_inventory - x_cum_final) * Product.initial_price * Product.salvage_rate
).where(
    Product.cum_sales(week_end, x_cum_final)
)

s.maximize(revenue + salvage)
```

### Solve and print results

The model is solved with the HiGHS backend and a 60-second time limit. The script then prints filtered tables from `s.variable_values().to_df()`:

```python
resources = model._to_executor().resources
solver = Solver("highs", resources=resources)
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total revenue (sales + salvage): ${s.objective_value:.2f}")

df = s.variable_values().to_df()

print("\n=== Selected Discounts by Product-Week ===")
selected = df[df["name"].str.startswith("select") & (df["float"] > 0.5)]
print(selected.to_string(index=False))

print("\n=== Sales by Product-Week ===")
sales = df[df["name"].str.startswith("sales") & (df["float"] > 0.01)]
print(sales.to_string(index=False))

print("\n=== Cumulative Sales by Product-Week ===")
cum = df[df["name"].str.startswith("cum")]
print(cum.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSV files under `data/`.
- Keep key columns consistent:
  - `products.csv` must have at least: `name`, `initial_price`, `initial_inventory`, `base_demand`, `salvage_rate`
  - `discounts.csv` must have at least: `level`, `discount_pct`, `demand_lift`
  - `weeks.csv` must have at least: `week_num`, `demand_multiplier`

### Tune parameters

- In `retail_markdown.py`, adjust `week_start` / `week_end` to change the horizon.
- Modify `discounts.csv` to change the available discount ladder.
- Update `weeks.csv` to reflect your seasonal demand profile.

### Extend the model

- Add a minimum-margin constraint using `Product.cost`.
- Add per-week sales caps, store capacity limits, or budget constraints.
- Add product-specific discount availability (some products cannot be discounted beyond a tier).

## Troubleshooting

<details>
	<summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
	<summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
	<summary><code>ModuleNotFoundError</code> when running the script</summary>

- Confirm your virtual environment is activated.
- Install the template dependencies from this folder: `python -m pip install .`

</details>

<details>
	<summary>CSV loading fails (missing file or column)</summary>

- Confirm the CSVs exist under `data/` and the filenames match.
- Ensure the headers match the expected schema:
  - `products.csv`: `id`, `name`, `initial_price`, `cost`, `initial_inventory`, `base_demand`, `salvage_rate`
  - `discounts.csv`: `id`, `level`, `discount_pct`, `demand_lift`
  - `weeks.csv`: `id`, `week_num`, `demand_multiplier`

</details>

<details>
	<summary>Why are the printed tables empty?</summary>

- The script filters printed rows:
  - selected discounts: `name` starts with `select` and `float > 0.5`
  - sales: `name` starts with `sales` and `float > 0.01`
- If your solution has very small values, lower the thresholds or print `df` without filtering.

</details>

<details>
	<summary>Solver fails or returns an unexpected termination status</summary>

- Try re-running; transient connectivity issues can affect the solve step.
- If the solve is slow, reduce problem size (fewer products/discounts/weeks) or increase `time_limit_sec` in `retail_markdown.py`.

</details>
