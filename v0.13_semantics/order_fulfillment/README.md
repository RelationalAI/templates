---
title: "Order Fulfillment"
description: "Assign customer orders to fulfillment centers to minimize total shipping cost."
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

## What is this problem?

E-commerce companies must decide which warehouse should fulfill each order. This template models assigning orders to fulfillment centers where each FC has a capacity limit, a fixed operating cost when used, and variable shipping costs by FC-customer pair.

Simple rules like "ship from nearest warehouse" often fail because the nearest FC may not have inventory, shipping costs aren't always proportional to distance (carrier contracts vary), and capacity constraints create bottlenecks.

## Why is optimization valuable?

- **Shipping cost reduction**: Achieves lower outbound shipping costs through optimal sourcing decisions
- **FC utilization**: Balances fixed costs of using FCs against shipping savings
- **Capacity balancing**: Distributes workload across fulfillment centers to prevent bottlenecks

## What are similar problems?

- **Grocery delivery routing**: Assign orders to dark stores or fulfillment centers for last-mile delivery
- **Parts distribution**: Decide which warehouse ships replacement parts for service requests
- **Call center routing**: Assign incoming calls to agents across multiple call centers
- **Cloud workload placement**: Assign compute jobs to data centers based on capacity and latency

## Problem Details

### Model

**Concepts:**
- `FulfillmentCenter`: Warehouses with capacity and fixed operating costs
- `Order`: Customer orders with quantity requirements
- `Assignment`: Decision entity for order-FC shipping assignment
- `FCUsage`: Tracks whether each FC is activated (for fixed costs)

**Relationships:**
- `Assignment` connects `FulfillmentCenter` → `Order` with shipping cost

### Decision Variables

- `Assignment.qty` (continuous): Units to ship from each FC to each order
- `FCUsage.used` (binary): 1 if FC is used at all, 0 otherwise

### Objective

Minimize total cost (shipping + fixed):
```
minimize sum(quantity * cost_per_unit) + sum(fc_used * fixed_cost)
```

### Constraints

1. **Order fulfillment**: Each order must be completely fulfilled (total quantity assigned equals order quantity)
2. **FC capacity**: Total quantity assigned from each FC cannot exceed its capacity
3. **FC usage linking**: If any quantity is shipped from an FC, that FC is marked as used

## Data

Data files are located in the `data/` subdirectory.

### fulfillment_centers.csv

| Column | Description |
|--------|-------------|
| id | Unique fulfillment center identifier |
| name | FC name (e.g., FC_East) |
| capacity | Maximum units FC can fulfill |
| fixed_cost | Fixed operating cost if FC is used ($) |

### orders.csv

| Column | Description |
|--------|-------------|
| id | Unique order identifier |
| customer | Customer name |
| quantity | Units ordered |
| priority | Priority level (1=highest, 3=lowest) |

### shipping_costs.csv

| Column | Description |
|--------|-------------|
| fc_id | Reference to fulfillment center |
| order_id | Reference to order |
| cost_per_unit | Cost per unit to ship from this FC to this order's destination ($) |

## Usage

```python
from order_fulfillment import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python order_fulfillment.py
```

## Expected Output

```
Status: OPTIMAL
Total cost (shipping + fixed): $1475.00

Assignments:
              name  float
   fc_used_FC_East    1.0
   fc_used_FC_West    1.0
qty_FC_East_Cust_A   25.0
qty_FC_East_Cust_B   15.0
qty_FC_East_Cust_C   15.0
qty_FC_East_Cust_E   20.0
qty_FC_East_Cust_G   25.0
qty_FC_West_Cust_B   15.0
qty_FC_West_Cust_D   40.0
qty_FC_West_Cust_F   35.0
qty_FC_West_Cust_H   30.0
```

The solution shows which FCs are activated and how orders are assigned to minimize total shipping cost. Both FCs are used to balance shipping distances across customers.
