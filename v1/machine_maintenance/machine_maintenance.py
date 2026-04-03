"""Machine maintenance (multi-reasoner) template.

This script demonstrates a chained multi-reasoner workflow in RelationalAI,
combining graph analysis, rules-based classification, and prescriptive
optimization in a single template:

- Stage 1 -- Graph: build a machine dependency graph from shared-technician
  qualifications, compute weakly connected components (dependency clusters)
  and betweenness centrality (bottleneck machines).
- Stage 2 -- Rules: derive compliance flags for overdue maintenance, high-risk
  machines, parts reorder triggers, and expiring certifications.
- Stage 3 -- Prescriptive: schedule preventive maintenance across a multi-period
  horizon, assigning qualified technicians to machines. The optimization
  consumes graph and rules outputs: betweenness centrality weights the failure
  cost term, and overdue-maintenance flags add hard scheduling constraints.

Run:
    `python machine_maintenance.py`

Output:
    Prints graph analysis results (dependency clusters, centrality scores),
    compliance flags (overdue machines, parts reorder, expiring certs), and
    the optimized maintenance schedule with technician assignments and cost
    breakdown.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

model = Model("machine_maintenance")

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PERIOD_HORIZON = 4  # number of discrete planning periods
PARTS_CAPACITY_PER_PERIOD = 5  # max maintenance jobs per period (parts/bay limit)
TRAVEL_COST_PER_HOUR = 50.0  # cost penalty when technician travels to another facility
CENTRALITY_WEIGHT = 2.0  # multiplier for betweenness centrality in failure cost
OVERDUE_DEADLINE = 2  # overdue machines must be maintained by this period

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Load machine data from CSV.
machines_df = read_csv(DATA_DIR / "machines.csv")
technicians_df = read_csv(DATA_DIR / "technicians.csv")
availability_df = read_csv(DATA_DIR / "availability.csv")
qualifications_df = read_csv(DATA_DIR / "qualifications.csv")
parts_df = read_csv(DATA_DIR / "parts_inventory.csv")
cert_df = read_csv(DATA_DIR / "certification_expiry.csv")

# Machine concept: manufacturing machines with ML-predicted failure probability,
# numeric criticality (1-5), maintenance duration, and estimated parts cost.
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

# Technician concept: maintenance personnel with skills, certifications,
# hourly rates, and weekly hour caps.
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

# Qualification concept: pre-computed mapping of which technicians are
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

# PartsInventory concept: spare parts stock levels at each facility.
PartsInventory = model.Concept("PartsInventory", identify_by={"part_id": String})
PartsInventory.facility = model.Property(f"{PartsInventory} at {String:facility}")
PartsInventory.part_name = model.Property(f"{PartsInventory} has {String:part_name}")
PartsInventory.stock_level = model.Property(
    f"{PartsInventory} has {Integer:stock_level} units in stock"
)
PartsInventory.min_order_qty = model.Property(
    f"{PartsInventory} minimum order {Integer:min_order_qty} units"
)
model.define(PartsInventory.new(model.data(parts_df).to_schema()))

# CertificationExpiry concept: tracks days remaining on technician-machine-type
# certifications. Used by rules stage to flag expiring qualifications.
CertificationExpiry = model.Concept(
    "CertificationExpiry",
    identify_by={"technician_id": String, "machine_type": String},
)
CertificationExpiry.days_remaining = model.Property(
    f"{CertificationExpiry} has {Integer:days_remaining} days remaining"
)
CertificationExpiry.technician = model.Property(
    f"{CertificationExpiry} for {Technician}"
)
cert_data_ref = model.data(cert_df)
model.define(
    c := CertificationExpiry.new(
        technician_id=cert_data_ref["technician_id"],
        machine_type=cert_data_ref["machine_type"],
    ),
    c.days_remaining(cert_data_ref["days_remaining"]),
)
model.define(CertificationExpiry.technician(Technician)).where(
    CertificationExpiry.technician_id == Technician.technician_id
)

# Period concept: discrete planning periods (1..PERIOD_HORIZON).
Period = model.Concept("Period", identify_by={"pid": Integer})
period_data = model.data([{"pid": t} for t in range(1, PERIOD_HORIZON + 1)])
model.define(Period.new(pid=period_data["pid"]))

# MachinePeriod concept: (machine, period) pairs -- the scheduling decision space.
# Use string/integer keys to avoid entity-valued identify_by recursion (SDK 1.0.12).
MachinePeriod = model.Concept(
    "MachinePeriod", identify_by={"machine_id": String, "pid": Integer}
)
MachinePeriod.machine = model.Property(f"{MachinePeriod} for {Machine}")
MachinePeriod.period = model.Property(f"{MachinePeriod} in {Period}")
MpInitM = Machine.ref()
MpInitP = Period.ref()
model.define(
    mp := MachinePeriod.new(machine_id=MpInitM.machine_id, pid=MpInitP.pid),
    mp.machine(MpInitM),
    mp.period(MpInitP),
)

# TechnicianPeriod concept: technician capacity per period in hours
# (availability fraction * max_weekly_hours).
TechnicianPeriod = model.Concept(
    "TechnicianPeriod", identify_by={"technician_id": String, "pid": Integer}
)
TechnicianPeriod.technician = model.Property(f"{TechnicianPeriod} for {Technician}")
TechnicianPeriod.period = model.Property(f"{TechnicianPeriod} in {Period}")
TechnicianPeriod.capacity_hours = model.Property(
    f"{TechnicianPeriod} has available hours {Float:capacity_hours}"
)

avail_data = model.data(availability_df)
TcInit = Technician.ref()
PrInit = Period.ref()
model.define(
    tp := TechnicianPeriod.new(
        technician_id=TcInit.technician_id,
        pid=PrInit.pid,
        capacity_hours=avail_data["available"] * TcInit.max_weekly_hours,
    ),
    tp.technician(TcInit),
    tp.period(PrInit),
).where(
    TcInit.technician_id == avail_data["technician_id"],
    PrInit.pid == avail_data["period"],
)

# TechnicianMachinePeriod concept: (technician, machine, period) triples --
# the assignment decision space, restricted to qualified pairs only.
TechnicianMachinePeriod = model.Concept(
    "TechnicianMachinePeriod",
    identify_by={"technician_id": String, "machine_id": String, "pid": Integer},
)
TechnicianMachinePeriod.technician = model.Property(
    f"{TechnicianMachinePeriod} for {Technician}"
)
TechnicianMachinePeriod.machine = model.Property(
    f"{TechnicianMachinePeriod} for {Machine}"
)
TechnicianMachinePeriod.period = model.Property(
    f"{TechnicianMachinePeriod} in {Period}"
)
TechnicianMachinePeriod.same_location = model.Property(
    f"{TechnicianMachinePeriod} same location flag {Integer:same_location}"
)

QualRef = Qualification.ref()
TmpInitTech = Technician.ref()
TmpInitMach = Machine.ref()
TmpInitPer = Period.ref()
model.define(
    tmp := TechnicianMachinePeriod.new(
        technician_id=TmpInitTech.technician_id,
        machine_id=TmpInitMach.machine_id,
        pid=TmpInitPer.pid,
    ),
    tmp.technician(TmpInitTech),
    tmp.machine(TmpInitMach),
    tmp.period(TmpInitPer),
).where(
    QualRef.technician(TmpInitTech),
    QualRef.machine_type_str == TmpInitMach.machine_type,
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
# Stage 1: Graph -- dependency clusters & centrality
# --------------------------------------------------

# Separate model for graph analysis. Post-solve queries via p.variable_values()
# conflict with recursive graph definitions on the same model, so the graph
# runs on its own model with results written back via model.data().
#
# Pre-compute edges in pandas: two machines share an edge if any technician is
# qualified for both their machine types.
qual_machines = qualifications_df.merge(
    machines_df[["machine_id", "machine_type"]], on="machine_type"
)
edge_pairs = qual_machines.merge(
    qual_machines, on="technician_id", suffixes=("_src", "_dst")
)
edges_df = (
    edge_pairs[edge_pairs["machine_id_src"] < edge_pairs["machine_id_dst"]]
    [["machine_id_src", "machine_id_dst"]]
    .drop_duplicates()
    .reset_index(drop=True)
)

graph_model = Model("machine_maintenance_graph")
GMachine = graph_model.Concept("Machine", identify_by={"machine_id": String})
GMachine.machine_name = graph_model.Property(f"{GMachine} has {String:machine_name}")
GMachine.machine_type = graph_model.Property(f"{GMachine} has type {String:machine_type}")
GMachine.facility = graph_model.Property(f"{GMachine} at {String:facility}")
GMachine.failure_probability = graph_model.Property(
    f"{GMachine} has failure probability {Float:failure_probability}"
)
graph_model.define(GMachine.new(
    graph_model.data(machines_df[["machine_id", "machine_name", "machine_type",
                                  "facility", "failure_probability"]]).to_schema()
))

dep_graph = Graph(
    graph_model, directed=False, weighted=False, node_concept=GMachine, aggregator="sum"
)

edge_data = graph_model.data(edges_df)
gm1 = GMachine.ref("gm1")
gm2 = GMachine.ref("gm2")
graph_model.where(
    gm1.machine_id == edge_data["machine_id_src"],
    gm2.machine_id == edge_data["machine_id_dst"],
).define(dep_graph.Edge.new(src=gm1, dst=gm2))

print("=" * 70)
print("STAGE 1: Graph Analysis -- Dependency Clusters & Centrality")
print("=" * 70)

dep_graph.num_nodes().inspect()
dep_graph.num_edges().inspect()

# Weakly connected components: identify dependency clusters.
wcc = dep_graph.weakly_connected_component()

node_ref = dep_graph.Node.ref("n")
comp_ref = dep_graph.Node.ref("comp")

wcc_df = (
    graph_model.where(wcc(node_ref, comp_ref))
    .select(
        node_ref.machine_id.alias("machine_id"),
        node_ref.machine_name.alias("machine_name"),
        node_ref.machine_type.alias("machine_type"),
        node_ref.facility.alias("facility"),
        comp_ref.machine_id.alias("component_id"),
        aggs.count(node_ref).per(comp_ref).alias("cluster_size"),
    )
    .to_df()
)

num_clusters = wcc_df["component_id"].nunique()
print(f"\nDependency clusters found: {num_clusters}")
for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    cluster_size = int(comp_df["cluster_size"].iloc[0])
    facilities = ", ".join(sorted(comp_df["facility"].unique()))
    print(f"\n  Cluster {comp_id}: {cluster_size} machines ({facilities})")
    for _, row in comp_df.sort_values(["facility", "machine_name"]).head(5).iterrows():
        print(f"    - {row['machine_name']} ({row['machine_type']}, {row['facility']})")
    if cluster_size > 5:
        print(f"    ... and {cluster_size - 5} more")

# Betweenness centrality: find bottleneck machines whose maintenance blocks
# the most technician scheduling options.
betweenness = dep_graph.betweenness_centrality()

node_b = dep_graph.Node.ref("nb")
btwn_score = Float.ref("btwn")

betweenness_df = (
    graph_model.where(betweenness(node_b, btwn_score))
    .select(
        node_b.machine_id.alias("machine_id"),
        node_b.machine_name.alias("machine_name"),
        node_b.machine_type.alias("machine_type"),
        node_b.facility.alias("facility"),
        node_b.failure_probability.alias("failure_probability"),
        btwn_score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\nTop bottleneck machines (betweenness centrality):")
for _, row in betweenness_df.head(10).iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_type']}, {row['facility']}): "
        f"betweenness={row['betweenness']:.4f}, "
        f"failure_prob={row['failure_probability']:.3f}"
    )

# Store betweenness as a property on Machine for use in the optimization objective.
# Normalize to [0, 1] range so the centrality weight is interpretable.
max_betweenness = betweenness_df["betweenness"].max()
if max_betweenness == 0:
    max_betweenness = 1.0  # avoid division by zero

Machine.betweenness = model.Property(
    f"{Machine} has betweenness centrality {Float:betweenness}"
)
betweenness_df["normalized"] = betweenness_df["betweenness"] / max_betweenness
btwn_data = model.data(betweenness_df[["machine_id", "normalized"]])
model.where(Machine.machine_id == btwn_data["machine_id"]).define(
    Machine.betweenness(btwn_data["normalized"])
)

# --------------------------------------------------
# Stage 2: Rules -- compliance flags
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 2: Rules -- Compliance Flags")
print("=" * 70)

# Rule 1: Machine is overdue for maintenance when remaining useful life
# is less than the time required to perform maintenance.
Machine.is_overdue_maintenance = model.Relationship(
    f"{Machine} is overdue maintenance"
)
model.where(
    Machine.remaining_useful_life < floats.float(Machine.maintenance_duration_hours)
).define(Machine.is_overdue_maintenance())

overdue_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.machine_name.alias("machine_name"),
        Machine.facility.alias("facility"),
        Machine.remaining_useful_life.alias("remaining_useful_life"),
        Machine.maintenance_duration_hours.alias("maintenance_duration_hours"),
    )
    .where(Machine.is_overdue_maintenance())
    .to_df()
)
print(f"\nOverdue maintenance ({len(overdue_df)} machines):")
for _, row in overdue_df.iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_name']}): "
        f"RUL={row['remaining_useful_life']:.1f}h < "
        f"duration={int(row['maintenance_duration_hours'])}h"
    )

# Rule 2: Machine is high risk when failure probability > 0.3 AND
# criticality >= 4 (on a 1-5 scale).
Machine.is_high_risk = model.Relationship(f"{Machine} is high risk")
model.where(
    Machine.failure_probability > 0.3,
    Machine.criticality >= 4,
).define(Machine.is_high_risk())

high_risk_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.machine_name.alias("machine_name"),
        Machine.failure_probability.alias("failure_probability"),
        Machine.criticality.alias("criticality"),
    )
    .where(Machine.is_high_risk())
    .to_df()
)
print(f"\nHigh-risk machines ({len(high_risk_df)}):")
for _, row in high_risk_df.iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_name']}): "
        f"prob={row['failure_probability']:.3f}, crit={int(row['criticality'])}"
    )

# Rule 3: Parts inventory needs reorder when stock has dropped to or below
# the minimum order quantity.
PartsInventory.needs_reorder = model.Relationship(
    f"{PartsInventory} needs reorder"
)
model.where(
    PartsInventory.stock_level <= PartsInventory.min_order_qty
).define(PartsInventory.needs_reorder())

reorder_df = (
    model.select(
        PartsInventory.part_id.alias("part_id"),
        PartsInventory.part_name.alias("part_name"),
        PartsInventory.facility.alias("facility"),
        PartsInventory.stock_level.alias("stock_level"),
        PartsInventory.min_order_qty.alias("min_order_qty"),
    )
    .where(PartsInventory.needs_reorder())
    .to_df()
)
print(f"\nParts needing reorder ({len(reorder_df)}):")
for _, row in reorder_df.iterrows():
    print(
        f"  {row['part_id']} ({row['part_name']}, {row['facility']}): "
        f"stock={int(row['stock_level'])} <= min_order={int(row['min_order_qty'])}"
    )

# Rule 4: Certification is expiring when fewer than 30 days remain.
CertificationExpiry.is_expiring = model.Relationship(
    f"{CertificationExpiry} is expiring"
)
model.where(
    CertificationExpiry.days_remaining < 30
).define(CertificationExpiry.is_expiring())

TechRef = Technician.ref()
expiring_df = (
    model.select(
        TechRef.technician_id.alias("technician_id"),
        TechRef.technician_name.alias("technician_name"),
        CertificationExpiry.machine_type.alias("machine_type"),
        CertificationExpiry.days_remaining.alias("days_remaining"),
    )
    .where(
        CertificationExpiry.is_expiring(),
        CertificationExpiry.technician(TechRef),
    )
    .to_df()
)
print(f"\nExpiring certifications ({len(expiring_df)}):")
for _, row in expiring_df.iterrows():
    print(
        f"  {row['technician_id']} ({row['technician_name']}): "
        f"{row['machine_type']} -- {int(row['days_remaining'])} days remaining"
    )

# --------------------------------------------------
# Stage 3: Prescriptive -- maintenance scheduling
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 3: Prescriptive -- Maintenance Scheduling")
print("=" * 70)

p = Problem(model, Float)

# References for aggregation.
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

# Decision variable: maintain -- whether to maintain machine m in period t.
MachinePeriod.x_maintain = model.Property(
    f"{MachinePeriod} maintain decision {Float:x_maintain}"
)
p.solve_for(
    MachinePeriod.x_maintain,
    type="bin",
    name=["maintain", MachinePeriod.machine_id, MachinePeriod.pid],
)

# Decision variable: vulnerable -- whether machine m remains unmaintained
# through period t.
MachinePeriod.x_vulnerable = model.Property(
    f"{MachinePeriod} vulnerable flag {Float:x_vulnerable}"
)
p.solve_for(
    MachinePeriod.x_vulnerable,
    type="bin",
    name=["vulnerable", MachinePeriod.machine_id, MachinePeriod.pid],
)

# Decision variable: assigned -- whether technician k is assigned to
# machine m in period t.
TechnicianMachinePeriod.x_assigned = model.Property(
    f"{TechnicianMachinePeriod} assigned flag {Float:x_assigned}"
)
p.solve_for(
    TechnicianMachinePeriod.x_assigned,
    type="bin",
    name=[
        "assigned",
        TechnicianMachinePeriod.technician_id,
        TechnicianMachinePeriod.machine_id,
        TechnicianMachinePeriod.pid,
    ],
)

# Constraint: cumulative maintenance coverage.
# For each (machine, tau): sum_{t=1..tau} x_maintain(m,t) + x_vulnerable(m,tau) = 1.
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

# Constraint: assignment-maintenance linkage.
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

# Constraint: technician hours capacity.
# Total assigned maintenance hours per technician per period <= available hours.
Machine_hrs = Machine.ref()
assigned_hours = (
    sum(
        TechnicianMachinePeriod_ref.x_assigned
        * Machine_hrs.maintenance_duration_hours
    )
    .where(
        TechnicianMachinePeriod_ref.technician(Technician_ref),
        TechnicianMachinePeriod_ref.period(Period_tc),
        TechnicianMachinePeriod_ref.machine(Machine_hrs),
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

# Constraint: parts/bay capacity per period.
# At most PARTS_CAPACITY_PER_PERIOD maintenance jobs in any single period.
maint_per_period = (
    sum(MachinePeriod_cap.x_maintain)
    .where(MachinePeriod_cap.period(Period_cap))
    .per(Period_cap)
)
p.satisfy(model.require(maint_per_period <= PARTS_CAPACITY_PER_PERIOD))

# Constraint (from rules): overdue machines must be maintained by OVERDUE_DEADLINE.
# Machines flagged by Stage 2 as overdue get a hard scheduling requirement.
MachinePeriod_overdue = MachinePeriod.ref()
Machine_overdue = Machine.ref()
Period_overdue = Period.ref()
maintained_by_deadline = (
    sum(MachinePeriod_overdue.x_maintain)
    .where(
        MachinePeriod_overdue.machine(Machine_overdue),
        MachinePeriod_overdue.period(Period_overdue),
        Period_overdue.pid <= OVERDUE_DEADLINE,
    )
    .per(Machine_overdue)
)
p.satisfy(
    model.require(maintained_by_deadline >= 1).where(
        Machine_overdue.is_overdue_maintenance()
    )
)

# Objective: minimize expected total cost.
# 1. Failure risk: failure_probability * estimated_parts_cost * criticality
#    * (1 + CENTRALITY_WEIGHT * betweenness) for each vulnerable machine-period.
#    Betweenness centrality from Stage 1 amplifies cost for bottleneck machines.
# 2. Labor cost: maintenance_duration_hours * technician hourly_rate.
# 3. Travel cost: TRAVEL_COST_PER_HOUR * duration when technician is not
#    co-located with the machine.
Machine_obj = Machine.ref()
Technician_obj = Technician.ref()
Machine_labor = Machine.ref()
Machine_travel = Machine.ref()
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * Machine_obj.failure_probability
    * Machine_obj.estimated_parts_cost
    * Machine_obj.criticality
    * (1 + CENTRALITY_WEIGHT * Machine_obj.betweenness)
).where(
    MachinePeriod_outer.machine(Machine_obj), MachinePeriod_outer.period(Period_outer)
)
labor_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * Machine_labor.maintenance_duration_hours
    * Technician_obj.hourly_rate
).where(
    TechnicianMachinePeriod_ref.machine(Machine_labor),
    TechnicianMachinePeriod_ref.technician(Technician_obj),
    TechnicianMachinePeriod_ref.period(Period_outer),
)
travel_cost = sum(
    TechnicianMachinePeriod_ref.x_assigned
    * (1 - TechnicianMachinePeriod_ref.same_location)
    * Machine_travel.maintenance_duration_hours
    * TRAVEL_COST_PER_HOUR
).where(
    TechnicianMachinePeriod_ref.machine(Machine_travel),
    TechnicianMachinePeriod_ref.period(Period_outer),
)
p.minimize(failure_cost + labor_cost + travel_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

p.display()
p.solve("highs", time_limit_sec=120)
si = p.solve_info()
si.display()

print(f"\nStatus: {si.termination_status}")
print(f"Objective value: {si.objective_value:.2f}")
assert si.termination_status == "OPTIMAL", f"Expected OPTIMAL, got {si.termination_status}"

# Extract results via variable_values() as a DataFrame for parsing.
vars_df = p.variable_values().to_df()

# Parse maintain decisions: name format "maintain_<machine_id>_<pid>"
maintain_vars = vars_df[vars_df["name"].str.startswith("maintain_")].copy()
maintain_vars[["_prefix", "machine_id", "period"]] = maintain_vars["name"].str.split(
    "_", n=2, expand=True
)
maintain_vars["period"] = maintain_vars["period"].astype(int)
maintain_vars = maintain_vars[maintain_vars["value"] > 0.5]

# Join with machine data for display.
maint_df = maintain_vars.merge(machines_df, on="machine_id", how="left")
maint_df = maint_df.sort_values(["period", "machine_id"])
print(f"\nMaintenance schedule ({len(maint_df)} jobs):")
for period, g in maint_df.groupby("period"):
    print(f"  Period {int(period)}:")
    for _, row in g.iterrows():
        print(
            f"    {row['machine_id']} ({row['machine_type']}, {row['facility']}, "
            f"crit={int(row['criticality'])})"
        )

# Parse assignment decisions: name format "assigned_<tech_id>_<machine_id>_<pid>"
assign_vars = vars_df[vars_df["name"].str.startswith("assigned_")].copy()
assign_vars[["_prefix", "technician_id", "machine_id", "period"]] = assign_vars[
    "name"
].str.split("_", n=3, expand=True)
assign_vars["period"] = assign_vars["period"].astype(int)
assign_vars = assign_vars[assign_vars["value"] > 0.5]

# Join with machine and technician data for display.
assign_df = assign_vars.merge(
    machines_df[["machine_id", "location", "maintenance_duration_hours"]],
    on="machine_id",
    how="left",
)
assign_df = assign_df.merge(
    technicians_df[["technician_id", "base_location", "hourly_rate"]],
    on="technician_id",
    how="left",
)
assign_df = assign_df.sort_values(["period", "machine_id"])
print(f"\nTechnician assignments ({len(assign_df)}):")
for period, g in assign_df.groupby("period"):
    print(f"  Period {int(period)}:")
    for _, row in g.iterrows():
        travel = "" if row["base_location"] == row["location"] else " [TRAVEL]"
        cost = float(row["maintenance_duration_hours"]) * float(row["hourly_rate"])
        print(
            f"    {row['machine_id']}: {row['technician_id']} "
            f"({int(row['maintenance_duration_hours'])}h x ${float(row['hourly_rate']):.0f}/h = ${cost:.0f}){travel}"
        )
