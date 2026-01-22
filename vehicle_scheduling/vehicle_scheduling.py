# vehicle scheduling problem:
# assign trips to vehicles minimizing total cost

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("vehicle_scheduling", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: vehicles with capacity and costs
Vehicle = model.Concept("Vehicle")
Vehicle.id = model.Property("{Vehicle} has {id:int}")
Vehicle.name = model.Property("{Vehicle} has {name:string}")
Vehicle.capacity = model.Property("{Vehicle} has {capacity:int}")
Vehicle.cost_per_mile = model.Property("{Vehicle} has {cost_per_mile:float}")
Vehicle.fixed_cost = model.Property("{Vehicle} has {fixed_cost:float}")
data(read_csv(data_dir / "vehicles.csv")).into(Vehicle, keys=["id"])

# Concept: trips with origin, destination, distance, and load
Trip = model.Concept("Trip")
Trip.id = model.Property("{Trip} has {id:int}")
Trip.name = model.Property("{Trip} has {name:string}")
Trip.origin = model.Property("{Trip} from {origin:string}")
Trip.destination = model.Property("{Trip} to {destination:string}")
Trip.distance = model.Property("{Trip} has {distance:int}")
Trip.load = model.Property("{Trip} has {load:int}")
Trip.start_time = model.Property("{Trip} has {start_time:int}")
Trip.end_time = model.Property("{Trip} has {end_time:int}")
data(read_csv(data_dir / "trips.csv")).into(Trip, keys=["id"])

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: assignments of vehicles to trips
Assignment = model.Concept("Assignment")
Assignment.vehicle = model.Property("{Assignment} assigns {vehicle:Vehicle}")
Assignment.trip = model.Property("{Assignment} to {trip:Trip}")
Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(vehicle=Vehicle, trip=Trip))

# Decision concept: track whether vehicle is used
VehicleUsage = model.Concept("VehicleUsage")
VehicleUsage.vehicle = model.Property("{VehicleUsage} for {vehicle:Vehicle}")
VehicleUsage.used = model.Property("{VehicleUsage} is {used:float}")
define(VehicleUsage.new(vehicle=Vehicle))

# Parameters
max_trips_per_vehicle = 100

Asn = Assignment.ref()

s = SolverModel(model, "cont")

# Variable: binary assignment and usage
s.solve_for(Assignment.assigned, type="bin", name=["x", Assignment.vehicle.name, Assignment.trip.name])
s.solve_for(VehicleUsage.used, type="bin", name=["used", VehicleUsage.vehicle.name])

# Constraint: each trip assigned to exactly one vehicle
trip_coverage = sum(Asn.assigned).where(Asn.trip == Trip).per(Trip)
one_vehicle = require(trip_coverage == 1)
s.satisfy(one_vehicle)

# Constraint: vehicle capacity
vehicle_load = sum(Asn.assigned * Asn.trip.load).where(Asn.vehicle == Vehicle).per(Vehicle)
capacity_limit = require(vehicle_load <= Vehicle.capacity)
s.satisfy(capacity_limit)

# Constraint: link vehicle usage to assignments
vehicle_trips = sum(Asn.assigned).where(Asn.vehicle == VehicleUsage.vehicle).per(VehicleUsage)
usage_link = require(VehicleUsage.used * max_trips_per_vehicle >= vehicle_trips)
s.satisfy(usage_link)

# Objective: minimize total cost
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
