---
title: "Order Fulfillment"
description: "Assign customer orders to fulfillment centers to minimize shipping and fixed costs."
featured: true
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
   - Prescriptive
tags:
   - Allocation
   - MILP
   - E-commerce
---

# Order Fulfillment

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.14` of the `relationalai` Python package.

## What this template is for

E-commerce and retail operations need to decide which fulfillment center should ship each order.
This template models a capacity-constrained assignment problem where shipping costs vary by fulfillment center and customer, and each fulfillment center also incurs a fixed operating cost if it is used.
The model is solved using **prescriptive reasoning (optimization)** to minimize total costs while fulfilling all orders.

Prescriptive reasoning helps you:

- **Reduce total fulfillment cost** by optimizing assignments end-to-end.
- **Balance capacity** across fulfillment centers.
- **Trade off fixed vs. variable costs** by deciding which facilities to activate.

## Who this is for

- You want a small, end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear optimization concepts.

## What you’ll build

- A semantic model of fulfillment centers, orders, and shipping costs.
- A mixed-integer linear program (MILP) with shipment quantities and binary activation variables.
- Capacity and fulfillment constraints defined with `require(...)`.
- A solve step using the **HiGHS** backend with readable printed results.

## What’s included

- **Model + solve script**: `order_fulfillment.py`
- **Sample data**: `data/fulfillment_centers.csv`, `data/orders.csv`, `data/shipping_costs.csv`
- **Outputs**: printed solver status, objective value, an assignment table, and active fulfillment centers

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
   curl -O https://private.relational.ai/templates/zips/v0.14/order_fulfillment.zip
   unzip order_fulfillment.zip
   cd order_fulfillment
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

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python order_fulfillment.py
   ```

6. **Expected output**

   ```text
   Status: OPTIMAL
   Total cost (shipping + fixed): $1475.00

   Assignments:
   fulfillment_center customer  quantity
              FC_East   Cust_A      25.0

   Active fulfillment centers: FC_East, FC_West
   ```

> [!NOTE]
> Alternative optimal solutions may split orders differently at the same total cost.

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ order_fulfillment.py     # main runner / entrypoint
└─ data/                    # sample input data
   ├─ fulfillment_centers.csv
   ├─ orders.csv
   └─ shipping_costs.csv
```

**Start here**: `order_fulfillment.py`

## Sample data

Data files are in `data/`.

### `fulfillment_centers.csv`

Lists fulfillment centers, their capacity, and fixed cost to activate.

| Column | Meaning |
| --- | --- |
| `id` | Unique fulfillment center identifier |
| `name` | Fulfillment center name (for display) |
| `capacity` | Maximum units the center can ship |
| `fixed_cost` | Fixed operating cost if the center is used |

### `orders.csv`

Lists customer orders and their required quantities.

| Column | Meaning |
| --- | --- |
| `id` | Unique order identifier |
| `customer` | Customer name (for display) |
| `quantity` | Units ordered |
| `priority` | Priority level (loaded but not used in the optimization model) |

### `shipping_costs.csv`

Defines per-unit shipping costs for each (fulfillment center, order) pair.

| Column | Meaning |
| --- | --- |
| `fc_id` | Fulfillment center ID |
| `order_id` | Order ID |
| `cost_per_unit` | Cost per unit shipped |

## Model overview

The semantic model includes three data concepts and two decision concepts.

### `FulfillmentCenter`

Represents a fulfillment center that may be activated and used to ship orders.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded from `data/fulfillment_centers.csv` |
| `name` | string | No | Used for output labeling |
| `capacity` | int | No | Capacity constraint bound |
| `fixed_cost` | float | No | Fixed cost if used |

### `Order`

Represents a customer order that must be fully fulfilled.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded from `data/orders.csv` |
| `customer` | string | No | Used for output labeling |
| `quantity` | int | No | Fulfillment constraint RHS |
| `priority` | int | No | Loaded but not used in the model |

### `ShippingCost`

Represents a per-unit shipping cost for shipping an order from a fulfillment center.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `fc` | `FulfillmentCenter` | No | Joined via `shipping_costs.csv.fc_id` |
| `order` | `Order` | No | Joined via `shipping_costs.csv.order_id` |
| `cost_per_unit` | float | No | Per-unit cost |

### `Assignment` (decision concept)

Represents how much quantity is shipped for each `ShippingCost` option.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `shipping` | `ShippingCost` | No | Links to FC, order, and cost |
| `qty` | float | No | Decision variable (continuous, non-negative) |

### `FCUsage` (decision concept)

Tracks whether a fulfillment center is used at all.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `fc` | `FulfillmentCenter` | No | One row per center |
| `used` | float | No | Binary decision variable |

## How it works

This section walks through the highlights in `order_fulfillment.py`.

### Import libraries and configure inputs

First, the script imports the Semantics and optimization APIs, configures the data directory, and sets the pandas option used by templates that target relationalai versions prior to v1.0:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, select, sum, where
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

Next, it creates a `Model`, defines concepts for fulfillment centers and orders, and loads the CSVs with `data(...).into(...)`. It also defines `ShippingCost` rows by joining IDs from `shipping_costs.csv` using `where(...).define(...)`:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("order_fulfillment", config=globals().get("config", None))

# FulfillmentCenter concept: fulfillment centers with capacity and fixed operating costs.
FC = model.Concept("FulfillmentCenter")
FC.id = model.Property("{FulfillmentCenter} has {id:int}")
FC.name = model.Property("{FulfillmentCenter} has {name:string}")
FC.capacity = model.Property("{FulfillmentCenter} has {capacity:int}")
FC.fixed_cost = model.Property("{FulfillmentCenter} has {fixed_cost:float}")

# Load fulfillment center data from CSV.
data(read_csv(DATA_DIR / "fulfillment_centers.csv")).into(FC, keys=["id"])

# Order concept: customer orders with required quantity and priority.
Order = model.Concept("Order")
Order.id = model.Property("{Order} has {id:int}")
Order.customer = model.Property("{Order} for {customer:string}")
Order.quantity = model.Property("{Order} has {quantity:int}")
Order.priority = model.Property("{Order} has {priority:int}")

# Load order data from CSV.
data(read_csv(DATA_DIR / "orders.csv")).into(Order, keys=["id"])

# ShippingCost concept: per-unit shipping cost for an FC/order pair.
ShippingCost = model.Concept("ShippingCost")
ShippingCost.fc = model.Relationship("{ShippingCost} from {fc:FulfillmentCenter}")
ShippingCost.order = model.Relationship("{ShippingCost} for {order:Order}")
ShippingCost.cost_per_unit = model.Property("{ShippingCost} has {cost_per_unit:float}")

# Load shipping cost data from CSV.
costs_data = data(read_csv(DATA_DIR / "shipping_costs.csv"))

# Define ShippingCost entities by joining FC and Order IDs from the CSV.
where(
    FC.id == costs_data.fc_id,
    Order.id == costs_data.order_id,
).define(
    ShippingCost.new(fc=FC, order=Order, cost_per_unit=costs_data.cost_per_unit)
)
```

