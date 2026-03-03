# shift assignment problem:
# assign workers to shifts based on availability to meet coverage requirements

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("shift_assignment")

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: workers
Worker = model.Concept("Worker", identify_by={"id": Integer})
Worker.name = model.Property(f"{Worker} has {String:name}")
worker_csv = read_csv(data_dir / "workers.csv")
model.define(Worker.new(model.data(worker_csv).to_schema()))

# Concept: shifts with minimum coverage requirements
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
# Model the problem
# --------------------------------------------------

# Parameters
max_shifts = 1         # Maximum shifts per worker

# Decision variable property (defined on model, solved per scenario)
Worker.x_assign = model.Property(f"{Worker} has {Shift} if {Integer:assigned}")

# Scenarios (what-if analysis)
SCENARIO_PARAM = "min_coverage"
SCENARIO_VALUES = [1, 2, 3]

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")
    min_coverage = scenario_value

    s = Problem(model, Integer)
    x = Integer.ref()
    s.solve_for(
        Worker.x_assign(Shift, x),
        type="bin",
        name=["x", Worker.name, Shift.name],
        where=[Worker.available_for(Shift)],
        populate=False,
    )
    s.satisfy(model.where(Worker.x_assign(Shift, x)).require(
        sum(Worker, x).per(Shift) >= min_coverage
    ))
    s.satisfy(model.where(Worker.x_assign(Shift, x)).require(
        sum(Shift, x).per(Worker) <= max_shifts
    ))

    s.display()
    s.solve("minizinc", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
    })
    print(f"  Status: {s.termination_status}")

    # Extract solution via variable_values() — populate=False avoids overwriting between scenarios
    var_df = s.variable_values().to_df()
    var_df["value"] = var_df["value"].astype(float)
    assigned = var_df[var_df["value"] > 0.5]
    print(f"  Assignments:\n{assigned.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  min_coverage={result['scenario']}: {result['status']}")
