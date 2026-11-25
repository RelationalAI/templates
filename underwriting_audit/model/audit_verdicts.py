"""Audit verdicts: each property's PASS, FAIL, or INCONCLUSIVE verdict, whether its search stopped at
the witness limit, and how many properties received each verdict."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates as aggs

from .property_audits import NumPoints, SolveStatus
from .schema import model

# --------------------------------------------------
# Verdict per property
# --------------------------------------------------

# A verdict is classified from the status and number of witnesses of the property's solve:
# - FAIL: at least one witness. A counterexample exists, which falsifies the property
#   regardless of whether the search was exhaustive; the witness count is partial when the
#   status is not OPTIMAL or SOLUTION_LIMIT, but the verdict itself is conclusive.
# - PASS: INFEASIBLE, or OPTIMAL with a published count of zero. The solver proved no
#   counterexample exists (or exhausted the search and found none), so the property holds under
#   the encoded rule pack. Soundness is bounded by encoding fidelity: missing rule arms can
#   produce a silent pass. Local-only statuses (e.g. LOCALLY_SOLVED from an LP solver) do not
#   count as exhaustion and are INCONCLUSIVE.
# - INCONCLUSIVE: anything else (TIME_LIMIT, MEMORY_LIMIT, OTHER_ERROR, ... with zero
#   witnesses, or OPTIMAL with no published count). The audit did not finish or its count is
#   missing, and no witness was found, so neither pass nor fail can be concluded.
PropertyVerdict = model.Relationship(f"property {String:property_name} has verdict {String:verdict}")
HitWitnessLimit = model.Relationship(f"property {String:property_name} stopped at the witness limit")

_n_witnesses = Integer.ref()
for name in SolveStatus:
    found = (NumPoints[name](_n_witnesses), _n_witnesses >= 1)
    infeasible = SolveStatus[name]("INFEASIBLE")
    exhausted = (SolveStatus[name]("OPTIMAL"), NumPoints[name](0))
    model.where(*found).define(PropertyVerdict(name, "FAIL"))
    model.where(infeasible, model.not_(*found)).define(PropertyVerdict(name, "PASS"))
    model.where(*exhausted).define(PropertyVerdict(name, "PASS"))
    model.where(
        model.not_(*found), model.not_(infeasible), model.not_(*exhausted)
    ).define(PropertyVerdict(name, "INCONCLUSIVE"))

    # A FAIL whose search stopped at the witness limit: more counterexamples may exist.
    model.where(*found, SolveStatus[name]("SOLUTION_LIMIT")).define(HitWitnessLimit(name))

# --------------------------------------------------
# Verdict tallies
# --------------------------------------------------

# The number of properties with each verdict, zero when none has it, and the number of properties.
VerdictTally = model.Concept("VerdictTally", identify_by={"verdict": String})
VerdictTally.n_properties = model.Property(f"{VerdictTally} has {Integer:n_properties} properties")
model.define(
    VerdictTally.new(verdict="PASS"),
    VerdictTally.new(verdict="FAIL"),
    VerdictTally.new(verdict="INCONCLUSIVE"),
)
_property_name, _verdict = String.ref(), String.ref()
model.define(
    VerdictTally.n_properties(
        aggs.count(_property_name)
        .per(VerdictTally)
        .where(PropertyVerdict(_property_name, VerdictTally.verdict))
        | 0
    )
)

NumProperties = model.Relationship(f"the audit covers {Integer:n_properties} properties")
model.define(NumProperties(aggs.count(_property_name).where(PropertyVerdict(_property_name, _verdict))))
