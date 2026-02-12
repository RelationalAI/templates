"""Vehicle scheduling (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) workflow in
RelationalAI:

- Load sample CSVs describing vehicles and trips.
- Model vehicles and trips as *concepts* with typed properties.
- Decide which vehicle is assigned to each trip.
- Enforce trip coverage and vehicle capacity constraints.
- Minimize total cost (variable distance cost plus fixed vehicle usage cost).

Run:
    `python vehicle_scheduling.py`

Output:
    Prints the solver termination status, objective value, and a table of
    vehicle-trip assignments.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum
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

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("vehicle_scheduling", config=globals().get("config", None), use_lqp=False)

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

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Assignment decision concept: assignment of vehicles to trips.
Assignment = model.Concept("Assignment")
Assignment.vehicle = model.Property("{Assignment} assigns {vehicle:Vehicle}")
Assignment.trip = model.Property("{Assignment} to {trip:Trip}")
Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(vehicle=Vehicle, trip=Trip))

# VehicleUsage decision concept: tracks whether a vehicle is used.
VehicleUsage = model.Concept("VehicleUsage")
VehicleUsage.vehicle = model.Property("{VehicleUsage} for {vehicle:Vehicle}")
VehicleUsage.used = model.Property("{VehicleUsage} is {used:float}")
define(VehicleUsage.new(vehicle=Vehicle))

assignment = Assignment.ref()

# Create a continuous optimization model.
s = SolverModel(model, "cont")

# Decision variable: assignment (binary 0/1).
s.solve_for(
    Assignment.assigned,
    type="bin",
    name=["x", Assignment.vehicle.name, Assignment.trip.name],
)

# Decision variable: vehicle usage (binary 0/1).
s.solve_for(
    VehicleUsage.used,
    type="bin",
    name=["used", VehicleUsage.vehicle.name],
)

# Constraint: each trip must be assigned to exactly one vehicle.
trip_coverage = sum(assignment.assigned).where(
    assignment.trip == Trip
).per(Trip)
one_vehicle = require(trip_coverage == 1)
s.satisfy(one_vehicle)

# Constraint: vehicle capacity.
vehicle_load = sum(assignment.assigned * assignment.trip.load).where(
    assignment.vehicle == Vehicle
).per(Vehicle)
capacity_limit = require(vehicle_load <= Vehicle.capacity)
s.satisfy(capacity_limit)

# Constraint: link vehicle usage to assignments.
vehicle_trips = sum(assignment.assigned).where(
    assignment.vehicle == VehicleUsage.vehicle
).per(VehicleUsage)
usage_link = require(VehicleUsage.used * MAX_TRIPS_PER_VEHICLE >= vehicle_trips)
s.satisfy(usage_link)

# Objective: minimize total cost.
variable_cost = sum(Assignment.assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
fixed_cost = sum(VehicleUsage.used * VehicleUsage.vehicle.fixed_cost)
total_cost = variable_cost + fixed_cost
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

assignments = select(
    Assignment.vehicle.name.alias("vehicle"),
    Assignment.trip.name.alias("trip"),
    Assignment.trip.origin.alias("from"),
    Assignment.trip.destination.alias("to")
).where(Assignment.assigned > 0.5).to_df()

print("\nVehicle assignments:")
print(assignments.to_string(index=False))
