"""Hospital Staffing - Assign nurses to shifts meeting coverage and skill requirements."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Nurse, Shift, and Availability concepts."""
    model = Model(f"hospital_staffing_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Nurse = model.Concept("Nurse")
    Nurse.id = model.Property("{Nurse} has {id:int}")
    Nurse.name = model.Property("{Nurse} has {name:string}")
    Nurse.skill_level = model.Property("{Nurse} has {skill_level:int}")
    Nurse.hourly_cost = model.Property("{Nurse} has {hourly_cost:float}")

    Shift = model.Concept("Shift")
    Shift.id = model.Property("{Shift} has {id:int}")
    Shift.name = model.Property("{Shift} has {name:string}")
    Shift.start_hour = model.Property("{Shift} has {start_hour:int}")
    Shift.duration = model.Property("{Shift} has {duration:int}")
    Shift.min_nurses = model.Property("{Shift} has {min_nurses:int}")
    Shift.min_skill = model.Property("{Shift} has {min_skill:int}")

    Availability = model.Concept("Availability")
    Availability.nurse = model.Property("{Availability} for {nurse:Nurse}")
    Availability.shift = model.Property("{Availability} in {shift:Shift}")
    Availability.available = model.Property("{Availability} is {available:int}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    nurses_df = read_csv(data_dir / "nurses.csv")
    data(nurses_df).into(Nurse, keys=["id"])

    shifts_df = read_csv(data_dir / "shifts.csv")
    data(shifts_df).into(Shift, keys=["id"])

    avail_df = read_csv(data_dir / "availability.csv")
    avail_data = data(avail_df)
    where(Nurse.id(avail_data.nurse_id), Shift.id(avail_data.shift_id)).define(
        Availability.new(nurse=Nurse, shift=Shift, available=avail_data.available)
    )

    # Assignment: decision variable for nurse-to-shift assignment
    Assignment = model.Concept("Assignment")
    Assignment.availability = model.Property("{Assignment} uses {availability:Availability}")
    Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
    define(Assignment.new(availability=Availability))

    model.Nurse, model.Shift, model.Availability, model.Assignment = Nurse, Shift, Availability, Assignment
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Nurse, Shift, Availability, Assignment = model.Nurse, model.Shift, model.Availability, model.Assignment

    # Decision variable: binary assignment
    s.solve_for(Assignment.assigned, type="bin", name=["x", Assignment.availability.nurse.name, Assignment.availability.shift.name])

    # Constraint: can only assign if available
    s.satisfy(require(Assignment.assigned <= Assignment.availability.available))

    # Constraint: each nurse works at most one shift
    Asn = Assignment.ref()
    nurse_shifts = sum(Asn.assigned).where(Asn.availability.nurse == Nurse).per(Nurse)
    s.satisfy(require(nurse_shifts <= 1))

    # Constraint: minimum nurses per shift
    shift_coverage = sum(Asn.assigned).where(Asn.availability.shift == Shift).per(Shift)
    s.satisfy(require(shift_coverage >= Shift.min_nurses))

    # Constraint: at least one nurse with required skill level per shift
    skilled_coverage = sum(Asn.assigned).where(
        Asn.availability.shift == Shift,
        Asn.availability.nurse.skill_level >= Shift.min_skill,
    ).per(Shift)
    s.satisfy(require(skilled_coverage >= 1))

    # Objective: minimize total staffing cost
    total_cost = sum(
        Assignment.assigned * Assignment.availability.shift.duration * Assignment.availability.nurse.hourly_cost
    )
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
    print(f"Total staffing cost: ${sol['objective']:.2f}")
    print("\nStaff assignments:")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
