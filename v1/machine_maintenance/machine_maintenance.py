"""Machine Maintenance -- multi-reasoner template (PyRel v1).

A 50-machine, 3-plant, 12-period manufacturing operation. The script threads five
reasoning stages through a single ontology so each stage's enrichments feed the next:

  Stage 1  Querying     -- OEE by plant, downtime drivers, waste rates,
                           technician coverage.
  Stage 2  Rules        -- per-machine risk tier (chronic / high-risk / overdue).
  Stage 3  Graph        -- machine-product producibility bottlenecks.
  Stage 4  Predictive   -- forward failure risk & mode (pre-loaded predictions;
                           live GNN optional).
  Stage 5  Prescriptive -- preventive-maintenance schedule + a technician what-if.

Data is the bundled sample in data/*.csv.

Run:
    python machine_maintenance.py

Output:
    Prints each stage's findings to stdout.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PERIOD_HORIZON = 12                  # weekly planning periods
OEE_PLANNED_MIN_PER_RUN = 480        # planned minutes per production run (availability base)
CHRONIC_DOWNTIME_THRESHOLD = 15      # downtime events above which a machine is chronic
HIGH_RISK_FP = 0.20                  # failure-probability cutoff for high-risk
HIGH_RISK_CRITICALITY = 4            # criticality cutoff for high-risk
OVERDUE_RUL = 9                      # remaining-useful-life at/below which maintenance is overdue
USE_PRELOADED_PREDICTIONS = True     # predictive stage: read the bundled failure_predictions
#                                      (default); set False to wire a live GNN -- see README "Customize"

model = Model("machine_maintenance")

# ==================================================================
# Stage 0: Ontology -- load the bundled sample data
# ==================================================================

# Machine ---------------------------------------------------------------------
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.machine_name = model.Property(f"{Machine} has name {String:machine_name}")
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at facility {String:facility}")
Machine.location = model.Property(f"{Machine} at location {String:location}")
Machine.remaining_useful_life = model.Property(f"{Machine} has remaining useful life {Float:remaining_useful_life}")
Machine.failure_probability = model.Property(f"{Machine} has failure probability {Float:failure_probability}")
Machine.criticality = model.Property(f"{Machine} has criticality {Integer:criticality}")
Machine.maintenance_duration_hours = model.Property(f"{Machine} needs {Integer:maintenance_duration_hours} maintenance hours")
Machine.estimated_parts_cost = model.Property(f"{Machine} has parts cost {Float:estimated_parts_cost}")

_m = model.data(read_csv(DATA_DIR / "machines.csv"))
model.define(
    m := Machine.new(machine_id=_m["machine_id"]),
    m.machine_name(_m["machine_name"]),
    m.machine_type(_m["machine_type"]),
    m.facility(_m["facility"]),
    m.location(_m["location"]),
    m.remaining_useful_life(_m["remaining_useful_life"]),
    m.failure_probability(_m["failure_probability"]),
    m.criticality(_m["criticality"]),
    m.maintenance_duration_hours(_m["maintenance_duration_hours"]),
    m.estimated_parts_cost(_m["estimated_parts_cost"]),
)

# Product ---------------------------------------------------------------------
Product = model.Concept("Product", identify_by={"product_id": String})
Product.product_name = model.Property(f"{Product} has name {String:product_name}")
_p = model.data(read_csv(DATA_DIR / "products.csv"))
model.define(
    p := Product.new(product_id=_p["product_id"]),
    p.product_name(_p["product_name"]),
)

# Technician ------------------------------------------------------------------
Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.technician_name = model.Property(f"{Technician} has name {String:technician_name}")
Technician.skill_level = model.Property(f"{Technician} has skill level {String:skill_level}")
Technician.base_location = model.Property(f"{Technician} based at {String:base_location}")
Technician.hourly_rate = model.Property(f"{Technician} has hourly rate {Float:hourly_rate}")
Technician.max_weekly_hours = model.Property(f"{Technician} has max weekly hours {Integer:max_weekly_hours}")
_t = model.data(read_csv(DATA_DIR / "technicians.csv"))
model.define(
    t := Technician.new(technician_id=_t["technician_id"]),
    t.technician_name(_t["technician_name"]),
    t.skill_level(_t["skill_level"]),
    t.base_location(_t["base_location"]),
    t.hourly_rate(_t["hourly_rate"]),
    t.max_weekly_hours(_t["max_weekly_hours"]),
)

# Qualification (technician x machine_type) -----------------------------------
Qualification = model.Concept("Qualification", identify_by={"technician_id": String, "machine_type": String})
Qualification.technician = model.Property(f"{Qualification} held by {Technician}")
Qualification.machine_type_str = model.Property(f"{Qualification} covers type {String:machine_type_str}")
_q = model.data(read_csv(DATA_DIR / "qualifications.csv"))
model.define(
    q := Qualification.new(technician_id=_q["technician_id"], machine_type=_q["machine_type"]),
    q.machine_type_str(_q["machine_type"]),
)
_QT = Technician.ref()
model.define(Qualification.technician(_QT)).where(Qualification.technician_id == _QT.technician_id)

# ProductionRun ---------------------------------------------------------------
ProductionRun = model.Concept("ProductionRun", identify_by={"run_id": String})
ProductionRun.machine_id_str = model.Property(f"{ProductionRun} on machine {String:machine_id_str}")
ProductionRun.product_id_str = model.Property(f"{ProductionRun} of product {String:product_id_str}")
ProductionRun.period_int = model.Property(f"{ProductionRun} in period {Integer:period_int}")
ProductionRun.actual_quantity = model.Property(f"{ProductionRun} actual qty {Integer:actual_quantity}")
ProductionRun.good_quantity = model.Property(f"{ProductionRun} good qty {Integer:good_quantity}")
ProductionRun.waste_quantity = model.Property(f"{ProductionRun} waste qty {Integer:waste_quantity}")
ProductionRun.actual_speed = model.Property(f"{ProductionRun} actual speed {Float:actual_speed}")
ProductionRun.target_speed = model.Property(f"{ProductionRun} target speed {Float:target_speed}")
ProductionRun.machine = model.Property(f"{ProductionRun} runs on {Machine}")
ProductionRun.product = model.Property(f"{ProductionRun} produces {Product}")
_pr = model.data(read_csv(DATA_DIR / "production_runs.csv"))
model.define(
    r := ProductionRun.new(run_id=_pr["run_id"]),
    r.machine_id_str(_pr["machine_id"]),
    r.product_id_str(_pr["product_id"]),
    r.period_int(_pr["period"]),
    r.actual_quantity(_pr["actual_quantity"]),
    r.good_quantity(_pr["good_quantity"]),
    r.waste_quantity(_pr["waste_quantity"]),
    r.actual_speed(_pr["actual_speed"]),
    r.target_speed(_pr["target_speed"]),
)
_PRM = Machine.ref()
_PRP = Product.ref()
model.define(ProductionRun.machine(_PRM)).where(ProductionRun.machine_id_str == _PRM.machine_id)
model.define(ProductionRun.product(_PRP)).where(ProductionRun.product_id_str == _PRP.product_id)

# DowntimeEvent ---------------------------------------------------------------
DowntimeEvent = model.Concept("DowntimeEvent", identify_by={"event_id": String})
DowntimeEvent.machine_id_str = model.Property(f"{DowntimeEvent} on machine {String:machine_id_str}")
DowntimeEvent.fault_name = model.Property(f"{DowntimeEvent} has fault {String:fault_name}")
DowntimeEvent.duration_minutes = model.Property(f"{DowntimeEvent} lasted {Integer:duration_minutes} minutes")
DowntimeEvent.is_planned = model.Property(f"{DowntimeEvent} planned flag {Integer:is_planned}")
DowntimeEvent.machine = model.Property(f"{DowntimeEvent} affects {Machine}")
_de = model.data(read_csv(DATA_DIR / "downtime_events.csv"))
model.define(
    d := DowntimeEvent.new(event_id=_de["event_id"]),
    d.machine_id_str(_de["machine_id"]),
    d.fault_name(_de["fault_name"]),
    d.duration_minutes(_de["duration_minutes"]),
    d.is_planned(_de["is_planned"]),
)
_DEM = Machine.ref()
model.define(DowntimeEvent.machine(_DEM)).where(DowntimeEvent.machine_id_str == _DEM.machine_id)

# FailurePrediction -----------------------------------------------------------
FailurePrediction = model.Concept("FailurePrediction", identify_by={"prediction_id": String})
FailurePrediction.machine_id_str = model.Property(f"{FailurePrediction} for machine {String:machine_id_str}")
FailurePrediction.period_int = model.Property(f"{FailurePrediction} in period {Integer:period_int}")
FailurePrediction.failure_probability = model.Property(f"{FailurePrediction} probability {Float:failure_probability}")
FailurePrediction.predicted_failure_mode = model.Property(f"{FailurePrediction} mode {String:predicted_failure_mode}")
_fp = model.data(read_csv(DATA_DIR / "failure_predictions.csv"))
model.define(
    f := FailurePrediction.new(prediction_id=_fp["prediction_id"]),
    f.machine_id_str(_fp["machine_id"]),
    f.period_int(_fp["period"]),
    f.failure_probability(_fp["failure_probability"]),
    f.predicted_failure_mode(_fp["predicted_failure_mode"]),
)

# MachineProductCapability (machine x product) --------------------------------
MachineProductCapability = model.Concept("MachineProductCapability", identify_by={"machine_id": String, "product_id": String})
MachineProductCapability.machine_id_str = model.Property(f"{MachineProductCapability} of machine {String:machine_id_str}")
MachineProductCapability.product_id_str = model.Property(f"{MachineProductCapability} for product {String:product_id_str}")
MachineProductCapability.machine = model.Property(f"{MachineProductCapability} via {Machine}")
MachineProductCapability.product = model.Property(f"{MachineProductCapability} makes {Product}")
_mpc = model.data(read_csv(DATA_DIR / "machine_product_capabilities.csv"))
model.define(
    c := MachineProductCapability.new(machine_id=_mpc["machine_id"], product_id=_mpc["product_id"]),
    c.machine_id_str(_mpc["machine_id"]),
    c.product_id_str(_mpc["product_id"]),
)
_CM = Machine.ref()
_CP = Product.ref()
model.define(MachineProductCapability.machine(_CM)).where(MachineProductCapability.machine_id_str == _CM.machine_id)
model.define(MachineProductCapability.product(_CP)).where(MachineProductCapability.product_id_str == _CP.product_id)


def banner(text):
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


# ==================================================================
# Stage 1: Querying -- diagnose plant operations
# ==================================================================

banner("STAGE 1  Querying")

# --- OEE by plant = Availability x Performance x Quality ---
# Performance / quality / run counts come from production runs; unplanned downtime
# from downtime events. Aggregated separately (different fact tables) then combined.
runs_by_plant = model.where(ProductionRun.machine(Machine)).select(
    distinct(
        Machine.facility.alias("facility"),
        aggs.count(ProductionRun).per(Machine.facility).alias("n_runs"),
        aggs.avg(floats.float(ProductionRun.actual_speed) / floats.float(ProductionRun.target_speed))
        .per(Machine.facility).alias("performance"),
        aggs.sum(floats.float(ProductionRun.good_quantity)).per(Machine.facility).alias("good_q"),
        aggs.sum(floats.float(ProductionRun.actual_quantity)).per(Machine.facility).alias("actual_q"),
    )
).to_df()

dt_unplanned_by_plant = model.where(
    DowntimeEvent.machine(Machine), DowntimeEvent.is_planned == 0
).select(
    distinct(
        Machine.facility.alias("facility"),
        aggs.sum(floats.float(DowntimeEvent.duration_minutes)).per(Machine.facility).alias("unplanned_dt"),
    )
).to_df()

oee = runs_by_plant.merge(dt_unplanned_by_plant, on="facility")
oee["n_runs"] = oee["n_runs"].astype(float)  # count comes back as Int128Array
oee["availability"] = (oee["n_runs"] * OEE_PLANNED_MIN_PER_RUN - oee["unplanned_dt"]) / (
    oee["n_runs"] * OEE_PLANNED_MIN_PER_RUN
)
oee["quality"] = oee["good_q"] / oee["actual_q"]
oee["oee"] = oee["availability"] * oee["performance"] * oee["quality"]
oee = oee.sort_values("oee", ascending=False)
print("\n-- OEE by plant --")
for _, row in oee.iterrows():
    print(
        f"   {row['facility']}: availability {row['availability']*100:.1f}%  "
        f"performance {row['performance']*100:.1f}%  quality {row['quality']*100:.1f}%  "
        f"OEE {row['oee']*100:.1f}%"
    )

# --- Top downtime drivers by fault name ---
fault_dt = model.select(
    distinct(
        DowntimeEvent.fault_name.alias("fault_name"),
        aggs.sum(floats.float(DowntimeEvent.duration_minutes)).per(DowntimeEvent.fault_name).alias("dt_min"),
    )
).to_df()
total_dt = fault_dt["dt_min"].sum()
fault_dt["pct"] = 100 * fault_dt["dt_min"] / total_dt
fault_dt = fault_dt.sort_values("dt_min", ascending=False)
print(f"\n-- Top downtime by fault name (total {total_dt:.0f} min) --")
for _, row in fault_dt.head(5).iterrows():
    print(f"   {row['fault_name']}: {row['dt_min']:.0f} min ({row['pct']:.1f}%)")

# --- Downtime by plant ---
plant_dt = model.where(DowntimeEvent.machine(Machine)).select(
    distinct(
        Machine.facility.alias("facility"),
        aggs.sum(floats.float(DowntimeEvent.duration_minutes)).per(Machine.facility).alias("dt_min"),
    )
).to_df()
plant_dt["pct"] = 100 * plant_dt["dt_min"] / plant_dt["dt_min"].sum()
plant_dt = plant_dt.sort_values("dt_min", ascending=False)
print("\n-- Downtime by plant --")
for _, row in plant_dt.iterrows():
    print(f"   {row['facility']}: {row['dt_min']:.0f} min ({row['pct']:.1f}%)")

# --- Worst waste rates by machine-product ---
waste = model.where(ProductionRun.machine(Machine), ProductionRun.product(Product)).select(
    distinct(
        Machine.machine_id.alias("machine_id"),
        Product.product_name.alias("product_name"),
        (
            aggs.sum(floats.float(ProductionRun.waste_quantity)).per(Machine, Product)
            / aggs.sum(floats.float(ProductionRun.actual_quantity)).per(Machine, Product)
        ).alias("waste_rate"),
    )
).to_df().sort_values("waste_rate", ascending=False)
print("\n-- Worst waste rates by machine-product --")
for _, row in waste.head(5).iterrows():
    print(f"   {row['machine_id']} + {row['product_name']} ({row['waste_rate']*100:.1f}%)")

# --- Machine types with fewest qualified technicians ---
tech_cov = model.select(
    distinct(
        Qualification.machine_type_str.alias("machine_type"),
        aggs.count(Qualification).per(Qualification.machine_type_str).alias("n_techs"),
    )
).to_df()
tech_cov["n_techs"] = tech_cov["n_techs"].astype(int)
tech_cov = tech_cov.sort_values("n_techs")
print("\n-- Qualified technicians per machine type --")
for _, row in tech_cov.iterrows():
    print(f"   {row['machine_type']}: {int(row['n_techs'])}")


# ==================================================================
# Stage 2: Rules -- classify machine risk
# ==================================================================

banner("STAGE 2  Rules")

Machine.downtime_event_count = model.Property(f"{Machine} has downtime event count {Integer:downtime_event_count}")
model.define(
    Machine.downtime_event_count(
        aggs.count(DowntimeEvent).per(Machine).where(DowntimeEvent.machine(Machine)) | 0
    )
)

Machine.is_chronic = model.Relationship(f"{Machine} has chronic downtime")
model.where(Machine.downtime_event_count > CHRONIC_DOWNTIME_THRESHOLD).define(Machine.is_chronic())

Machine.is_high_risk = model.Relationship(f"{Machine} is high risk")
model.where(
    Machine.failure_probability > HIGH_RISK_FP, Machine.criticality >= HIGH_RISK_CRITICALITY
).define(Machine.is_high_risk())

Machine.is_overdue = model.Relationship(f"{Machine} is overdue for maintenance")
model.where(Machine.remaining_useful_life <= OVERDUE_RUL).define(Machine.is_overdue())

Machine.risk_tier = model.Property(f"{Machine} has risk tier {String:risk_tier}")
# Critical: all three flags fire
model.where(Machine.is_chronic(), Machine.is_high_risk(), Machine.is_overdue()).define(Machine.risk_tier("Critical"))
# Elevated: exactly two
model.where(Machine.is_chronic(), Machine.is_high_risk(), model.not_(Machine.is_overdue())).define(Machine.risk_tier("Elevated"))
model.where(Machine.is_chronic(), model.not_(Machine.is_high_risk()), Machine.is_overdue()).define(Machine.risk_tier("Elevated"))
model.where(model.not_(Machine.is_chronic()), Machine.is_high_risk(), Machine.is_overdue()).define(Machine.risk_tier("Elevated"))
# Standard: zero or one
model.where(model.not_(Machine.is_chronic()), model.not_(Machine.is_high_risk()), model.not_(Machine.is_overdue())).define(Machine.risk_tier("Standard"))
model.where(Machine.is_chronic(), model.not_(Machine.is_high_risk()), model.not_(Machine.is_overdue())).define(Machine.risk_tier("Standard"))
model.where(model.not_(Machine.is_chronic()), Machine.is_high_risk(), model.not_(Machine.is_overdue())).define(Machine.risk_tier("Standard"))
model.where(model.not_(Machine.is_chronic()), model.not_(Machine.is_high_risk()), Machine.is_overdue()).define(Machine.risk_tier("Standard"))

tiers = model.select(
    distinct(
        Machine.risk_tier.alias("tier"),
        aggs.count(Machine).per(Machine.risk_tier).alias("n"),
    )
).to_df()
tiers["n"] = tiers["n"].astype(int)
tiers = tiers.sort_values("n", ascending=False)
print("\n-- Machine risk tiers --")
for _, row in tiers.iterrows():
    print(f"   {row['tier']}: {int(row['n'])}")

critical = model.where(Machine.risk_tier == "Critical").select(
    Machine.machine_id.alias("machine_id"),
    Machine.machine_type.alias("machine_type"),
    Machine.facility.alias("facility"),
).to_df().sort_values("machine_id")
print("   Critical machines:")
for _, row in critical.iterrows():
    print(f"     {row['machine_id']} ({row['machine_type']}, {row['facility']})")

# ==================================================================
# Stage 3: Graph -- producibility bottlenecks
# ==================================================================

banner("STAGE 3  Graph")

# Bipartite machine-product graph (edge = machine can produce product).
# Betweenness centrality surfaces machines that bridge many products --
# production-network bottlenecks whose loss is hardest to route around.
prod_graph = Graph(model, directed=False, weighted=False)
_GM = Machine.ref()
_GP = Product.ref()
model.where(
    MachineProductCapability.machine(_GM), MachineProductCapability.product(_GP)
).define(prod_graph.Edge.new(src=_GM, dst=_GP))

n_nodes = int(model.select(prod_graph.num_nodes().alias("n")).to_df()["n"].iloc[0])
n_edges = int(model.select(prod_graph.num_edges().alias("n")).to_df()["n"].iloc[0])
print(f"\n   bipartite graph: {n_nodes} nodes (machines + products), {n_edges} edges")

prod_graph.Node.bottleneck_raw = prod_graph.betweenness_centrality()
Machine.bottleneck = model.Property(f"{Machine} has bottleneck centrality {Float:bottleneck}")
model.where(prod_graph.Node == Machine).define(Machine.bottleneck(prod_graph.Node.bottleneck_raw))

Machine.product_count = model.Property(f"{Machine} makes {Integer:product_count} products")
model.define(
    Machine.product_count(
        aggs.count(MachineProductCapability).per(Machine).where(MachineProductCapability.machine(Machine)) | 0
    )
)

bottlenecks = model.select(
    Machine.machine_id.alias("machine_id"),
    Machine.machine_type.alias("machine_type"),
    Machine.bottleneck.alias("bottleneck"),
    Machine.product_count.alias("product_count"),
).to_df()
bottlenecks["product_count"] = bottlenecks["product_count"].astype(int)
bottlenecks = bottlenecks.sort_values("bottleneck", ascending=False)
print("\n-- Top machine producibility bottlenecks (betweenness centrality) --")
for _, row in bottlenecks.head(8).iterrows():
    print(
        f"   {row['machine_id']} ({row['machine_type']}): betweenness {row['bottleneck']:.4f}, "
        f"makes {row['product_count']} products"
    )

# ==================================================================
# Stage 4: Predictive -- forward failure risk
# ==================================================================
#
# Ships with pre-loaded predictions (failure_predictions.csv) so the predictive
# question is answerable out of the box, with no training step. To run a live model
# instead, set USE_PRELOADED_PREDICTIONS = False and train a GNN over the sensor and
# downtime history (see README "Customize" and the rai-predictive-* skills).

banner("STAGE 4  Predictive")

if USE_PRELOADED_PREDICTIONS:
    fail_p12 = model.where(FailurePrediction.period_int == PERIOD_HORIZON).select(
        FailurePrediction.machine_id_str.alias("machine_id"),
        FailurePrediction.predicted_failure_mode.alias("mode"),
        FailurePrediction.failure_probability.alias("fp"),
    ).to_df().sort_values("fp", ascending=False)
    print(f"\n-- Most likely to fail by period {PERIOD_HORIZON} (pre-loaded predictions) --")
    for _, row in fail_p12.head(5).iterrows():
        print(f"   {row['machine_id']} {row['mode']} ({row['fp'] * 100:.1f}%)")
else:
    raise NotImplementedError(
        "Live GNN path is not wired in this template. Either set "
        "USE_PRELOADED_PREDICTIONS = True to use the bundled predictions, or train a "
        "GNN over sensor/downtime history and write FailurePrediction "
        "(see README 'Customize' and the rai-predictive-modeling / -training skills)."
    )


# ==================================================================
# Stage 5: Prescriptive -- preventive-maintenance schedule + what-if
# ==================================================================

banner("STAGE 5  Prescriptive")

# Periods 1..H as a concept so the schedule can index (machine, period).
Period = model.Concept("Period", identify_by={"pid": Integer})
_per = model.data([{"pid": t} for t in range(1, PERIOD_HORIZON + 1)])
model.define(Period.new(pid=_per["pid"]))

# Coverage feasibility: a machine can be maintained only if a qualified technician
# is available -- and Turbine work requires an ON-SITE (same-location) technician.
Machine.has_onsite_qualified = model.Relationship(f"{Machine} has an on-site qualified technician")
_QL = Qualification.ref()
_QLT = Technician.ref()
model.where(
    _QL.machine_type_str == Machine.machine_type,
    _QL.technician(_QLT),
    _QLT.base_location == Machine.location,
).define(Machine.has_onsite_qualified())

# Same, but excluding technician T001 -- used for the what-if re-solve.
Machine.has_onsite_qualified_excl = model.Relationship(f"{Machine} has an on-site qualified technician excluding T001")
_QL2 = Qualification.ref()
_QLT2 = Technician.ref()
model.where(
    _QL2.machine_type_str == Machine.machine_type,
    _QL2.technician(_QLT2),
    _QLT2.base_location == Machine.location,
    _QLT2.technician_id != "T001",
).define(Machine.has_onsite_qualified_excl())

# coverable / coverable_wif: Turbine needs on-site tech; everything else is coverable.
Machine.coverable = model.Property(f"{Machine} coverage feasible {Integer:coverable}")
model.where(Machine.machine_type != "Turbine").define(Machine.coverable(1))
model.where(Machine.machine_type == "Turbine", Machine.has_onsite_qualified()).define(Machine.coverable(1))
model.where(Machine.machine_type == "Turbine", model.not_(Machine.has_onsite_qualified())).define(Machine.coverable(0))

Machine.coverable_wif = model.Property(f"{Machine} coverage feasible without T001 {Integer:coverable_wif}")
model.where(Machine.machine_type != "Turbine").define(Machine.coverable_wif(1))
model.where(Machine.machine_type == "Turbine", Machine.has_onsite_qualified_excl()).define(Machine.coverable_wif(1))
model.where(Machine.machine_type == "Turbine", model.not_(Machine.has_onsite_qualified_excl())).define(Machine.coverable_wif(0))

# Machine x Period decision space.
MachinePeriod = model.Concept("MachinePeriod", identify_by={"machine_id": String, "pid": Integer})
MachinePeriod.machine = model.Property(f"{MachinePeriod} for {Machine}")
MachinePeriod.period = model.Property(f"{MachinePeriod} in {Period}")
MachinePeriod.machine_id_str = model.Property(f"{MachinePeriod} machine id {String:machine_id_str}")
MachinePeriod.period_num = model.Property(f"{MachinePeriod} period number {Integer:period_num}")
_MPM = Machine.ref()
_MPP = Period.ref()
model.define(
    mp := MachinePeriod.new(machine_id=_MPM.machine_id, pid=_MPP.pid),
    mp.machine(_MPM),
    mp.period(_MPP),
    mp.machine_id_str(_MPM.machine_id),
    mp.period_num(_MPP.pid),
)

# Pre-derive Float coefficients -- inline casts (floats.float) are not allowed
# inside the objective expression, so materialize them as properties first.
Machine.criticality_f = model.Property(f"{Machine} criticality as float {Float:criticality_f}")
model.define(Machine.criticality_f(floats.float(Machine.criticality)))
MachinePeriod.earliness = model.Property(f"{MachinePeriod} earliness weight {Float:earliness}")
model.define(MachinePeriod.earliness(floats.float(PERIOD_HORIZON + 1 - MachinePeriod.period_num)))


def _report_schedule(label, sched_df, si):
    print(f"\n-- {label}: status {si.termination_status}, objective {si.objective_value:.3f} --")
    print(f"   machines scheduled: {len(sched_df)} of 50; periods used: 1..{int(sched_df['pid'].max())}")
    per_period = sched_df.groupby("pid").size()
    print("   jobs per period: " + ", ".join(f"p{p}={n}" for p, n in per_period.items()))


# --- Baseline solve --------------------------------------------------------
MachinePeriod.x_maintain = model.Property(f"{MachinePeriod} maintain decision {Float:x_maintain}")
prob = Problem(model, Float)
prob.solve_for(MachinePeriod.x_maintain, type="bin", name=["maintain", MachinePeriod.machine_id_str, MachinePeriod.period_num])
prob.satisfy(
    model.require(
        aggs.sum(MachinePeriod.x_maintain).per(Machine).where(MachinePeriod.machine(Machine)) <= Machine.coverable
    ),
    name=["cover", Machine.machine_id],
)
prob.satisfy(
    model.require(
        aggs.sum(MachinePeriod.x_maintain).per(Period).where(MachinePeriod.period(Period)) <= 5
    ),
    name=["bay", Period.pid],
)
prob.maximize(
    aggs.sum(
        MachinePeriod.x_maintain
        * Machine.failure_probability
        * Machine.criticality_f
        * MachinePeriod.earliness
    ).where(MachinePeriod.machine(Machine))
)
prob.solve("highs", time_limit_sec=120)
si = prob.solve_info()

_vr = Float.ref()
_sm = Machine.ref()
sched = model.select(
    _sm.machine_id.alias("machine_id"),
    _sm.machine_type.alias("machine_type"),
    _sm.facility.alias("facility"),
    MachinePeriod.period_num.alias("pid"),
).where(MachinePeriod.machine(_sm), MachinePeriod.x_maintain(_vr), _vr > 0.5).to_df()
sched["pid"] = sched["pid"].astype(int)
_report_schedule("Baseline schedule", sched, si)
earliest = sched.sort_values("pid").head(5)
print("   first jobs (riskiest, earliest): " + ", ".join(f"{r.machine_id}(p{r.pid})" for r in earliest.itertuples()))

# --- What-if: technician T001 unavailable ----------------------------------
dropped = model.where(Machine.coverable == 1, Machine.coverable_wif == 0).select(
    Machine.machine_id.alias("machine_id"),
    Machine.machine_type.alias("machine_type"),
    Machine.facility.alias("facility"),
).to_df().sort_values("machine_id")

MachinePeriod.x_maintain_wif = model.Property(f"{MachinePeriod} maintain decision without T001 {Float:x_maintain_wif}")
prob2 = Problem(model, Float)
prob2.solve_for(MachinePeriod.x_maintain_wif, type="bin", name=["maintain_wif", MachinePeriod.machine_id_str, MachinePeriod.period_num])
prob2.satisfy(
    model.require(
        aggs.sum(MachinePeriod.x_maintain_wif).per(Machine).where(MachinePeriod.machine(Machine)) <= Machine.coverable_wif
    ),
    name=["cover_wif", Machine.machine_id],
)
prob2.satisfy(
    model.require(
        aggs.sum(MachinePeriod.x_maintain_wif).per(Period).where(MachinePeriod.period(Period)) <= 5
    ),
    name=["bay_wif", Period.pid],
)
prob2.maximize(
    aggs.sum(
        MachinePeriod.x_maintain_wif
        * Machine.failure_probability
        * Machine.criticality_f
        * MachinePeriod.earliness
    ).where(MachinePeriod.machine(Machine))
)
prob2.solve("highs", time_limit_sec=120)
si2 = prob2.solve_info()

_vr2 = Float.ref()
_sm2 = Machine.ref()
sched2 = model.select(
    _sm2.machine_id.alias("machine_id"),
    MachinePeriod.period_num.alias("pid"),
).where(MachinePeriod.machine(_sm2), MachinePeriod.x_maintain_wif(_vr2), _vr2 > 0.5).to_df()
print(f"\n-- What-if (T001 unavailable): status {si2.termination_status}, objective {si2.objective_value:.3f} --")
print(f"   machines scheduled: {len(sched2)} of 50 (baseline {len(sched)}); objective delta {si.objective_value - si2.objective_value:.3f}")
print(f"   machines that lose coverage: {len(dropped)}")
for _, row in dropped.iterrows():
    print(f"     {row['machine_id']} ({row['machine_type']}, {row['facility']})")

# Persist the plan headline as ontology so it stays queryable after the run.
MaintenancePlan = model.Concept("MaintenancePlan", identify_by={"key": Integer})
MaintenancePlan.objective = model.Property(f"{MaintenancePlan} has objective {Float:objective}")
MaintenancePlan.machines_scheduled = model.Property(f"{MaintenancePlan} schedules {Integer:machines_scheduled} machines")
MaintenancePlan.periods_used = model.Property(f"{MaintenancePlan} spans {Integer:periods_used} periods")
_plan = model.data([{"key": 1, "obj": float(si.objective_value), "n": int(len(sched)), "p": int(sched["pid"].max())}])
model.define(
    plan := MaintenancePlan.new(key=_plan["key"]),
    plan.objective(_plan["obj"]),
    plan.machines_scheduled(_plan["n"]),
    plan.periods_used(_plan["p"]),
)
plan_df = model.select(
    MaintenancePlan.machines_scheduled.alias("machines_scheduled"),
    MaintenancePlan.periods_used.alias("periods_used"),
    MaintenancePlan.objective.alias("objective"),
).to_df()
print(
    f"\n-- MaintenancePlan (persisted to ontology): "
    f"{int(plan_df['machines_scheduled'].iloc[0])} machines over "
    f"{int(plan_df['periods_used'].iloc[0])} periods, objective {plan_df['objective'].iloc[0]:.3f} --"
)

print("\n>>> ALL STAGES complete")
