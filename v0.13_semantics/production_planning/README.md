---
title: "Production Planning"
description: "Schedule production across machines to meet demand while maximizing profit."
featured: false
experience_level: beginner
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
---

# Production Planning

## What is this problem?

Manufacturing facilities must coordinate production across machines to meet customer demand while maximizing profit. This template models scheduling discrete production quantities where different products have different profit margins, and machines have varying efficiency (hours per unit) and availability.

The challenge is that demand must be met, but machine capacity is limited—so the optimizer must determine exactly how many units of each product to produce on each machine.

**Note**: This template uses integer (MILP) variables for discrete production units. For high-volume continuous production with machine operating costs factored into the objective, see the `factory_production` template.

## Why is optimization valuable?

- **Profit maximization**: Improves production profitability by optimally allocating constrained capacity to highest-value products <!-- TODO: Add % improvement from results -->
- **Resource efficiency**: Ensures expensive equipment runs on the most profitable work
- **Demand fulfillment**: Meets customer commitments while maximizing margin

## What are similar problems?

- **Semiconductor fab scheduling**: Allocate wafer fab capacity across product families
- **Pharmaceutical batch planning**: Schedule drug production across reactors and packaging lines
- **Steel mill scheduling**: Decide which grades to produce on which rolling mills
- **Contract manufacturing**: Allocate capacity across customer orders with different margins

## Problem Details

### Model

**Concepts:**
- `Product`: Items to manufacture with demand and holding costs
- `Period`: Time buckets for planning horizon
- `Production`: Decision entity for units produced per product-period

**Relationships:**
- `Production` links `Product` → `Period` for multi-period planning

### Decision Variables

- `Production.quantity` (integer): Units to produce on each machine for each product

### Objective

Maximize total profit:
```
maximize sum(quantity * profit_per_unit)
```

### Constraints

1. **Machine hours**: Total production time on each machine cannot exceed hours available
2. **Demand satisfaction**: Total production of each product must meet demand

## Data

Data files are located in the `data/` subdirectory.

### products.csv

| Column | Description |
|--------|-------------|
| id | Unique product identifier |
| name | Product name |
| demand | Units that must be produced |
| profit | Profit per unit ($) |

### machines.csv

| Column | Description |
|--------|-------------|
| id | Unique machine identifier |
| name | Machine name |
| hours_available | Hours available per period |

### production_rates.csv

| Column | Description |
|--------|-------------|
| machine_id | Reference to machine |
| product_id | Reference to product |
| hours_per_unit | Hours required to produce one unit |

## Usage

```python
from production_planning import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total profit: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python production_planning.py
```

## Expected Output

```

Status: OPTIMAL
Total profit: $14945.00
Production schedule:
                  name  float
qty_Machine_1_Widget_A    4.0
qty_Machine_1_Widget_C   95.0
qty_Machine_2_Widget_B   70.0
qty_Machine_3_Widget_A   96.0
qty_Machine_3_Widget_B   11.0
```

The schedule shows which machines produce which products and in what quantities.