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
    python defect_root_cause.py

Output:
    Prints per-stage diagnostics -- genealogy reachability validation, the
    contrast-scored suspect factors with lift, the MILP termination status,
    and a final DiagnosisResult singleton row (defective units, units
    explained, coverage, and the ranked root-cause factors) showing the
    diagnosis as queryable ontology.
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

DATA_DIR = Path(__file__).parent / "data"

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

n_units = model.select(Unit.id).to_df()
n_def = model.where(Unit.is_defective()).select(Unit.id).to_df()
print(f"Loaded {len(n_units)} units, {len(n_def)} defective ({len(n_def) / len(n_units):.2%} final-test failure rate)")

# Descriptive: when did the spike start? A real investigation begins on the
# timeline -- failures by build week -- before touching genealogy. The onset is
# the first week whose rate runs well above the opening week's baseline; it
# tells the rest of the chain which window's changes to interrogate.
wk = model.select(Unit.build_week.alias("week"), Unit.defective.alias("defective")).to_df()
wk["defective"] = wk["defective"].astype(int)
timeline = wk.groupby("week").agg(units=("defective", "size"), defects=("defective", "sum"))
timeline["rate"] = timeline["defects"] / timeline["units"]
opening = timeline["rate"].iloc[0]
onset = next((int(w) for w, r in timeline["rate"].items() if r > 2 * opening), None)
print("\nWhen did the spike start? Final-test failure rate by build week:")
for week, r in timeline.iterrows():
    mark = "  <- spike onset" if onset == int(week) else ""
    print(f"  week {int(week)}: {int(r['units']):>4} units   {r['rate']:>5.1%}{mark}")
print(f"Spike onset at week {onset}: the chain interrogates what entered the line then.")

# --------------------------------------------------
# Stage 1 -- Graph: backward reachability over the lot genealogy
# --------------------------------------------------

# Directed parent -> child genealogy graph on Lot. Following edges from a
# top-tier lot reaches every lot consumed beneath it.
graph = Graph(model, directed=True, weighted=False, node_concept=Lot)
parent, child = Lot.ref(), Lot.ref()
model.where(parent.consumes(child)).define(graph.Edge.new(src=parent, dst=child))
n_nodes = int(model.select(graph.num_nodes().alias("n")).to_df()["n"].iloc[0])
n_edges = int(model.select(graph.num_edges().alias("n")).to_df()["n"].iloc[0])
print(f"\nGenealogy graph: {n_nodes} lot nodes, {n_edges} parent->child edges")

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


# Naive view: rank candidate factors by the raw count of defective units they
# touch. High-volume factors dominate -- a near-universal housing lot and the
# busiest placement line top the list purely because they touch almost
# everything. That is exactly the trap the contrast stage corrects. Genealogy
# closure puts lots and machines on the same footing: a deep lot is "touched by"
# every finished unit that carries it.
incidence = model.where((f := Factor.ref()).touches(u := Unit.ref())).select(
    f.id.alias("factor"), f.kind.alias("kind"), u.defective.alias("defective")
).to_df()
incidence["defective"] = incidence["defective"].astype(int)
top_raw = (
    incidence.groupby(["factor", "kind"])
    .agg(units=("defective", "size"), defects=("defective", "sum"))
    .reset_index().sort_values("defects", ascending=False).head(6).reset_index(drop=True)
)
print(f"\nBackward reachability built {len(incidence):,} (factor, unit) incidence facts.")
print("Top candidate factors by RAW defective units touched (pre-contrast -- note the high-volume bias):")
print(top_raw.to_string(index=False))

# --------------------------------------------------
# Stage 2 -- Rules: contrast scoring of candidate factors
# --------------------------------------------------

BASELINE_RATE = len(n_def) / len(n_units)

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
    Factor.lift((floats.float(Factor.defect_count) / floats.float(Factor.touched_count)) / BASELINE_RATE)
)
# A factor is a suspect only when defect lift, support, and defect count all
# clear threshold -- screening out high-coverage, low-lift trunk factors.
model.where(
    Factor.lift >= LIFT_THRESHOLD,
    Factor.touched_count >= MIN_SUPPORT,
    Factor.defect_count >= MIN_DEFECTS
).define(Factor.is_suspect(Factor))

