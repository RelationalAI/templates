"""Root-cause diagnosis: the minimal-diagnosis set-cover MILP over the suspect factors, its
formulation counts and solve status, and the DiagnosisResult headline."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# Declares the suspect screen and the per-factor counts the solve reads.
from . import contrast_scoring  # noqa: F401
from .schema import Factor, Unit, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Stage 3 minimal-diagnosis objective weights.
W_SELECT = 5.0       # parsimony: cost of naming one more factor a root cause
W_GOOD = 0.02        # specificity: penalty per good unit a named factor also touches
W_UNEXPLAINED = 1.0  # cost of leaving a defective unit unexplained (relief valve for scattered baseline failures)

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

# The problem-structure counts the formulation audit reads, which the deployed model
# publishes for the queries.
num_vars = model.Relationship(f"defect diagnosis has {Integer:num_variables} variables")
num_cons = model.Relationship(f"defect diagnosis has {Integer:num_constraints} constraints")
num_min_objs = model.Relationship(
    f"defect diagnosis has {Integer:num_min_objectives} minimization objectives"
)
num_cover = model.Relationship(f"defect diagnosis grounds {Integer:num_cover} coverage constraints")
model.define(
    num_vars(problem.num_variables()),
    num_cons(problem.num_constraints()),
    num_min_objs(problem.num_min_objectives()),
    num_cover(aggs.count(cover)),
)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"defect diagnosis solve status is {String:status}")
DiagnosisCost = model.Relationship(f"defect diagnosis cost is {Float:cost}")
model.define(
    SolveStatus(problem.termination_status()), DiagnosisCost(problem.objective_value())
)

# Persist the headline as queryable ontology: a DiagnosisResult singleton derived
# from the named root causes (populate=True writes the solution onto is_root_cause).
# A solved diagnosis that names no cause explains zero units, so both counts default
# to 0; they are defined only when the solve returned a solution (an objective value),
# so a failed solve publishes no diagnosis rather than an empty one.
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
model.where(DiagnosisCost(Float.ref())).define(
    DiagnosisResult.n_explained(
        aggs.count(Unit)
        .per(DiagnosisResult)
        .where(
            Unit.is_defective(),
            (f := Factor.ref()).is_root_cause > 0.5,
            f.touches(Unit),
        )
        | 0
    )
)
model.where(DiagnosisCost(Float.ref())).define(
    DiagnosisResult.n_root_causes(
        aggs.count(Factor).per(DiagnosisResult).where(Factor.is_root_cause > 0.5) | 0
    )
)
model.define(
    DiagnosisResult.coverage(
        floats.float(DiagnosisResult.n_explained)
        / floats.float(DiagnosisResult.n_defective)
    )
)
