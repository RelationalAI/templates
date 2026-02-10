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

```bash
python supply_chain_transport.py
```

## Expected Output

Decision variables shown for the baseline scenario (no warehouse excluded). The summary below shows objectives for all scenarios.

```text
Running scenario: excluded_warehouse = None
  Status: OPTIMAL, Objective: 2420.0

  Shipments:
                                 name  value
qty_Warehouse_Central_Customer_C_Rail  250.0
qty_Warehouse_Central_Customer_D_Rail   20.0
  qty_Warehouse_East_Customer_A_Truck   80.0
  qty_Warehouse_West_Customer_B_Truck  120.0
   qty_Warehouse_West_Customer_D_Rail  280.0

==================================================
Scenario Analysis Summary
==================================================
  None: OPTIMAL, obj=2420.0
  Warehouse_East: OPTIMAL, obj=2620.0
  Warehouse_Central: OPTIMAL, obj=2690.0
```

## Scenario Analysis

This template includes **facility outage analysis** — what happens when a warehouse goes offline?

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `excluded_warehouse` | Entity (Warehouse) | `None`, `"Warehouse_East"`, `"Warehouse_Central"` | Warehouse to take offline |

Excluding Warehouse_Central (+11%) has a larger impact than Warehouse_East (+8%) because Central has short distances to key high-demand customers, forcing shipments through longer, more expensive routes.
