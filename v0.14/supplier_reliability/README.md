---
title: "Supplier Reliability"
description: "Select suppliers to meet product demand while balancing cost and reliability."
featured: false
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP
  - Procurement
  - Risk
---

# Supplier Reliability

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Procurement teams routinely need to decide which suppliers to buy from to meet product demand.
The hard part is that sourcing decisions are rarely “cost only”: cheaper suppliers can be less reliable (late deliveries, quality issues, disruptions), while highly reliable suppliers can be more expensive or have limited capacity.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose a feasible order plan that meets demand and supplier capacity constraints, while minimizing total cost.
You can optionally add a reliability penalty to quantify the trade-off between low price and delivery risk, and run disruption scenarios that exclude a supplier entirely.

## Who this is for

- You want a small, end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and the idea of decision variables, constraints, and objectives.

## What you’ll build

- A semantic model of `Supplier`, `Product`, and supplier–product `SupplyOption` data.
- A continuous decision variable (`Order.x_quantity`) for how much to buy through each supply option.
- Constraints that enforce supplier capacity and product demand satisfaction.
- An objective that minimizes procurement cost, with an optional reliability penalty.
- A small scenario analysis loop that re-solves the model after excluding a supplier.

## What’s included

- **Model + solve script**: `supplier_reliability.py`
- **Sample data**: `data/suppliers.csv`, `data/products.csv`, `data/supply_options.csv`
- **Outputs**: solver status/objective per scenario, an orders table per scenario, and a scenario summary

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
   curl -O https://private.relational.ai/templates/zips/v0.13/supplier_reliability.zip
   unzip supplier_reliability.zip
   cd supplier_reliability
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
   python supplier_reliability.py
   ```

6. **Expected output**

   Your exact plan may vary if multiple optima exist, but you should see an OPTIMAL status and an orders table for each scenario:

   ```text
   Running scenario: excluded_supplier = None
      Status: OPTIMAL, Objective: 4850.0

    Orders:
                 name  value
     qty_SupplierB_Gadget  150.0
   qty_SupplierC_Component  200.0
     qty_SupplierC_Gadget  100.0
     qty_SupplierC_Widget  300.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
         None: OPTIMAL, obj=4850.0
         SupplierC: OPTIMAL, obj=6750.0
         SupplierB: OPTIMAL, obj=5150.0
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ supplier_reliability.py      # main runner / entrypoint
└─ data/                        # sample input data
   ├─ suppliers.csv
   ├─ products.csv
   └─ supply_options.csv
```

**Start here**: `supplier_reliability.py`

## Sample data

Data files are in `data/`.

### `suppliers.csv`

Defines the supplier master data (reliability and capacity).

| Column | Meaning |
| --- | --- |
| `id` | Unique supplier identifier |
| `name` | Supplier name (used for labeling variables/output) |
| `reliability` | Reliability score (0 to 1, higher is better) |
| `capacity` | Maximum total units the supplier can provide |

### `products.csv`

Defines product demand requirements.

| Column | Meaning |
| --- | --- |
| `id` | Unique product identifier |
| `name` | Product name (used for labeling variables/output) |
| `demand` | Units required |

### `supply_options.csv`

Defines which suppliers can supply which products, and the per-unit price for each option.

| Column | Meaning |
| --- | --- |
| `id` | Unique supply option identifier |
| `supplier_id` | Foreign key to `suppliers.csv.id` |
| `product_id` | Foreign key to `products.csv.id` |
| `cost_per_unit` | Cost per unit for this supplier–product option |

## Model overview

The semantic model for this template is built around four concepts.

### `Supplier`

Suppliers are the sourcing entities with reliability and total capacity.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/suppliers.csv` |
| `name` | string | No | Used for output labeling and scenario selection |
| `reliability` | float | No | Used in the optional reliability penalty term |
| `capacity` | int | No | Upper bound in the capacity constraint |

### `Product`

