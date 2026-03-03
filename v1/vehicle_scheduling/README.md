---
title: "Vehicle Scheduling"
description: "Assign trips to a fleet of vehicles minimizing total operating cost."
featured: false
experience_level: beginner
industry: "Transportation & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Vehicle Routing
  - Fleet Management
  - Mixed-Integer Programming
---

# Vehicle Scheduling

## What this template is for

Fleet operators need to assign a set of trips to available vehicles while respecting capacity limits and minimizing total cost. Each vehicle has a fixed daily cost (incurred when used) and a variable cost per mile driven. The goal is to cover all trips using the fewest, cheapest combination of vehicles without overloading any of them.

This template formulates the problem as a mixed-integer program. Binary decision variables indicate whether each vehicle-trip assignment is active and whether each vehicle is used at all. The solver finds the assignment that minimizes the sum of fixed costs (for vehicles used) and variable costs (distance times per-mile rate).

The approach generalizes to larger fleets and trip sets, making it a practical starting point for delivery scheduling, field service dispatch, or shuttle planning.

## Who this is for

- Logistics and fleet managers optimizing daily vehicle assignments
- Operations researchers learning mixed-integer programming with RelationalAI
- Developers building dispatch or routing applications

## What you'll build

- A mixed-integer programming model with binary assignment variables
- Capacity constraints ensuring no vehicle is overloaded
- Trip coverage constraints ensuring every trip is served exactly once
- Vehicle usage tracking with fixed-cost minimization

## What's included

- `vehicle_scheduling.py` -- Main script defining the model, constraints, and solver call
- `data/vehicles.csv` -- Vehicle capacity, cost per mile, and fixed cost
- `data/trips.csv` -- Trip origin, destination, distance, load, and time windows
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/vehicle_scheduling.zip
   unzip vehicle_scheduling.zip
   cd vehicle_scheduling
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
   python vehicle_scheduling.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total cost: $147.50

   Vehicle assignments:
    vehicle   trip   from     to
      Van_1  Trip_A  Depot  Site_1
      Van_1  Trip_C  Depot  Site_3
      Van_1  Trip_F  Site_3  Depot
    Truck_1  Trip_B  Depot  Site_2
    Truck_1  Trip_D  Site_1  Site_2
    Truck_1  Trip_E  Site_2  Depot
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── vehicle_scheduling.py
└── data/
    ├── trips.csv
    └── vehicles.csv
```

## How it works

### 1. Define vehicles and trips

The model loads vehicle and trip data from CSV files. Vehicles have capacity, cost per mile, and a fixed daily cost. Trips have origin, destination, distance, and load:

```python
Vehicle = Concept("Vehicle", identify_by={"id": Integer})
Vehicle.capacity = Property(f"{Vehicle} has {Integer:capacity}")
Vehicle.cost_per_mile = Property(f"{Vehicle} has {Float:cost_per_mile}")
Vehicle.fixed_cost = Property(f"{Vehicle} has {Float:fixed_cost}")
```

### 2. Create assignment variables

An Assignment concept pairs every vehicle with every trip. A binary variable indicates whether each pair is active. A separate VehicleUsage concept tracks whether each vehicle is used at all:

```python
Assignment = Concept("Assignment")
Assignment.vehicle = Property(f"{Assignment} assigns {Vehicle}", short_name="vehicle")
Assignment.trip = Property(f"{Assignment} to {Trip}", short_name="trip")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(vehicle=Vehicle, trip=Trip))

s.solve_for(Assignment.x_assigned, type="bin", name=["assigned", Assignment.vehicle.name, Assignment.trip.name])
s.solve_for(VehicleUsage.x_used, type="bin", name=["used", VehicleUsage.vehicle.name])
```

### 3. Add constraints

Every trip must be assigned to exactly one vehicle, and no vehicle can carry more than its capacity:

```python
trip_coverage = sum(AssignmentRef.x_assigned).where(AssignmentRef.trip == Trip).per(Trip)
s.satisfy(model.require(trip_coverage == 1))

vehicle_load = sum(AssignmentRef.x_assigned * AssignmentRef.trip.load).where(
    AssignmentRef.vehicle == Vehicle
).per(Vehicle)
s.satisfy(model.require(vehicle_load <= Vehicle.capacity))
```

### 4. Minimize total cost

The objective combines variable cost (distance times per-mile rate) and fixed cost (incurred per vehicle used):

```python
variable_cost = sum(Assignment.x_assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
fixed_cost = sum(VehicleUsage.x_used * VehicleUsage.vehicle.fixed_cost)
s.minimize(variable_cost + fixed_cost)
```

## Customize this template

- **Add time window constraints** using the `start_time` and `end_time` fields already present in the trip data to prevent overlapping assignments on the same vehicle.
- **Introduce vehicle types** with different capabilities (e.g., refrigerated, hazmat) and restrict certain trips to compatible vehicle types.
- **Scale up** by adding more vehicles and trips to `vehicles.csv` and `trips.csv`.
- **Add driver constraints** such as maximum hours or mandatory breaks between trips.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Total fleet capacity may be insufficient to cover all trip loads. Check that the sum of vehicle capacities in `vehicles.csv` is at least as large as the sum of trip loads in `trips.csv`. Add more vehicles or reduce trip loads.
</details>

<details>
<summary>All trips assigned to a single vehicle</summary>

If one vehicle is much cheaper and has enough capacity, the solver will use only that vehicle. Add time window constraints or maximum trip count limits per vehicle to force diversification.
</details>

<details>
<summary>ModuleNotFoundError: No module named 'relationalai'</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that your account has the RAI Native App installed and that your user has the required permissions.
</details>
