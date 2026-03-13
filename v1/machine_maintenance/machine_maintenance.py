"""Machine maintenance (prescriptive optimization) template.

This script demonstrates a multi-period preventive maintenance scheduling
workflow in RelationalAI:

- Load sample CSVs describing 30 machines (with ML-predicted failure
  probability), 10 technicians (with skills and certifications), technician
  availability across a 4-period planning horizon, and a qualification
  mapping linking technicians to machine types they are certified for.
- Create binary decision variables for maintenance timing (x_maintain),
  vulnerability tracking (x_vulnerable), and technician-machine assignment
  (x_assigned).
- Add constraints for cumulative maintenance coverage, assignment-maintenance
  linkage, technician hours capacity, and parts/bay capacity per period.
- Minimize expected total cost: failure risk (probability * parts cost *
  criticality) for vulnerable machines, plus labor cost (duration * hourly
  rate) and travel cost for cross-location assignments.

Run:
    `python machine_maintenance.py`

Output:
    Prints the solver termination status, objective value, a period-by-period
    maintenance schedule, and technician assignment details with cost breakdown.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("machine_maintenance")

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PERIOD_HORIZON = 4  # number of discrete planning periods
PARTS_CAPACITY_PER_PERIOD = 5  # max maintenance jobs per period (parts/bay limit)
TRAVEL_COST_PER_HOUR = 50.0  # cost penalty when technician travels to another facility

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

machines_df = read_csv(DATA_DIR / "machines.csv")
technicians_df = read_csv(DATA_DIR / "technicians.csv")
availability_df = read_csv(DATA_DIR / "availability.csv")
qualifications_df = read_csv(DATA_DIR / "qualifications.csv")

# Concept: machines with ML-predicted failure probability, numeric
# criticality (1-5), maintenance duration, and estimated parts cost.
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.machine_name = model.Property(f"{Machine} has {String:machine_name}")
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.location = model.Property(f"{Machine} in {String:location}")
Machine.remaining_useful_life = model.Property(
    f"{Machine} has remaining useful life {Float:remaining_useful_life}"
)
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}"
)
Machine.criticality = model.Property(f"{Machine} has criticality {Integer:criticality}")
Machine.maintenance_duration_hours = model.Property(
    f"{Machine} requires {Integer:maintenance_duration_hours} hours"
)
Machine.last_maintenance_date = model.Property(
    f"{Machine} last maintained {String:last_maintenance_date}"
)
Machine.parts_required = model.Property(
    f"{Machine} needs parts {String:parts_required}"
)
Machine.estimated_parts_cost = model.Property(
    f"{Machine} has parts cost {Float:estimated_parts_cost}"
)
model.define(Machine.new(model.data(machines_df).to_schema()))

# Concept: technicians with skills, certifications, hourly rates, and
# weekly hour caps.
Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.technician_name = model.Property(
    f"{Technician} has {String:technician_name}"
)
Technician.skill_level = model.Property(
    f"{Technician} has skill level {String:skill_level}"
)
Technician.base_location = model.Property(
    f"{Technician} based in {String:base_location}"
)
Technician.certifications = model.Property(
    f"{Technician} certified for {String:certifications}"
)
Technician.hourly_rate = model.Property(
    f"{Technician} has hourly rate {Float:hourly_rate}"
)
Technician.max_weekly_hours = model.Property(
    f"{Technician} has max weekly hours {Integer:max_weekly_hours}"
)
Technician.specialization = model.Property(
    f"{Technician} specializes in {String:specialization}"
)
model.define(Technician.new(model.data(technicians_df).to_schema()))

# Concept: pre-computed qualification mapping — which technicians are
# certified to service which machine types.
Qualification = model.Concept(
    "Qualification", identify_by={"technician_id": String, "machine_type": String}
)
Qualification.technician = model.Property(f"{Qualification} for {Technician}")
Qualification.machine_type_str = model.Property(
    f"{Qualification} covers {String:machine_type_str}"
)
qual_data = model.data(qualifications_df)
model.define(
    q := Qualification.new(
        technician_id=qual_data["technician_id"], machine_type=qual_data["machine_type"]
    ),
    q.machine_type_str(qual_data["machine_type"]),
)
model.define(Qualification.technician(Technician)).where(
    Qualification.technician_id == Technician.technician_id
)

# Concept: discrete planning periods (1..PERIOD_HORIZON).
Period = model.Concept("Period", identify_by={"pid": Integer})
period_data = model.data([{"pid": t} for t in range(1, PERIOD_HORIZON + 1)])
model.define(Period.new(pid=period_data["pid"]))

# Cross-product concept: (machine, period) pairs — the scheduling decision
# space.
MachinePeriod = model.Concept(
    "MachinePeriod", identify_by={"machine": Machine, "period": Period}
)
model.define(MachinePeriod.new(machine=Machine, period=Period))

# Cross-product concept: (technician, period) pairs — technician capacity
# per period in hours (availability fraction * max_weekly_hours).
TechnicianPeriod = model.Concept(
    "TechnicianPeriod", identify_by={"technician": Technician, "period": Period}
)
TechnicianPeriod.capacity_hours = model.Property(
    f"{TechnicianPeriod} has available hours {Float:capacity_hours}"
)

avail_data = model.data(availability_df)
TcInit = Technician.ref()
PrInit = Period.ref()
model.define(
    TechnicianPeriod.new(
        technician=TcInit,
        period=PrInit,
        capacity_hours=avail_data["available"] * TcInit.max_weekly_hours,
    )
).where(
    TcInit.technician_id == avail_data["technician_id"],
    PrInit.pid == avail_data["period"],
)

# Cross-product concept: (technician, machine, period) triples — the
# assignment decision space, restricted to qualified pairs only.
TechnicianMachinePeriod = model.Concept(
    "TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period},
)
TechnicianMachinePeriod.same_location = model.Property(
    f"{TechnicianMachinePeriod} same location flag {Integer:same_location}"
)

QualRef = Qualification.ref()
model.define(
    TechnicianMachinePeriod.new(technician=Technician, machine=Machine, period=Period)
).where(
    QualRef.technician(Technician),
    QualRef.machine_type_str == Machine.machine_type,
)

# Derived property: same_location flag (1 if co-located, 0 otherwise).
TmpRef = TechnicianMachinePeriod.ref()
TmpTech = Technician.ref()
TmpMach = Machine.ref()
model.where(
    TmpRef.technician(TmpTech),
    TmpRef.machine(TmpMach),
    TmpTech.base_location == TmpMach.location,
).define(TmpRef.same_location(1))
model.where(
    TmpRef.technician(TmpTech),
    TmpRef.machine(TmpMach),
    TmpTech.base_location != TmpMach.location,
).define(TmpRef.same_location(0))

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Initialize
p = Problem(model, Float)

# References for aggregation
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

# Variable: maintain
MachinePeriod.x_maintain = model.Property(
    f"{MachinePeriod} maintain decision {Float:x_maintain}"
)
p.solve_for(MachinePeriod.x_maintain, type="bin")

# Variable: vulnerable
MachinePeriod.x_vulnerable = model.Property(
    f"{MachinePeriod} vulnerable flag {Float:x_vulnerable}"
)
p.solve_for(MachinePeriod.x_vulnerable, type="bin")

# Variable: assigned
TechnicianMachinePeriod.x_assigned = model.Property(
    f"{TechnicianMachinePeriod} assigned flag {Float:x_assigned}"
)
p.solve_for(TechnicianMachinePeriod.x_assigned, type="bin")

# Constraint: cumulative maintenance coverage
# For each (machine, tau): sum_{t=1..tau} x_maintain(m,t) + x_vulnerable(m,tau) = 1
# A machine is either maintained by period tau or remains vulnerable.
maintained_until_tau = (
    sum(MachinePeriod_inner.x_maintain)
    .where(
        MachinePeriod_outer.machine(Machine_ref),
        MachinePeriod_outer.period(Period_outer),
        MachinePeriod_inner.machine(Machine_ref),
        MachinePeriod_inner.period(Period_inner),
        Period_inner.pid >= 1,
        Period_inner.pid <= Period_outer.pid,
    )
    .per(Machine_ref, Period_outer)
)
p.satisfy(
    model.require(maintained_until_tau + MachinePeriod_outer.x_vulnerable == 1).where(
        MachinePeriod_outer.machine(Machine_ref),
        MachinePeriod_outer.period(Period_outer),
    )
)

# Constraint: assignment-maintenance linkage
# If a machine is maintained in period t, exactly one technician must be assigned.
assign_per_mp = (
    sum(TechnicianMachinePeriod_ref.x_assigned)
    .where(
        TechnicianMachinePeriod_ref.machine(Machine_ref),
        TechnicianMachinePeriod_ref.period(Period_outer),
    )
    .per(Machine_ref, Period_outer)
)
p.satisfy(
    model.require(assign_per_mp == MachinePeriod_outer.x_maintain).where(
        MachinePeriod_outer.machine(Machine_ref),
        MachinePeriod_outer.period(Period_outer),
    )
)

# Constraint: technician hours capacity
# Total assigned maintenance hours per technician per period <= available hours
assigned_hours = (
    sum(
        TechnicianMachinePeriod_ref.x_assigned
        * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
    )
    .where(
        TechnicianMachinePeriod_ref.technician(Technician_ref),
        TechnicianMachinePeriod_ref.period(Period_tc),
    )
    .per(Technician_ref, Period_tc)
)
avail_hours = (
    sum(TechnicianPeriod_ref.capacity_hours)
    .where(
        TechnicianPeriod_ref.technician(Technician_ref),
        TechnicianPeriod_ref.period(Period_tc),
    )
    .per(Technician_ref, Period_tc)
)
p.satisfy(model.require(assigned_hours <= avail_hours))

# Constraint: parts/bay capacity per period
# At most PARTS_CAPACITY_PER_PERIOD maintenance jobs in any single period.
maint_per_period = (
    sum(MachinePeriod_cap.x_maintain)
    .where(MachinePeriod_cap.period(Period_cap))
    .per(Period_cap)
)
p.satisfy(model.require(maint_per_period <= PARTS_CAPACITY_PER_PERIOD))

# Objective: minimize expected total cost
# 1. Failure risk: failure_probability * estimated_parts_cost * criticality
#    for each vulnerable machine-period.
# 2. Labor cost: maintenance_duration_hours * technician hourly_rate
#    for each assignment.
# 3. Travel cost: TRAVEL_COST_PER_HOUR * duration when technician is not
#    co-located with the machine.
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * MachinePeriod_outer.machine.failure_probability
    * MachinePeriod_outer.machine.estimated_parts_cost
    * MachinePeriod_outer.machine.criticality
).where(
    MachinePeriod_outer.machine(Machine_ref), MachinePeriod_outer.period(Period_outer)
)
labor_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
    * TechnicianMachinePeriod_ref.technician.hourly_rate
).where(
    TechnicianMachinePeriod_ref.machine(Machine_ref),
    TechnicianMachinePeriod_ref.period(Period_outer),
)
travel_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * (1 - TechnicianMachinePeriod_ref.same_location)
    * TechnicianMachinePeriod_ref.machine.maintenance_duration_hours
    * TRAVEL_COST_PER_HOUR
).where(
    TechnicianMachinePeriod_ref.machine(Machine_ref),
    TechnicianMachinePeriod_ref.period(Period_outer),
)
p.minimize(failure_cost + labor_cost + travel_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

p.display()
p.solve("highs", time_limit_sec=120)
p.display_solve_info()

print(f"\nStatus: {p.termination_status}")
print(f"Objective value: {p.objective_value:.2f}")

# Maintenance schedule
maint_df = (
    model.select(
        MachinePeriod.machine.machine_id.alias("machine_id"),
        MachinePeriod.machine.machine_type.alias("type"),
        MachinePeriod.machine.facility.alias("facility"),
        MachinePeriod.machine.criticality.alias("criticality"),
        MachinePeriod.period.pid.alias("period"),
    )
    .where(MachinePeriod.x_maintain > 0.5)
    .to_df()
)

maint_df = maint_df.sort_values(["period", "machine_id"])
print(f"\nMaintenance schedule ({len(maint_df)} jobs):")
for period, g in maint_df.groupby("period"):
    print(f"  Period {int(period)}:")
    for _, row in g.iterrows():
        print(
            f"    {row['machine_id']} ({row['type']}, {row['facility']}, crit={int(row['criticality'])})"
        )

# Technician assignments
assign_df = (
    model.select(
        TechnicianMachinePeriod.technician.technician_id.alias("technician_id"),
        TechnicianMachinePeriod.technician.base_location.alias("tech_location"),
        TechnicianMachinePeriod.machine.machine_id.alias("machine_id"),
        TechnicianMachinePeriod.machine.location.alias("machine_location"),
        TechnicianMachinePeriod.machine.maintenance_duration_hours.alias("hours"),
        TechnicianMachinePeriod.technician.hourly_rate.alias("rate"),
        TechnicianMachinePeriod.period.pid.alias("period"),
    )
    .where(TechnicianMachinePeriod.x_assigned > 0.5)
    .to_df()
)

assign_df = assign_df.sort_values(["period", "machine_id"])
print(f"\nTechnician assignments ({len(assign_df)}):")
for period, g in assign_df.groupby("period"):
    print(f"  Period {int(period)}:")
    for _, row in g.iterrows():
        travel = "" if row["tech_location"] == row["machine_location"] else " [TRAVEL]"
        cost = float(row["hours"]) * float(row["rate"])
        print(
            f"    {row['machine_id']}: {row['technician_id']} "
            f"({int(row['hours'])}h x ${float(row['rate']):.0f}/h = ${cost:.0f}){travel}"
        )
