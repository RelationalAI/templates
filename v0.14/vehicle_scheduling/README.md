---
title: "Vehicle Scheduling"
description: "Assign trips to vehicles to minimize total cost, including fixed vehicle activation costs and per-mile costs."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Scheduling
  - Fleet
  - MILP
---

# Vehicle Scheduling

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.14.2` of the `relationalai` Python package.

## What this template is for

Fleet operators often need to assign a set of required trips to a limited set of vehicles.
Each vehicle has a fixed “activation” cost (it costs something just to put it into service), plus a variable per-mile cost once it starts moving.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose which vehicles to use and assign exactly one vehicle to each trip, while respecting capacity limits and minimizing total cost.

Prescriptive reasoning helps you:

- **Trade off fixed vs. variable costs**: Avoid activating an extra vehicle unless it reduces variable mileage enough to be worth it.
- **Guarantee trip coverage**: Ensure every trip is assigned exactly once.
- **Stay within capacity**: Prevent infeasible assignments where the total load exceeds a vehicle’s capacity.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** using RelationalAI Semantics.
- You’re comfortable with basic Python and the idea of decision variables, constraints, and an objective.

## What you’ll build

- A semantic model of `Vehicle` and `Trip` entities loaded from CSV.
- A MILP with binary assignment variables per vehicle–trip pair.
- Constraints for trip coverage, per-vehicle capacity, and fixed-cost “vehicle used” linking.
- A solver run using the **HiGHS** backend that prints a readable assignment table.

## What’s included

- **Model + solve script**: `vehicle_scheduling.py`
- **Sample data**: `data/vehicles.csv`, `data/trips.csv`
- **Outputs**: Solver status, objective value (total cost), and a table of assignments printed to stdout

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
   curl -O https://private.relational.ai/templates/zips/v0.14/vehicle_scheduling.zip
   unzip vehicle_scheduling.zip
   cd vehicle_scheduling
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
   python vehicle_scheduling.py
   ```

6. **Expected output**

   Your exact assignments may differ if multiple solutions have the same minimum cost, but the output shape should look like:

   ```text
   Status: OPTIMAL
   Total cost: $183.50

   Vehicle assignments:
   vehicle   trip   from     to
   Truck_2 Trip_A  Depot Site_1
   Truck_2 Trip_B  Depot Site_2
     Van_2 Trip_C  Depot Site_3
     Van_2 Trip_D Site_1 Site_2
     Van_2 Trip_E Site_2  Depot
     Van_2 Trip_F Site_3  Depot
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ vehicle_scheduling.py      # main runner / entrypoint
└─ data/                      # sample input data
   ├─ vehicles.csv
   └─ trips.csv
```

**Start here**: `vehicle_scheduling.py`

## Sample data

Data files are in `data/`.

### `vehicles.csv`

Defines the fleet, including capacity and costs.

| Column | Meaning |
| --- | --- |
| `id` | Unique vehicle identifier |
| `name` | Vehicle name (e.g., `Van_1`, `Truck_2`) |
| `capacity` | Maximum load capacity (units) |
| `cost_per_mile` | Variable operating cost per mile ($) |
| `fixed_cost` | Fixed cost if the vehicle is used at all ($) |

### `trips.csv`

Defines the required trips that must be covered.
This template loads `start_time` and `end_time` as properties, but does not enforce time-window feasibility yet.

| Column | Meaning |
| --- | --- |
| `id` | Unique trip identifier |
| `name` | Trip name |
| `origin` | Starting location |
| `destination` | Ending location |
| `distance` | Trip distance (miles) |
| `load` | Load requirement (units) |
| `start_time` | Earliest start time (integer time index) |
| `end_time` | Latest end time (integer time index) |

## Model overview

The optimization model is built around four concepts.

### `Vehicle`

A vehicle with capacity and cost parameters.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/vehicles.csv` |
| `name` | string | No | Used for variable naming and printed output |
| `capacity` | int | No | Upper bound for the total assigned `Trip.load` |
| `cost_per_mile` | float | No | Used in the variable cost term |
| `fixed_cost` | float | No | Charged when `VehicleUsage.x_used = 1` |

### `Trip`

A required trip to be covered by exactly one vehicle.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/trips.csv` |
| `name` | string | No | Used for variable naming and printed output |
| `origin` | string | No | Printed in the assignment table |
| `destination` | string | No | Printed in the assignment table |
| `distance` | int | No | Used in the variable cost term |
| `load` | int | No | Consumed capacity on the chosen vehicle |
| `start_time` | int | No | Loaded for extension; not constrained in this template |
| `end_time` | int | No | Loaded for extension; not constrained in this template |

