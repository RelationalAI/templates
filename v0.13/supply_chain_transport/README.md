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

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Supply chain teams often need to decide how to fulfill customer demand from a set of warehouses while choosing between transport modes such as truck, rail, and air.
Each mode has different costs, transit times, and capacity limits, so the cheapest option is not always feasible when delivery deadlines are tight.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to compute a minimum-cost shipment plan that meets demand, respects warehouse inventory limits, and avoids late deliveries.
It also includes a small what-if analysis that shows how the optimal plan changes if a warehouse is taken offline.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI Semantics.
- You’re comfortable with basic Python and the idea of constraints + objectives.
- You want a small template that demonstrates scenario analysis (what-if runs).

## What you’ll build

- A semantic model for warehouses, customers, routes, and transport modes.
- A mixed-integer optimization model with shipment quantities and binary selection flags.
- Constraints for inventory, demand satisfaction, mode capacity, and on-time delivery.
- A scenario loop that excludes a warehouse and compares objective values.

## What’s included

- **Model + solve script**: `supply_chain_transport.py`
- **Sample data**: `data/warehouses.csv`, `data/customers.csv`, `data/transport_modes.csv`, `data/routes.csv`
- **Outputs**: a readable shipment table per scenario and a scenario summary (status + objective)

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template using the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/supply_chain_transport.zip
   unzip supply_chain_transport.zip
   cd supply_chain_transport
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
   python supply_chain_transport.py
   ```

6. **Expected output**

   The script solves three scenarios (no warehouse excluded, then excluding one warehouse at a time), prints the non-zero shipment quantities for each run, and ends with a summary:

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

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ supply_chain_transport.py   # main runner / entrypoint
└─ data/                       # sample input data
   ├─ customers.csv
   ├─ routes.csv
   ├─ transport_modes.csv
   └─ warehouses.csv
```

**Start here**: `supply_chain_transport.py`

## Sample data

Data files are located in `data/`.

### `warehouses.csv`

Warehouses and their available inventory.

| Column | Meaning |
| --- | --- |
| `id` | Unique warehouse identifier |
| `name` | Warehouse name (used in scenario exclusions) |
| `inventory` | Available units in stock |

### `customers.csv`

Customers, their demand, and the delivery deadline.

| Column | Meaning |
| --- | --- |
| `id` | Unique customer identifier |
| `name` | Customer name |
| `demand` | Units required |
| `due_day` | Latest acceptable delivery time (in days) |

### `transport_modes.csv`

Transport modes and their cost / service characteristics.

| Column | Meaning |
| --- | --- |
| `id` | Unique mode identifier |
| `name` | Mode name (e.g., Truck, Rail, Air) |
| `cost_per_unit` | Cost per unit shipped |
| `transit_days` | Transit time in days |
| `capacity` | Maximum units per route–mode shipment |

### `routes.csv`

Feasible lanes from warehouses to customers.

| Column | Meaning |
| --- | --- |
| `id` | Unique route identifier |
| `warehouse_id` | Foreign key to `warehouses.csv.id` |
| `customer_id` | Foreign key to `customers.csv.id` |
| `distance` | Route distance (used to scale cost) |

## Model overview

This template models a classic multi-mode transportation problem with five core concepts: `Warehouse`, `Customer`, `TransportMode`, `Route`, and `Shipment`.

### `Warehouse`

A warehouse with an inventory limit.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/warehouses.csv` |
| `name` | string | No | Used for printing and scenario exclusions |
| `inventory` | int | No | Upper bound on total outbound shipments |

### `Customer`

A customer with demand and a delivery deadline.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/customers.csv` |
| `name` | string | No | Used for output labeling |
| `demand` | int | No | Minimum inbound shipment quantity |
| `due_day` | int | No | Any mode with `transit_days > due_day` is disallowed |

### `TransportMode`

