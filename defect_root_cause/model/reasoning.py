"""Root-cause diagnosis: lot genealogy graph, contrast scoring, and the minimal-diagnosis set cover."""

from relationalai.semantics import (
    Float,
    Integer,
    String,
)
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

from .schema import Factor, Lot, Unit, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

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

problem = Problem(model, Float, name="defect_root_cause")
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

# The solve's status and objective, which the deployed model publishes for the queries.
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