### `Assignment` (decision concept)

One potential assignment per vehicle–trip pair, with a binary decision variable.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `vehicle` | `Vehicle` | Part of compound key | The vehicle being assigned |
| `trip` | `Trip` | Part of compound key | The trip being covered |
| `assigned` | float | No | Binary decision variable (0/1) |

### `VehicleUsage` (decision concept)

Tracks whether a vehicle is activated so the model can apply fixed costs.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `vehicle` | `Vehicle` | Yes | One usage record per vehicle |
| `used` | float | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `vehicle_scheduling.py`.

### Import libraries and configure inputs

First, the script imports the Semantics APIs and sets up the local data directory and a simple Big-M value (`MAX_TRIPS_PER_VEHICLE`) used to link fixed vehicle usage to trip assignments:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

MAX_TRIPS_PER_VEHICLE = 100
```

### Define concepts and load CSV data

Next, it creates a model container with `Model(...)`, defines `Vehicle` and `Trip` concepts with typed properties, and loads the CSVs into those concepts using `data(...).into(...)`:

```python
# Create a Semantics model container.
model = Model("vehicle_scheduling", config=globals().get("config", None))

# Vehicle concept: vehicles with capacity and costs.
Vehicle = model.Concept("Vehicle")
Vehicle.id = model.Property("{Vehicle} has {id:int}")
Vehicle.name = model.Property("{Vehicle} has {name:string}")
Vehicle.capacity = model.Property("{Vehicle} has {capacity:int}")
Vehicle.cost_per_mile = model.Property("{Vehicle} has {cost_per_mile:float}")
Vehicle.fixed_cost = model.Property("{Vehicle} has {fixed_cost:float}")

# Load vehicle data from CSV.
data(read_csv(DATA_DIR / "vehicles.csv")).into(Vehicle, keys=["id"])

# Trip concept: trips with origin, destination, distance, and load.
Trip = model.Concept("Trip")
Trip.id = model.Property("{Trip} has {id:int}")
Trip.name = model.Property("{Trip} has {name:string}")
Trip.origin = model.Property("{Trip} from {origin:string}")
Trip.destination = model.Property("{Trip} to {destination:string}")
Trip.distance = model.Property("{Trip} has {distance:int}")
Trip.load = model.Property("{Trip} has {load:int}")
Trip.start_time = model.Property("{Trip} has {start_time:int}")
Trip.end_time = model.Property("{Trip} has {end_time:int}")

# Load trip data from CSV.
data(read_csv(DATA_DIR / "trips.csv")).into(Trip, keys=["id"])
```

### Define decision variables

With the entities in place, it defines two decision concepts.
`Assignment` creates one candidate vehicle–trip pairing, and `VehicleUsage` captures whether each vehicle is used so the model can apply fixed costs:

```python
# Assignment decision concept: assignment of vehicles to trips.
Assignment = model.Concept("Assignment")
Assignment.vehicle = model.Relationship("{Assignment} assigns {vehicle:Vehicle}")
Assignment.trip = model.Relationship("{Assignment} to {trip:Trip}")
Assignment.x_assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(vehicle=Vehicle, trip=Trip))

# VehicleUsage decision concept: tracks whether a vehicle is used.
VehicleUsage = model.Concept("VehicleUsage")
VehicleUsage.vehicle = model.Relationship("{VehicleUsage} for {vehicle:Vehicle}")
VehicleUsage.x_used = model.Property("{VehicleUsage} is {used:float}")
define(VehicleUsage.new(vehicle=Vehicle))

AssignmentRef = Assignment.ref()

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision variable: assignment (binary 0/1).
s.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=["x", Assignment.vehicle.name, Assignment.trip.name],
)

# Decision variable: vehicle usage (binary 0/1).
s.solve_for(
    VehicleUsage.x_used,
    type="bin",
    name=["used", VehicleUsage.vehicle.name],
)
```

### Add constraints and objective

Then it enforces trip coverage and capacity with `require(...)` and `s.satisfy(...)`, links `VehicleUsage.x_used` to the number of assigned trips via a Big-M constraint, and minimizes variable + fixed cost:

```python
# Constraint: each trip must be assigned to exactly one vehicle.
trip_coverage = sum(AssignmentRef.x_assigned).where(
   AssignmentRef.trip == Trip
).per(Trip)
one_vehicle = require(trip_coverage == 1)
s.satisfy(one_vehicle)

