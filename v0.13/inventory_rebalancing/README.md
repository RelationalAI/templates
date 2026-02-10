---
title: "Inventory Rebalancing"
description: "Transfer inventory between warehouse sites to meet demand at minimum cost."
featured: false
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP
---

# Inventory Rebalancing

## What is this problem?

Inventory is often in the wrong place—one warehouse has excess stock while another faces stockouts. This template models transferring inventory between sites via lanes with different costs and capacity limits to meet demand at minimum transfer cost.

The challenge is that simple heuristics ("move from highest inventory to lowest") fail because transfer costs vary by lane, lead times matter, and capacity constraints limit how much can be moved.

## Why is optimization valuable?

- **Stockout prevention**: Reduces lost sales from regional inventory imbalances through proactive redistribution <!-- TODO: Add % improvement from results -->
- **Carrying cost reduction**: Avoids markdowns on excess regional inventory by redistributing before it's too late
- **Transport efficiency**: Minimizes transfer costs compared to rule-based rebalancing through optimal lane selection

## What are similar problems?

- **Blood bank redistribution**: Transfer blood products between hospitals based on expiration dates and demand
- **Rental car rebalancing**: Move vehicles between locations to match demand patterns
- **Bike-share rebalancing**: Redistribute bikes across stations based on predicted demand
- **Spare parts positioning**: Allocate service parts across depots to minimize response time

## Problem Details

### Model

**Concepts:**
- `Location`: Warehouses or stores with current inventory
- `Product`: Items to rebalance
- `Transfer`: Decision entity for units moved between locations

**Relationships:**
- `Transfer` connects source `Location` → destination `Location` for each `Product`

### Decision Variables

- `Transfer.quantity` (continuous): Units to transfer on each lane

### Objective

Minimize total transfer cost:
```
minimize sum(transfer_quantity * lane_cost_per_unit)
```

### Constraints

1. **Lane capacity**: Transfer on each lane cannot exceed lane capacity
2. **Source availability**: Total outbound from a site cannot exceed its inventory
3. **Demand satisfaction**: Inbound transfers + local inventory must meet demand

## Data

Data files are located in the `data/` subdirectory.

### sites.csv

| Column | Description |
|--------|-------------|
| id | Unique site identifier |
| name | Site name (e.g., Warehouse_A, Store_1) |
| inventory | Units of inventory at this site |

### lanes.csv

| Column | Description |
|--------|-------------|
| id | Unique lane identifier |
| source_id | Site where transfer originates |
| dest_id | Site where transfer arrives |
| cost_per_unit | Cost to transfer one unit ($) |
| capacity | Maximum units that can be transferred |

### demand.csv

| Column | Description |
|--------|-------------|
| id | Unique demand identifier |
| site_id | Site where demand exists |
| quantity | Units required |

## Usage

```python
from inventory_rebalancing import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total transfer cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python inventory_rebalancing.py
```

## Expected Output

```

Status: OPTIMAL
Total transfer cost: $1500.00
Transfers:
                   name  float
qty_Warehouse_A_Store_1   50.0
qty_Warehouse_B_Store_1  150.0
qty_Warehouse_B_Store_2   70.0
qty_Warehouse_C_Store_2  100.0
```

The optimal rebalancing plan transfers inventory from warehouses to stores:
- **Store_1** receives 50 units from Warehouse_A + 150 units from Warehouse_B
- **Store_2** receives 70 units from Warehouse_B + 100 units from Warehouse_C