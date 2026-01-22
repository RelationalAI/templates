# Shift Assignment:
# Assign workers to shifts ensuring minimum coverage while limiting shifts per worker

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("shift_assignment", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Workers
Worker = model.Concept("Worker")
Worker.id = model.Property("{Worker} has {id:int}")
Worker.name = model.Property("{Worker} has {name:string}")
data(read_csv(data_dir / "workers.csv")).into(Worker, keys=["id"])

# Shifts
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
data(read_csv(data_dir / "shifts.csv")).into(Shift, keys=["id"])

# Assignments - only for available worker-shift pairs
Assignment = model.Concept("Assignment")
Assignment.worker = model.Property("{Assignment} has {worker:Worker}")
Assignment.shift = model.Property("{Assignment} has {shift:Shift}")

avail = data(read_csv(data_dir / "availability.csv"))
where(
    Worker.id(avail.worker_id),
    Shift.id(avail.shift_id)
).define(
    Assignment.new(worker=Worker, shift=Shift)
)

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

min_coverage = 2  # minimum workers per shift
max_shifts_per_worker = 1  # maximum shifts per worker

# Decision variable: binary assignment (0 or 1)
Assignment.assigned = model.Property("{Assignment} assigned {assigned:int}")

# Reuse single ref for constraints
Asn = Assignment.ref()

# Constraint: each worker works at most max_shifts_per_worker shifts
worker_shifts = sum(Asn.assigned).where(Asn.worker == Worker).per(Worker)
max_shifts = require(worker_shifts <= max_shifts_per_worker)

# Constraint: each shift has minimum coverage
shift_coverage = sum(Asn.assigned).where(Asn.shift == Shift).per(Shift)
min_workers = require(shift_coverage >= min_coverage)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "int")
s.solve_for(
    Assignment.assigned,
    name=["x", Assignment.worker.name, Assignment.shift.name],
    type="bin"
)
s.satisfy(max_shifts)
s.satisfy(min_workers)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("minizinc")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")

# Access solution via populated relations
assignments = select(
    Assignment.worker.name.alias("worker"),
    Assignment.shift.name.alias("shift"),
    Assignment.assigned
).where(Assignment.assigned >= 1).to_df()

print("\nAssignments:")
print(assignments[["worker", "shift"]].to_string(index=False))

# Coverage summary
print("\nCoverage per shift:")
print(assignments.groupby("shift").size().reset_index(name="workers").to_string(index=False))
