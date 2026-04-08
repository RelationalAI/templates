"""Machine maintenance (multi-reasoner) template.

This script demonstrates a chained multi-reasoner workflow in RelationalAI,
combining querying, graph analysis, rules-based classification, and prescriptive
optimization in a single template:

- Stage 0 -- Querying: compute OEE by facility, surface sensor anomalies, and
  identify machines with the steepest failure degradation trajectories.
- Stage 1 -- Graph: build a machine dependency graph from shared-technician
  qualifications, compute weakly connected components (dependency clusters)
  and betweenness centrality (bottleneck machines).
- Stage 2 -- Rules: derive compliance flags for overdue maintenance, high-risk
  machines, sensor anomalies, chronic downtime, parts reorder, and expiring
  certifications. Chain individual flags into a composite risk tier
  (Critical / Elevated / Standard).
- Stage 3 -- Prescriptive: schedule preventive maintenance across a multi-period
  horizon, assigning qualified technicians to machines. The optimization
  consumes outputs from all earlier stages: per-period failure predictions
  from Stage 0, betweenness centrality from Stage 1, and overdue-maintenance
  flags from Stage 2.
- Stage 4 -- Resilience: analyze the optimal schedule for single-point-of-failure
  technicians and recommend cross-training to eliminate concentration risk.

Run:
    `python machine_maintenance.py`

Output:
    Prints OEE and anomaly analysis, graph clusters and centrality, compliance
    flags with composite risk tier, optimized maintenance schedule, and
    resilience analysis with cross-training recommendations.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PERIOD_HORIZON = 4  # number of discrete planning periods
PARTS_CAPACITY_PER_PERIOD = 5  # max maintenance jobs per period (parts/bay limit)
TRAVEL_COST_PER_HOUR = 50.0  # cost penalty when technician travels to another facility
CENTRALITY_WEIGHT = 2.0  # multiplier for betweenness centrality in failure cost
OVERDUE_DEADLINE = 2  # overdue machines must be maintained by this period
CHRONIC_DOWNTIME_THRESHOLD = 8  # event count above which a machine is chronic

# --------------------------------------------------
# Load CSV data
# --------------------------------------------------

# Equipment and maintenance data.
machines_df = read_csv(DATA_DIR / "machines.csv")
technicians_df = read_csv(DATA_DIR / "technicians.csv")
availability_df = read_csv(DATA_DIR / "availability.csv")
qualifications_df = read_csv(DATA_DIR / "qualifications.csv")
parts_df = read_csv(DATA_DIR / "parts_inventory.csv")
cert_df = read_csv(DATA_DIR / "certification_expiry.csv")

# Sensor and prediction data.
sensors_df = read_csv(DATA_DIR / "sensors.csv")
sensor_readings_df = read_csv(DATA_DIR / "sensor_readings.csv")
failure_pred_df = read_csv(DATA_DIR / "failure_predictions.csv")

# Operational data.
downtime_df = read_csv(DATA_DIR / "downtime_events.csv")
production_df = read_csv(DATA_DIR / "production_runs.csv")
training_df = read_csv(DATA_DIR / "training_options.csv")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("machine_maintenance")

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

# --------------------------------------------------
# New concepts: sensors, predictions, downtime, production
# --------------------------------------------------

# Sensor concept: physical sensors attached to machines with thresholds.
Sensor = model.Concept("Sensor", identify_by={"sensor_id": String})
Sensor.machine_id_str = model.Property(f"{Sensor} for machine {String:machine_id_str}")
Sensor.sensor_type = model.Property(f"{Sensor} measures {String:sensor_type}")
Sensor.unit = model.Property(f"{Sensor} in {String:unit}")
Sensor.warning_threshold = model.Property(
    f"{Sensor} has warning threshold {Float:warning_threshold}"
)
Sensor.critical_threshold = model.Property(
    f"{Sensor} has critical threshold {Float:critical_threshold}"
)
Sensor.machine = model.Property(f"{Sensor} attached to {Machine}")

sensor_src = model.data(sensors_df)
model.define(
    s := Sensor.new(sensor_id=sensor_src["sensor_id"]),
    s.machine_id_str(sensor_src["machine_id"]),
    s.sensor_type(sensor_src["sensor_type"]),
    s.unit(sensor_src["unit"]),
    s.warning_threshold(sensor_src["warning_threshold"]),
    s.critical_threshold(sensor_src["critical_threshold"]),
)
model.define(Sensor.machine(Machine)).where(
    Sensor.machine_id_str == Machine.machine_id
)

# SensorReading concept: periodic sensor measurements with anomaly flags.
SensorReading = model.Concept(
    "SensorReading",
    identify_by={"sensor_id": String, "machine_id": String, "pid": Integer},
)
SensorReading.value = model.Property(f"{SensorReading} has value {Float:value}")
SensorReading.is_anomaly = model.Property(
    f"{SensorReading} anomaly flag {Integer:is_anomaly}"
)
SensorReading.sensor = model.Property(f"{SensorReading} from {Sensor}")
SensorReading.machine = model.Property(f"{SensorReading} on {Machine}")
SensorReading.period = model.Property(f"{SensorReading} in {Period}")

sr_src = model.data(sensor_readings_df)
model.define(
    sr := SensorReading.new(
        sensor_id=sr_src["sensor_id"],
        machine_id=sr_src["machine_id"],
        pid=sr_src["period"],
    ),
    sr.value(sr_src["value"]),
    sr.is_anomaly(sr_src["is_anomaly"]),
)
SRSensor = Sensor.ref()
SRMachine = Machine.ref()
SRPeriod = Period.ref()
model.define(SensorReading.sensor(SRSensor)).where(
    SensorReading.sensor_id == SRSensor.sensor_id
)
model.define(SensorReading.machine(SRMachine)).where(
    SensorReading.machine_id == SRMachine.machine_id
)
model.define(SensorReading.period(SRPeriod)).where(
    SensorReading.pid == SRPeriod.pid
)

# FailurePrediction concept: ML-predicted per-period failure probabilities.
# These replace the static Machine.failure_probability in the optimization
# objective, giving period-specific degradation curves.
FailurePrediction = model.Concept(
    "FailurePrediction", identify_by={"prediction_id": String}
)
FailurePrediction.machine_id_str = model.Property(
    f"{FailurePrediction} for machine {String:machine_id_str}"
)
FailurePrediction.period_int = model.Property(
    f"{FailurePrediction} in period {Integer:period_int}"
)
FailurePrediction.failure_probability = model.Property(
    f"{FailurePrediction} has failure probability {Float:failure_probability}"
)
FailurePrediction.predicted_failure_mode = model.Property(
    f"{FailurePrediction} predicts mode {String:predicted_failure_mode}"
)
FailurePrediction.confidence = model.Property(
    f"{FailurePrediction} has confidence {Float:confidence}"
)
FailurePrediction.machine = model.Property(f"{FailurePrediction} for {Machine}")
FailurePrediction.period = model.Property(f"{FailurePrediction} in {Period}")

fp_src = model.data(failure_pred_df)
model.define(
    fp := FailurePrediction.new(prediction_id=fp_src["prediction_id"]),
    fp.machine_id_str(fp_src["machine_id"]),
    fp.period_int(fp_src["period"]),
    fp.failure_probability(fp_src["failure_probability"]),
    fp.predicted_failure_mode(fp_src["predicted_failure_mode"]),
    fp.confidence(fp_src["confidence"]),
)
FPMachineInit = Machine.ref()
FPPeriodInit = Period.ref()
model.define(FailurePrediction.machine(FPMachineInit)).where(
    FailurePrediction.machine_id_str == FPMachineInit.machine_id
)
model.define(FailurePrediction.period(FPPeriodInit)).where(
    FailurePrediction.period_int == FPPeriodInit.pid
)

# DowntimeEvent concept: unplanned and planned downtime events per machine.
DowntimeEvent = model.Concept("DowntimeEvent", identify_by={"event_id": String})
DowntimeEvent.machine_id_str = model.Property(
    f"{DowntimeEvent} for machine {String:machine_id_str}"
)
DowntimeEvent.period_int = model.Property(
    f"{DowntimeEvent} in period {Integer:period_int}"
)
DowntimeEvent.fault_category = model.Property(
    f"{DowntimeEvent} fault category {String:fault_category}"
)
DowntimeEvent.duration_minutes = model.Property(
    f"{DowntimeEvent} lasted {Integer:duration_minutes} minutes"
)
DowntimeEvent.is_planned = model.Property(
    f"{DowntimeEvent} planned flag {Integer:is_planned}"
)
DowntimeEvent.machine = model.Property(f"{DowntimeEvent} on {Machine}")

dt_src = model.data(downtime_df)
model.define(
    dt := DowntimeEvent.new(event_id=dt_src["event_id"]),
    dt.machine_id_str(dt_src["machine_id"]),
    dt.period_int(dt_src["period"]),
    dt.fault_category(dt_src["fault_category"]),
    dt.duration_minutes(dt_src["duration_minutes"]),
    dt.is_planned(dt_src["is_planned"]),
)
model.define(DowntimeEvent.machine(Machine)).where(
    DowntimeEvent.machine_id_str == Machine.machine_id
)

# ProductionRun concept: production output per machine per period.
ProductionRun = model.Concept("ProductionRun", identify_by={"run_id": String})
ProductionRun.machine_id_str = model.Property(
    f"{ProductionRun} for machine {String:machine_id_str}"
)
ProductionRun.period_int = model.Property(
    f"{ProductionRun} in period {Integer:period_int}"
)
ProductionRun.planned_quantity = model.Property(
    f"{ProductionRun} planned {Integer:planned_quantity} units"
)
ProductionRun.actual_quantity = model.Property(
    f"{ProductionRun} produced {Integer:actual_quantity} units"
)
ProductionRun.good_quantity = model.Property(
    f"{ProductionRun} good output {Integer:good_quantity} units"
)
ProductionRun.machine = model.Property(f"{ProductionRun} on {Machine}")

pr_src = model.data(production_df)
model.define(
    pr := ProductionRun.new(run_id=pr_src["run_id"]),
    pr.machine_id_str(pr_src["machine_id"]),
    pr.period_int(pr_src["period"]),
    pr.planned_quantity(pr_src["planned_quantity"]),
    pr.actual_quantity(pr_src["actual_quantity"]),
    pr.good_quantity(pr_src["good_quantity"]),
)
model.define(ProductionRun.machine(Machine)).where(
    ProductionRun.machine_id_str == Machine.machine_id
)

# --------------------------------------------------
# Cross-product concepts (scheduling decision space)
# --------------------------------------------------

# MachinePeriod concept: (machine, period) pairs.
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

# Store per-period failure prediction on MachinePeriod for the objective.
MachinePeriod.predicted_fp = model.Property(
    f"{MachinePeriod} has predicted failure probability {Float:predicted_fp}"
)
FPJoin = FailurePrediction.ref()
model.where(
    MachinePeriod.machine_id == FPJoin.machine_id_str,
    MachinePeriod.pid == FPJoin.period_int,
).define(MachinePeriod.predicted_fp(FPJoin.failure_probability))

# TechnicianPeriod concept: technician capacity per period in hours.
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

# TechnicianMachinePeriod concept: (technician, machine, period) triples,
# restricted to qualified pairs only.
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
# Machine-level derived aggregates (for querying & rules)
# --------------------------------------------------

# Production aggregates: total planned, actual, and good quantities.
Machine.total_planned_qty = model.Property(
    f"{Machine} has total planned qty {Float:total_planned_qty}"
)
Machine.total_actual_qty = model.Property(
    f"{Machine} has total actual qty {Float:total_actual_qty}"
)
Machine.total_good_qty = model.Property(
    f"{Machine} has total good qty {Float:total_good_qty}"
)
model.define(Machine.total_planned_qty(
    aggs.sum(ProductionRun.planned_quantity).per(Machine)
    .where(ProductionRun.machine(Machine)) | 0
))
model.define(Machine.total_actual_qty(
    aggs.sum(ProductionRun.actual_quantity).per(Machine)
    .where(ProductionRun.machine(Machine)) | 0
))
model.define(Machine.total_good_qty(
    aggs.sum(ProductionRun.good_quantity).per(Machine)
    .where(ProductionRun.machine(Machine)) | 0
))

# Performance ratio (actual / planned) and quality ratio (good / actual).
Machine.performance_ratio = model.Property(
    f"{Machine} has performance ratio {Float:performance_ratio}"
)
Machine.quality_ratio = model.Property(
    f"{Machine} has quality ratio {Float:quality_ratio}"
)
model.where(Machine.total_planned_qty > 0).define(
    Machine.performance_ratio(
        floats.float(Machine.total_actual_qty)
        / floats.float(Machine.total_planned_qty)
    )
)
model.where(Machine.total_actual_qty > 0).define(
    Machine.quality_ratio(
        floats.float(Machine.total_good_qty)
        / floats.float(Machine.total_actual_qty)
    )
)

# Downtime aggregates: total downtime minutes and event count.
Machine.total_downtime_minutes = model.Property(
    f"{Machine} has total downtime {Float:total_downtime_minutes} minutes"
)
Machine.downtime_event_count = model.Property(
    f"{Machine} has downtime event count {Float:downtime_event_count}"
)
model.define(Machine.total_downtime_minutes(
    aggs.sum(DowntimeEvent.duration_minutes).per(Machine)
    .where(DowntimeEvent.machine(Machine)) | 0
))
model.define(Machine.downtime_event_count(
    aggs.count(DowntimeEvent).per(Machine)
    .where(DowntimeEvent.machine(Machine)) | 0
))

# Sensor anomaly count across all periods.
Machine.anomaly_count = model.Property(
    f"{Machine} has anomaly count {Float:anomaly_count}"
)
model.define(Machine.anomaly_count(
    aggs.count(SensorReading).per(Machine).where(
        SensorReading.machine(Machine),
        SensorReading.is_anomaly == 1,
    ) | 0
))

# --------------------------------------------------
# Stage 0: Querying -- Operational Intelligence
# --------------------------------------------------

print("=" * 70)
print("STAGE 0: Querying -- Operational Intelligence")
print("=" * 70)

# 0a. OEE proxy by facility (Performance x Quality).
# Quality is uniformly high (~98%); the differentiator is Performance.
oee_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.facility.alias("facility"),
        Machine.performance_ratio.alias("performance"),
        Machine.quality_ratio.alias("quality"),
    )
    .to_df()
)
oee_by_fac = (
    oee_df.groupby("facility")
    .agg(avg_perf=("performance", "mean"), avg_qual=("quality", "mean"))
    .reset_index()
)
oee_by_fac["oee_proxy"] = oee_by_fac["avg_perf"] * oee_by_fac["avg_qual"]
oee_by_fac = oee_by_fac.sort_values("oee_proxy", ascending=False)

print("\nOEE proxy by facility (Performance x Quality):")
for _, row in oee_by_fac.iterrows():
    print(
        f"  {row['facility']}: "
        f"Perf={row['avg_perf']:.1%}, Qual={row['avg_qual']:.1%}, "
        f"OEE={row['oee_proxy']:.1%}"
    )

# 0b. Sensor anomalies: machines with above-threshold readings.
SensorQ = Sensor.ref()
anomaly_detail_df = (
    model.select(
        SensorReading.machine_id.alias("machine_id"),
        SensorReading.pid.alias("period"),
        SensorReading.value.alias("value"),
        SensorQ.sensor_type.alias("sensor_type"),
        SensorQ.warning_threshold.alias("warning"),
        SensorQ.critical_threshold.alias("critical"),
    )
    .where(
        SensorReading.is_anomaly == 1,
        SensorReading.sensor(SensorQ),
    )
    .to_df()
    .sort_values(["machine_id", "period"])
)
anomaly_counts = anomaly_detail_df.groupby("machine_id").size().reset_index(name="count")
anomaly_counts = anomaly_counts.merge(
    machines_df[["machine_id", "machine_type", "facility"]], on="machine_id"
).sort_values("count", ascending=False)

print(f"\nSensor anomalies ({len(anomaly_detail_df)} readings across "
      f"{len(anomaly_counts)} machines):")
for _, row in anomaly_counts.iterrows():
    print(f"  {row['machine_id']} ({row['machine_type']}, {row['facility']}): "
          f"{row['count']} anomalies")

by_fac = anomaly_counts.groupby("facility")["count"].sum()
print(f"  By facility: {dict(by_fac.sort_values(ascending=False))}")

# 0c. Failure trajectories: identify machines with steepest degradation.
FPMachQ = Machine.ref()
fp_query_df = (
    model.select(
        FailurePrediction.machine_id_str.alias("machine_id"),
        FPMachQ.machine_type.alias("machine_type"),
        FPMachQ.facility.alias("facility"),
        FailurePrediction.period_int.alias("period"),
        FailurePrediction.failure_probability.alias("failure_probability"),
        FailurePrediction.predicted_failure_mode.alias("failure_mode"),
    )
    .where(FailurePrediction.machine(FPMachQ))
    .to_df()
)

pivot = fp_query_df.pivot_table(
    index=["machine_id", "machine_type", "facility", "failure_mode"],
    columns="period",
    values="failure_probability",
).reset_index()
pivot["delta"] = pivot[PERIOD_HORIZON] - pivot[1]
pivot = pivot.sort_values("delta", ascending=False)

print(f"\nSteepest failure trajectories (period 1 -> {PERIOD_HORIZON}):")
for _, row in pivot.head(6).iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_type']}, {row['facility']}): "
        f"{row[1]:.3f} -> {row[PERIOD_HORIZON]:.3f} "
        f"(+{row['delta']:.3f}) [{row['failure_mode']}]"
    )

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

print(f"\n{'=' * 70}")
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

# Betweenness centrality: find bottleneck machines.
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
# Stage 2: Rules -- compliance flags & composite risk tier
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 2: Rules -- Compliance Flags & Composite Risk Tier")
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
# criticality >= 4.
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

# Rule 3: Machine has sensor anomalies.
Machine.is_anomalous = model.Relationship(f"{Machine} has sensor anomalies")
model.where(Machine.anomaly_count > 0).define(Machine.is_anomalous())

anomalous_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.machine_name.alias("machine_name"),
        Machine.facility.alias("facility"),
        Machine.anomaly_count.alias("anomaly_count"),
    )
    .where(Machine.is_anomalous())
    .to_df()
    .sort_values("anomaly_count", ascending=False)
)
print(f"\nAnomalous machines ({len(anomalous_df)}):")
for _, row in anomalous_df.iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_name']}, {row['facility']}): "
        f"{int(row['anomaly_count'])} anomalies"
    )

# Rule 4: Machine has chronic downtime (event count > threshold).
Machine.is_chronic_downtime = model.Relationship(f"{Machine} has chronic downtime")
model.where(
    Machine.downtime_event_count > CHRONIC_DOWNTIME_THRESHOLD
).define(Machine.is_chronic_downtime())

chronic_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.machine_name.alias("machine_name"),
        Machine.facility.alias("facility"),
        Machine.downtime_event_count.alias("event_count"),
        Machine.total_downtime_minutes.alias("total_minutes"),
    )
    .where(Machine.is_chronic_downtime())
    .to_df()
    .sort_values("event_count", ascending=False)
)
print(f"\nChronic downtime machines (>{CHRONIC_DOWNTIME_THRESHOLD} events, "
      f"{len(chronic_df)} machines):")
for _, row in chronic_df.iterrows():
    print(
        f"  {row['machine_id']} ({row['machine_name']}, {row['facility']}): "
        f"{int(row['event_count'])} events, "
        f"{int(row['total_minutes'])} min total downtime"
    )

# Rule 5: Composite risk tier -- chains overdue, high-risk, and chronic
# downtime flags into a single classification.
Machine.risk_tier = model.Property(f"{Machine} has risk tier {String:risk_tier}")

# Critical: all 3 flags.
model.where(
    Machine.is_chronic_downtime(),
    Machine.is_high_risk(),
    Machine.is_overdue_maintenance(),
).define(Machine.risk_tier("Critical"))

# Elevated: exactly 2 of 3 flags (enumerate pairs, negate the third).
model.where(
    Machine.is_chronic_downtime(),
    Machine.is_high_risk(),
    model.not_(Machine.is_overdue_maintenance()),
).define(Machine.risk_tier("Elevated"))
model.where(
    Machine.is_chronic_downtime(),
    model.not_(Machine.is_high_risk()),
    Machine.is_overdue_maintenance(),
).define(Machine.risk_tier("Elevated"))
model.where(
    model.not_(Machine.is_chronic_downtime()),
    Machine.is_high_risk(),
    Machine.is_overdue_maintenance(),
).define(Machine.risk_tier("Elevated"))

# Standard: 0 or 1 flag.
model.where(
    model.not_(Machine.is_chronic_downtime()),
    model.not_(Machine.is_high_risk()),
    model.not_(Machine.is_overdue_maintenance()),
).define(Machine.risk_tier("Standard"))
model.where(
    Machine.is_chronic_downtime(),
    model.not_(Machine.is_high_risk()),
    model.not_(Machine.is_overdue_maintenance()),
).define(Machine.risk_tier("Standard"))
model.where(
    model.not_(Machine.is_chronic_downtime()),
    Machine.is_high_risk(),
    model.not_(Machine.is_overdue_maintenance()),
).define(Machine.risk_tier("Standard"))
model.where(
    model.not_(Machine.is_chronic_downtime()),
    model.not_(Machine.is_high_risk()),
    Machine.is_overdue_maintenance(),
).define(Machine.risk_tier("Standard"))

risk_tier_df = (
    model.select(
        Machine.machine_id.alias("machine_id"),
        Machine.machine_name.alias("machine_name"),
        Machine.machine_type.alias("machine_type"),
        Machine.facility.alias("facility"),
        Machine.risk_tier.alias("risk_tier"),
    )
    .to_df()
    .sort_values("risk_tier")
)
print("\nComposite risk tier:")
for tier in ["Critical", "Elevated", "Standard"]:
    tier_machines = risk_tier_df[risk_tier_df["risk_tier"] == tier]
    ids = ", ".join(tier_machines["machine_id"].tolist())
    print(f"  {tier} ({len(tier_machines)}): {ids}")

# Rule 6: Parts inventory needs reorder.
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

# Rule 7: Certification is expiring when fewer than 30 days remain.
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
maint_per_period = (
    sum(MachinePeriod_cap.x_maintain)
    .where(MachinePeriod_cap.period(Period_cap))
    .per(Period_cap)
)
p.satisfy(model.require(maint_per_period <= PARTS_CAPACITY_PER_PERIOD))

# Constraint (from rules): overdue machines must be maintained by OVERDUE_DEADLINE.
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
# 1. Failure risk: per-period failure prediction (from Stage 0) * parts cost
#    * criticality * (1 + centrality_weight * betweenness from Stage 1).
# 2. Labor cost: maintenance_duration * technician hourly_rate.
# 3. Travel cost: flat rate * duration when technician is not co-located.
Machine_obj = Machine.ref()
Technician_obj = Technician.ref()
Machine_labor = Machine.ref()
Machine_travel = Machine.ref()
failure_cost = sum(
    MachinePeriod_outer.x_vulnerable
    * MachinePeriod_outer.predicted_fp
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
# Solve and extract results
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
            f"({int(row['maintenance_duration_hours'])}h x "
            f"${float(row['hourly_rate']):.0f}/h = ${cost:.0f}){travel}"
        )

# --------------------------------------------------
# Stage 4: Resilience -- concentration risk & cross-training
# --------------------------------------------------

print(f"\n{'=' * 70}")
print("STAGE 4: Resilience -- Concentration Risk Analysis")
print("=" * 70)

# 4a. Technician utilization from the optimal schedule.
tech_assignments = (
    assign_df.groupby("technician_id")
    .agg(
        assignment_count=("machine_id", "count"),
        machines=("machine_id", list),
    )
    .reset_index()
    .sort_values("assignment_count", ascending=False)
)
tech_assignments = tech_assignments.merge(
    technicians_df[["technician_id", "technician_name", "base_location", "skill_level"]],
    on="technician_id",
)

print("\nTechnician utilization in optimal schedule:")
total_assignments = len(assign_df)
for _, row in tech_assignments.iterrows():
    pct = row["assignment_count"] / total_assignments * 100
    print(
        f"  {row['technician_id']} ({row['technician_name']}, "
        f"{row['skill_level']}, {row['base_location']}): "
        f"{row['assignment_count']} assignments ({pct:.0f}%)"
    )

# 4b. Geographic concentration analysis by machine type.
# For each machine type, check if all qualified technicians are in one location.
# This reveals structural fragility invisible in the per-assignment view.
print("\nQualification coverage by machine type:")
concentrated_types = []
machine_types = sorted(qualifications_df["machine_type"].unique())
for mtype in machine_types:
    qual_techs = qualifications_df[
        qualifications_df["machine_type"] == mtype
    ]["technician_id"].tolist()
    tech_info = technicians_df[technicians_df["technician_id"].isin(qual_techs)]
    locations = tech_info["base_location"].unique().tolist()
    tech_count = len(qual_techs)

    # Machines of this type and their locations.
    type_machines = machines_df[machines_df["machine_type"] == mtype]
    machine_locations = type_machines["location"].unique().tolist()
    uncovered_locs = [loc for loc in machine_locations if loc not in locations]

    status = "OK"
    if len(locations) == 1:
        concentrated_types.append((mtype, locations[0], tech_count))
        status = f"CONCENTRATED -- all {tech_count} techs in {locations[0]}"
    elif uncovered_locs:
        status = f"gaps at {', '.join(uncovered_locs)}"

    print(f"  {mtype}: {tech_count} techs in {', '.join(sorted(locations))} -- {status}")

# 4c. Impact analysis for concentrated types.
if concentrated_types:
    print(f"\nConcentration risk detail:")
    for mtype, conc_loc, tech_count in concentrated_types:
        type_machines = machines_df[machines_df["machine_type"] == mtype]
        remote_machines = type_machines[type_machines["location"] != conc_loc]
        local_machines = type_machines[type_machines["location"] == conc_loc]

        # How many scheduled assignments for this type required travel?
        type_assign = assign_df.merge(
            machines_df[["machine_id", "machine_type"]], on="machine_id"
        )
        type_assign = type_assign[type_assign["machine_type"] == mtype]
        travel_assign = type_assign[type_assign["base_location"] != type_assign["location"]]

        print(f"\n  {mtype}: {len(type_machines)} machines across "
              f"{len(type_machines['facility'].unique())} facilities, "
              f"all {tech_count} qualified techs in {conc_loc}")
        print(f"    Local machines ({conc_loc}): {len(local_machines)}")
        print(f"    Remote machines (require travel): {len(remote_machines)}")
        if not remote_machines.empty:
            for _, m in remote_machines.iterrows():
                print(f"      {m['machine_id']} ({m['facility']}, {m['location']})")
        if not type_assign.empty:
            print(f"    Scheduled {mtype} jobs: {len(type_assign)}, "
                  f"of which {len(travel_assign)} require travel "
                  f"({len(travel_assign)/len(type_assign)*100:.0f}%)")

        # Show qualified techs.
        qual_techs = qualifications_df[
            qualifications_df["machine_type"] == mtype
        ]["technician_id"].tolist()
        tech_detail = technicians_df[technicians_df["technician_id"].isin(qual_techs)]
        print(f"    Qualified techs (all {conc_loc}):")
        for _, t in tech_detail.iterrows():
            print(f"      {t['technician_id']} ({t['technician_name']}, "
                  f"{t['skill_level']})")

    # 4d. Cross-training recommendation.
    print(f"\n{'=' * 70}")
    print("RECOMMENDATION: Cross-Training to Eliminate Concentration Risk")
    print("=" * 70)

    for mtype, conc_loc, _ in concentrated_types:
        candidates = training_df[training_df["machine_type"] == mtype].merge(
            technicians_df[["technician_id", "technician_name", "base_location",
                            "skill_level"]],
            on="technician_id",
        ).sort_values("training_cost")

        # Prefer candidates NOT in the concentrated location.
        non_local = candidates[candidates["base_location"] != conc_loc]
        if not non_local.empty:
            best = non_local.iloc[0]
        elif not candidates.empty:
            best = candidates.iloc[0]
        else:
            print(f"\n  No {mtype} cross-training options available.")
            continue

        print(f"\n  {mtype} -- add coverage outside {conc_loc}:")
        print(f"    Best candidate: {best['technician_id']} "
              f"({best['technician_name']}, {best['skill_level']}, "
              f"{best['base_location']})")
        print(f"    Cost: ${int(best['training_cost']):,}, "
              f"Duration: {int(best['training_weeks'])} weeks")

        if len(candidates) > 1:
            print(f"    All candidates:")
            for _, cand in candidates.iterrows():
                local_tag = " (same location)" if cand["base_location"] == conc_loc else ""
                print(f"      {cand['technician_id']} ({cand['technician_name']}, "
                      f"{cand['base_location']}): "
                      f"${int(cand['training_cost']):,}, "
                      f"{int(cand['training_weeks'])} weeks{local_tag}")
else:
    print("\nNo geographic concentration risk detected.")
