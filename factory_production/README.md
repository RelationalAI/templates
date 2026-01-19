# Factory Production

Schedule production across machines to maximize profit while meeting minimum requirements.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Allocation |
| **Industry** | Manufacturing |
| **Method** | LP (Linear Programming) |
| **Complexity** | Beginner |

## What is this problem?

Manufacturing facilities must decide what to produce given limited resources. This template models a factory with multiple machines producing different products, where each machine has limited hours available and different hourly operating costs. Each product has a selling price and minimum production requirement.

The goal is to find the optimal product mix—how much of each product to make on each machine—to maximize profit (revenue minus machine operating costs) while respecting machine capacity and meeting minimum production targets.

**Note**: This template uses continuous (LP) variables suitable for high-volume production where fractional units are acceptable. For discrete production units, see the `production_planning` template which uses integer variables.

## Why is optimization valuable?

- **Profit maximization**: Improves production profitability by finding the best product mix <!-- TODO: Add % improvement from results -->
- **Resource utilization**: Better use of expensive equipment and skilled labor through mathematically optimal scheduling
- **Demand fulfillment**: Prioritizes production to meet the most valuable orders when capacity is constrained

## What are similar problems?

- **Job shop scheduling**: Assign jobs to machines to minimize makespan or maximize throughput
- **Refinery blending**: Determine crude oil mix and process routing to maximize margin
- **Bakery production**: Decide daily quantities of bread, pastries, and cakes given oven capacity
- **Print shop scheduling**: Allocate press time across print jobs to maximize revenue

## Problem Description

A factory has multiple machines that can produce different products. Each machine has limited hours available per period and an operating cost per hour. Each product has a selling price and a minimum production requirement. Different machines take different amounts of time to produce each product.

The goal is to determine how many units of each product to produce on each machine to maximize profit (revenue minus machine costs) while meeting minimum production requirements.

### Decision Variables

- `Production.quantity` (continuous): Units to produce on each machine for each product

### Objective

Maximize total profit:
```
maximize sum(quantity * product_price) - sum(hours_used * hourly_cost)
```

### Constraints

1. **Machine capacity**: Total production hours on each machine cannot exceed hours available
2. **Minimum production**: Total production of each product must meet minimum requirement

## Data

Data files are located in the `data/` subdirectory.

### machines.csv

| Column | Description |
|--------|-------------|
| id | Unique machine identifier |
| name | Machine name |
| hours_available | Hours available per period |
| hourly_cost | Operating cost per hour ($) |

### products.csv

| Column | Description |
|--------|-------------|
| id | Unique product identifier |
| name | Product name |
| price | Selling price per unit ($) |
| min_production | Minimum units that must be produced |

### production_times.csv

| Column | Description |
|--------|-------------|
| machine_id | Reference to machine |
| product_id | Reference to product |
| hours_per_unit | Hours required to produce one unit |

## Usage

```python
from factory_production import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total profit: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python factory_production.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Total Profit: $X.XX
...
```
