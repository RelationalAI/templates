# Order Fulfillment

Assign customer orders to fulfillment centers to minimize total shipping cost.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Allocation |
| **Industry** | E-commerce / Logistics |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Beginner |

## What is this problem?

E-commerce companies must decide which warehouse should fulfill each order. This template models assigning orders to fulfillment centers where each FC has a capacity limit and shipping costs vary by FC-customer pair.

Simple rules like "ship from nearest warehouse" often fail because the nearest FC may not have inventory, shipping costs aren't always proportional to distance (carrier contracts vary), and capacity constraints create bottlenecks.

## Why is optimization valuable?

- **Shipping cost reduction**: Achieves lower outbound shipping costs through optimal sourcing decisions <!-- TODO: Add % improvement from results -->
- **Delivery speed**: Improved on-time delivery by selecting FCs that can actually fulfill orders quickly
- **Capacity balancing**: Distributes workload across fulfillment centers to prevent bottlenecks

## What are similar problems?

- **Grocery delivery routing**: Assign orders to dark stores or fulfillment centers for last-mile delivery
- **Parts distribution**: Decide which warehouse ships replacement parts for service requests
- **Call center routing**: Assign incoming calls to agents across multiple call centers
- **Cloud workload placement**: Assign compute jobs to data centers based on capacity and latency

## Problem Description

An e-commerce company has multiple fulfillment centers (FCs) across regions. Customer orders arrive and must be assigned to FCs for fulfillment. Each FC has a capacity limit and each FC-customer pair has a different shipping cost.

The goal is to assign orders to fulfillment centers to minimize total shipping cost while ensuring all orders are completely fulfilled and no FC exceeds its capacity.

### Decision Variables

- `Assignment.quantity` (continuous): Units to ship from each FC to each order
- `Assignment.selected` (binary): 1 if FC-order assignment is used, 0 otherwise

### Objective

Minimize total shipping cost:
```
minimize sum(quantity * cost_per_unit)
```

### Constraints

1. **Order fulfillment**: Each order must be completely fulfilled (total quantity assigned equals order quantity)
2. **FC capacity**: Total quantity assigned from each FC cannot exceed its capacity

## Data

Data files are located in the `data/` subdirectory.

### fulfillment_centers.csv

| Column | Description |
|--------|-------------|
| id | Unique fulfillment center identifier |
| name | FC name (e.g., FC_East) |
| capacity | Maximum units FC can fulfill |
| fixed_cost | Fixed operating cost ($) |

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

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Total Shipping Cost: $X.XX
...
```
