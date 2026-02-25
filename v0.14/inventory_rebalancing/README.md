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

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13` of the `relationalai` Python package.

## What this template is for

Inventory is often in the wrong place: one warehouse has excess stock while another location is at risk of stockouts.
This template models a small **inventory transfer** problem where you move units from source sites to destination sites through a set of transfer lanes.

The goal is to meet demand at each destination site while respecting lane capacities and available source inventory, and doing so at **minimum total transfer cost**.
It’s an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI Semantics.

## Who this is for

- You want a small, end-to-end example of prescriptive reasoning (optimization) using RelationalAI Semantics.
- You’re comfortable with basic Python and the idea of decision variables, constraints, and objectives.

## What you’ll build

- A semantic model for `Site`, `Lane`, and `Demand` loaded from CSV.
- A linear program (LP) with one non-negative transfer decision variable per lane.
- Constraints for lane capacity, source inventory limits, and demand satisfaction.
- A cost-minimizing objective and a solve step using the **HiGHS** backend.

## What’s included

- `inventory_rebalancing.py` — defines the semantic model, optimization problem, and prints a solution
- `data/` — sample CSV inputs (`sites.csv`, `lanes.csv`, `demand.csv`)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/inventory_rebalancing.zip
   unzip inventory_rebalancing.zip
   cd inventory_rebalancing
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python inventory_rebalancing.py
   ```

6. **Expected output**

   ```text
   Status: OPTIMAL
   Total transfer cost: $1500.00

   Transfers:
          from      to  quantity
   Warehouse_B Store_1     150.0
   Warehouse_A Store_1      50.0
   Warehouse_C Store_2     100.0
   Warehouse_B Store_2      70.0
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ inventory_rebalancing.py   # main runner / entrypoint
└─ data/                      # sample input data
   ├─ demand.csv
   ├─ lanes.csv
   └─ sites.csv
```

**Start here**: `inventory_rebalancing.py`

## Sample data

Data files are in `data/`.

### `sites.csv`

Each row is a site (warehouse or store) with its current on-hand inventory.

| Column | Meaning |
| --- | --- |
| `id` | Unique site identifier |
| `name` | Site name (used for readable output) |
| `inventory` | Current inventory available at the site |

### `lanes.csv`

Each row is a directed transfer lane from a source site to a destination site.

| Column | Meaning |
| --- | --- |
| `id` | Unique lane identifier |
| `source_id` | Source site ID (foreign key to `sites.csv.id`) |
| `dest_id` | Destination site ID (foreign key to `sites.csv.id`) |
| `cost_per_unit` | Cost to transfer one unit on this lane |
| `capacity` | Maximum transferable units on this lane |

### `demand.csv`

Each row is a demand requirement at a site.

| Column | Meaning |
| --- | --- |
| `id` | Unique demand record identifier |
| `site_id` | Site ID where demand must be met (foreign key to `sites.csv.id`) |
| `quantity` | Required units at the site |

## Model overview

The optimization model is built around four concepts.

### `Site`

A warehouse or store location that has current inventory.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/sites.csv` |
| `name` | string | No | Used for output labeling |
| `inventory` | int | No | Used to limit total outbound transfers |

### `Lane`

A directed transfer option between two sites.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/lanes.csv` |
| `source` | `Site` | No | Resolved from `data/lanes.csv.source_id` |
| `dest` | `Site` | No | Resolved from `data/lanes.csv.dest_id` |
| `cost_per_unit` | float | No | Cost coefficient in the objective |
| `capacity` | int | No | Upper bound for each lane’s transfer |

### `Demand`

A demand requirement at a site.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Primary key loaded from `data/demand.csv` |
| `site` | `Site` | No | Site where demand must be met |
| `quantity` | int | No | Required units |

### `Transfer` (decision concept)

One transfer decision is created for each `Lane`. The solver chooses a non-negative quantity.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `lane` | `Lane` | Yes | One decision per lane |
| `quantity` | float | No | Continuous decision variable ($\ge 0$) |

## How it works

This section walks through the highlights in `inventory_rebalancing.py`.

### Import libraries and configure inputs

This template uses `Concept` objects from the `relationalai.semantics` module to model sites, lanes, and demands, and uses the `Solver` and `SolverModel` classes from `relationalai.semantics.reasoners.optimization` to define and solve the optimization problem:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False
```

### Define concepts and load CSV data

First, declare a `Site` concept and load one entity per row in `sites.csv` using `data(...).into(...)`.

```python
model = Model("inventory_rebalancing", config=globals().get("config", None), use_lqp=False)

# Concept: sites with current inventory
Site = model.Concept("Site")
Site.id = model.Property("{Site} has {id:int}")
Site.name = model.Property("{Site} has {name:string}")
Site.inventory = model.Property("{Site} has {inventory:int}")

# Load site data from CSV and populate the Site concept.
data(read_csv(DATA_DIR / "sites.csv")).into(Site, keys=["id"])
```

Next, declare a `Lane` concept for directed transfer options and use a `where(...)` join to resolve `source_id` and `dest_id` into `Site` entity references.

```python
# Relationship: lanes between sites with cost and capacity
Lane = model.Concept("Lane")
Lane.id = model.Property("{Lane} has {id:int}")
Lane.source = model.Property("{Lane} from {source:Site}")
Lane.dest = model.Property("{Lane} to {dest:Site}")
Lane.cost_per_unit = model.Property("{Lane} has {cost_per_unit:float}")
Lane.capacity = model.Property("{Lane} has {capacity:int}")

