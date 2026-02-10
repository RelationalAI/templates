---
title: "Markdown Optimization"
description: "Set discount levels for products across a selling season to maximize revenue while clearing inventory."
featured: false
experience_level: intermediate
industry: "Retail"
reasoning_types:
  - Prescriptive
tags:
  - Pricing
  - MILP
---

# Markdown Optimization

## What is this problem?

Retailers must clear seasonal inventory before it loses value, but markdown decisions are complex: deeper discounts drive more sales but at lower margins, and once you mark down a product, you typically can't raise the price again. This template models choosing optimal discount levels (0%, 10%, 20%, 30%, 50%) for products across multiple weeks to maximize revenue recovery.

The challenge is balancing the trade-off between selling early at higher prices versus waiting and potentially needing steeper discounts—or being stuck with unsold inventory that must be salvaged at low value.

## Why is optimization valuable?

- **Revenue recovery**: Achieves higher revenue from clearance inventory compared to rule-based markdowns
- **Inventory turnover**: Clears seasonal merchandise optimally, freeing capital and shelf space
- **Reduced waste**: Less product sent to liquidators or destroyed at end of season

## What are similar problems?

- **Hotel yield management**: Adjust room rates dynamically based on demand and remaining capacity
- **Airline pricing**: Set seat prices across fare classes to maximize revenue before departure
- **Grocery perishables**: Markdown items approaching expiration to minimize spoilage
- **Event ticket pricing**: Adjust prices as event date approaches based on remaining inventory

## Problem Details

### Model

**Concepts:**
- `Product`: Items with initial price, cost, inventory, base demand, and salvage rate
- `Discount`: Available discount levels with demand lift factors
- `TimePeriod`: Weeks in the selling season with demand multipliers

### Decision Variables

- `selected` (binary): 1 if discount level is applied to product in week
- `sales` (continuous): Units sold at each product-week-discount combination
- `cum_sales` (continuous): Cumulative sales through each week for inventory tracking

### Objective

Maximize total revenue from sales plus salvage value of unsold inventory:
```
maximize sum(sales * price * (1 - discount%)) + sum(unsold_inventory * price * salvage_rate)
```

### Constraints

1. **Single discount**: Exactly one discount level per product per week
2. **Price ladder**: Discount level can only stay the same or increase week over week (no price increases)
3. **Sales bound**: Sales cannot exceed demand (base_demand * demand_lift * demand_multiplier * selected)
4. **Inventory balance**: Cumulative sales = previous cumulative sales + current week sales
5. **Inventory limit**: Cumulative sales cannot exceed initial inventory

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
| base_demand | Base weekly demand at full price |
| salvage_rate | Fraction of price recovered for unsold inventory |

### weeks.csv

| Column | Description |
|--------|-------------|
| id | Unique week identifier |
| week_num | Week number in the season (1, 2, 3, 4) |
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
from retail_markdown import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total revenue: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python retail_markdown.py
```

## Expected Output

```
Status: OPTIMAL
Total revenue (sales + salvage): $23374.65

=== Selected Discounts by Product-TimePeriod ===
          name  float
sel_Jacket_1_20.0    1.0
sel_Jacket_2_20.0    1.0
sel_Jacket_3_20.0    1.0
sel_Jacket_4_20.0    1.0
 sel_Pants_1_20.0    1.0
 sel_Pants_2_20.0    1.0
 sel_Pants_3_30.0    1.0
 sel_Pants_4_30.0    1.0
...

=== Cumulative Sales by Product-TimePeriod ===
         name   float
 cum_Jacket_4  55.080
  cum_Pants_4 119.125
  cum_Shirt_4 148.950
cum_Sweater_4  99.300
```

The optimal markdown strategy shows:
- **Gradual price reductions**: Products deepen discounts over time (e.g., Sweater goes 20% → 20% → 30% → 30%)
- **Product-specific strategies**: High-demand products (Sweater, Pants, Shirt) start moderate and deepen; lower-demand products (Jacket) stay conservative
- **Inventory clearing**: Most products sell nearly all inventory; remaining units earn salvage value
- **Price ladder compliance**: No product ever has a price increase week-over-week
