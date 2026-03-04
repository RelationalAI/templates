---
title: "Order Fulfillment"
description: "Assign customer orders to fulfillment centers to minimize total shipping and fixed operating costs."
featured: false
experience_level: intermediate
industry: "Retail & E-Commerce"
reasoning_types:
  - Prescriptive
tags:
  - Fulfillment
  - Logistics
  - Facility Location
---

# Order Fulfillment

## What this template is for

E-commerce and retail businesses must decide which fulfillment centers should handle each customer order. Shipping costs vary by origin-destination pair, each center has limited capacity, and opening a center incurs a fixed operating cost. The challenge is to fulfill all orders at the lowest total cost while deciding which centers to activate.

This template uses prescriptive reasoning to optimally assign orders to fulfillment centers. It minimizes the combined cost of per-unit shipping and fixed facility costs, while ensuring every order is completely fulfilled and no center exceeds its capacity. The model automatically determines which centers to open based on cost efficiency.

This is a facility location and allocation problem, a foundational pattern in logistics optimization. It combines continuous assignment variables with binary facility-open decisions, making it a practical mixed-integer programming example.

## Who this is for

- E-commerce operations teams optimizing order routing across fulfillment networks
- Logistics analysts evaluating facility location and capacity decisions
- Developers learning mixed-integer programming with fixed-charge costs
- Anyone building order allocation or warehouse selection systems

## What you'll build

- A multi-center order assignment model with continuous quantity variables
- Binary variables tracking which fulfillment centers are activated
- Capacity constraints per fulfillment center
- Full order fulfillment constraints ensuring every order is satisfied
- A combined shipping cost + fixed cost minimization objective

## What's included

- `order_fulfillment.py` -- Main script that defines the model, solves it, and prints results
- `data/fulfillment_centers.csv` -- Centers with capacity limits and fixed operating costs
- `data/orders.csv` -- Customer orders with quantities and priority levels
- `data/shipping_costs.csv` -- Per-unit shipping costs between each center and order
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/order_fulfillment.zip
   unzip order_fulfillment.zip
   cd order_fulfillment
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
   python order_fulfillment.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total cost (shipping + fixed): $1897.50

   Assignments:
    fulfillment_center customer  quantity
               FC_East   Cust_A      25.0
               FC_East   Cust_C      15.0
               FC_East   Cust_E      20.0
               FC_West   Cust_B      30.0
               FC_West   Cust_D      40.0
               FC_West   Cust_F      35.0
               FC_West   Cust_G      15.0
           FC_Central   Cust_G      10.0
           FC_Central   Cust_H      30.0

   Active fulfillment centers: FC_East, FC_West, FC_Central
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── order_fulfillment.py
└── data/
    ├── fulfillment_centers.csv
    ├── orders.csv
    └── shipping_costs.csv
```

## How it works

### 1. Define the ontology and load data

The model defines fulfillment centers with capacity and fixed costs, orders with customer details and quantities, and a shipping cost relationship connecting every center-order pair.

```python
FC = Concept("FulfillmentCenter", identify_by={"id": Integer})
FC.name = Property(f"{FC} has {String:name}")
FC.capacity = Property(f"{FC} has {Integer:capacity}")
FC.fixed_cost = Property(f"{FC} has {Float:fixed_cost}")

Order = Concept("Order", identify_by={"id": Integer})
Order.customer = Property(f"{Order} for {String:customer}")
Order.quantity = Property(f"{Order} has {Integer:quantity}")

ShippingCost = Concept("ShippingCost")
ShippingCost.fc = Property(f"{ShippingCost} from {FC}", short_name="fc")
ShippingCost.order = Property(f"{ShippingCost} for {Order}", short_name="order")
ShippingCost.cost_per_unit = Property(f"{ShippingCost} has {Float:cost_per_unit}")
```

### 2. Set up decision variables

Two types of variables: continuous assignment quantities for how much each center ships per order, and binary usage flags for whether each center is active.

```python
s.solve_for(Assignment.x_qty,
    name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer], lower=0)
s.solve_for(FCUsage.x_used, type="bin", name=["fc_used", FCUsage.fc.name])
```

### 3. Add constraints

Capacity limits at each center, linkage between usage flags and assignment quantities, and full order fulfillment requirements.

```python
# FC capacity
fc_total_qty = sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FC).per(FC)
s.satisfy(model.require(fc_total_qty <= FC.capacity))

# Link usage flag to assignments
fc_total_qty_for_usage = sum(AssignmentRef.x_qty).where(
    AssignmentRef.shipping.fc == FCUsage.fc).per(FCUsage)
s.satisfy(model.require(fc_total_qty_for_usage <= FCUsage.fc.capacity * FCUsage.x_used))

# Every order fully fulfilled
order_fulfilled = sum(AssignmentRef.x_qty).where(
    AssignmentRef.shipping.order == Order).per(Order)
s.satisfy(model.require(order_fulfilled == Order.quantity))
```

### 4. Minimize total cost

The objective combines variable shipping costs with fixed facility activation costs.

```python
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.x_used * FCUsage.fc.fixed_cost)
s.minimize(shipping_cost + fixed_cost)
```

## Customize this template

- **Add more fulfillment centers or orders** by extending the CSV files.
- **Introduce order priorities** by weighting shipping costs or adding service-level constraints for high-priority orders.
- **Add product types** so each center has product-specific capacities and costs.
- **Model split-order penalties** to discourage fulfilling a single order from multiple centers.
- **Add delivery time constraints** using distance or zone-based lead times per center-order pair.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that total fulfillment center capacity (100 + 120 + 80 = 300 units) can cover total order quantity (25 + 30 + 15 + 40 + 20 + 35 + 25 + 30 = 220 units). If you add orders or reduce capacity, the problem may become infeasible.
</details>

<details>
<summary>All fulfillment centers are active</summary>

If total demand is high relative to individual center capacities, the solver must activate all centers to meet demand. To see center consolidation, reduce demand or increase center capacities.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>
