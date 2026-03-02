---
title: "Factory Production"
description: "Choose production quantities per machine-product pair to maximize profit while meeting minimum production requirements."
featured: false
experience_level: beginner
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP

---

# Factory Production

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.14.2` of the `relationalai` Python package.

## What this template is for

Manufacturing facilities must decide what to produce given limited resources.
This template models a factory with multiple machines producing different products, where:

- Each machine has limited hours available and a machine-specific hourly operating cost.
- Each product has a selling price and a minimum production requirement.
- Different machines take different amounts of time to produce each product.

The goal is to find the optimal product mix—how much of each product to make on each machine—to **maximize profit** (revenue minus machine operating costs) while respecting machine capacity and meeting minimum production targets.

This template uses RelationalAI's **Prescriptive** reasoning capabilities (optimization) to compute a profit-maximizing production plan that meets minimum requirements while respecting machine capacity.

> [!NOTE]
> This template uses continuous decision variables (LP), so fractional quantities are allowed.
> If you need integer production units, see the [production planning](https://private.relational.ai/early-access/pyrel/templates/production_planning) template.

## Who this is for

- You want a small, end-to-end example of prescriptive reasoning (optimization) using RelationalAI Semantics.
- You’re comfortable with basic Python and the idea of constraints + objectives.

## What you’ll build

- A semantic model of machines, products, and machine-product production times.
- A linear program (LP) with one continuous decision variable per feasible machine-product pair.
- Capacity and minimum-production constraints.
- A profit-maximizing objective.

## What’s included

- `factory_production.py` — defines the semantic model, optimization problem, and prints a solution
- `data/` — sample CSV inputs (`machines.csv`, `products.csv`, `production_times.csv`)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template using the included sample data:

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.14/factory_production.zip
   unzip factory_production.zip
   cd factory_production
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Initialize your RAI profile:

   ```bash
   rai init
   ```

5. Run the template script:

   ```bash
   python factory_production.py
   ```

6. Expected output:

  ```text
   Status: OPTIMAL
   Total profit: $20977.78

   Production plan:
   machine product  quantity
   Machine_A  Widget 80.000000
   Machine_B  Device 38.888889
   Machine_C  Gadget 15.000000
   Machine_C  Widget 90.000000
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ factory_production.py      # main runner / entrypoint
└─ data/                      # sample input data
    ├─ machines.csv
    ├─ products.csv
    └─ production_times.csv
```

**Start here**: `factory_production.py`

## Sample data

Data files are located in the `data/` subdirectory.

### machines.csv

| Column | Description |
| --- | --- |
| `id` | Unique machine identifier |
| `name` | Machine name |
| `hours_available` | Hours available per period |
| `hourly_cost` | Operating cost per hour ($) |

### products.csv

| Column | Description |
| --- | --- |
| `id` | Unique product identifier |
| `name` | Product name |
| `price` | Selling price per unit ($) |
| `min_production` | Minimum units that must be produced |

### production_times.csv

| Column | Description |
| --- | --- |
| `machine_id` | Reference to machine |
| `product_id` | Reference to product |
| `hours_per_unit` | Hours required to produce one unit |

## Model overview

The optimization model is built around four concepts.

### Machine

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `machines.csv` |
| `name` | string | No | Used for output labels |
| `hours_available` | float | No | Capacity for each machine |
| `hourly_cost` | float | No | Cost term in the objective |

### Product

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `products.csv` |
| `name` | string | No | Used for output labels |
| `price` | float | No | Revenue per unit |
| `min_production` | int | No | Minimum units required |

### ProductionTime

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `machine` | `Machine` | Part of compound key | Machine for the route |
| `product` | `Product` | Part of compound key | Product for the route |
| `hours_per_unit` | float | No | Time to make one unit |

### Production (decision concept)

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `prod_time` | `ProductionTime` | Yes | One variable per machine-product route |
| `quantity` | float | No | Continuous decision variable, lower bounded by 0 |

## How it works

This section walks through the highlights in `factory_production.py`.

### Import libraries and configure inputs

This template uses `Concept` objects from `relationalai.semantics` to model machines, products, and production times, and uses `Solver` and `SolverModel` from `relationalai.semantics.reasoners.optimization` to define and solve the linear program:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("factory")
```

### Define concepts and load CSV data

Next, it declares the `Machine`, `Product`, and `ProductionTime` concepts and loads the corresponding CSV tables. `data(...).into(...)` creates entities from `machines.csv` and `products.csv`, and `where(...).define(...)` joins `production_times.csv` onto those concepts:

