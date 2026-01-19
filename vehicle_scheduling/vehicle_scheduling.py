"""Vehicle Scheduling - Assign trips to vehicles minimizing total cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Vehicle and Trip concepts."""
    model = Model(f"vehicle_scheduling_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Vehicle: available vehicles with capacity and costs
    Vehicle = Concept("Vehicle")
    Vehicle.name = Property("{Vehicle} has name {name:String}")
    Vehicle.capacity = Property("{Vehicle} has capacity {capacity:int}")
    Vehicle.cost_per_mile = Property("{Vehicle} has cost_per_mile {cost_per_mile:float}")
    Vehicle.fixed_cost = Property("{Vehicle} has fixed_cost {fixed_cost:float}")
    vehicles_df = read_csv(data_dir / "vehicles.csv")
    data(vehicles_df).into(Vehicle, id="id", properties=["name", "capacity", "cost_per_mile", "fixed_cost"])

    # Trip: routes to be serviced
    Trip = Concept("Trip")
    Trip.name = Property("{Trip} has name {name:String}")
    Trip.origin = Property("{Trip} from origin {origin:String}")
    Trip.destination = Property("{Trip} to destination {destination:String}")
    Trip.distance = Property("{Trip} has distance {distance:int}")
    Trip.load = Property("{Trip} has load {load:int}")
    Trip.start_time = Property("{Trip} has start_time {start_time:int}")
    Trip.end_time = Property("{Trip} has end_time {end_time:int}")
    trips_df = read_csv(data_dir / "trips.csv")
    data(trips_df).into(Trip, id="id", properties=["name", "origin", "destination", "distance", "load", "start_time", "end_time"])

    # Assignment: decision variable for vehicle-to-trip assignment
    Assignment = Concept("Assignment")
    Assignment.vehicle = Relationship("{Assignment} assigns {vehicle:Vehicle}")
    Assignment.trip = Relationship("{Assignment} to {trip:Trip}")
    Assignment.assigned = Property("{Assignment} is assigned {assigned:float}")
    define(Assignment.new(vehicle=Vehicle, trip=Trip))

    # VehicleUsage: track whether vehicle is used (for fixed cost)
    VehicleUsage = Concept("VehicleUsage")
    VehicleUsage.vehicle = Relationship("{VehicleUsage} for {vehicle:Vehicle}")
    VehicleUsage.used = Property("{VehicleUsage} is used {used:float}")
    define(VehicleUsage.new(vehicle=Vehicle))

    model.Vehicle, model.Trip, model.Assignment, model.VehicleUsage = Vehicle, Trip, Assignment, VehicleUsage
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Vehicle, Trip, Assignment, VehicleUsage = model.Vehicle, model.Trip, model.Assignment, model.VehicleUsage

    # Decision variable: binary assignment of trips to vehicles
    s.solve_for(Assignment.assigned, type="bin", name=[Assignment.vehicle, Assignment.trip])

    # Decision variable: binary vehicle usage
    s.solve_for(VehicleUsage.used, type="bin", name=VehicleUsage.vehicle)

    # Constraint: each trip assigned to exactly one vehicle
    Asn = Assignment.ref()
    trip_coverage = sum(Asn.assigned).where(Asn.trip == Trip).per(Trip)
    s.satisfy(require(trip_coverage == 1))

    # Constraint: vehicle capacity - total load assigned to vehicle cannot exceed capacity
    vehicle_load = sum(Asn.assigned * Asn.trip.load).where(Asn.vehicle == Vehicle).per(Vehicle)
    s.satisfy(require(vehicle_load <= Vehicle.capacity))

    # Constraint: link vehicle usage to assignments
    vehicle_trips = sum(Asn.assigned).where(Asn.vehicle == VehicleUsage.vehicle).per(VehicleUsage)
    s.satisfy(require(VehicleUsage.used * 100 >= vehicle_trips))  # If any trip assigned, vehicle is used

    # Objective: minimize total cost (fixed + variable)
    variable_cost = sum(Assignment.assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
    fixed_cost = sum(VehicleUsage.used * VehicleUsage.vehicle.fixed_cost)
    total_cost = variable_cost + fixed_cost
    s.minimize(total_cost)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)
    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Total cost: ${sol['objective']:.2f}")
    print("\nVehicle assignments:")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