# Load lane data from CSV and create Lane entities.
lanes_data = data(read_csv(DATA_DIR / "lanes.csv"))
Dest = Site.ref()
where(
    Site.id == lanes_data.source_id,
    Dest.id == lanes_data.dest_id
).define(
    Lane.new(
        id=lanes_data.id,
        source=Site,
        dest=Dest,
        cost_per_unit=lanes_data.cost_per_unit,
        capacity=lanes_data.capacity
    )
)
```

  Finally, declare a `Demand` concept and join `demand.csv.site_id` to the matching `Site` entity.

```python
# Concept: demand at each site
Demand = model.Concept("Demand")
Demand.id = model.Property("{Demand} has {id:int}")
Demand.site = model.Property("{Demand} at {site:Site}")
Demand.quantity = model.Property("{Demand} has {quantity:int}")

# Load demand data from CSV and create Demand entities.
demand_data = data(read_csv(DATA_DIR / "demand.csv"))
where(Site.id == demand_data.site_id).define(
    Demand.new(id=demand_data.id, site=Site, quantity=demand_data.quantity)
)
```

### Define decision variables, constraints, and objective

Create a `Transfer` decision concept and register one continuous, non-negative decision variable per lane.

```python
# Decision concept: transfers on each lane
Transfer = model.Concept("Transfer")
Transfer.lane = model.Property("{Transfer} uses {lane:Lane}")
Transfer.x_quantity = model.Property("{Transfer} has {quantity:float}")
define(Transfer.new(lane=Lane))

Tr = Transfer.ref()
Dm = Demand.ref()

s = SolverModel(model, "cont")

# Variable: transfer quantity
s.solve_for(Transfer.x_quantity, name=["qty", Transfer.lane.source.name, Transfer.lane.dest.name], lower=0)
```

Then add constraints to enforce lane capacities, limit total outbound shipments by source inventory, and meet destination demand (allowing local inventory to contribute):

```python
# Constraint: transfer cannot exceed lane capacity
capacity_limit = require(Transfer.x_quantity <= Transfer.lane.capacity)
s.satisfy(capacity_limit)

# Constraint: total outbound from source cannot exceed source inventory
outbound = sum(Tr.quantity).where(Tr.lane.source == Site).per(Site)
inventory_limit = require(outbound <= Site.inventory)
s.satisfy(inventory_limit)

# Constraint: demand satisfaction at each destination site
inbound = sum(Tr.quantity).where(Tr.lane.dest == Dm.site).per(Dm)
local_inv = sum(Site.inventory).where(Site == Dm.site).per(Dm)
demand_met = require(inbound + local_inv >= Dm.quantity)
s.satisfy(demand_met)
```

With the feasible region defined, minimize the total transfer cost (quantity times per-unit lane cost):

```python
# Objective: minimize total transfer cost
total_cost = sum(Transfer.x_quantity * Transfer.lane.cost_per_unit)
s.minimize(total_cost)
```

### Solve and print results

After defining variables, constraints, and the objective, run the HiGHS solver and print only transfers with a non-trivial quantity:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total transfer cost: ${s.objective_value:.2f}")

transfers = select(
    Transfer.lane.source.name.alias("from"),
    Transfer.lane.dest.name.alias("to"),
    Transfer.x_quantity
).where(Transfer.x_quantity > 0.001).to_df()

print("\nTransfers:")
print(transfers.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own data, keeping the same column names (or update the load logic in `inventory_rebalancing.py`).
- Make sure `lanes.csv.source_id` and `lanes.csv.dest_id` only reference valid site IDs in `sites.csv.id`.
- Make sure `demand.csv.site_id` only references valid site IDs.

> [!TIP]
> If you want demand to be met entirely by transfers (ignoring local inventory), remove `local_inv` from the demand constraint and require `inbound >= Dm.quantity`.

### Tune parameters

- Change the solver time limit in:

  ```python
  s.solve(solver, time_limit_sec=60)
  ```

- Swap the solver backend if your environment supports a different one.

### Extend the model

- Add per-lane fixed costs (requires binary “use lane” variables).
- Add service-level constraints (e.g., require minimum shipments into a subset of sites).
- Enforce integer transfer quantities by switching to a mixed-integer model and using integer decision variables.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>


- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>


- Check that each demand site has enough supply available across inbound lanes (considering lane capacities).
- If you’re relying on transfers only, ensure total supply across all sources is sufficient.
- Confirm that site IDs referenced in `lanes.csv` and `demand.csv` exist in `sites.csv`.

</details>

<details>
  <summary>Why is the Transfers table empty?</summary>


- The script filters transfers with `Transfer.x_quantity > 0.001`. If the optimal solution uses only local inventory (no transfers needed), the table will be empty.
- Confirm `demand.csv.quantity` exceeds local inventory at some site if you expect transfers.

</details>

<details>
  <summary>Why does the script fail when reading CSVs?</summary>


- Confirm the CSV headers match the expected column names.
- Check for non-numeric values in numeric columns like `inventory`, `capacity`, and `quantity`.
- Ensure the files are saved as UTF-8 and are comma-delimited.

</details>
