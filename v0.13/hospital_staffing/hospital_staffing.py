"""Hospital staffing (prescriptive optimization) template.

This script models assigning nurses to shifts while minimizing overtime costs
and overflow penalties from unmet patient demand:

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

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, define, require, select, sum, where
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

model = Model("hospital_staffing", config=globals().get("config", None), use_lqp=False)

# Nurse concept: staff members with skill level, cost, and overtime parameters.
Nurse = model.Concept("Nurse")
Nurse.id = model.Property("{Nurse} has {id:int}")
Nurse.name = model.Property("{Nurse} has {name:string}")
Nurse.skill_level = model.Property("{Nurse} has {skill_level:int}")
Nurse.hourly_cost = model.Property("{Nurse} has {hourly_cost:float}")
Nurse.regular_hours = model.Property("{Nurse} has {regular_hours:int}")
Nurse.overtime_multiplier = model.Property("{Nurse} has {overtime_multiplier:float}")
Nurse.x_overtime_hours = model.Property("{Nurse} has {overtime_hours:float}")

# Load nurse data from CSV and create Nurse entities.
data(read_csv(DATA_DIR / "nurses.csv")).into(Nurse, keys=["id"])

# Shift concept: time periods with coverage requirements and patient demand.
Shift = model.Concept("Shift")
Shift.id = model.Property("{Shift} has {id:int}")
Shift.name = model.Property("{Shift} has {name:string}")
Shift.start_hour = model.Property("{Shift} has {start_hour:int}")
Shift.duration = model.Property("{Shift} has {duration:int}")
Shift.min_nurses = model.Property("{Shift} has {min_nurses:int}")
Shift.min_skill = model.Property("{Shift} has {min_skill:int}")
Shift.patient_demand = model.Property("{Shift} has {patient_demand:int}")
Shift.patients_per_nurse_hour = model.Property("{Shift} has {patients_per_nurse_hour:float}")
Shift.x_patients_served = model.Property("{Shift} has {patients_served:float}")
Shift.x_unmet_demand = model.Property("{Shift} has {unmet_demand:float}")

# Load shift data from CSV and create Shift entities.
data(read_csv(DATA_DIR / "shifts.csv")).into(Shift, keys=["id"])

# Availability concept: links nurses to shifts they can work.
Availability = model.Concept("Availability")
Availability.nurse = model.Property("{Availability} for {nurse:Nurse}")
Availability.shift = model.Property("{Availability} in {shift:Shift}")
Availability.available = model.Property("{Availability} is {available:int}")

# Load availability data from CSV.
avail_data = data(read_csv(DATA_DIR / "availability.csv"))

# Define Availability entities by joining nurse/shift IDs from the CSV with the
# Nurse and Shift concepts.
where(
    Nurse.id == avail_data.nurse_id,
    Shift.id == avail_data.shift_id,
).define(
    Availability.new(nurse=Nurse, shift=Shift, available=avail_data.available)
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Assignment decision concept: represents the decision variables for assigning
# nurses to shifts. Each Assignment is linked to an Availability entity, which
# indicates whether the nurse can work that shift.
Assignment = model.Concept("Assignment")
Assignment.availability = model.Property("{Assignment} uses {availability:Availability}")
Assignment.x_assigned = model.Property("{Assignment} is {assigned:float}")
define(Assignment.new(availability=Availability))

Asn = Assignment.ref()

s = SolverModel(model, "cont")

# Variable: binary assignment (nurse to shift)
s.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=[
        "x",
        Assignment.availability.nurse.name,
        Assignment.availability.shift.name,
    ],
)

# Variable: overtime hours per nurse (continuous >= 0)
s.solve_for(Nurse.x_overtime_hours, type="cont", name=["ot", Nurse.name], lower=0)

# Variable: patients served per shift (continuous >= 0)
s.solve_for(Shift.x_patients_served, type="cont", name=["pt", Shift.name], lower=0)

# Variable: unmet patient demand per shift (continuous >= 0)
s.solve_for(Shift.x_unmet_demand, type="cont", name=["ud", Shift.name], lower=0)

# Constraint: can only assign if available
must_be_available = require(Assignment.x_assigned <= Assignment.availability.available)
s.satisfy(must_be_available)

# Constraint: every nurse works at least one shift
nurse_shift_count = sum(Asn.assigned).where(Asn.availability.nurse == Nurse).per(Nurse)
min_one_shift = require(nurse_shift_count >= 1)
s.satisfy(min_one_shift)

# Constraint: max 2 shifts per nurse (safety limit: 16 hours max)
max_two_shifts = require(nurse_shift_count <= 2)
s.satisfy(max_two_shifts)

# Constraint: minimum nurses per shift
shift_staff_count = sum(Asn.assigned).where(Asn.availability.shift == Shift).per(Shift)
min_coverage = require(shift_staff_count >= Shift.min_nurses)
s.satisfy(min_coverage)

# Constraint: at least one nurse with required skill level per shift
skilled_coverage = sum(Asn.assigned).where(
    Asn.availability.shift == Shift,
    Asn.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
min_skilled = require(skilled_coverage >= 1)
s.satisfy(min_skilled)

# Constraint: overtime >= total hours worked - regular hours
total_hours_worked = sum(Asn.assigned * Asn.availability.shift.duration).where(
    Asn.availability.nurse == Nurse
).per(Nurse)
overtime_def = require(Nurse.x_overtime_hours >= total_hours_worked - Nurse.regular_hours)
s.satisfy(overtime_def)

# Constraint: patients served <= patient demand per shift
demand_cap = require(Shift.x_patients_served <= Shift.patient_demand)
s.satisfy(demand_cap)

# Constraint: patients served <= nursing capacity per shift
shift_nursing_capacity = shift_staff_count * Shift.patients_per_nurse_hour * Shift.duration
capacity_cap = require(Shift.x_patients_served <= shift_nursing_capacity)
s.satisfy(capacity_cap)

# Constraint: unmet demand >= patient demand - patients served
unmet_def = require(Shift.x_unmet_demand >= Shift.patient_demand - Shift.x_patients_served)
s.satisfy(unmet_def)

# Objective: minimize overtime cost + overflow penalty for unmet patient demand.
# overflow_penalty_per_patient represents the cost of failing to serve a patient
# (missed care ratios, throughput shortfall, regulatory risk).
overflow_penalty_per_patient = 20
overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)
total_overflow_penalty = overflow_penalty_per_patient * sum(Shift.x_unmet_demand)
s.minimize(overtime_cost + total_overflow_penalty)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

# Overtime summary
overtime = select(
    Nurse.name.alias("nurse"),
    Nurse.x_overtime_hours.alias("overtime_hours"),
).where(Nurse.x_overtime_hours > 0.5).to_df()

if not overtime.empty:
    print("\nOvertime assignments:")
    print(overtime.to_string(index=False))
else:
    print("\nNo overtime assigned.")

# Throughput and overflow summary
throughput = select(
    Shift.name.alias("shift"),
    Shift.x_patients_served.alias("patients_served"),
    Shift.patient_demand.alias("patient_demand"),
    Shift.x_unmet_demand.alias("unmet_demand"),
).to_df()

print("\nPatient throughput by shift:")
print(throughput.to_string(index=False))
print(f"Total patients served: {throughput['patients_served'].sum():.0f} / {throughput['patient_demand'].sum()}")
print(f"Total unmet demand: {throughput['unmet_demand'].sum():.0f} patients")

# Staff assignments
assignments = select(
    Assignment.availability.nurse.name.alias("nurse"),
    Assignment.availability.shift.name.alias("shift"),
).where(Assignment.x_assigned > 0.5).to_df()

print("\nStaff assignments:")
print(assignments.to_string(index=False))