suspects = model.where(Factor.is_suspect(f := Factor.ref())).select(
    f.id.alias("factor"),
    f.kind.alias("kind"),
    f.touched_count.alias("units"),
    f.defect_count.alias("defects"),
    f.defect_rate.alias("rate"),
    f.lift.alias("lift"),
).to_df().sort_values("lift", ascending=False).reset_index(drop=True)
print(f"\nContrast scoring: {len(suspects)} suspect factors (baseline failure rate {BASELINE_RATE:.2%}, "
      f"lift>={LIFT_THRESHOLD}, support>={MIN_SUPPORT}, defects>={MIN_DEFECTS})")
print(suspects.to_string(index=False))

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

# Pre-solve audit: variables and objective registered, and -- the easy thing to
# get wrong -- one coverage constraint grounded per defective unit.
model.require(problem.num_variables() > 0)
model.require(problem.num_constraints() > 0)
model.require(problem.num_min_objectives() == 1)
n_cover = len(model.select(cover).to_df())
assert n_cover == len(n_def), f"coverage grounded {n_cover} rows, expected {len(n_def)}"
print(f"\nPre-solve audit: {n_cover} coverage constraints grounded (one per defective unit).")

problem.solve("highs", time_limit_sec=120)
si = problem.solve_info()
print(f"\nDiagnosis solve: {si.termination_status}   objective={si.objective_value}")

# Read back the diagnosis (populate=True wrote the solution onto is_root_cause).
diagnosis = model.where((f := Factor.ref()).is_root_cause > 0.5).select(
    f.id.alias("factor"),
    f.label.alias("label"),
    f.kind.alias("kind"),
    f.defect_count.alias("defects_on_factor"),
    f.lift.alias("lift"),
).to_df().sort_values("lift", ascending=False).reset_index(drop=True)

explained = model.where(
    Unit.is_defective(),
    (f := Factor.ref()).is_root_cause > 0.5,
    f.touches(Unit)
).select(Unit.id.alias("unit")).to_df()
n_defective = len(n_def)
n_explained = explained["unit"].nunique()

# Persist the headline as queryable ontology: a DiagnosisResult singleton.
DiagnosisResult = model.Concept("DiagnosisResult", identify_by={"id": Integer})
DiagnosisResult.n_defective = model.Property(f"{DiagnosisResult} has {Integer:n_defective}")
DiagnosisResult.n_explained = model.Property(f"{DiagnosisResult} has {Integer:n_explained}")
DiagnosisResult.n_root_causes = model.Property(f"{DiagnosisResult} has {Integer:n_root_causes}")
DiagnosisResult.coverage = model.Property(f"{DiagnosisResult} has {Float:coverage}")
model.define(
    dr := DiagnosisResult.new(id=1),
    dr.n_defective(n_defective),
    dr.n_explained(n_explained),
    dr.n_root_causes(len(diagnosis)),
    dr.coverage(n_explained / n_defective),
)

print(f"\nRoot-cause diagnosis: {len(diagnosis)} factors explain {n_explained}/{n_defective} "
      f"defective units ({n_explained / n_defective:.0%} coverage)")
print(diagnosis.to_string(index=False))

# Corroborating evidence per named cause, the way a real RCA write-up reads:
# the defect signature it concentrates (a paste fault should present as cold
# solder, a reflow fault as solder bridging), plus a kind-specific tell --
# supplier and receipt date for a lot, calibration age for a machine. All of it
# is read back from ontology already loaded; the diagnosis is the hypothesis,
# this is the supporting evidence an engineer would confirm physically.
sig = model.where(
    (f := Factor.ref()).is_root_cause > 0.5,
    f.touches(u := Unit.ref()),
    u.is_defective()
).select(f.id.alias("factor"), u.defect_type.alias("defect_type")).to_df()
print("\nCorroborating evidence per root cause:")
for _, row in diagnosis.iterrows():
    fid, kind, label = row["factor"], row["kind"], row["label"]
    types = sig[sig["factor"] == fid]["defect_type"]
    dom = types.value_counts()
    signature = f"{dom.iloc[0] / len(types):.0%} {dom.index[0]}"
    ref = fid.split("::", 1)[1]
    if kind == "LOT":
        tell_df = model.where(
            (lo := Lot.ref()).id == ref,
            lo.supplier(sp := Supplier.ref())
        ).select(sp.name.alias("supplier"), lo.received_date.alias("recv")).to_df()
        tell = f"supplier {tell_df['supplier'].iloc[0]}, received {tell_df['recv'].iloc[0]}"
    else:
        tell_df = model.where((mm := Machine.ref()).id == ref).select(
            mm.calibration_age_days.alias("age")
        ).to_df()
        tell = f"{int(tell_df['age'].iloc[0])} days since last calibration"
    print(f"  {label:<26} {signature:<18} {tell}")
