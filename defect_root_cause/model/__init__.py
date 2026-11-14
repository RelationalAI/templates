"""Defect root-cause analysis (multi-reasoner) template.

Three-stage RelationalAI pipeline that turns a batch of final-test failures
into a defensible root-cause diagnosis over a serialized electronics-assembly
genealogy. The narrative: final-test failures have spiked from ~1.2% to 6.3%.
Every finished unit carries its full material genealogy (which lots,
transitively, went into it through a multi-tier BOM) and its process history
(which machine and shift ran each operation). The chain works backward from
the failures to the smallest, most specific set of causes that explains them.

- Stage 1 -- Graph: backward reachability over the lot genealogy. A directed
  parent -> child graph on Lot is closed transitively so that each Unit is
  linked (`Unit.touches_lot`) to every lot consumed anywhere beneath it --
  the inverse of forward BOM dependency tracing. This is what surfaces a
  contaminated paste lot sitting two genealogy hops below the finished unit.
- Stage 2 -- Rules: contrast scoring. Each candidate Factor (a lot, machine,
  or shift) is scored by how concentrated defects are among the units it
  touches versus the plant-wide baseline (`Factor.lift`). A factor is flagged
  `is_suspect` only when its defect lift and support clear thresholds -- so a
  near-universal trunk lot or a high-volume machine (high coverage, ~1x lift)
  is screened out before optimization.
- Stage 3 -- Prescriptive: minimal-diagnosis set-cover MILP. Binary
  `Factor.is_root_cause` selects a smallest-cost set of suspect factors that
  together explain (cover) the defective units, with a per-unit slack so a
  few scattered baseline failures are left unexplained rather than forcing
  spurious causes. The objective penalizes collateral (good units a factor
  also touches), so the diagnosis prefers the specific deep root over the
  proximate sub-assembly lots that merely carry it.

Each stage enriches the shared ontology, and downstream stages consume those
enrichments as first-class properties -- the accretive enrichment pattern.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which runs the solve; `python
    -m queries.root_cause_report` then prints the report from the deployed model.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import (
    Float,
    Integer,
    Model,
    String,
)
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Stage 2 contrast-scoring thresholds. A factor is a suspect only if defects
# among the units it touches run materially above the plant-wide baseline
# (LIFT) and it touches enough units to trust the rate (SUPPORT) and enough
# defects to matter (MIN_DEFECTS).
LIFT_THRESHOLD = 1.5
MIN_SUPPORT = 30
MIN_DEFECTS = 5

# Stage 3 minimal-diagnosis objective weights.
W_SELECT = 5.0       # parsimony: cost of naming one more factor a root cause
W_GOOD = 0.02        # specificity: penalty per good unit a named factor also touches
W_UNEXPLAINED = 1.0  # cost of leaving a defective unit unexplained (relief valve for scattered baseline failures)

# --------------------------------------------------
# Stage 0 -- Ontology: define the semantic model & load the genealogy corpus
# --------------------------------------------------

model = Model("defect_root_cause")

# SKU concept: a node in the product structure -- a finished good,
# sub-assembly, component, or raw material.
SKU = model.Concept("SKU", identify_by={"id": String})
SKU.name = model.Property(f"{SKU} has {String:name}")
SKU.tier = model.Property(f"{SKU} has {String:tier}")

# BillOfMaterials concept: one output SKU requires one input SKU (the
# type-level product structure that the lot genealogy instantiates).
BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.output_sku = model.Property(f"{BillOfMaterials} produces {SKU:output_sku}")
BillOfMaterials.input_sku = model.Property(f"{BillOfMaterials} requires {SKU:input_sku}")

# Supplier concept: who sourced a lot.
Supplier = model.Concept("Supplier", identify_by={"id": String})
Supplier.name = model.Property(f"{Supplier} has {String:name}")

# Machine concept: a piece of process equipment (placement, reflow, assembly,
# test). calibration_age_days corroborates a machine-as-cause finding.
Machine = model.Concept("Machine", identify_by={"id": String})
Machine.name = model.Property(f"{Machine} has {String:name}")
Machine.machine_type = model.Property(f"{Machine} has {String:machine_type}")
Machine.calibration_age_days = model.Property(f"{Machine} has {Integer:calibration_age_days}")

# Lot concept: a specific received or produced batch of a SKU. Lot.consumes is
# the genealogy edge -- a built lot consumes its input lots (parent -> child).
Lot = model.Concept("Lot", identify_by={"id": String})
Lot.sku = model.Property(f"{Lot} is of {SKU:sku}")
Lot.supplier = model.Property(f"{Lot} supplied by {Supplier:supplier}")
Lot.received_date = model.Property(f"{Lot} received on {String:received_date}")
Lot.consumes = model.Relationship(f"{Lot} consumes {Lot:child}")

# Unit concept: a serialized finished unit and its final-test outcome.
Unit = model.Concept("Unit", identify_by={"id": String})
Unit.sku = model.Property(f"{Unit} is a {SKU:sku}")
Unit.build_date = model.Property(f"{Unit} built on {String:build_date}")
Unit.build_week = model.Property(f"{Unit} built in week {Integer:build_week}")
Unit.defective = model.Property(f"{Unit} has defective flag {Integer:defective}")
Unit.defect_type = model.Property(f"{Unit} has {String:defect_type}")
Unit.shift = model.Property(f"{Unit} ran on shift {String:shift}")
Unit.consumes_lot = model.Relationship(f"{Unit} consumes {Lot}")
Unit.ran_on = model.Relationship(f"{Unit} ran on {Machine}")
# is_defective: the symptom set the diagnosis must explain.
Unit.is_defective = model.Relationship(f"{Unit} is defective")

# Factor concept: a candidate root cause -- a lot, a machine, or a shift. The
# per-kind pointer properties let the touch incidence be derived in-engine.
Factor = model.Concept("Factor", identify_by={"id": String})
Factor.kind = model.Property(f"{Factor} has {String:kind}")
Factor.label = model.Property(f"{Factor} has {String:label}")
Factor.lot = model.Property(f"{Factor} points to {Lot:lot}")
Factor.machine = model.Property(f"{Factor} points to {Machine:machine}")
Factor.shift_name = model.Property(f"{Factor} points to shift {String:shift_name}")

# --- Load the corpus (explicit binding; CSV columns are upper-case) ---

# SKUs and bill of materials.
sd = model.data(read_csv(DATA_DIR / "skus.csv"))
model.define(sku := SKU.new(id=sd.SKU_ID), sku.name(sd.NAME), sku.tier(sd.TIER))
bd = model.data(read_csv(DATA_DIR / "bill_of_materials.csv"))
model.define(
    b := BillOfMaterials.new(id=bd.BOM_ID),
    b.output_sku(SKU.lookup(id=bd.OUTPUT_SKU_ID)),
    b.input_sku(SKU.lookup(id=bd.INPUT_SKU_ID)),
)

# Suppliers and machines.
spd = model.data(read_csv(DATA_DIR / "suppliers.csv"))
model.define(s := Supplier.new(id=spd.SUPPLIER_ID), s.name(spd.NAME))
md = model.data(read_csv(DATA_DIR / "machines.csv"))
model.define(
    m := Machine.new(id=md.MACHINE_ID),
    m.name(md.NAME),
    m.machine_type(md.MACHINE_TYPE),
    m.calibration_age_days(md.CALIBRATION_AGE_DAYS),
)

# Lots and the genealogy edges between them.
ld = model.data(read_csv(DATA_DIR / "lots.csv"))
model.define(
    lot := Lot.new(id=ld.LOT_ID),
    lot.sku(SKU.lookup(id=ld.SKU_ID)),
    lot.supplier(Supplier.lookup(id=ld.SUPPLIER_ID)),
    lot.received_date(ld.RECEIVED_DATE),
)
gd = model.data(read_csv(DATA_DIR / "lot_genealogy.csv"))
model.define(Lot.lookup(id=gd.PARENT_LOT_ID).consumes(Lot.lookup(id=gd.CHILD_LOT_ID)))

# Units, their final-test result, and the top-tier lots they consume.
ud = model.data(read_csv(DATA_DIR / "units.csv"))
model.define(
    u := Unit.new(id=ud.UNIT_ID),
    u.sku(SKU.lookup(id=ud.SKU_ID)),
    u.build_date(ud.BUILD_DATE),
    u.defective(ud.DEFECTIVE),
    u.defect_type(ud.DEFECT_TYPE),
    u.shift(ud.SHIFT),
    u.build_week(ud.BUILD_WEEK),
)
model.define(Unit.is_defective(u := Unit.ref())).where(u.defective == 1)
uld = model.data(read_csv(DATA_DIR / "unit_lots.csv"))
model.define(Unit.lookup(id=uld.UNIT_ID).consumes_lot(Lot.lookup(id=uld.LOT_ID)))

# Process history: which machine ran each operation on each unit.
ppd = model.data(read_csv(DATA_DIR / "unit_process.csv"))
model.define(Unit.lookup(id=ppd.UNIT_ID).ran_on(Machine.lookup(id=ppd.MACHINE_ID)))

# Candidate factors, loaded per kind so each gets the right back-pointer.
fac = read_csv(DATA_DIR / "factors.csv")
lf = model.data(fac[fac.KIND == "LOT"])
model.define(f := Factor.new(id=lf.FACTOR_ID), f.kind(lf.KIND), f.label(lf.LABEL), f.lot(Lot.lookup(id=lf.REF_ID)))
mf = model.data(fac[fac.KIND == "MACHINE"])
model.define(f := Factor.new(id=mf.FACTOR_ID), f.kind(mf.KIND), f.label(mf.LABEL), f.machine(Machine.lookup(id=mf.REF_ID)))
sf = model.data(fac[fac.KIND == "SHIFT"])
model.define(f := Factor.new(id=sf.FACTOR_ID), f.kind(sf.KIND), f.label(sf.LABEL), f.shift_name(sf.REF_ID))

# --------------------------------------------------
# Stage 1 -- Graph: backward reachability over the lot genealogy
# --------------------------------------------------

# Directed parent -> child genealogy graph on Lot. Following edges from a
# top-tier lot reaches every lot consumed beneath it.
graph = Graph(model, directed=True, weighted=False, node_concept=Lot)
parent, child = Lot.ref(), Lot.ref()
model.where(parent.consumes(child)).define(graph.Edge.new(src=parent, dst=child))
num_nodes = graph.num_nodes()
num_edges = graph.num_edges()

# Transitive closure: which lots each top-tier lot reaches.
reach = graph.reachable(full=True)

# Unit.touches_lot: a unit touches the top-tier lots it consumes directly,
# plus every lot reachable beneath them. This backward closure is what lets a
# deep contaminated lot be attributed to the finished units that carry it.
Unit.touches_lot = model.Relationship(f"{Unit} touches {Lot:lot}")
model.where((u := Unit.ref()).consumes_lot(top := Lot.ref())).define(Unit.touches_lot(u, top))
model.where(
    (u := Unit.ref()).consumes_lot(top := Lot.ref()),
    reach(top, deep := Lot.ref())
).define(Unit.touches_lot(u, deep))

# Factor.touches: the unified incidence the diagnosis ranges over. Lot factors
# inherit the genealogy closure; machine and shift factors come from process.
Factor.touches = model.Relationship(f"{Factor} touches {Unit}")
model.where((u := Unit.ref()).touches_lot((f := Factor.ref()).lot)).define(Factor.touches(f, u))
model.where((u := Unit.ref()).ran_on((f := Factor.ref()).machine)).define(Factor.touches(f, u))
model.where((u := Unit.ref()).shift == (f := Factor.ref()).shift_name).define(Factor.touches(f, u))


# --------------------------------------------------
# Stage 2 -- Rules: contrast scoring of candidate factors
# --------------------------------------------------

# Plant-wide failure rate: defective units over the distinct units in the model.
PlantBaseline = model.Concept("PlantBaseline", identify_by={"id": Integer})
PlantBaseline.n_units = model.Property(f"{PlantBaseline} has {Integer:n_units}")
PlantBaseline.n_defective = model.Property(f"{PlantBaseline} has {Integer:n_defective}")
PlantBaseline.failure_rate = model.Property(f"{PlantBaseline} has {Float:failure_rate}")
model.define(PlantBaseline.new(id=1))
model.define(PlantBaseline.n_units(aggs.count(Unit).per(PlantBaseline)))
model.define(
    PlantBaseline.n_defective(aggs.count(Unit).per(PlantBaseline).where(Unit.is_defective()))
)
model.define(
    PlantBaseline.failure_rate(
        floats.float(PlantBaseline.n_defective) / floats.float(PlantBaseline.n_units)
    )
)

# Per-factor incidence: how many units it touches, and how many of those failed.
Factor.touched_count = model.Property(f"{Factor} touches {Integer:touched_count}")
Factor.defect_count = model.Property(f"{Factor} has {Integer:defect_count}")
Factor.defect_rate = model.Property(f"{Factor} has {Float:defect_rate}")
Factor.lift = model.Property(f"{Factor} has {Float:lift}")
# is_suspect: defects are concentrated enough among the units this factor
# touches to warrant optimization -- the contrast screen before the MILP.
Factor.is_suspect = model.Relationship(f"{Factor} is suspect")

model.define(Factor.touched_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit))))
model.define(Factor.defect_count(aggs.count(Unit).per(Factor).where(Factor.touches(Unit), Unit.is_defective())))
# defect_rate and lift each derive directly from the two counts (kept one
# level deep so the chain stays robust alongside the genealogy graph).
model.where(Factor.defect_count > 0).define(
    Factor.defect_rate(floats.float(Factor.defect_count) / floats.float(Factor.touched_count))
)
model.where(Factor.defect_count > 0).define(
    Factor.lift(
        (floats.float(Factor.defect_count) / floats.float(Factor.touched_count))
        / PlantBaseline.failure_rate
    )
)
# A factor is a suspect only when defect lift, support, and defect count all
# clear threshold -- screening out high-coverage, low-lift trunk factors.
model.where(
    Factor.lift >= LIFT_THRESHOLD,
    Factor.touched_count >= MIN_SUPPORT,
    Factor.defect_count >= MIN_DEFECTS
).define(Factor.is_suspect(Factor))

# --------------------------------------------------
# Stage 3 -- Prescriptive: minimal-diagnosis set-cover MILP
# --------------------------------------------------

# Pre-derive the per-factor selection cost as a Float so the objective stays a
# plain sum of (variable * coefficient) -- inline arithmetic/casts inside
# minimize() are rejected by the rewriter. good_count is the collateral: good
# units a factor also touches, which the objective penalizes for specificity.
Factor.good_count = model.Property(f"{Factor} has {Integer:good_count}")
Factor.select_cost = model.Property(f"{Factor} has {Float:select_cost}")
model.where(Factor.is_suspect(f := Factor.ref())).define(Factor.good_count(f, f.touched_count - f.defect_count))
model.where(Factor.is_suspect(f := Factor.ref())).define(
    Factor.select_cost(f, W_SELECT + W_GOOD * floats.float(f.good_count))
)

# Decision variables: name a suspect factor a root cause (binary), and mark a
# defective unit unexplained (binary slack).
Factor.is_root_cause = model.Property(f"{Factor} has {Float:is_root_cause}")
Unit.unexplained = model.Property(f"{Unit} has {Float:unexplained}")

problem = Problem(model, Float)
problem.solve_for(Factor.is_root_cause, where=[Factor.is_suspect()], type="bin", name=["pick", Factor.id])
problem.solve_for(Unit.unexplained, where=[Unit.is_defective()], type="bin", name=["slack", Unit.id])

# Coverage: every defective unit must be explained by at least one named suspect
# factor it touches, or else marked unexplained. The `| 0` coalesces the sum to
# zero for units no suspect touches, so the constraint still grounds for them
# (they fall to the unexplained slack) rather than being silently dropped.
cover = problem.satisfy(
    model.where(Unit.is_defective()).require(
        (aggs.sum(Factor.is_root_cause).per(Unit).where(Factor.touches(Unit)) | 0) + Unit.unexplained >= 1.0
    ),
    name=["cover", Unit.id],
)

# Objective: the smallest, most specific diagnosis -- fewest / least-collateral
# named factors, fewest unexplained defects.
problem.minimize(
    aggs.sum(Factor.is_root_cause * Factor.select_cost) + W_UNEXPLAINED * aggs.sum(Unit.unexplained)
)

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=120)

# Problem-structure relations the formulation audit reads, declared here so they
# deploy with the model.
num_vars = problem.num_variables()
num_cons = problem.num_constraints()
num_min_objs = problem.num_min_objectives()

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"defect diagnosis solve status is {String:status}")
DiagnosisCost = model.Relationship(f"defect diagnosis cost is {Float:cost}")
model.define(
    SolveStatus(problem.termination_status()), DiagnosisCost(problem.objective_value())
)

# Persist the headline as queryable ontology: a DiagnosisResult singleton derived
# from the named root causes (populate=True writes the solution onto is_root_cause).
DiagnosisResult = model.Concept("DiagnosisResult", identify_by={"id": Integer})
DiagnosisResult.n_defective = model.Property(f"{DiagnosisResult} has {Integer:n_defective}")
DiagnosisResult.n_explained = model.Property(f"{DiagnosisResult} has {Integer:n_explained}")
DiagnosisResult.n_root_causes = model.Property(f"{DiagnosisResult} has {Integer:n_root_causes}")
DiagnosisResult.coverage = model.Property(f"{DiagnosisResult} has {Float:coverage}")
model.define(DiagnosisResult.new(id=1))
model.define(
    DiagnosisResult.n_defective(
        aggs.count(Unit).per(DiagnosisResult).where(Unit.is_defective())
    )
)
model.define(
    DiagnosisResult.n_explained(
        aggs.count(Unit)
        .per(DiagnosisResult)
        .where(
            Unit.is_defective(),
            (f := Factor.ref()).is_root_cause > 0.5,
            f.touches(Unit),
        )
    )
)
model.define(
    DiagnosisResult.n_root_causes(
        aggs.count(Factor).per(DiagnosisResult).where(Factor.is_root_cause > 0.5)
    )
)
model.define(
    DiagnosisResult.coverage(
        floats.float(DiagnosisResult.n_explained)
        / floats.float(DiagnosisResult.n_defective)
    )
)
