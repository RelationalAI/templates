"""Hospital staffing (prescriptive optimization) template.

This script models assigning nurses to shifts while minimizing overtime costs
and overflow penalties from unmet patient demand in RelationalAI:

- Load sample CSVs describing nurses, shifts, and nurse-shift availability.
- Create decision variables for nurse-shift assignments, overtime hours,
  patients served, and unmet demand per shift.
- Enforce availability, coverage, skill, overtime, and capacity constraints.
- Minimize overtime cost + overflow penalty for unserved patients.

Run:
    `python hospital_staffing.py`

Output:
    Prints the solver termination status, objective value, overtime assignments,
    patient throughput by shift, and staff assignments.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("hospital_staffing")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: nurses with skill level, cost, and overtime parameters
Nurse = Concept("Nurse", identify_by={"id": Integer})
Nurse.name = Property(f"{Nurse} has {String:name}")
Nurse.skill_level = Property(f"{Nurse} has {Integer:skill_level}")
Nurse.hourly_cost = Property(f"{Nurse} has {Float:hourly_cost}")
Nurse.regular_hours = Property(f"{Nurse} has {Integer:regular_hours}")
Nurse.overtime_multiplier = Property(f"{Nurse} has {Float:overtime_multiplier}")
Nurse.x_overtime_hours = Property(f"{Nurse} has {Float:overtime_hours}")
nurse_csv = read_csv(data_dir / "nurses.csv")
model.define(Nurse.new(model.data(nurse_csv).to_schema()))

# Concept: shifts with coverage requirements and patient demand
Shift = Concept("Shift", identify_by={"id": Integer})
Shift.name = Property(f"{Shift} has {String:name}")
Shift.start_hour = Property(f"{Shift} has {Integer:start_hour}")
Shift.duration = Property(f"{Shift} has {Integer:duration}")
Shift.min_nurses = Property(f"{Shift} has {Integer:min_nurses}")
Shift.min_skill = Property(f"{Shift} has {Integer:min_skill}")
Shift.patient_demand = Property(f"{Shift} has {Integer:patient_demand}")
Shift.patients_per_nurse_hour = Property(f"{Shift} has {Float:patients_per_nurse_hour}")
Shift.x_patients_served = Property(f"{Shift} has {Float:patients_served}")
Shift.x_unmet_demand = Property(f"{Shift} has {Float:unmet_demand}")
shift_csv = read_csv(data_dir / "shifts.csv")
model.define(Shift.new(model.data(shift_csv).to_schema()))

# Relationship: availability linking nurses to shifts
Availability = Concept("Availability", identify_by={"nurse_id": Integer, "shift_id": Integer})
Availability.nurse = Property(f"{Availability} for {Nurse}")
Availability.shift = Property(f"{Availability} in {Shift}")
Availability.available = Property(f"{Availability} is {Integer:available}")

avail_csv = read_csv(data_dir / "availability.csv")
avail_data = model.data(avail_csv)
model.define(
    a := Availability.new(nurse_id=avail_data.nurse_id, shift_id=avail_data.shift_id),
    a.available(avail_data.available),
)
model.define(Availability.nurse(Nurse)).where(Availability.nurse_id == Nurse.id)
model.define(Availability.shift(Shift)).where(Availability.shift_id == Shift.id)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: assignments of nurses to shifts
Assignment = Concept("Assignment", identify_by={"availability": Availability})
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(availability=Availability))

AssignmentRef = Assignment.ref()

# Parameters
overflow_penalty_per_patient = 20

s = Problem(model, Float)

# Variable: binary assignment (nurse to shift)
s.solve_for(Assignment.x_assigned, type="bin", name=["assigned", Assignment.availability.nurse.name, Assignment.availability.shift.name])

# Variable: overtime hours per nurse (continuous >= 0)
s.solve_for(Nurse.x_overtime_hours, type="cont", name=["ot", Nurse.name], lower=0)

# Variable: patients served per shift (continuous >= 0)
s.solve_for(Shift.x_patients_served, type="cont", name=["pt", Shift.name], lower=0)

# Variable: unmet patient demand per shift (continuous >= 0)
s.solve_for(Shift.x_unmet_demand, type="cont", name=["ud", Shift.name], lower=0)

# Constraint: can only assign if available
must_be_available = model.require(Assignment.x_assigned <= Assignment.availability.available)
s.satisfy(must_be_available)

# Constraint: every nurse works at least one shift
nurse_shift_count = sum(AssignmentRef.x_assigned).where(AssignmentRef.availability.nurse == Nurse).per(Nurse)
min_one_shift = model.require(nurse_shift_count >= 1)
s.satisfy(min_one_shift)

# Constraint: max 2 shifts per nurse (safety limit: 16 hours max)
max_two_shifts = model.require(nurse_shift_count <= 2)
s.satisfy(max_two_shifts)

# Constraint: minimum nurses per shift
shift_staff_count = sum(AssignmentRef.x_assigned).where(AssignmentRef.availability.shift == Shift).per(Shift)
min_coverage = model.require(shift_staff_count >= Shift.min_nurses)
s.satisfy(min_coverage)

# Constraint: at least one nurse with required skill level per shift
skilled_coverage = sum(AssignmentRef.x_assigned).where(
    AssignmentRef.availability.shift == Shift,
    AssignmentRef.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
min_skilled = model.require(skilled_coverage >= 1)
s.satisfy(min_skilled)

# Constraint: overtime >= total hours worked - regular hours
total_hours_worked = sum(AssignmentRef.x_assigned * AssignmentRef.availability.shift.duration).where(
    AssignmentRef.availability.nurse == Nurse
).per(Nurse)
overtime_def = model.require(Nurse.x_overtime_hours >= total_hours_worked - Nurse.regular_hours)
s.satisfy(overtime_def)

# Constraint: patients served <= patient demand per shift
demand_cap = model.require(Shift.x_patients_served <= Shift.patient_demand)
s.satisfy(demand_cap)

# Constraint: patients served <= nursing capacity per shift
shift_nursing_capacity = shift_staff_count * Shift.patients_per_nurse_hour * Shift.duration
capacity_cap = model.require(Shift.x_patients_served <= shift_nursing_capacity)
s.satisfy(capacity_cap)

# Constraint: unmet demand >= patient demand - patients served
unmet_def = model.require(Shift.x_unmet_demand >= Shift.patient_demand - Shift.x_patients_served)
s.satisfy(unmet_def)

# Objective: minimize overtime cost + overflow penalty for unmet patient demand
overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)
total_overflow_penalty = overflow_penalty_per_patient * sum(Shift.x_unmet_demand)
s.minimize(overtime_cost + total_overflow_penalty)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Objective value: ${s.objective_value:.2f}")

# Overtime summary
overtime = model.select(
    Nurse.name.alias("nurse"),
    Nurse.x_overtime_hours.alias("overtime_hours"),
).where(Nurse.x_overtime_hours > 0.5).to_df()

if not overtime.empty:
    print(f"\nOvertime assignments:")
    print(overtime.to_string(index=False))
else:
    print("\nNo overtime assigned.")

# Throughput and overflow summary
throughput = model.select(
    Shift.name.alias("shift"),
    Shift.x_patients_served.alias("patients_served"),
    Shift.patient_demand.alias("patient_demand"),
    Shift.x_unmet_demand.alias("unmet_demand"),
).to_df()

print(f"\nPatient throughput by shift:")
print(throughput.to_string(index=False))
print(f"Total patients served: {float(throughput['patients_served'].sum()):.0f} / {int(throughput['patient_demand'].astype(int).sum())}")
print(f"Total unmet demand: {float(throughput['unmet_demand'].sum()):.0f} patients")

# Staff assignments
assignments = model.select(
    Assignment.availability.nurse.name.alias("nurse"),
    Assignment.availability.shift.name.alias("shift"),
).where(Assignment.x_assigned > 0.5).to_df()

print(f"\nStaff assignments:")
print(assignments.to_string(index=False))