Products have demand requirements that must be met.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/products.csv` |
| `name` | string | No | Used for output labeling |
| `demand` | int | No | Lower bound in the demand constraint |

### `SupplyOption`

A feasible supplier–product option with a per-unit cost.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded from `data/supply_options.csv.id` |
| `supplier` | `Supplier` | No | Joined via `data/supply_options.csv.supplier_id` |
| `product` | `Product` | No | Joined via `data/supply_options.csv.product_id` |
| `cost_per_unit` | float | No | Used in the direct cost term |

### `Order` (decision concept)

One decision row per `SupplyOption`, with a non-negative quantity chosen by the solver.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `option` | `SupplyOption` | Yes | One order per supply option |
| `quantity` | float | No | Continuous decision variable, lower-bounded by 0 |
| `supplier` | `Supplier` | No | Derived from `Order.option` |
| `product` | `Product` | No | Derived from `Order.option` |
| `cost_per_unit` | float | No | Derived from `Order.option` |

## How it works

This section walks through the highlights in `supplier_reliability.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs and defines the data folder (`DATA_DIR`), along with the scenario configuration that controls which supplier to exclude:

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

# Parameters.
RELIABILITY_WEIGHT = 0.0  # Penalty weight for unreliable suppliers (0 = cost only).
EXCLUDED_SUPPLIER = None

# Scenarios (what-if analysis).
SCENARIO_PARAM = "excluded_supplier"
SCENARIO_VALUES = [None, "SupplierC", "SupplierB"]
SCENARIO_CONCEPT = "Supplier"  # Entity type for exclusion scenarios.
```

### Define concepts and load CSV data

Next, it creates a `Model`, defines `Supplier`, `Product`, and `SupplyOption`, and loads the CSVs with `data(...).into(...)` and a `where(...).define(...)` join:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("supplier_reliability", config=globals().get("config", None))

# Supplier concept: suppliers with reliability scores and capacity.
Supplier = model.Concept("Supplier")
Supplier.id = model.Property("{Supplier} has {id:int}")
Supplier.name = model.Property("{Supplier} has {name:string}")
Supplier.reliability = model.Property("{Supplier} has {reliability:float}")
Supplier.capacity = model.Property("{Supplier} has {capacity:int}")

# Load supplier data from CSV.
data(read_csv(DATA_DIR / "suppliers.csv")).into(Supplier, keys=["id"])

# Product concept: products with demand requirements.
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.demand = model.Property("{Product} has {demand:int}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["id"])

# SupplyOption concept: supplier–product supply options with a per-unit cost.
SupplyOption = model.Concept("SupplyOption")
SupplyOption.id = model.Property("{SupplyOption} has {id:int}")
SupplyOption.supplier = model.Property("{SupplyOption} from {supplier:Supplier}")
SupplyOption.product = model.Property("{SupplyOption} for {product:Product}")
SupplyOption.cost_per_unit = model.Property("{SupplyOption} has {cost_per_unit:float}")

# Load supply option data from CSV.
options_data = data(read_csv(DATA_DIR / "supply_options.csv"))

# Create one SupplyOption entity per row by joining supplier_id and product_id.
where(
    Supplier.id == options_data.supplier_id,
    Product.id == options_data.product_id
).define(
    SupplyOption.new(
        id=options_data.id,
        supplier=Supplier,
        product=Product,
        cost_per_unit=options_data.cost_per_unit,
    )
)
```

### Define decision variables, constraints, and objective

Then it declares an `Order` decision concept and builds a continuous optimization model. The solver chooses `Order.x_quantity`, enforces capacity and demand with `require(...)`, and minimizes cost (optionally adding a reliability penalty):

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Order decision concept: quantity ordered via each supply option.
Order = model.Concept("Order")
Order.option = model.Property("{Order} uses {option:SupplyOption}")
Order.x_quantity = model.Property("{Order} has {quantity:float}")
define(Order.new(option=SupplyOption))

# Derived properties for direct access in constraints and objective.
Order.supplier = model.Property("{Order} has {supplier:Supplier}")
define(Order.supplier(Supplier)).where(
    Order.option == SupplyOption,
    SupplyOption.supplier == Supplier,
)

Order.product = model.Property("{Order} has {product:Product}")
define(Order.product(Product)).where(
    Order.option == SupplyOption,
    SupplyOption.product == Product,
)