A transport option with cost, transit time, and capacity.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/transport_modes.csv` |
| `name` | string | No | Used for printing |
| `cost_per_unit` | float | No | Per-unit cost used in the objective |
| `transit_days` | int | No | Used in the on-time constraint |
| `capacity` | int | No | Upper bound when a route–mode is selected |

### `Route`

A lane from one warehouse to one customer.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded from `data/routes.csv.id` |
| `warehouse` | `Warehouse` | No | Set by joining `routes.csv.warehouse_id` to `Warehouse.id` |
| `customer` | `Customer` | No | Set by joining `routes.csv.customer_id` to `Customer.id` |
| `distance` | int | No | Scales transport cost in the objective |

### `Shipment`

A decision over a `(route, mode)` pair.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `route` | `Route` | No | Which lane the shipment uses |
| `mode` | `TransportMode` | No | Which transport mode the shipment uses |
| `quantity` | float | No | Continuous decision variable ($\ge 0$) |
| `selected` | float | No | Binary decision variable (0/1) used for capacity and fixed-lane logic |

## How it works

This section walks through the highlights in `supply_chain_transport.py`.

### Import libraries and configure inputs

First, the script configures the data location and scenario settings. The `SCENARIO_VALUES` list drives the what-if loop that excludes one warehouse at a time:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Parameters.
EXCLUDED_WAREHOUSE = None

# Scenarios (what-if analysis).
SCENARIO_PARAM = "excluded_warehouse"
SCENARIO_VALUES = [None, "Warehouse_East", "Warehouse_Central"]
SCENARIO_CONCEPT = "Warehouse"  # Entity type for exclusion scenarios.
```

### Define concepts and load CSV data

Next, it declares concepts and loads the CSVs using `data(...).into(...)`:

```python
# Create a Semantics model container.
model = Model("supply_chain_transport", config=globals().get("config", None), use_lqp=False)

# Warehouse concept: warehouses with inventory.
Warehouse = model.Concept("Warehouse")
Warehouse.id = model.Property("{Warehouse} has {id:int}")
Warehouse.name = model.Property("{Warehouse} has {name:string}")
Warehouse.inventory = model.Property("{Warehouse} has {inventory:int}")

# Load warehouse data from CSV.
data(read_csv(DATA_DIR / "warehouses.csv")).into(Warehouse, keys=["id"])
```

Then it creates `Route` entities by joining `routes.csv` to `Warehouse` and `Customer` with `where(...).define(...)`:

```python
# Load route data from CSV.
routes_data = data(read_csv(DATA_DIR / "routes.csv"))

# Create one Route entity per row by joining warehouse_id and customer_id.
where(
    Warehouse.id == routes_data.warehouse_id,
    Customer.id == routes_data.customer_id
).define(
    Route.new(
        id=routes_data.id,
        warehouse=Warehouse,
        customer=Customer,
        distance=routes_data.distance,
    )
)
```

### Define decision variables, constraints, and objective

With the base data in place, the template defines a `Shipment` concept over `(Route, TransportMode)` pairs and registers decision variables with `solve_for`.
The constraints are expressed with `require(...)` and attached to the solver via `s.satisfy(...)`:

```python
# Shipment decision concept: quantity shipped for each route–mode combination.
Shipment = model.Concept("Shipment")
Shipment.route = model.Property("{Shipment} on {route:Route}")
Shipment.mode = model.Property("{Shipment} via {mode:TransportMode}")
Shipment.quantity = model.Property("{Shipment} has {quantity:float}")
Shipment.selected = model.Property("{Shipment} is {selected:float}")
define(Shipment.new(route=Route, mode=TransportMode))

Sh = Shipment.ref()


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Variable: shipment quantity and selection.
    s.solve_for(
        Shipment.quantity,
        name=[
            "qty",
            Shipment.route.warehouse.name,
            Shipment.route.customer.name,
            Shipment.mode.name,
        ],
        lower=0,
    )
    s.solve_for(
        Shipment.selected,
        type="bin",
        name=[
            "sel",
            Shipment.route.warehouse.name,
            Shipment.route.customer.name,
            Shipment.mode.name,
        ],
    )

    # Constraint: shipment quantity bounded by mode capacity when selected.
    capacity_bound = require(Shipment.quantity <= Shipment.mode.capacity * Shipment.selected)
    s.satisfy(capacity_bound)

    min_bound = require(Shipment.quantity >= Shipment.selected)
    s.satisfy(min_bound)

    # Constraint: total outbound from warehouse cannot exceed inventory.
    outbound = sum(Sh.quantity).where(Sh.route.warehouse == Warehouse).per(Warehouse)
    inventory_limit = require(outbound <= Warehouse.inventory)
    s.satisfy(inventory_limit)

    # Constraint: demand satisfaction for each customer.
    inbound = sum(Sh.quantity).where(Sh.route.customer == Customer).per(Customer)
    demand_met = require(inbound >= Customer.demand)
    s.satisfy(demand_met)

    # Constraint: on-time delivery (no shipments via modes that would be late)
    on_time = require(Shipment.quantity == 0).where(
        Shipment.mode.transit_days > Shipment.route.customer.due_day
    )
    s.satisfy(on_time)

    # Constraint: exclude warehouse if specified.
    if EXCLUDED_WAREHOUSE is not None:
        exclude = require(Shipment.quantity == 0).where(
            Shipment.route.warehouse.name == EXCLUDED_WAREHOUSE
        )
        s.satisfy(exclude)

    # Objective: minimize total transport cost (distance-weighted)
    total_cost = sum(Shipment.quantity * Shipment.mode.cost_per_unit * Shipment.route.distance / 100)
    s.minimize(total_cost)
```

