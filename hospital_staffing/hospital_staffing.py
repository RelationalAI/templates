# Hospital Staffing:
# Assign nurses to shifts meeting coverage and skill requirements at minimum cost

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("hospital_staffing", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Nurses with skill level and hourly cost
Nurse = model.Concept("Nurse")
Nurse.id = model.Property("{Nurse} has {id:int}")
Nurse.name = model.Property("{Nurse} has {name:string}")
Nurse.skill_level = model.Property("{Nurse} has {skill_level:int}")
Nurse.hourly_cost = model.Property("{Nurse} has {hourly_cost:float}")
data(read_csv(data_dir / "nurses.csv")).into(Nurse, keys=["id"])

# Shifts with coverage requirements
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
Shift.start_hour = model.Property("{Shift} has {start_hour:int}")
Shift.duration = model.Property("{Shift} has {duration:int}")
Shift.min_nurses = model.Property("{Shift} has {min_nurses:int}")
Shift.min_skill = model.Property("{Shift} has {min_skill:int}")
data(read_csv(data_dir / "shifts.csv")).into(Shift, keys=["id"])

# Availability: which nurses can work which shifts
Availability = model.Concept("Availability")
Availability.nurse = model.Property("{Availability} for {nurse:Nurse}")
Availability.shift = model.Property("{Availability} in {shift:Shift}")
Availability.available = model.Property("{Availability} is {available:int}")

avail_data = data(read_csv(data_dir / "availability.csv"))
where(Nurse.id(avail_data.nurse_id), Shift.id(avail_data.shift_id)).define(
    Availability.new(nurse=Nurse, shift=Shift, available=avail_data.available)
)

# Assignment: decision variable for nurse-to-shift assignment
Assignment = model.Concept("Assignment")
Assignment.availability = model.Property("{Assignment} uses {availability:Availability}")
Assignment.assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(availability=Availability))

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

Asn = Assignment.ref()

# Constraint: can only assign if available
must_be_available = require(Assignment.assigned <= Assignment.availability.available)

# Constraint: each nurse works at most one shift
nurse_shifts = sum(Asn.assigned).where(Asn.availability.nurse == Nurse).per(Nurse)
one_shift_max = require(nurse_shifts <= 1)

# Constraint: minimum nurses per shift
shift_coverage = sum(Asn.assigned).where(Asn.availability.shift == Shift).per(Shift)
min_coverage = require(shift_coverage >= Shift.min_nurses)

# Constraint: at least one nurse with required skill level per shift
skilled_coverage = sum(Asn.assigned).where(
    Asn.availability.shift == Shift,
    Asn.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
min_skilled = require(skilled_coverage >= 1)

# Objective: minimize total staffing cost
total_cost = sum(
    Assignment.assigned * Assignment.availability.shift.duration * Assignment.availability.nurse.hourly_cost
)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Assignment.assigned, type="bin", name=["x", Assignment.availability.nurse.name, Assignment.availability.shift.name])
s.minimize(total_cost)
s.satisfy(must_be_available)
s.satisfy(one_shift_max)
s.satisfy(min_coverage)
s.satisfy(min_skilled)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total staffing cost: ${s.objective_value:.2f}")

# Access solution via populated relations
assignments = select(
    Assignment.availability.nurse.name.alias("nurse"),
    Assignment.availability.shift.name.alias("shift")
).where(Assignment.assigned > 0.5).to_df()

print("\nStaff assignments:")
print(assignments.to_string(index=False))
