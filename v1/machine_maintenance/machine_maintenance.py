"""Machine maintenance (prescriptive optimization) template.

This script demonstrates a mixed-integer linear optimization (MILP) scheduling
workflow in RelationalAI:

- Load sample CSVs describing machines, time slots, and machine conflict pairs.
- Create a binary decision variable for assigning each machine to a time slot.
- Add constraints for exactly-once scheduling, per-slot crew-hour capacity, and
  conflict exclusions.
- Minimize total expected maintenance cost.

Run:
    `python machine_maintenance.py`

Output:
    Prints the solver termination status, objective value, and a table
    describing the selected machine-to-day schedule.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("machine_maintenance")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: machines with maintenance requirements
Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.maintenance_hours = Property(f"{Machine} has {Integer:maintenance_hours}")
Machine.failure_cost = Property(f"{Machine} has {Float:failure_cost}")
Machine.importance = Property(f"{Machine} has {Integer:importance}")
machine_csv = read_csv(data_dir / "machines.csv")
model.define(Machine.new(model.data(machine_csv).to_schema()))

# Concept: time slots with crew availability
TimeSlot = Concept("TimeSlot", identify_by={"id": Integer})
TimeSlot.day = Property(f"{TimeSlot} on {String:day}")
TimeSlot.crew_hours = Property(f"{TimeSlot} has {Integer:crew_hours}")
TimeSlot.cost_multiplier = Property(f"{TimeSlot} has {Float:cost_multiplier}")
timeslot_csv = read_csv(data_dir / "time_slots.csv")
model.define(TimeSlot.new(model.data(timeslot_csv).to_schema()))

# Relationship: conflicts between machines that cannot be maintained at same time
Conflict = Concept("Conflict")
Conflict.machine1 = Property(f"{Conflict} between {Machine}", short_name="machine1")
Conflict.machine2 = Property(f"{Conflict} and {Machine}", short_name="machine2")

OtherMachine = Machine.ref()
conflicts_csv = read_csv(data_dir / "conflicts.csv")
conflict_data = model.data(conflicts_csv)
model.define(Conflict.new(machine1=Machine, machine2=OtherMachine)).where(
    Machine.id == conflict_data.machine1_id, OtherMachine.id == conflict_data.machine2_id
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: schedule assignments of machines to time slots
Schedule = Concept("Schedule")
Schedule.machine = Property(f"{Schedule} for {Machine}", short_name="machine")
Schedule.slot = Property(f"{Schedule} in {TimeSlot}", short_name="slot")
Schedule.x_assigned = Property(f"{Schedule} is {Float:assigned}")
model.define(Schedule.new(machine=Machine, slot=TimeSlot))

ScheduleRef = Schedule.ref()
ScheduleA = Schedule.ref()
ScheduleB = Schedule.ref()

s = Problem(model, Float)

# Variable: binary assignment
s.solve_for(Schedule.x_assigned, type="bin", name=["sched", Schedule.machine.name, Schedule.slot.day])

# Constraint: each machine scheduled exactly once
machine_scheduled = sum(ScheduleRef.x_assigned).where(ScheduleRef.machine == Machine).per(Machine)
exactly_once = model.require(machine_scheduled == 1)
s.satisfy(exactly_once)

# Constraint: crew hours per slot not exceeded
slot_hours = sum(ScheduleRef.x_assigned * ScheduleRef.machine.maintenance_hours).where(ScheduleRef.slot == TimeSlot).per(TimeSlot)
crew_limit = model.require(slot_hours <= TimeSlot.crew_hours)
s.satisfy(crew_limit)

# Constraint: conflicting machines cannot be scheduled in same slot
no_conflicts = model.require(ScheduleA.x_assigned + ScheduleB.x_assigned <= 1).where(
    ScheduleA.machine == Conflict.machine1,
    ScheduleB.machine == Conflict.machine2,
    ScheduleA.slot == ScheduleB.slot,
)
s.satisfy(no_conflicts)

# Objective: minimize total maintenance cost (base cost * slot multiplier)
total_cost = sum(Schedule.x_assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier)
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total maintenance cost: ${s.objective_value:.2f}")

schedule = model.select(
    Schedule.machine.name.alias("machine"),
    Schedule.slot.day.alias("day")
).where(Schedule.x_assigned > 0.5).to_df()

print("\nMaintenance schedule:")
print(schedule.to_string(index=False))
