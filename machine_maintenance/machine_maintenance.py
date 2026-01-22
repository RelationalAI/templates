# Machine Maintenance:
# Schedule preventive maintenance minimizing downtime cost

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("machine_maintenance", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Machines with maintenance requirements
Machine = model.Concept("Machine")
Machine.id = model.Property("{Machine} has {id:int}")
Machine.name = model.Property("{Machine} has {name:string}")
Machine.maintenance_hours = model.Property("{Machine} has {maintenance_hours:int}")
Machine.failure_cost = model.Property("{Machine} has {failure_cost:float}")
Machine.importance = model.Property("{Machine} has {importance:int}")
data(read_csv(data_dir / "machines.csv")).into(Machine, keys=["id"])

# Time slots with crew availability
TimeSlot = model.Concept("TimeSlot")
TimeSlot.id = model.Property("{TimeSlot} has {id:int}")
TimeSlot.day = model.Property("{TimeSlot} on {day:string}")
TimeSlot.crew_hours = model.Property("{TimeSlot} has {crew_hours:int}")
TimeSlot.cost_multiplier = model.Property("{TimeSlot} has {cost_multiplier:float}")
data(read_csv(data_dir / "time_slots.csv")).into(TimeSlot, keys=["id"])

# Conflicts: machines that cannot be maintained at the same time
Conflict = model.Concept("Conflict")
Conflict.machine1 = model.Property("{Conflict} between {machine1:Machine}")
Conflict.machine2 = model.Property("{Conflict} and {machine2:Machine}")

conflicts_data = data(read_csv(data_dir / "conflicts.csv"))
M2 = Machine.ref()
where(Machine.id(conflicts_data.machine1_id), M2.id(conflicts_data.machine2_id)).define(
    Conflict.new(machine1=Machine, machine2=M2)
)

# Schedule: decision variable for machine-to-slot assignment
Schedule = model.Concept("Schedule")
Schedule.machine = model.Property("{Schedule} for {machine:Machine}")
Schedule.slot = model.Property("{Schedule} in {slot:TimeSlot}")
Schedule.assigned = model.Property("{Schedule} is {assigned:float}")
define(Schedule.new(machine=Machine, slot=TimeSlot))

# --------------------------------------------------
# Define Optimization Problem
# --------------------------------------------------

Sch = Schedule.ref()

# Constraint: each machine scheduled exactly once
machine_scheduled = sum(Sch.assigned).where(Sch.machine == Machine).per(Machine)
exactly_once = require(machine_scheduled == 1)

# Constraint: crew hours per slot not exceeded
slot_hours = sum(Sch.assigned * Sch.machine.maintenance_hours).where(Sch.slot == TimeSlot).per(TimeSlot)
crew_limit = require(slot_hours <= TimeSlot.crew_hours)

# Constraint: conflicting machines cannot be scheduled in same slot
Sch1 = Schedule.ref()
Sch2 = Schedule.ref()
no_conflicts = require(Sch1.assigned + Sch2.assigned <= 1).where(
    Sch1.machine == Conflict.machine1,
    Sch2.machine == Conflict.machine2,
    Sch1.slot == Sch2.slot,
)

# Objective: minimize total maintenance cost (base cost * slot multiplier)
total_cost = sum(Schedule.assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier)

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont")
s.solve_for(Schedule.assigned, type="bin", name=["x", Schedule.machine.name, Schedule.slot.day])
s.minimize(total_cost)
s.satisfy(exactly_once)
s.satisfy(crew_limit)
s.satisfy(no_conflicts)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total maintenance cost: ${s.objective_value:.2f}")

# Access solution via populated relations
schedule = select(
    Schedule.machine.name.alias("machine"),
    Schedule.slot.day.alias("day")
).where(Schedule.assigned > 0.5).to_df()

print("\nMaintenance schedule:")
print(schedule.to_string(index=False))
