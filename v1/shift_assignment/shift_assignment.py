"""Shift Assignment (prescriptive optimization) template.

This script demonstrates a constraint satisfaction / feasibility problem in RelationalAI:

- Load sample CSVs describing workers, shifts, and worker-shift availability.
- Model workers and shifts as *concepts* with typed properties and an availability
  relationship.
- Choose a binary assignment variable for each available worker-shift pair.
- Enforce minimum coverage per shift and a maximum number of shifts per worker.
- Solve multiple minimum-coverage scenarios simultaneously using Scenario as a
  first-class Concept (single solve, all scenarios at once).

Modeling approach:
- Scenario is a Concept with a min_coverage parameter property.
- Decision variables are triple-argument Properties: (Worker, Shift, Scenario).
- Constraints use ref() bindings + .per(Scenario) to scope per-scenario.
- One solve handles all coverage levels; results extracted via model.select().

Run:
    `python shift_assignment.py`

Output:
    Prints per-scenario termination status and a table of assignments, followed
    by a scenario analysis summary.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("shift_assignment")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: workers
Worker = model.Concept("Worker", identify_by={"id": Integer})
Worker.name = model.Property(f"{Worker} has {String:name}")
worker_csv = read_csv(data_dir / "workers.csv")
model.define(Worker.new(model.data(worker_csv).to_schema()))

# Concept: shifts with capacity limits
Shift = model.Concept("Shift", identify_by={"id": Integer})
Shift.name = model.Property(f"{Shift} has {String:name}")
Shift.capacity = model.Property(f"{Shift} has {Integer:capacity}")
shift_csv = read_csv(data_dir / "shifts.csv")
model.define(Shift.new(model.data(shift_csv).to_schema()))

# Relationship: worker availability for shifts
Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")
availability_csv = read_csv(data_dir / "availability.csv")
availability_data = model.data(availability_csv)
model.define(Worker.available_for(Shift)).where(
    Worker.id(availability_data.worker_id),
    Shift.id(availability_data.shift_id)
)

# --------------------------------------------------
# Scenario Concept — min_coverage parameter variations
# --------------------------------------------------

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_coverage = model.Property(f"{Scenario} has {Integer:min_coverage}")
scenario_data = model.data(
    [("coverage_1", 1), ("coverage_2", 2), ("coverage_3", 3)],
    columns=["name", "min_coverage"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters
max_shifts = 1  # Maximum shifts per worker

# Decision variable — triple-arg: Worker x Shift x Scenario
Worker.x_assign = model.Property(f"{Worker} has {Shift} in {Scenario} if {Integer:assigned}")

# Ref for binding multi-arg variable in constraints
assigned_ref = Integer.ref()

p = Problem(model, Integer)

# Variable: binary assignment per available worker-shift-scenario
p.solve_for(
    Worker.x_assign(Shift, Scenario, assigned_ref),
    type="bin",
    name=["x", Scenario.name, Worker.name, Shift.name],
    where=[Worker.available_for(Shift)],
)

# Constraint: minimum coverage per shift (per scenario)
coverage_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Worker, assigned_ref).per(Shift, Scenario) >= Scenario.min_coverage)
p.satisfy(coverage_ic)

# Constraint: max shifts per worker (per scenario)
workload_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Shift, assigned_ref).per(Worker, Scenario) <= max_shifts)
p.satisfy(workload_ic)

# Constraint: max workers per shift (capacity limit per scenario)
capacity_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Worker, assigned_ref).per(Shift, Scenario) <= Shift.capacity)
p.satisfy(capacity_ic)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

p.display()
p.solve("minizinc", time_limit_sec=60)
p.solve_info().display()

# Verify constraints hold in the solver's solution — fires ICs without a separate query.
p.verify(coverage_ic, workload_ic, capacity_ic)
model.require(p.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Extract results per scenario
# --------------------------------------------------

print("\nAssignments per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Worker.name.alias("worker"),
    Shift.name.alias("shift"),
).where(
    Worker.x_assign(Shift, Scenario, assigned_ref), assigned_ref > 0
).inspect()
