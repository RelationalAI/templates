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

## What is this problem?

Procurement teams must balance cost against supply chain risk. Cheaper suppliers may have reliability issues (delays, quality problems, disruptions), while more reliable suppliers charge premium prices. This template models sourcing products from multiple suppliers with different reliability scores and costs.

The reliability_weight parameter lets you tune the trade-off: set it to 0 for pure cost minimization, or increase it to penalize unreliable suppliers.

## Why is optimization valuable?

- **Risk-aware sourcing**: Quantify the cost of reliability and make informed trade-offs <!-- TODO: Add % improvement from results -->
- **Disruption resilience**: Diversify supplier base to reduce exposure to single points of failure
- **Scenario analysis**: Evaluate impact of supplier issues before they happen, enabling proactive contingency planning

## What are similar problems?

- **Cloud provider selection**: Choose between AWS, Azure, GCP balancing cost, reliability, and vendor lock-in
- **Contract manufacturing allocation**: Distribute production across contract manufacturers with different quality levels
- **Logistics carrier selection**: Choose freight carriers balancing cost and on-time delivery rates
- **IT vendor selection**: Source software/services balancing cost, support quality, and vendor stability

## Problem Details

### Model

**Concepts:**
- `Supplier`: Vendors with reliability scores and capacity
- `Product`: Items to procure
- `SupplierProduct`: Links suppliers to products with cost and lead time
- `Order`: Decision entity for quantity ordered

**Relationships:**
- `SupplierProduct` connects `Supplier` → `Product` with pricing

### Decision Variables

- `Order.quantity` (continuous): Units to order via each supply option

### Objective

Minimize total procurement cost (with optional reliability penalty):
```
minimize sum(quantity * cost_per_unit) + weight * sum(quantity * (1 - reliability))
```

### Constraints

1. **Supplier capacity**: Total orders from each supplier cannot exceed capacity
2. **Demand satisfaction**: Total supply for each product must meet demand

## Data

Data files are located in the `data/` subdirectory.

### suppliers.csv

| Column | Description |
|--------|-------------|
| id | Unique supplier identifier |
| name | Supplier name |
| reliability | On-time delivery probability (0.0 to 1.0) |
| capacity | Maximum units supplier can provide |

### products.csv

| Column | Description |
|--------|-------------|
| id | Unique product identifier |
| name | Product name |
| demand | Units required |

### supply_options.csv

| Column | Description |
|--------|-------------|
| id | Unique option identifier |
| supplier_id | Reference to supplier |
| product_id | Reference to product |
| cost_per_unit | Cost per unit from this supplier ($) |

## Usage

```python
from supplier_reliability import solve, extract_solution

# Pure cost minimization
solver_model = solve(reliability_weight=0.0)
result = extract_solution(solver_model)

# With reliability preference (penalize unreliable suppliers)
solver_model = solve(reliability_weight=50.0)
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
```

Or run directly:

```bash
python supplier_reliability.py
```

## Expected Output

```

Status: OPTIMAL
Total cost: $4850.00
Order quantities:
                   name  float
   qty_SupplierB_Gadget  150.0
qty_SupplierC_Component  200.0
   qty_SupplierC_Gadget  100.0
   qty_SupplierC_Widget  300.0
```

The cost-minimizing solution sources from the cheapest suppliers:
- **SupplierC** (lowest cost, 75% reliability): Widget (300), Gadget (100), Component (200)
- **SupplierB** (mid cost, 85% reliability): Gadget (150)

## Scenario Analysis

This template includes **supplier disruption analysis** — what happens if a key supplier goes offline?

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `excluded_supplier` | Entity (Supplier) | `None`, `"SupplierC"`, `"SupplierB"` | Supplier to exclude from sourcing |

### Expected Results

| Scenario | Objective (Cost) | Impact |
|----------|-----------------|--------|
| Baseline (None) | $4,850 | All suppliers available |
| Exclude SupplierC | $6,750 | +39% — cheapest supplier removed |
| Exclude SupplierB | $5,150 | +6% — moderate cost increase |

SupplierC is the cheapest ($5-7/unit) so excluding it causes the largest cost increase. SupplierB ($8-9/unit) is mid-range, so its exclusion has less impact.