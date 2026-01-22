# shift assignment problem:
# assign workers to shifts ensuring minimum coverage while limiting shifts per worker

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("shift_assignment", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: workers
Worker = model.Concept("Worker")
Worker.id = model.Property("{Worker} has {id:int}")
Worker.name = model.Property("{Worker} has {name:string}")
data(read_csv(data_dir / "workers.csv")).into(Worker, keys=["id"])

# Concept: shifts
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
data(read_csv(data_dir / "shifts.csv")).into(Shift, keys=["id"])

# Relationship: assignments linking available worker-shift pairs
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
# Model the problem
# --------------------------------------------------

# Parameters
min_coverage = 2
max_shifts_per_worker = 1

Asn = Assignment.ref()

s = SolverModel(model, "int")

# Variable: binary assignment (0 or 1)
Assignment.assigned = model.Property("{Assignment} assigned {assigned:int}")
s.solve_for(
    Assignment.assigned,
    name=["x", Assignment.worker.name, Assignment.shift.name],
    type="bin"
)

# Constraint: each worker works at most max_shifts_per_worker shifts
worker_shifts = sum(Asn.assigned).where(Asn.worker == Worker).per(Worker)
max_shifts = require(worker_shifts <= max_shifts_per_worker)
s.satisfy(max_shifts)

# Constraint: each shift has minimum coverage
shift_coverage = sum(Asn.assigned).where(Asn.shift == Shift).per(Shift)
min_workers = require(shift_coverage >= min_coverage)
s.satisfy(min_workers)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("minizinc")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")

assignments = select(
    Assignment.worker.name.alias("worker"),
    Assignment.shift.name.alias("shift"),
    Assignment.assigned
).where(Assignment.assigned >= 1).to_df()

print("\nAssignments:")
print(assignments[["worker", "shift"]].to_string(index=False))

print("\nCoverage per shift:")
print(assignments.groupby("shift").size().reset_index(name="workers").to_string(index=False))