# Constraint: vehicle capacity.
vehicle_load = sum(AssignmentRef.x_assigned * AssignmentRef.trip.load).where(
   AssignmentRef.vehicle == Vehicle
).per(Vehicle)
capacity_limit = require(vehicle_load <= Vehicle.capacity)
s.satisfy(capacity_limit)

# Constraint: link vehicle usage to assignments.
vehicle_trips = sum(AssignmentRef.x_assigned).where(
   AssignmentRef.vehicle == VehicleUsage.vehicle
).per(VehicleUsage)
usage_link = require(VehicleUsage.x_used * MAX_TRIPS_PER_VEHICLE >= vehicle_trips)
s.satisfy(usage_link)

# Objective: minimize total cost.
variable_cost = sum(Assignment.x_assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
fixed_cost = sum(VehicleUsage.x_used * VehicleUsage.vehicle.fixed_cost)
total_cost = variable_cost + fixed_cost
s.minimize(total_cost)
```

### Solve and print results

Finally, it solves the MILP with the HiGHS backend and prints assignments where `Assignment.x_assigned > 0.5`:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

assignments = select(
    Assignment.vehicle.name.alias("vehicle"),
    Assignment.trip.name.alias("trip"),
    Assignment.trip.origin.alias("from"),
    Assignment.trip.destination.alias("to")
).where(Assignment.x_assigned > 0.5).to_df()

print("\nVehicle assignments:")
print(assignments.to_string(index=False))
```

## Customize this template

### Use your own data

- Replace `data/vehicles.csv` and `data/trips.csv` with your own files.
- Keep the same column headers (or update the properties and `data(...).into(...)` calls in `vehicle_scheduling.py`).

### Tune parameters

- Adjust `MAX_TRIPS_PER_VEHICLE` in `vehicle_scheduling.py` to control the strength of the usage-link Big-M constraint.
  It must be at least the maximum number of trips you’d ever assign to a single vehicle.

### Extend the model

- Add vehicle–trip compatibility rules (for example, vehicle type restrictions) by introducing a relationship and constraining which `Assignment` rows are allowed.
- Add time-window feasibility using `Trip.start_time` and `Trip.end_time` (currently loaded but not constrained).

## Troubleshooting

<details>
<summary>I can’t authenticate or my profile isn’t found (<code>rai init</code>, <code>RAI_PROFILE</code>)</summary>

- Run <code>rai init</code> and ensure it creates/updates your <code>raiconfig.toml</code>.
- If you use multiple profiles, set <code>RAI_PROFILE</code> to the right one before running the script.
- Confirm your Snowflake account has the RAI Native App installed and you have permission to use it.

</details>

<details>
<summary>Connection fails to the RAI Native App (Snowflake role/warehouse/app access)</summary>

- Verify you can access the RelationalAI Native App in Snowflake with your current role.
- Make sure your Snowflake warehouse is running and your role has usage permissions.
- Re-run <code>rai init</code> and double-check the selected connection details.

</details>

<details>
<summary>Dependency import fails (<code>ModuleNotFoundError</code>)</summary>

- Confirm your virtual environment is activated (<code>source .venv/bin/activate</code>).
- Install dependencies from the template folder with <code>python -m pip install .</code>.
- If you’re in a shared environment, try a fresh venv and upgrade pip (<code>python -m pip install -U pip</code>).

</details>

<details>
<summary>Data loading fails (missing CSV file or columns)</summary>

- Confirm the input files exist at <code>data/vehicles.csv</code> and <code>data/trips.csv</code>.
- Ensure the headers match exactly.
- <code>vehicles.csv</code> must include: <code>id,name,capacity,cost_per_mile,fixed_cost</code>
- <code>trips.csv</code> must include: <code>id,name,origin,destination,distance,load,start_time,end_time</code>
- Check that numeric columns contain valid numbers (no blanks or non-numeric strings).

</details>

<details>
<summary>The solver returns <code>Status: INFEASIBLE</code></summary>

- Check that every trip can fit in at least one vehicle: for each trip, <code>load</code> must be <code>&lt;=</code> some vehicle’s <code>capacity</code>.
- Verify vehicle capacities are positive and loads are non-negative.
- If you changed constraints, temporarily comment them out to isolate which one causes infeasibility.

</details>

<details>
<summary>My assignment table is empty</summary>

- This template prints assignments filtered by <code>Assignment.x_assigned &gt; 0.5</code>.
- If the solver didn’t find a feasible solution, the decision variables may be unset.
- Print the status line first and confirm it is <code>OPTIMAL</code> (or at least a feasible status) before inspecting assignments.

</details>