```python
# Machine concept: represents a production machine with available hours and hourly cost
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")
Machine.hourly_cost = model.Property("{Machine} has {hourly_cost:float}")

# Load machine data from CSV and create Machine entities.
data(read_csv(DATA_DIR / "machines.csv")).into(Machine, keys=["id"])

# Product concept: represents a product with price and minimum production requirements
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.price = model.Property("{Product} has {price:float}")
Product.min_production = model.Property("{Product} has {min_production:int}")

# Load product data from CSV and create Product entities.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# ProdTime concept: represents the time required to produce one unit of a product on a machine
ProdTime = model.Concept("ProductionTime")
ProdTime.machine = model.Relationship("{ProductionTime} on {machine:Machine}")
ProdTime.product = model.Relationship("{ProductionTime} of {product:Product}")
ProdTime.hours_per_unit = model.Property("{ProductionTime} takes {hours_per_unit:float}")

# Load production time data from CSV.
times_data = data(read_csv(DATA_DIR / "production_times.csv"))

# Define ProductionTime entities by joining machine/product IDs from the CSV with
# the Machine and Product concepts.
where(
    Machine.id == times_data.machine_id,
    Product.id == times_data.product_id,
).define(
    ProdTime.new(machine=Machine, product=Product, hours_per_unit=times_data.hours_per_unit)
)
```

### Define decision variables, constraints, and objective

Then it creates one continuous, non-negative decision variable per machine–product route, adds machine-hour and minimum-production constraints with `require(...)`, and maximizes profit:

```python
# Decision concept: production quantities for each machine/product
Production = model.Concept("Production")
Production.prod_time = model.Relationship("{Production} uses {prod_time:ProductionTime}")
Production.x_quantity = model.Property("{Production} has {quantity:float}")

# Define one Production entity per machine-product ProductionTime record.
define(Production.new(prod_time=ProdTime))

ProductionRef = Production.ref()

s = SolverModel(model, "cont")

# Variable: production quantity
s.solve_for(
    Production.x_quantity,
    name=["qty", Production.prod_time.machine.name, Production.prod_time.product.name],
    lower=0,
)

# Constraint: total production hours per machine <= hours_available
total_hours = sum(
    ProductionRef.x_quantity * ProductionRef.prod_time.hours_per_unit
).where(
    ProductionRef.prod_time.machine == Machine
).per(Machine)
machine_limit = require(total_hours <= Machine.hours_available)
s.satisfy(machine_limit)

# Constraint: total production per product >= min_production
total_produced = sum(ProductionRef.x_quantity).where(ProductionRef.prod_time.product == Product).per(Product)
meet_minimum = require(total_produced >= Product.min_production)
s.satisfy(meet_minimum)

# Objective: maximize profit (revenue - machine costs)
revenue = sum(Production.x_quantity * Production.prod_time.product.price)
machine_cost = sum(
    Production.x_quantity * Production.prod_time.hours_per_unit * Production.prod_time.machine.hourly_cost
)
profit = revenue - machine_cost
s.maximize(profit)
```

### Solve and print results

Finally, it solves using the HiGHS backend and prints only rows where `Production.x_quantity > 0`:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total profit: ${s.objective_value:.2f}")

plan = select(
    Production.prod_time.machine.name.alias("machine"),
    Production.prod_time.product.name.alias("product"),
    Production.x_quantity
).where(Production.x_quantity > 0).to_df()

print("\nProduction plan:")
print(plan.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSV files under `data/`.
- Keep IDs consistent across files (`machine_id`/`product_id` must exist in the respective tables).

### Extend the model

- Add maximum production limits, inventory constraints, or demand caps.
- Add setup/changeover costs and binary on/off decisions (MILP).
- Switch to integer quantities (or start from ../production_planning/README.md).

## Troubleshooting

<details>
  <summary>Connection/auth issues</summary>

- Re-run `rai init` and confirm the selected profile is correct.
- Ensure you have access to the RAI Native App in Snowflake.

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
  - `machines.csv`: `id`, `name`, `hours_available`, `hourly_cost`
  - `products.csv`: `id`, `name`, `price`, `min_production`
  - `production_times.csv`: `machine_id`, `product_id`, `hours_per_unit`

</details>

<details>
  <summary>Status is INFEASIBLE</summary>

- Check that product minimums can be met with available machine hours.
- Ensure each required product has at least one route in `production_times.csv`.

</details>

<details>
  <summary>No rows printed in the production plan</summary>

- The output filters on `Production.x_quantity > 0`.
- If quantities are extremely small, print the full variable set or relax the filter.

</details>

<details>
  <summary>Solver fails or returns an unexpected termination status</summary>

- Try re-running; transient connectivity issues can affect the solve step.
- If the solve is slow, reduce problem size (fewer machines/products/routes) or increase the time limit in `factory_production.py`.

</details>
