"""Shift Assignment (prescriptive optimization) template.

This script demonstrates a small constraint satisfaction / feasibility problem in
RelationalAI:

- Load sample CSVs describing workers, shifts, and worker-shift availability.
- Create an `Assignment` decision concept for each available worker-shift pair.
- Choose a binary assignment variable for each pair.
- Enforce minimum coverage per shift and a maximum number of shifts per worker.

Run:
    `python shift_assignment.py`

Output:
    Prints the solver termination status, a table of assignments, and a coverage
    summary per shift.
"""

from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, Relationship, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("shift_assignment", config=globals().get("config", None))

# Worker concept: employees available for scheduling.
Worker = model.Concept("Worker")
Worker.id = model.Property("{Worker} has {id:int}")
Worker.name = model.Property("{Worker} has {name:string}")

# Load worker data from CSV.
data(read_csv(DATA_DIR / "workers.csv")).into(Worker, keys=["id"])

# Shift concept: time periods that require staffing.
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")

# Load shift data from CSV.
data(read_csv(DATA_DIR / "shifts.csv")).into(Shift, keys=["id"])

# Assignment decision concept: a worker-shift pair that can potentially be staffed.
# The availability table determines which pairs exist.
Assignment = model.Concept("Assignment")
Assignment.worker = model.Relationship("{Assignment} has {worker:Worker}")
Assignment.shift = model.Relationship("{Assignment} has {shift:Shift}")
Assignment.x_assigned = model.Property("{Assignment} assigned {assigned:int}")

# Load availability data from CSV.
avail = data(read_csv(DATA_DIR / "availability.csv"))

# Define Assignment entities by joining availability rows to Worker and Shift.
where(
    Worker.id == avail.worker_id,
    Shift.id == avail.shift_id
).define(
    Assignment.new(worker=Worker, shift=Shift)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters.
min_coverage = 2
max_shifts_per_worker = 1

AssignmentRef = Assignment.ref()

s = SolverModel(model, "int")

# Variable: binary assignment (0 or 1)
s.solve_for(
    Assignment.x_assigned,
    name=["x", Assignment.worker.name, Assignment.shift.name],
    type="bin",
)

# Constraint: each shift has minimum coverage
shift_coverage = where(
    AssignmentRef.shift == Shift
).require(
    sum(AssignmentRef.x_assigned).per(Shift) >= min_coverage
)
s.satisfy(shift_coverage)

# Constraint: each worker works at most max_shifts_per_worker shifts
worker_capacity = where(
    AssignmentRef.worker == Worker
).require(
    sum(AssignmentRef.x_assigned).per(Worker) <= max_shifts_per_worker
)
s.satisfy(worker_capacity)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("minizinc")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")

assignments = select(
    Assignment.worker.name.alias("worker"),
    Assignment.shift.name.alias("shift")
).where(Assignment.x_assigned >= 1).to_df()

print("\nAssignments:")
print(assignments.to_string(index=False))

print("\nCoverage per shift:")
print(assignments.groupby("shift").size().reset_index(name="workers").to_string(index=False))
