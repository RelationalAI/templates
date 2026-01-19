"""Shift Assignment - Find valid worker-shift assignments using constraint satisfaction."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Worker, Shift, and Assignment concepts."""
    model = Model(f"shift_assignment_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Worker = model.Concept("Worker")
    Worker.id = model.Property("{Worker} has {id:int}")
    Worker.name = model.Property("{Worker} has {name:string}")

    Shift = model.Concept("Shift")
    Shift.id = model.Property("{Shift} has {id:int}")
    Shift.name = model.Property("{Shift} has {name:string}")

    Assignment = model.Concept("Assignment")
    Assignment.worker = model.Property("{Assignment} has {worker:Worker}")
    Assignment.shift = model.Property("{Assignment} has {shift:Shift}")
    Assignment.assigned = model.Property("{Assignment} assigned {assigned:int}")

    # Load data
    data_dir = Path(__file__).parent / "data"
    workers_csv = read_csv(data_dir / "workers.csv")
    shifts_csv = read_csv(data_dir / "shifts.csv")
    availability_csv = read_csv(data_dir / "availability.csv")

    data(workers_csv).into(Worker, keys=["id"])
    data(shifts_csv).into(Shift, keys=["id"])

    # Create assignments only for available worker-shift pairs
    avail = data(availability_csv)
    where(
        Worker.id(avail.worker_id),
        Shift.id(avail.shift_id)
    ).define(
        Assignment.new(worker=Worker, shift=Shift)
    )

    model.Worker = Worker
    model.Shift = Shift
    model.Assignment = Assignment
    return model


def define_problem(model, min_coverage=2, max_shifts_per_worker=1):
    """Define decision variables and constraints (CSP - no objective)."""
    Worker = model.Worker
    Shift = model.Shift
    Assignment = model.Assignment

    s = SolverModel(model, "int")

    # Decision variable: binary assignment
    s.solve_for(
        Assignment.assigned,
        name=["x", Assignment.worker.id, Assignment.shift.id],
        type="int"
    )

    # Constraint: binary bounds (0 or 1)
    s.satisfy(require(Assignment.assigned >= 0, Assignment.assigned <= 1))

    # Constraint: each worker works at most max_shifts_per_worker shifts
    worker_total = sum(Assignment.assigned).where(Assignment.worker == Worker)
    s.satisfy(require(worker_total <= max_shifts_per_worker).where(Worker))

    # Constraint: each shift needs minimum coverage
    shift_total = sum(Assignment.assigned).where(Assignment.shift == Shift)
    s.satisfy(require(shift_total >= min_coverage).where(Shift))

    # No objective - pure CSP (any valid assignment is acceptable)

    return s


def solve(config=None, solver_name="minizinc", min_coverage=2, max_shifts_per_worker=1):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model, min_coverage=min_coverage,
                                   max_shifts_per_worker=max_shifts_per_worker)

    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)

    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": None,  # CSP has no objective
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve(min_coverage=2)
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print("\nAssignments:")
    df = sol["variables"]
    if "int128" in df.columns:
        active = df[df["int128"] >= 1]
    elif "float" in df.columns:
        active = df[df["float"] >= 0.5]
    else:
        active = df
    print(active.to_string(index=False))
