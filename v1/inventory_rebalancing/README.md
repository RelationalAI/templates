---
title: "Inventory Rebalancing"
description: "Transfer inventory between warehouse and store locations to meet demand at minimum shipping cost."
featured: false
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Inventory
  - Supply Chain
  - Transportation
---

# Inventory Rebalancing

## What this template is for

Retail and distribution networks often have inventory spread unevenly across warehouses and stores. Some locations hold excess stock while others face shortages. Manually deciding which transfers to make, from where, and in what quantities quickly becomes impractical as the network grows.

This template uses prescriptive reasoning to determine the optimal set of inventory transfers across a network of sites. It minimizes total shipping cost while ensuring every demand point receives enough stock, respecting lane capacities and available inventory at each source.

The model is a classic network flow formulation that naturally scales to larger networks. It handles multiple source warehouses, destination stores, and shipping lanes with heterogeneous costs and capacities.

## Who this is for

- Supply chain analysts optimizing inventory distribution across locations
- Operations teams managing warehouse-to-store replenishment
- Developers learning network flow optimization with RelationalAI
- Anyone building inventory transfer recommendation systems

## What you'll build

- A network flow model with continuous transfer quantity variables
- Lane capacity and source inventory constraints
- Demand satisfaction constraints at destination sites
- A minimum-cost objective over all shipping lanes

## What's included

- `inventory_rebalancing.py` -- Main script that defines the model, solves it, and prints results
- `data/sites.csv` -- Warehouse and store locations with current inventory levels
- `data/lanes.csv` -- Shipping lanes between sites with per-unit costs and capacities
- `data/demand.csv` -- Demand quantities at destination sites
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/inventory_rebalancing.zip
   unzip inventory_rebalancing.zip
   cd inventory_rebalancing
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python inventory_rebalancing.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total transfer cost: $1750.00

   Transfers:
           from        to  x_quantity
    Warehouse_A   Store_1       200.0
    Warehouse_B   Store_2       100.0
    Warehouse_C   Store_2        70.0
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── inventory_rebalancing.py
└── data/
    ├── sites.csv
    ├── lanes.csv
    └── demand.csv
```

## How it works

### 1. Define the ontology and load data

The model defines three concepts: sites with inventory levels, lanes connecting sites with costs and capacities, and demand at destination sites.

```python
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.inventory = Property(f"{Site} has {Integer:inventory}")

Lane = Concept("Lane", identify_by={"id": Integer})
Lane.source = Property(f"{Lane} from {Site}", short_name="source")
Lane.dest = Property(f"{Lane} to {Site}", short_name="dest")
Lane.cost_per_unit = Property(f"{Lane} has {Float:cost_per_unit}")
Lane.capacity = Property(f"{Lane} has {Integer:capacity}")
```

### 2. Set up decision variables

Each lane gets a continuous transfer quantity variable bounded at zero.

```python
Transfer = Concept("Transfer", identify_by={"lane": Lane})
Transfer.x_quantity = Property(f"{Transfer} has {Float:quantity}")
model.define(Transfer.new(lane=Lane))

s.solve_for(Transfer.x_quantity,
    name=["qty", Transfer.lane.source.name, Transfer.lane.dest.name], lower=0)
```

### 3. Add constraints

Three constraint families ensure feasibility: lane capacity limits, source inventory limits, and demand satisfaction at each destination.

```python
# Lane capacity
capacity_limit = model.require(Transfer.x_quantity <= Transfer.lane.capacity)
s.satisfy(capacity_limit)

# Source inventory
outbound = sum(TransferRef.x_quantity).where(TransferRef.lane.source == Site).per(Site)
s.satisfy(model.require(outbound <= Site.inventory))

# Demand satisfaction (inbound transfers + local inventory >= demand)
inbound = sum(TransferRef.x_quantity).where(TransferRef.lane.dest == DemandRef.site).per(DemandRef)
local_inv = sum(Site.inventory).where(Site == DemandRef.site).per(DemandRef)
s.satisfy(model.require(inbound + local_inv >= DemandRef.quantity))
```

### 4. Minimize total cost

The objective sums shipping costs across all active transfers.

```python
total_cost = sum(Transfer.x_quantity * Transfer.lane.cost_per_unit)
s.minimize(total_cost)
```

## Customize this template

- **Add more sites and lanes** by extending the CSV files to model a larger distribution network.
- **Introduce multi-product inventory** by adding a product dimension to sites, lanes, and demand.
- **Add transfer lead times** and model time-phased demand with delivery windows.
- **Include holding costs** at each site to balance between transfer costs and inventory carrying costs.
- **Add minimum transfer quantities** to model batch shipping requirements.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that total available inventory across all sites is sufficient to meet total demand. With the current data, stores need 250 + 200 = 450 units while warehouses hold 500 + 300 + 200 = 1000 units, plus stores have 50 + 30 = 80 units locally. Also verify that lane capacities allow enough flow to each destination.
</details>

<details>
<summary>Unexpected transfer routes</summary>

The solver minimizes total cost, so it may route through cheaper lanes even if they seem indirect. Check the `cost_per_unit` values in `lanes.csv` to verify the cost structure matches your expectations.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>