### Solve scenarios and print results

Finally, the script iterates over `SCENARIO_VALUES`, rebuilds a fresh `SolverModel` each time, solves with the HiGHS backend, and prints both a per-scenario shipment plan and an end summary:

```python
scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter (entity to exclude).
    EXCLUDED_WAREHOUSE = scenario_value

    # Create a fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append(
        {
            "scenario": scenario_value,
            "status": str(s.termination_status),
            "objective": s.objective_value,
        }
    )
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print shipment plan from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)
    ].rename(columns={"float": "value"})
    print("\n  Shipments:")
    print(qty_df.to_string(index=False))

# Summary.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
```

## Customize this template

Here are common ways to adapt the template once you’ve run it end-to-end.

### Use your own data

- Replace the CSVs in `data/` with your own data (or update the ingestion logic in `supply_chain_transport.py`).
- Keep the same headers, or update the code to match your schema.
- If you use warehouse exclusions, ensure `SCENARIO_VALUES` contains names that match `warehouses.csv.name`.

### Tune parameters

- Change the what-if analysis by editing `SCENARIO_VALUES`.
- Increase `time_limit_sec` if you scale the problem up.
- Adjust the output filter `var_df["float"] > 0.001` if you want to print smaller flows.
- If your `distance` is in different units, update the objective scaling (`... * Shipment.route.distance / 100`).

### Extend the model

- Add fixed charges for opening a route–mode option using `Shipment.selected`.
- Add minimum service requirements (e.g., at least two warehouses used).
- Add new constraints such as per-route maximum flow or carbon limits.

### Scale up and productionize

- Replace CSV ingestion with Snowflake tables.
- Write shipment decisions back to Snowflake after solving.
- Schedule runs (e.g., daily) and track objective changes over time.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>

- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
  <summary>Why do I get <code>ModuleNotFoundError</code> for a dependency?</summary>

- Confirm your virtual environment is activated (`source .venv/bin/activate`).
- From the template folder, run `python -m pip install .`.
- Confirm you are using Python >= 3.10.

</details>

<details>
  <summary>Why do I get file/column errors when loading CSVs?</summary>

- Confirm the files exist under `data/` and have headers.
- Ensure these columns are present:
  - `warehouses.csv`: `id`, `name`, `inventory`
  - `customers.csv`: `id`, `name`, `demand`, `due_day`
  - `transport_modes.csv`: `id`, `name`, `cost_per_unit`, `transit_days`, `capacity`
  - `routes.csv`: `id`, `warehouse_id`, `customer_id`, `distance`
- Check that `routes.csv.warehouse_id` values exist in `warehouses.csv.id` and `routes.csv.customer_id` values exist in `customers.csv.id`.

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>

- Check that total inventory across warehouses is at least total customer demand.
- Check that each customer has at least one route from a warehouse.
- Check delivery deadlines: if all modes have `transit_days > due_day` for a customer, that customer can’t be served.
- If you exclude a warehouse, you may remove the only feasible source for a customer.

</details>

<details>
  <summary>Why is the shipments table empty?</summary>

- The script filters shipment variables with `var_df["float"] > 0.001`. Lower the threshold to see smaller quantities.
- If the model is infeasible, there will be no meaningful shipment plan—check the status line printed above.

</details>

<details>
  <summary>Why isn’t the termination status <code>OPTIMAL</code>?</summary>

- If you scale up the data, the default `time_limit_sec=60` may be too small; increase it.
- Check the printed `termination_status` to see whether the solver hit a limit.

</details>