Order.cost_per_unit = model.Property("{Order} has {cost_per_unit:float}")
define(Order.cost_per_unit(SupplyOption.cost_per_unit)).where(Order.option == SupplyOption)


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: order quantity
    s.solve_for(Order.x_quantity, name=["qty", Order.supplier.name, Order.product.name], lower=0)

    # Constraint: total orders from supplier cannot exceed supplier capacity
    capacity_limit = require(
        sum(Order.x_quantity).where(Order.supplier == Supplier).per(Supplier) <= Supplier.capacity
    )
    s.satisfy(capacity_limit)

    # Constraint: demand satisfaction for each product
    meet_demand = require(
        sum(Order.x_quantity).where(Order.product == Product).per(Product) >= Product.demand
    )
    s.satisfy(meet_demand)

    # Constraint: exclude supplier if specified
    if EXCLUDED_SUPPLIER is not None:
        exclude = require(Order.x_quantity == 0).where(Order.supplier.name == EXCLUDED_SUPPLIER)
        s.satisfy(exclude)

    # Objective: minimize cost with optional reliability penalty
    direct_cost = sum(Order.x_quantity * Order.cost_per_unit)
    if RELIABILITY_WEIGHT > 0:
        reliability_penalty = RELIABILITY_WEIGHT * sum(
            Order.x_quantity * (1.0 - Order.supplier.reliability)
        )
        total_cost = direct_cost + reliability_penalty
    else:
        total_cost = direct_cost
    s.minimize(total_cost)
```

### Solve and print results

Finally, the template loops over scenarios, solves with HiGHS, and prints non-trivial order quantities (filtered with `value > 0.001`):

```python
# --------------------------------------------------
# Solve with Scenario Analysis (Supplier Exclusion)
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter (entity to exclude).
    EXCLUDED_SUPPLIER = scenario_value

    # Create a fresh SolverModel for each scenario.
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

    # Print order plan from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["value"] > 0.001)
    ]
    print("\n  Orders:")
    print(qty_df.to_string(index=False))

# Summary.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own data.
- Keep the required headers:
  - `suppliers.csv`: `id`, `name`, `reliability`, `capacity`
  - `products.csv`: `id`, `name`, `demand`
  - `supply_options.csv`: `id`, `supplier_id`, `product_id`, `cost_per_unit`
- Ensure foreign keys match (`supplier_id` exists in `suppliers.csv.id`, and `product_id` exists in `products.csv.id`).

### Tune parameters

Edit parameters in `supplier_reliability.py`:

- `RELIABILITY_WEIGHT`: set to `0.0` for pure cost minimization, or increase it to penalize unreliable sourcing.
- `SCENARIO_VALUES`: change which supplier names are excluded in the what-if scenarios.

### Extend the model

Common extensions include:

- Add per-product maximum sourcing shares (supplier diversification).
- Add fixed costs for activating a supplier.
- Replace the reliability penalty with a hard constraint (e.g., minimum average reliability).

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code> when running the script</summary>

- Confirm your virtual environment is active.
- Reinstall dependencies from the template folder: <code>python -m pip install .</code>
- Confirm you’re using Python 3.10+.

</details>

<details>
<summary>Why does authentication/configuration fail?</summary>

- Run <code>rai init</code> to create/update <code>raiconfig.toml</code>.
- If you have multiple profiles, set <code>RAI_PROFILE</code> or switch profiles in your config.

</details>

<details>
<summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and <code>rai_app_name</code> are correct in <code>raiconfig.toml</code>.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
<summary>CSV loading fails (missing file or column)</summary>

- Confirm the CSVs exist under <code>data/</code> and the filenames match.
- Ensure the headers match the expected schema:
 - <code>suppliers.csv</code>: <code>id</code>, <code>name</code>, <code>reliability</code>, <code>capacity</code>
- <code>products.csv</code>: <code>id</code>, <code>name</code>, <code>demand</code>
- <code>supply_options.csv</code>: <code>id</code>, <code>supplier_id</code>, <code>product_id</code>, <code>cost_per_unit</code>

</details>

<details>
<summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>

- Check that total supplier capacity is sufficient to meet total demand.
- Confirm every product has at least one feasible option in <code>supply_options.csv</code>.
- If you are excluding a supplier, make sure remaining options can still satisfy demand.

</details>

<details>
<summary>Why are my orders empty?</summary>

- The script filters variables with <code>float &gt; 0.001</code>. If you suspect near-zero values, print <code>s.variable_values().to_df()</code> without filtering.
- Confirm demands are non-zero and supply options exist for each product.

</details>
