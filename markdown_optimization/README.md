# Markdown Optimization

Set discount levels for products across a selling season to maximize revenue.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Pricing |
| **Industry** | Retail |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Retailers must clear seasonal inventory before it loses value, but markdown decisions are complex: deeper discounts drive more sales but at lower margins, and once you mark down a product, you typically can't raise the price again. This template models choosing optimal discount levels (0%, 10%, 20%, 30%, 50%) for products across multiple weeks to maximize revenue recovery.

The challenge is balancing the trade-off between selling early at higher prices versus waiting and potentially needing steeper discounts—or being stuck with unsold inventory.

## Why is optimization valuable?

- **Revenue recovery**: Achieves higher revenue from clearance inventory compared to rule-based markdowns <!-- TODO: Add % improvement from results -->
- **Inventory turnover**: Clears seasonal merchandise faster, freeing capital and shelf space
- **Reduced waste**: Less product sent to liquidators or destroyed at end of season

## What are similar problems?

- **Hotel yield management**: Adjust room rates dynamically based on demand and remaining capacity
- **Airline pricing**: Set seat prices across fare classes to maximize revenue before departure
- **Grocery perishables**: Markdown items approaching expiration to minimize spoilage
- **Event ticket pricing**: Adjust prices as event date approaches based on remaining inventory

## Problem Details

### Model

**Concepts:**
- `Product`: Items with initial price, cost, and inventory
- `Discount`: Available discount levels with demand lift factors
- `PricingDecision`: Decision entity for discount selection per product-week

**Relationships:**
- `PricingDecision` connects `Product` → `Discount` for each time period

### Decision Variables

- `PricingDecision.selected` (binary): 1 if discount level is applied to product in week, 0 otherwise

### Objective

Maximize total revenue:
```
maximize sum(discounted_price * estimated_demand)
```

Where estimated demand increases with deeper discounts (demand lift) but decreases over time (demand multiplier).

### Constraints

1. **Single discount**: Exactly one discount level per product per week
2. **No price increases**: Discount level can only stay the same or increase week over week

## Data

Data files are located in the `data/` subdirectory.

### products.csv

| Column | Description |
|--------|-------------|
| id | Unique product identifier |
| name | Product name |
| initial_price | Starting price before any discount ($) |
| cost | Product cost ($) |
| initial_inventory | Units available to sell |

### weeks.csv

| Column | Description |
|--------|-------------|
| id | Unique week identifier |
| week_num | Week number in the season (1, 2, 3, ...) |
| demand_multiplier | Seasonal demand factor (1.0 = normal, decreases over time) |

### discounts.csv

| Column | Description |
|--------|-------------|
| id | Unique discount level identifier |
| level | Discount tier (0=none, 1=small, 2=medium, etc.) |
| discount_pct | Percentage discount (0, 10, 20, 30, 50) |
| demand_lift | Multiplier on base demand (1.0 for no discount, higher for deeper discounts) |

## Usage

```python
from markdown_optimization import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total revenue: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python markdown_optimization.py
```

## Expected Output

```

Status: OPTIMAL
Total expected revenue: $51128.00
Pricing decisions:
     name  float
dec_1_1_4    1.0
dec_1_2_4    1.0
dec_1_3_4    1.0
dec_1_4_4    1.0
dec_2_1_4    1.0
dec_2_2_4    1.0
dec_2_3_4    1.0
dec_2_4_4    1.0
dec_3_1_4    1.0
dec_3_2_4    1.0
dec_3_3_4    1.0
dec_3_4_4    1.0
dec_4_1_4    1.0
dec_4_2_4    1.0
dec_4_3_4    1.0
dec_4_4_4    1.0
```