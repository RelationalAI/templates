"""Vehicle Scheduling - Assign trips to vehicles minimizing total cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Vehicle and Trip concepts."""
    model = Model(f"vehicle_scheduling_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Vehicle = model.Concept("Vehicle")
    Vehicle.id = model.Property("{Vehicle} has {id:int}")
    Vehicle.name = model.Property("{Vehicle} has {name:string}")
    Vehicle.capacity = model.Property("{Vehicle} has {capacity:int}")
    Vehicle.cost_per_mile = model.Property("{Vehicle} has {cost_per_mile:float}")
    Vehicle.fixed_cost = model.Property("{Vehicle} has {fixed_cost:float}")

    Trip = model.Concept("Trip")
    Trip.id = model.Property("{Trip} has {id:int}")
    Trip.name = model.Property("{Trip} has {name:string}")
    Trip.origin = model.Property("{Trip} from {origin:string}")
    Trip.destination = model.Property("{Trip} to {destination:string}")
    Trip.distance = model.Property("{Trip} has {distance:int}")
    Trip.load = model.Property("{Trip} has {load:int}")
    Trip.start_time = model.Property("{Trip} has {start_time:int}")
    Trip.end_time = model.Property("{Trip} has {end_time:int}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    vehicles_df = read_csv(data_dir / "vehicles.csv")
    data(vehicles_df).into(Vehicle, keys=["id"])

    trips_df = read_csv(data_dir / "trips.csv")
    data(trips_df).into(Trip, keys=["id"])

    # Assignment: decision variable for vehicle-to-trip assignment
    Assignment = model.Concept("Assignment")
    Assignment.vehicle = model.Property("{Assignment} assigns {vehicle:Vehicle}")
    Assignment.trip = model.Property("{Assignment} to {trip:Trip}")
    Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
    define(Assignment.new(vehicle=Vehicle, trip=Trip))

    # VehicleUsage: track whether vehicle is used
    VehicleUsage = model.Concept("VehicleUsage")
    VehicleUsage.vehicle = model.Property("{VehicleUsage} for {vehicle:Vehicle}")
    VehicleUsage.used = model.Property("{VehicleUsage} is {used:float}")
    define(VehicleUsage.new(vehicle=Vehicle))

    model.Vehicle, model.Trip, model.Assignment, model.VehicleUsage = Vehicle, Trip, Assignment, VehicleUsage
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Vehicle, Trip, Assignment, VehicleUsage = model.Vehicle, model.Trip, model.Assignment, model.VehicleUsage

    # Decision variable: binary assignment of trips to vehicles
    s.solve_for(Assignment.assigned, type="bin", name=["x", Assignment.vehicle.name, Assignment.trip.name])

    # Decision variable: binary vehicle usage
    s.solve_for(VehicleUsage.used, type="bin", name=["used", VehicleUsage.vehicle.name])

    # Constraint: each trip assigned to exactly one vehicle
    Asn = Assignment.ref()
    trip_coverage = sum(Asn.assigned).where(Asn.trip == Trip).per(Trip)
    s.satisfy(require(trip_coverage == 1))

    # Constraint: vehicle capacity
    vehicle_load = sum(Asn.assigned * Asn.trip.load).where(Asn.vehicle == Vehicle).per(Vehicle)
    s.satisfy(require(vehicle_load <= Vehicle.capacity))

    # Constraint: link vehicle usage to assignments
    vehicle_trips = sum(Asn.assigned).where(Asn.vehicle == VehicleUsage.vehicle).per(VehicleUsage)
    s.satisfy(require(VehicleUsage.used * 100 >= vehicle_trips))

    # Objective: minimize total cost
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
