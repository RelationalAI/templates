---
title: "Production Planning"
description: "Schedule production across machines to meet demand while maximizing profit."
featured: true
experience_level: beginner
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
---

# Production Planning

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Manufacturing teams often need to decide how much of each product to produce on each machine, given limited machine time and product demand targets.
This template models a small production planning problem where:

- Each product has a demand requirement and a per-unit profit.
- Each machine has a limited number of available production hours.
- Each machine–product route has a specific processing time (hours per unit).

The key challenge is that capacity is shared across products, so meeting demand for one product can crowd out more profitable production elsewhere.
This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to compute a profit-maximizing production plan that meets demand while respecting machine capacity.

> [!NOTE]
> This template uses integer decision variables (MILP), so production quantities are discrete.
> If you want a continuous (LP) variant with machine operating costs in the objective, see the [factory production](https://private.relational.ai/early-access/pyrel/templates/factory_production) template.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and the idea of decision variables, constraints, and objectives.

## What you’ll build

- A semantic model of machines, products, and machine–product production rates using concepts and properties.
- A MILP with one integer decision variable per feasible machine–product pair.
- Constraints that enforce machine-hour capacity and product demand satisfaction.
- A small scenario analysis loop that reruns the solve under different demand scaling assumptions.

## What’s included

- **Model + solve script**: `production_planning.py`
- **Sample data**: `data/products.csv`, `data/machines.csv`, `data/production_rates.csv`
- **Outputs**: solver status/objective per scenario, a per-scenario production plan table, and a scenario summary

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
	curl -O https://private.relational.ai/templates/zips/v0.13/production_planning.zip
	unzip production_planning.zip
	cd production_planning
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
   python production_planning.py
   ```

6. **Expected output**

   The script solves three demand scenarios and prints a production plan table for each.
   You should see output shaped like:

   ```text
   Running scenario: demand_multiplier = 1.0
     Status: OPTIMAL, Objective: 14945.0

     Production plan:
                     name  value
   qty_Machine_1_Widget_A    4.0
   qty_Machine_1_Widget_C   95.0
   ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     0.8: OPTIMAL, obj=15020.0
     1.0: OPTIMAL, obj=14945.0
     1.1: OPTIMAL, obj=14770.0
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ production_planning.py      # main runner / entrypoint
└─ data/                       # sample input data
   ├─ products.csv
   ├─ machines.csv
   └─ production_rates.csv
```

**Start here**: `production_planning.py`

## Sample data

Data files are in `data/`.

### `products.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique product identifier |
| `name` | Product name |
| `demand` | Units that must be produced (before scenario scaling) |
| `profit` | Profit per unit |

### `machines.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique machine identifier |
| `name` | Machine name |
| `hours_available` | Total hours available (capacity) |

### `production_rates.csv`

| Column | Meaning |
| --- | --- |
| `machine_id` | Foreign key to `machines.csv.id` |
| `product_id` | Foreign key to `products.csv.id` |
| `hours_per_unit` | Hours required to produce one unit on that machine |

## Model overview

The optimization model is built around four concepts.

### `Product`

A product with demand and profit parameters.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/products.csv` |
| `name` | string | No | Used for variable naming in the output |
| `demand` | int | No | Minimum units required (scaled by `demand_multiplier`) |
| `profit` | float | No | Profit per unit in the objective |

### `Machine`

A production resource with limited available hours.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/machines.csv` |
| `name` | string | No | Used for variable naming in the output |
| `hours_available` | float | No | Capacity constraint per machine |

### `ProductionRate`

A feasible machine–product route that specifies how long it takes to produce one unit.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `machine` | `Machine` | Part of compound key | Joined via `data/production_rates.csv.machine_id` |
| `product` | `Product` | Part of compound key | Joined via `data/production_rates.csv.product_id` |
| `hours_per_unit` | float | No | Coefficient in the machine-capacity constraints |

### `Production` (decision concept)

One decision row per `ProductionRate` route; the solver chooses the production quantity.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `rate` | `ProductionRate` | Yes | One decision variable per machine–product route |
| `quantity` | float | No | Integer decision variable (`type="int"`), lower bounded by 0 |

## How it works

This section walks through the highlights in `production_planning.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs and configures `DATA_DIR` and the pandas string inference behavior:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("production_planning", config=globals().get("config", None), use_lqp=False)
```

### Define concepts and load CSV data

Next, the script defines `Product` and `Machine`, loads `products.csv` and `machines.csv` via `data(...).into(...)`, and then joins the foreign keys in `production_rates.csv` to create `ProductionRate` rows using `where(...).define(...)`:

```python
# Product concept: products with demand and profit per unit.
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")
Product.profit = model.Property("{Product} has {profit:float}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# Machine concept: machines with a limited number of available production hours.
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.hours_available = model.Property("{Machine} has {hours_available:float}")

# Load machine data from CSV.
data(read_csv(DATA_DIR / "machines.csv")).into(Machine, keys=["id"])

# ProductionRate concept: hours required per unit for each machine-product pair.
Rate = model.Concept("ProductionRate")
Rate.machine = model.Property("{ProductionRate} on {machine:Machine}")
Rate.product = model.Property("{ProductionRate} for {product:Product}")
Rate.hours_per_unit = model.Property("{ProductionRate} has {hours_per_unit:float}")

# Load production rate data from CSV.
rates_data = data(read_csv(DATA_DIR / "production_rates.csv"))

# Define ProductionRate entities by joining the rate CSV with Machine and Product.
where(
    Machine.id == rates_data.machine_id,
    Product.id == rates_data.product_id
).define(
    Rate.new(machine=Machine, product=Product, hours_per_unit=rates_data.hours_per_unit)
)
```

### Define decision variables, constraints, and objective

Then the script creates a `Production` decision concept (one row per `ProductionRate`) and defines a `build_formulation` helper. That helper registers the integer decision variable with `solve_for(...)`, adds constraints with `require(...)`, and sets a profit-maximizing objective:

```python
# Production decision concept: production quantity for each machine-product pair.
Production = model.Concept("Production")
Production.rate = model.Property("{Production} uses {rate:ProductionRate}")
Production.quantity = model.Property("{Production} has {quantity:float}")
define(Production.new(rate=Rate))

Prod = Production.ref()

# Scenario parameter (overridden within the scenario loop).
demand_multiplier = 1.0


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: production quantity (integer)
    s.solve_for(
        Production.quantity,
        name=[
            "qty",
            Production.rate.machine.name,
            Production.rate.product.name,
        ],
        lower=0,
        type="int",
    )

    # Constraint: machine capacity
    machine_hours = (
        sum(Prod.quantity * Prod.rate.hours_per_unit)
        .where(Prod.rate.machine == Machine)
        .per(Machine)
    )
    capacity_limit = require(machine_hours <= Machine.hours_available)
    s.satisfy(capacity_limit)

    # Constraint: meet demand (scaled by demand_multiplier)
    product_qty = sum(Prod.quantity).where(Prod.rate.product == Product).per(Product)
    meet_demand = require(product_qty >= Product.demand * demand_multiplier)
    s.satisfy(meet_demand)

    # Objective: maximize total profit
    total_profit = sum(Production.quantity * Production.rate.product.profit)
    s.maximize(total_profit)
```

### Solve scenarios and print results

Finally, the script runs a small scenario analysis by setting `demand_multiplier`, solving a fresh `SolverModel` each time, and printing a filtered production plan table (only rows where the solver value is greater than `0.001`):

```python
SCENARIO_PARAM = "demand_multiplier"
SCENARIO_VALUES = [0.8, 1.0, 1.1]

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    demand_multiplier = scenario_value

    # Create fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append(
        {
            "scenario": scenario_value,
            "status": str(s.termination_status),
            "objective": s.objective_value,
        }
    )
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print production plan from solver results
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)
    ].rename(columns={"float": "value"})
    print(f"\n  Production plan:")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
```

## Customize this template

### Change the scenario parameters

This template includes a simple demand sensitivity analysis controlled by `demand_multiplier`.

| Parameter | Type | Values | Description |
| --- | --- | --- | --- |
| `demand_multiplier` | numeric | `0.8`, `1.0`, `1.1` | Multiplier applied to all product demands |

How to customize the scenarios:

- In `production_planning.py`, edit `SCENARIO_VALUES` to the multipliers you want to test.

How to interpret results:

- If increasing `demand_multiplier` decreases the objective, demand is forcing production into less-profitable routes.
- If changing `demand_multiplier` does not change the objective, the demand constraints are likely non-binding at those values.

### Use your own data

- Replace the CSV files under `data/`.
- Keep IDs consistent across files (`machine_id` / `product_id` must exist in `machines.csv` / `products.csv`).

### Extend the model

- Add setup costs and binary on/off decisions per route.
- Add maximum production limits per product (demand as an upper bound rather than a lower bound).
- Add multi-period planning (introduce a `Period` concept and inventory/transition constraints).

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
  - `products.csv`: `id`, `name`, `demand`, `profit`
  - `machines.csv`: `id`, `name`, `hours_available`
  - `production_rates.csv`: `machine_id`, `product_id`, `hours_per_unit`

</details>

<details>
<summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>

- Check that total machine hours are sufficient to meet demand: for each product, at least one route must exist in `production_rates.csv`.
- If you increased `demand_multiplier`, try lowering it or increasing `hours_available`.

</details>

<details>
<summary>Why is the production plan empty?</summary>

- The output filters on `float > 0.001` and only prints variables whose names start with `qty`.
- If you suspect near-zero values, print `s.variable_values().to_df()` without filtering.

</details>

<details>
<summary>Solver fails or returns an unexpected termination status</summary>

- Try re-running; transient connectivity issues can affect the solve step.
- If the solve is slow, reduce problem size (fewer machines/products/routes) or increase `time_limit_sec` in `production_planning.py`.

</details>
