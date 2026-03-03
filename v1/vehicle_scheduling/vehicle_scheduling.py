# vehicle scheduling problem:
# assign trips to vehicles minimizing total cost

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("vehicle_scheduling")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: vehicles with capacity and costs
Vehicle = Concept("Vehicle", identify_by={"id": Integer})
Vehicle.name = Property(f"{Vehicle} has {String:name}")
Vehicle.capacity = Property(f"{Vehicle} has {Integer:capacity}")
Vehicle.cost_per_mile = Property(f"{Vehicle} has {Float:cost_per_mile}")
Vehicle.fixed_cost = Property(f"{Vehicle} has {Float:fixed_cost}")
vehicle_csv = read_csv(data_dir / "vehicles.csv")
model.define(Vehicle.new(model.data(vehicle_csv).to_schema()))

# Concept: trips with origin, destination, distance, and load
Trip = Concept("Trip", identify_by={"id": Integer})
Trip.name = Property(f"{Trip} has {String:name}")
Trip.origin = Property(f"{Trip} from {String:origin}")
Trip.destination = Property(f"{Trip} to {String:destination}")
Trip.distance = Property(f"{Trip} has {Integer:distance}")
Trip.load = Property(f"{Trip} has {Integer:load}")
Trip.start_time = Property(f"{Trip} has {Integer:start_time}")
Trip.end_time = Property(f"{Trip} has {Integer:end_time}")
trip_csv = read_csv(data_dir / "trips.csv")
model.define(Trip.new(model.data(trip_csv).to_schema()))

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Decision concept: assignments of vehicles to trips
Assignment = Concept("Assignment")
Assignment.vehicle = Property(f"{Assignment} assigns {Vehicle}", short_name="vehicle")
Assignment.trip = Property(f"{Assignment} to {Trip}", short_name="trip")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(vehicle=Vehicle, trip=Trip))

# Decision concept: track whether vehicle is used
VehicleUsage = Concept("VehicleUsage")
VehicleUsage.vehicle = Property(f"{VehicleUsage} for {Vehicle}", short_name="vehicle")
VehicleUsage.x_used = Property(f"{VehicleUsage} is {Float:used}")
model.define(VehicleUsage.new(vehicle=Vehicle))

# Parameters
max_trips_per_vehicle = 100

AssignmentRef = Assignment.ref()

s = Problem(model, Float)

# Variable: binary assignment and usage
s.solve_for(Assignment.x_assigned, type="bin", name=["assigned", Assignment.vehicle.name, Assignment.trip.name])
s.solve_for(VehicleUsage.x_used, type="bin", name=["used", VehicleUsage.vehicle.name])

# Constraint: each trip assigned to exactly one vehicle
trip_coverage = sum(AssignmentRef.x_assigned).where(AssignmentRef.trip == Trip).per(Trip)
one_vehicle = model.require(trip_coverage == 1)
s.satisfy(one_vehicle)

# Constraint: vehicle capacity
vehicle_load = sum(AssignmentRef.x_assigned * AssignmentRef.trip.load).where(AssignmentRef.vehicle == Vehicle).per(Vehicle)
capacity_limit = model.require(vehicle_load <= Vehicle.capacity)
s.satisfy(capacity_limit)

# Constraint: link vehicle usage to assignments
vehicle_trips = sum(AssignmentRef.x_assigned).where(AssignmentRef.vehicle == VehicleUsage.vehicle).per(VehicleUsage)
usage_link = model.require(VehicleUsage.x_used * max_trips_per_vehicle >= vehicle_trips)
s.satisfy(usage_link)

# Objective: minimize total cost
variable_cost = sum(Assignment.x_assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
fixed_cost = sum(VehicleUsage.x_used * VehicleUsage.vehicle.fixed_cost)
total_cost = variable_cost + fixed_cost
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

assignments = model.select(
    Assignment.vehicle.name.alias("vehicle"),
    Assignment.trip.name.alias("trip"),
    Assignment.trip.origin.alias("from"),
    Assignment.trip.destination.alias("to")
).where(Assignment.x_assigned > 0.5).to_df()

print("\nVehicle assignments:")
print(assignments.to_string(index=False))
