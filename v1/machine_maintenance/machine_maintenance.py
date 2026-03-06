"""Machine maintenance (prescriptive optimization) template.

This script demonstrates a multi-period preventive maintenance scheduling
workflow in RelationalAI:

- Load sample CSVs describing 50 machines (with ML-predicted remaining useful
  life), 40 technicians (with skills and certifications), and technician
  availability across a 12-period planning horizon.
- Create binary decision variables for maintenance timing (x_maintain),
  vulnerability tracking (x_vulnerable), and technician-machine assignment
  (x_assigned).
- Add constraints for cumulative maintenance coverage, assignment-maintenance
  linkage, technician availability, and parts/space capacity per period.
- Minimize expected total cost: failure risk weighted by vulnerability plus
  maintenance cost.

Run:
    `python machine_maintenance.py`

Output:
    Prints the solver termination status, objective value, a period-by-period
    maintenance schedule, and technician assignment details.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("machine_maintenance")

# --------------------------------------------------
# Configuration
# --------------------------------------------------

PERIOD_HORIZON = 4              # number of discrete planning periods
PARTS_CAPACITY_PER_PERIOD = 10000  # max maintenance jobs per period (parts)
SPACE_CAPACITY_PER_PERIOD = 10000  # max maintenance jobs per period (space)
COST_OF_FAIL = 10.0              # cost multiplier for an unmitigated failure
COST_OF_MAINTENANCE = 1.0        # cost multiplier for performing maintenance
FAILURE_TO_MAINTENANCE_RATIO = COST_OF_FAIL / COST_OF_MAINTENANCE

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

machines_df = read_csv(data_dir / "machines.csv")
technicians_df = read_csv(data_dir / "technicians.csv")
availability_df = read_csv(data_dir / "availability.csv")

# Concept: machines with ML-predicted remaining useful life, failure
# probability, criticality rating, and maintenance requirements.
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.machine_name = model.Property(f"{Machine} has {String:machine_name}")
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.location = model.Property(f"{Machine} in {String:location}")
Machine.remaining_useful_life = model.Property(
    f"{Machine} has remaining useful life {Float:remaining_useful_life}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.criticality = model.Property(f"{Machine} has criticality {String:criticality}")
Machine.maintenance_duration_hours = model.Property(
    f"{Machine} requires {Integer:maintenance_duration_hours} hours")
Machine.last_maintenance_date = model.Property(
    f"{Machine} last maintained {String:last_maintenance_date}")
Machine.parts_required = model.Property(f"{Machine} needs parts {String:parts_required}")
Machine.estimated_parts_cost = model.Property(
    f"{Machine} has parts cost {Float:estimated_parts_cost}")
model.define(Machine.new(model.data(machines_df).to_schema()))

# Concept: technicians with skills, certifications, hourly rates, and
# weekly hour caps.
Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.technician_name = model.Property(f"{Technician} has {String:technician_name}")
Technician.skill_level = model.Property(
    f"{Technician} has skill level {String:skill_level}")
Technician.base_location = model.Property(
    f"{Technician} based in {String:base_location}")
Technician.certifications = model.Property(
    f"{Technician} certified for {String:certifications}")
Technician.hourly_rate = model.Property(
    f"{Technician} has hourly rate {Float:hourly_rate}")
Technician.max_weekly_hours = model.Property(
    f"{Technician} has max weekly hours {Integer:max_weekly_hours}")
Technician.specialization = model.Property(
    f"{Technician} specializes in {String:specialization}")
model.define(Technician.new(model.data(technicians_df).to_schema()))

# Concept: discrete planning periods (1..PERIOD_HORIZON).
Period = model.Concept("Period", identify_by={"pid": Integer})
period_data = model.data([{"pid": t} for t in range(1, PERIOD_HORIZON + 1)])
model.define(Period.new(pid=period_data["pid"]))

# Cross-product concept: (machine, period) pairs — the scheduling decision
# space. Each pair carries a time-varying failure probability derived from
# the machine's remaining useful life.
MachinePeriod = model.Concept("MachinePeriod",
    identify_by={"machine": Machine, "period": Period})
MachinePeriod.fail_prob = model.Property(
    f"{MachinePeriod} has failure probability {Float:fail_prob}")
model.define(MachinePeriod.new(machine=Machine, period=Period))

# Derived property: failure probability = 1/RUL (capped at 1.0 when RUL <= 0).
MpInit = MachinePeriod.ref()
MmInit = Machine.ref()
model.where(MpInit.machine(MmInit), MmInit.remaining_useful_life > 0).define(
    MpInit.fail_prob(1.0 / MmInit.remaining_useful_life))
model.where(MpInit.machine(MmInit), MmInit.remaining_useful_life <= 0).define(
    MpInit.fail_prob(1.0))

# Cross-product concept: (technician, period) pairs — technician availability
# per period (0.0 = unavailable, 0.5 = partial, 1.0 = fully available).
TechnicianPeriod = model.Concept("TechnicianPeriod",
    identify_by={"technician": Technician, "period": Period})
TechnicianPeriod.capacity = model.Property(
    f"{TechnicianPeriod} has availability {Float:capacity}")

avail_data = model.data(availability_df)
TcInit = Technician.ref()
PrInit = Period.ref()
model.define(TechnicianPeriod.new(
    technician=TcInit, period=PrInit, capacity=avail_data["available"]
)).where(
    TcInit.technician_id == avail_data["technician_id"],
    PrInit.pid == avail_data["period"],
)

# Cross-product concept: (technician, machine, period) triples — the full
# assignment decision space.
TechnicianMachinePeriod = model.Concept("TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period})
model.define(TechnicianMachinePeriod.new(
    technician=Technician, machine=Machine, period=Period))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision variable properties — one per decision dimension.
MachinePeriod.x_maintain = model.Property(
    f"{MachinePeriod} maintain decision {Float:x_maintain}")
MachinePeriod.x_vulnerable = model.Property(
    f"{MachinePeriod} vulnerable flag {Float:x_vulnerable}")
TechnicianMachinePeriod.x_assigned = model.Property(
    f"{TechnicianMachinePeriod} assigned flag {Float:x_assigned}")

s = Problem(model, Float)

# Variables: all binary (maintain-or-not, vulnerable-or-not, assigned-or-not).
s.solve_for(MachinePeriod.x_maintain, type="bin")
s.solve_for(MachinePeriod.x_vulnerable, type="bin")
s.solve_for(TechnicianMachinePeriod.x_assigned, type="bin")

# References for aggregation expressions.
MachinePeriod_outer = MachinePeriod.ref()
MachinePeriod_inner = MachinePeriod.ref()
TechnicianMachinePeriod_ref = TechnicianMachinePeriod.ref()
Machine_ref = Machine.ref()
Period_outer = Period.ref()
Period_inner = Period.ref()
Technician_ref = Technician.ref()
Period_tc = Period.ref()
MachinePeriod_cap = MachinePeriod.ref()
Period_cap = Period.ref()
TechnicianPeriod_ref = TechnicianPeriod.ref()

# C1: Cumulative maintenance coverage.
# For each (machine, tau): sum_{t=1..tau} x_maintain(m,t) + x_vulnerable(m,tau) = 1.
# A machine is either maintained by period tau or remains vulnerable.
maintained_until_tau = sum(MachinePeriod_inner.x_maintain).where(
    MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer),
    MachinePeriod_inner.machine(Machine_ref), MachinePeriod_inner.period(Period_inner),
    Period_inner.pid >= 1, Period_inner.pid <= Period_outer.pid
).per(Machine_ref, Period_outer)

s.satisfy(
    model.require(maintained_until_tau + MachinePeriod_outer.x_vulnerable == 1)
    .where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))
)

# C2: Assignment-maintenance linkage.
# If a machine is maintained in period t, exactly one technician must be assigned.
assign_per_mp = sum(TechnicianMachinePeriod_ref.x_assigned).where(
    TechnicianMachinePeriod_ref.machine(Machine_ref), TechnicianMachinePeriod_ref.period(Period_outer)
).per(Machine_ref, Period_outer)

s.satisfy(
    model.require(assign_per_mp == MachinePeriod_outer.x_maintain)
    .where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))
)

# C3: Technician availability.
# Total assignments per technician per period must not exceed their capacity.
assigned_per_tc_t = sum(TechnicianMachinePeriod_ref.x_assigned).where(
    TechnicianMachinePeriod_ref.technician(Technician_ref), TechnicianMachinePeriod_ref.period(Period_tc)
).per(Technician_ref, Period_tc)

cap_per_tc_t = sum(TechnicianPeriod_ref.capacity).where(
    TechnicianPeriod_ref.technician(Technician_ref), TechnicianPeriod_ref.period(Period_tc)
).per(Technician_ref, Period_tc)

s.satisfy(model.require(assigned_per_tc_t <= cap_per_tc_t))

# C4: Parts and space capacity per period.
# At most N maintenance jobs can happen in any single period.
maint_per_period = sum(MachinePeriod_cap.x_maintain).where(MachinePeriod_cap.period(Period_cap)).per(Period_cap)
s.satisfy(model.require(maint_per_period <= PARTS_CAPACITY_PER_PERIOD))
s.satisfy(model.require(maint_per_period <= SPACE_CAPACITY_PER_PERIOD))

# Objective: minimize expected total cost.
# Each vulnerable machine-period incurs failure risk (fail_prob * cost ratio).
# Each maintained machine-period incurs a unit maintenance cost.
expected_cost = sum(
    MachinePeriod_outer.x_vulnerable * MachinePeriod_outer.fail_prob * FAILURE_TO_MAINTENANCE_RATIO
    + MachinePeriod_outer.x_maintain
).where(MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer))

s.minimize(expected_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=120, _server_side_import=False)
s.display_solve_info()

print(f"\nStatus: {s.termination_status}")
print(f"Objective value: {s.objective_value}")

# Maintenance schedule
maint_df = model.select(
    MachinePeriod.machine.machine_id.alias("machine_id"),
    MachinePeriod.period.pid.alias("period"),
).where(MachinePeriod.x_maintain > 0.5).to_df()

maint_df = maint_df.sort_values(["period", "machine_id"])
print(f"\nMaintenance schedule ({len(maint_df)} assignments):")
for period, g in maint_df.groupby("period"):
    machines = ", ".join(g["machine_id"].tolist())
    print(f"  Period {int(period)}: {machines}")

# Technician assignments
assign_df = model.select(
    TechnicianMachinePeriod.technician.technician_id.alias("technician_id"),
    TechnicianMachinePeriod.machine.machine_id.alias("machine_id"),
    TechnicianMachinePeriod.period.pid.alias("period"),
).where(TechnicianMachinePeriod.x_assigned > 0.5).to_df()

assign_df = assign_df.sort_values(["period", "machine_id", "technician_id"])
print(f"\nTechnician assignments ({len(assign_df)}):")
for period, g_period in assign_df.groupby("period"):
    print(f"  Period {int(period)}:")
    for machine, g_machine in g_period.groupby("machine_id"):
        techs = ", ".join(g_machine["technician_id"].tolist())
        print(f"    {machine}: {techs}")
