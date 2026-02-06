---
title: "Supply Chain Transport"
description: "Route shipments from warehouses to customers using multiple transport modes to minimize cost."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - MILP
  - Transportation
---

# Supply Chain Transport

## What is this problem?

Companies ship products from warehouses to customers using different transport modes (truck, rail, air), each with different costs, transit times, and capacities. This template models choosing the optimal mode for each shipment to minimize total cost while meeting delivery deadlines.

The challenge is that faster modes cost more, but some customers have tight deadlines. The optimizer balances these trade-offs across the entire network.

## Why is optimization valuable?

- **Freight cost reduction**: Achieves savings through optimal mode selection and consolidation
- **Service compliance**: Meet delivery windows at minimum cost by using expensive fast modes only when necessary
- **Network visibility**: Understand total landed cost across all shipment options

## What are similar problems?

- **Parcel carrier selection**: Choose between FedEx, UPS, USPS for each package based on cost and speed
- **LTL vs truckload decisions**: Decide when to consolidate shipments vs ship separately
- **Intermodal routing**: Choose truck-rail-truck combinations for long-haul freight
- **Last-mile delivery**: Select delivery method (courier, locker, store pickup) based on cost and customer preference

## Problem Details

### Model

**Concepts:**
- `Warehouse`: Storage locations with inventory levels
- `Customer`: Demand points with required quantities and due dates
- `TransportMode`: Shipping options with cost, capacity, and transit time
- `Route`: Links warehouses to customers with distance
- `Shipment`: Decision entity for quantity shipped per route-mode

**Relationships:**
- `Route` connects `Warehouse` → `Customer`
- `Shipment` combines `Route` × `TransportMode`

### Decision Variables

- `Shipment.quantity` (continuous): Units to ship via each route/mode combination
- `Shipment.selected` (binary): 1 if shipment route is used, 0 otherwise

### Objective

Minimize total transport cost:
```
minimize sum(quantity * cost_per_unit)
```

### Constraints

1. **Warehouse inventory**: Total outbound shipments from each warehouse cannot exceed available inventory
2. **Customer demand**: Total inbound shipments to each customer must satisfy demand
3. **Mode capacity**: Each shipment cannot exceed the transport mode's capacity
4. **Delivery deadline**: Only modes with transit time within customer's due date can be used

## Data

Data files are located in the `data/` subdirectory.

### warehouses.csv

| Column | Description |
|--------|-------------|
| id | Unique warehouse identifier |
| name | Warehouse name (e.g., Warehouse_East) |
| inventory | Available units in stock |

### customers.csv

| Column | Description |
|--------|-------------|
| id | Unique customer identifier |
| name | Customer name |
| demand | Units required |
| due_day | Delivery deadline (day number) |

### transport_modes.csv

| Column | Description |
|--------|-------------|
| id | Unique transport mode identifier |
| name | Mode name (Truck, Rail, Air) |
| cost_per_unit | Cost to ship one unit ($) |
| transit_days | Days required for delivery |
| capacity | Maximum units per shipment |

### routes.csv

| Column | Description |
|--------|-------------|
| id | Unique route identifier |
| warehouse_id | Reference to warehouse |
| customer_id | Reference to customer |
| distance | Route distance (miles) |

## Usage

```python
from supply_chain_transport import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python supply_chain_transport.py
```

## Expected Output

```
Status: OPTIMAL
Total transport cost: $2100.00

Shipments:
        warehouse   customer  mode  quantity
Warehouse_Central Customer_A Truck      80.0
Warehouse_Central Customer_C  Rail     250.0
   Warehouse_East Customer_B Truck     120.0
   Warehouse_East Customer_D  Rail     300.0
```

The optimal solution demonstrates multi-modal transport selection:
- **Urgent customers** (A, B with due days 1-2) use **Truck** (1-day transit)
- **Regular customers** (C, D with due days 4-5) use **Rail** (3-day transit) for cost savings
- The optimizer selects the lowest-cost combination of warehouse-customer-mode routes

Note: Alternative optimal solutions may route from different warehouses at the same total cost.
