"""Hospital Staffing - Assign nurses to shifts meeting coverage and skill requirements."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Nurse, Shift, and Availability concepts."""
    model = Model(f"hospital_staffing_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Nurse: staff members with skills and costs
    Nurse = Concept("Nurse")
    Nurse.name = Property("{Nurse} has name {name:String}")
    Nurse.skill_level = Property("{Nurse} has skill_level {skill_level:int}")
    Nurse.hourly_cost = Property("{Nurse} has hourly_cost {hourly_cost:float}")
    nurses_df = read_csv(data_dir / "nurses.csv")
    data(nurses_df).into(Nurse, id="id", properties=["name", "skill_level", "hourly_cost"])

    # Shift: time periods requiring staffing
    Shift = Concept("Shift")
    Shift.name = Property("{Shift} has name {name:String}")
    Shift.start_hour = Property("{Shift} has start_hour {start_hour:int}")
    Shift.duration = Property("{Shift} has duration {duration:int}")
    Shift.min_nurses = Property("{Shift} has min_nurses {min_nurses:int}")
    Shift.min_skill = Property("{Shift} has min_skill {min_skill:int}")
    shifts_df = read_csv(data_dir / "shifts.csv")
    data(shifts_df).into(Shift, id="id", properties=["name", "start_hour", "duration", "min_nurses", "min_skill"])

    # Availability: which nurses can work which shifts
    Availability = Concept("Availability")
    Availability.nurse = Relationship("{Availability} for {nurse:Nurse}")
    Availability.shift = Relationship("{Availability} in {shift:Shift}")
    Availability.available = Property("{Availability} is available {available:int}")
    avail_df = read_csv(data_dir / "availability.csv")
    data(avail_df).into(
        Availability,
        keys=["nurse_id", "shift_id"],
        properties=["available"],
        relationships={"nurse": ("nurse_id", Nurse), "shift": ("shift_id", Shift)},
    )

    # Assignment: decision variable for nurse-to-shift assignment
    Assignment = Concept("Assignment")
    Assignment.availability = Relationship("{Assignment} uses {availability:Availability}")
    Assignment.assigned = Property("{Assignment} is assigned {assigned:float}")
    define(Assignment.new(availability=Availability))

    model.Nurse, model.Shift, model.Availability, model.Assignment = Nurse, Shift, Availability, Assignment
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Nurse, Shift, Availability, Assignment = model.Nurse, model.Shift, model.Availability, model.Assignment

    # Decision variable: binary assignment
    s.solve_for(Assignment.assigned, type="bin", name=[Assignment.availability.nurse, Assignment.availability.shift])

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