### Define decision variables, constraints, and objective

Then it creates decision concepts, declares decision variables with `solve_for(...)`, and adds constraints and the objective using `require(...)`, `satisfy(...)`, and `minimize(...)`:

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Assignment decision concept: shipment quantity for each shipping-cost option.
Assignment = model.Concept("Assignment")
Assignment.shipping = model.Relationship("{Assignment} uses {shipping:ShippingCost}")
Assignment.x_qty = model.Property("{Assignment} has {qty:float}")
define(Assignment.new(shipping=ShippingCost))

# FCUsage decision concept: whether each fulfillment center is active (for fixed costs).
FCUsage = model.Concept("FCUsage")
FCUsage.fc = model.Relationship("{FCUsage} for {fc:FulfillmentCenter}")
FCUsage.x_used = model.Property("{FCUsage} is {used:float}")
define(FCUsage.new(fc=FC))

AssignmentRef = Assignment.ref()

s = SolverModel(model, "cont")

# Decision variables: assignment quantity and fulfillment-center usage.
s.solve_for(
    Assignment.x_qty,
    name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer],
    lower=0,
)
s.solve_for(FCUsage.x_used, type="bin", name=["fc_used", FCUsage.fc.name])

# Constraint: FC capacity
fc_total_qty = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FC).per(FC)
capacity_limit = require(fc_total_qty <= FC.capacity)
s.satisfy(capacity_limit)

# Constraint: link FC usage to assignments
fc_total_qty_for_usage = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FCUsage.fc).per(FCUsage)
usage_link = require(fc_total_qty_for_usage <= FCUsage.fc.capacity * FCUsage.x_used)
s.satisfy(usage_link)

# Constraint: each order must be fully fulfilled
order_fulfilled = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.order == Order).per(Order)
fulfill_all = require(order_fulfilled == Order.quantity)
s.satisfy(fulfill_all)

# Objective: minimize total cost (shipping + fixed FC costs)
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.x_used * FCUsage.fc.fixed_cost)
total_cost = shipping_cost + fixed_cost
s.minimize(total_cost)
```

### Solve and print results

Finally, it solves with `Solver("highs")` and prints the assignments and the active fulfillment centers (with output filters `Assignment.x_qty > 0.001` and `FCUsage.x_used > 0.5`):

```python
# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost (shipping + fixed): ${s.objective_value:.2f}")

assignments = select(
    Assignment.shipping.fc.name.alias("fulfillment_center"),
    Assignment.shipping.order.customer.alias("customer"),
    Assignment.x_qty.alias("quantity")
).where(Assignment.x_qty > 0.001).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

fc_used = select(FCUsage.fc.name.alias("fc")).where(FCUsage.x_used > 0.5).to_df()
print(f"\nActive fulfillment centers: {', '.join(fc_used['fc'].tolist())}")
```

## Troubleshooting

<details>
  <summary>I get <code>ModuleNotFoundError</code> when running the script</summary>

  - Confirm you created and activated the virtual environment from the Quickstart.
  - Reinstall dependencies with `python -m pip install .`.
  - Verify you are running `python order_fulfillment.py` from the `order_fulfillment/` folder.
</details>

<details>
  <summary>The script fails while reading a CSV from <code>data/</code></summary>

  - Confirm the files exist in `data/`.
  - Verify CSV headers match the expected columns listed in the Sample data section.
  - Check for missing values in key columns (IDs and costs).
</details>

<details>
  <summary>I see <code>Status: INFEASIBLE</code></summary>

  - Check that total order quantities do not exceed total fulfillment capacity.
  - Confirm that every order has at least one matching row in `shipping_costs.csv`.
  - Verify capacities and quantities are non-negative.
</details>

<details>
  <summary>The <code>Assignments</code> table is empty</summary>

  - The output is filtered to `Assignment.x_qty > 0.001`; very small assignments will not display.
  - If the objective is 0, confirm `shipping_costs.csv.cost_per_unit` is non-zero and that orders have positive quantities.
</details>
