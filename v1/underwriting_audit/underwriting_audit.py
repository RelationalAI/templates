"""Underwriting Audit (rule verification, multi-solution witness enumeration) template.

This script demonstrates property-entailment audit on a small underwriting
ruleset:

- Define the ruleset as binary indicators on a synthesised applicant
  (`is_senior`, `is_frail`, `is_manual_review`), each tied to the applicant's
  decision-valued properties via OR-arithmetic equivalences.
- Audit the property "every frail applicant goes through manual review" by
  asking the solver for a counterexample applicant -- one who is frail but
  not flagged for manual review. If any feasible applicant exists, the
  property does NOT hold and the rules contain a bug.
- Solve as constraint satisfaction with `solution_limit=K` (MiniZinc) and
  enumerate every distinct witness via `Variable.values(solution_index, value)`.
  Audit / conflict surfacing is plural by definition: one witness tells the
  actuary that the property fails; K distinct witnesses surface concrete
  failure cases across age buckets, coverage bands, and condition profiles
  the buggy rule misses. The solver guarantees the witnesses are pairwise
  distinct, not maximally diverse. The default `MAX_WITNESSES` is set
  above the bundled feasible-set size so the search exhausts and the
  output is stable across runs; sizing the cap below the feasible set
  flips `status` to `SOLUTION_LIMIT` and only the existence of K
  witnesses (not their specific identity) is stable. Multi-solution
  is the right return shape.

The bundled ruleset has a deliberate bug: `is_manual_review` is defined as
"senior", but `is_frail` is defined as "senior OR has chronic condition".
The audit turns up witnesses with chronic conditions and non-senior age:
they are frail (chronic) but the buggy rule lets them skip manual review
because they are not senior.

Run:
    `python underwriting_audit.py`

Output:
    Prints the formulation, every counterexample applicant (one row per
    solution) with age, condition profile, coverage band, and the indicator
    flags, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from pandas import set_option as pd_set_option
from relationalai.semantics import Integer, Model
from relationalai.semantics.reasoners.prescriptive import Problem, implies

# Make sure every column of the witness table makes it into the printed
# output; the default pandas display width collapses to "..." when more
# than ~80 chars wide, which would hide the indicator columns the audit
# is supposed to surface.
pd_set_option("display.max_columns", None)
pd_set_option("display.width", 200)

# Runner-level parameters.
# Senior threshold: applicants with bucket age_years >= 70 are flagged
# `is_senior`. Drives both the (correct) `is_frail` and (buggy)
# `is_manual_review` rules.
SENIOR_THRESHOLD_YEARS = 70
# Solver solution-limit: how many distinct counterexample applicants to
# enumerate per audit run. Real audit workflows want a *batch* of
# witnesses showing the failure modes, not a single one. Set above
# the bundled feasible-set size (3 non-senior buckets * 4 coverage
# bands = 12) so the search exhausts and the verdict is `OPTIMAL` --
# this gives the actuary the full failure shape and makes the output
# stable across runs. Lower it (e.g. 4) to demonstrate the
# `SOLUTION_LIMIT` outcome where more witnesses may exist beyond
# the cap; raise it for production rule packs.
MAX_WITNESSES = 16

model = Model("underwriting_audit")

# --------------------------------------------------
# Define semantic model & load reference data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"


# Reference-data contract: integer IDs must be dense and contiguous so the
# solver's `lower=min(id), upper=max(id)` decision bounds line up exactly
# with the reference rows. Sparse IDs would let the solver pick a missing
# value: the relational-time `implies(...) ` ICs gated on the matching
# reference row would never fire, leaving the indicator decisions
# unconstrained for that solution. Validate up front rather than letting
# bad customizations silently degrade audit coverage.
def _assert_dense_ids(df, name):
    ids = sorted(int(v) for v in df["id"].tolist())
    if not ids:
        raise ValueError(
            f"{name} has no rows; at least one row is required to set the "
            "decision-variable bounds (`lower=min(id), upper=max(id)`)."
        )
    expected = list(range(ids[0], ids[-1] + 1))
    if ids != expected:
        raise ValueError(
            f"{name} `id` column must be dense and contiguous; got {ids}. "
            "Renumber the rows or add explicit ID-membership ICs before solving."
        )


# Concept: representative age bucket. Each row maps an integer bucket id
# to a representative age (in years) used to drive the senior indicator.
# Categorical age (rather than per-year integer) keeps the decision
# domain compact and similar in size to coverage band, which is what
# makes the multi-solution enumeration produce structurally varied
# witnesses across age and coverage rather than shifting one year at a
# time.
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
age_buckets_csv = read_csv(data_dir / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))

# Concept: representative coverage band. Used purely as a categorical
# decision dimension so witnesses spread across coverage values; coverage
# does not enter the (buggy) ruleset under audit here, but real
# underwriting rules typically mix it in -- the column is left in place
# so customising the ruleset to include coverage thresholds is a one-IC
# change.
CoverageBand = model.Concept("CoverageBand", identify_by={"id": Integer})
CoverageBand.coverage_dollars = model.Property(f"{CoverageBand} has {Integer:coverage_dollars}")
coverage_bands_csv = read_csv(data_dir / "coverage_bands.csv")
_assert_dense_ids(coverage_bands_csv, "coverage_bands.csv")
model.define(CoverageBand.new(model.data(coverage_bands_csv).to_schema()))

# Concept: synthesised applicant. The CSV holds a single placeholder row;
# every decision-valued property below describes that one slot. Each
# solution returned by the solver is a different feasible filling of
# that slot -- which is what gives us K witness applicants per audit.
Applicant = model.Concept("Applicant", identify_by={"id": Integer})
model.define(Applicant.new(id=1))

# --------------------------------------------------
# Decision-valued properties on Applicant
# --------------------------------------------------

# Free decisions: applicant attributes the audit is allowed to vary.
Applicant.age_bucket_id = model.Property(f"{Applicant} in age bucket {Integer:age_bucket_id}")
Applicant.has_chronic = model.Property(f"{Applicant} has {Integer:has_chronic}")
Applicant.coverage_band_id = model.Property(
    f"{Applicant} in coverage band {Integer:coverage_band_id}"
)

# Derived indicators: defined in terms of the free decisions via
# arithmetic-equivalence ICs below. These are also decision variables
# from the solver's point of view so that the property-entailment IC
# can compare them directly.
Applicant.is_senior = model.Property(f"{Applicant} has {Integer:is_senior}")
Applicant.is_frail = model.Property(f"{Applicant} has {Integer:is_frail}")
Applicant.is_manual_review = model.Property(f"{Applicant} has {Integer:is_manual_review}")

problem = Problem(model, Integer)
# `populate=True` (default) writes the first solution back into the
# `Applicant.*` properties so `problem.verify(...)` can re-evaluate the
# pure-arithmetic ICs against it. Multi-solution output below still goes
# through `Variable.values(solution_index, value)` for every witness.
age_bucket_var = problem.solve_for(
    Applicant.age_bucket_id,
    type="int",
    name=["age_bucket", Applicant.id],
    lower=int(age_buckets_csv["id"].min()),
    upper=int(age_buckets_csv["id"].max()),
)
chronic_var = problem.solve_for(
    Applicant.has_chronic, type="bin", name=["has_chronic", Applicant.id]
)
coverage_band_var = problem.solve_for(
    Applicant.coverage_band_id,
    type="int",
    name=["coverage_band", Applicant.id],
    lower=int(coverage_bands_csv["id"].min()),
    upper=int(coverage_bands_csv["id"].max()),
)
senior_var = problem.solve_for(Applicant.is_senior, type="bin", name=["is_senior", Applicant.id])
frail_var = problem.solve_for(Applicant.is_frail, type="bin", name=["is_frail", Applicant.id])
manual_review_var = problem.solve_for(
    Applicant.is_manual_review,
    type="bin",
    name=["is_manual_review", Applicant.id],
)

# --------------------------------------------------
# Rule definitions (the underwriting ruleset under audit)
# --------------------------------------------------

# Rule: `is_senior` is 1 iff the applicant's age bucket has age >= 70.
# Encoded as a per-bucket iteration over AgeBucket: for each senior
# bucket, if the applicant picks it, is_senior must be 1; for each
# non-senior bucket, if the applicant picks it, is_senior must be 0.
senior_def_pos_ic = model.where(AgeBucket.age_years >= SENIOR_THRESHOLD_YEARS).require(
    implies(Applicant.age_bucket_id == AgeBucket.id, Applicant.is_senior == 1)
)
problem.satisfy(senior_def_pos_ic)
senior_def_neg_ic = model.where(AgeBucket.age_years < SENIOR_THRESHOLD_YEARS).require(
    implies(Applicant.age_bucket_id == AgeBucket.id, Applicant.is_senior == 0)
)
problem.satisfy(senior_def_neg_ic)

# Rule: `is_frail` is 1 iff the applicant is senior OR has a chronic
# condition. Encoded as the standard OR-arithmetic equivalence on
# binaries (`y = a OR b` is `y >= a, y >= b, y <= a + b`). Keep all
# three arms even when one looks redundant under the bundled
# counterexample ICs -- each arm is part of the definition of the OR
# rule, and dropping an arm silently weakens the ruleset against a
# future rule change (the exact silent-pass shape the audit warns
# against). Same applies to the two `is_manual_review` arms below.
frail_lb_senior_ic = model.require(Applicant.is_frail >= Applicant.is_senior)
frail_lb_chronic_ic = model.require(Applicant.is_frail >= Applicant.has_chronic)
frail_ub_ic = model.require(Applicant.is_frail <= Applicant.is_senior + Applicant.has_chronic)
problem.satisfy(frail_lb_senior_ic)
problem.satisfy(frail_lb_chronic_ic)
problem.satisfy(frail_ub_ic)

# Rule (BUGGY): `is_manual_review` is 1 iff the applicant is senior. The
# correct rule should also flag frail applicants (senior OR chronic), but
# this version misses the chronic arm -- which is exactly the bug the
# audit exposes. Encoded as `y = senior` via two arithmetic constraints.
manual_review_eq_lb_ic = model.require(Applicant.is_manual_review >= Applicant.is_senior)
manual_review_eq_ub_ic = model.require(Applicant.is_manual_review <= Applicant.is_senior)
problem.satisfy(manual_review_eq_lb_ic)
problem.satisfy(manual_review_eq_ub_ic)

# --------------------------------------------------
# Property-entailment audit: ask for a counterexample
# --------------------------------------------------

# Property: every frail applicant goes through manual review. Stated as
# a property entailment, that is `is_frail == 1 implies is_manual_review
# == 1`, equivalently `is_frail <= is_manual_review`.
#
# The audit asks for a *counterexample*: a feasible applicant where the
# property fails -- `is_frail == 1` AND `is_manual_review == 0`. Each
# solution the solver returns is one witness. With the buggy rule above,
# the audit succeeds (witnesses exist); under a corrected rule the same
# IC would render the model INFEASIBLE, signalling that the property
# holds.
#
# These ICs are unconditional `model.require(...)` (no `model.where(...)`
# scope) because `Applicant` is a singleton -- there is exactly one row
# in the Applicant table, so the ICs bind to that single decision slot.
# When extending to a fleet of N applicants, scope each IC with
# `model.where(Applicant)` (or a tighter applicant filter), otherwise the
# unconditional require demands that *every* applicant be a counterexample
# rather than finding a single applicant that is.
counterexample_frail_ic = model.require(Applicant.is_frail == 1)
counterexample_no_review_ic = model.require(Applicant.is_manual_review == 0)
problem.satisfy(counterexample_frail_ic)
problem.satisfy(counterexample_no_review_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
# `solution_limit=MAX_WITNESSES` asks the solver to enumerate up to that
# many distinct witnesses; query each one via `Variable.values(idx, val)`.
# Without it, MiniZinc returns just the first witness and stops.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)
si = problem.solve_info()
si.display()

# Re-check the relational arithmetic ICs in the returned solution. The
# senior-definition ICs (`senior_def_pos_ic`, `senior_def_neg_ic`) are
# `implies`-bodied and solver-only; pass only the pure-arithmetic ICs
# to `verify()`. The OR-arithmetic constraints on `is_frail` and the
# equality constraints on `is_manual_review` ARE pure relational
# arithmetic and round-trip cleanly. `verify()` only re-evaluates the
# first returned solution, so it is a per-solution spot-check on the
# arithmetic ICs -- not a re-proof across every witness or every IC.
problem.verify(
    frail_lb_senior_ic,
    frail_lb_chronic_ic,
    frail_ub_ic,
    manual_review_eq_lb_ic,
    manual_review_eq_ub_ic,
    counterexample_frail_ic,
    counterexample_no_review_ic,
)

# --------------------------------------------------
# Audit verdict
# --------------------------------------------------

# Three outcomes for the audit:
# - INFEASIBLE: the solver proved no feasible counterexample exists, so the
#   property HOLDS under the encoded ruleset. This is the audit's pass
#   signal -- expected after a rule fix lands. Soundness is bounded by
#   encoding fidelity: missing rule arms can produce a silent pass.
# - OPTIMAL or SOLUTION_LIMIT with num_points >= 1: at least one feasible
#   counterexample applicant exists, so the property does NOT hold. Each
#   witness is a concrete failure mode for triage.
# - Anything else (TIME_LIMIT, error, num_points == 0 without INFEASIBLE):
#   inconclusive -- the audit did not finish. Surface explicitly rather
#   than treating it as a pass.
status = si.termination_status
if status == "INFEASIBLE":
    print(
        "\nAudit result: PASS -- proven no counterexample applicants exist. "
        "The property holds under the encoded ruleset."
    )
elif si.num_points is not None and si.num_points >= 1:
    print(
        f"\nAudit result: FAIL (ruleset has counterexamples) -- "
        f"{si.num_points} counterexample applicant(s) found (status: {status}). "
        "Each witness disproves the property under the encoded ruleset; "
        "witnesses below."
    )
else:
    n = si.num_points if si.num_points is not None else "(unavailable)"
    print(
        f"\nAudit result: INCONCLUSIVE -- solver returned status={status} "
        f"with num_points={n}. The audit did not finish and no witness was "
        "returned. Raise `time_limit_sec`, narrow the search, or inspect the formulation."
    )

# --------------------------------------------------
# Inspect every counterexample witness
# --------------------------------------------------

# `Variable.values(solution_index, value)` indexes the solver's outputs
# across every returned solution. Binding the value slot directly to a
# reference Concept's `.id` walks the chosen ID back to that row's columns
# in one step; for the binary indicators an Integer placeholder receives
# the 0/1 value for display.
#
# Skipped on the PASS path: `INFEASIBLE` means there are no witnesses to
# enumerate, so printing the header would dangle under a clean PASS line.

if si.num_points is not None and si.num_points >= 1:
    print(f"\nCounterexample witnesses (up to {MAX_WITNESSES} per run):")
    sol_idx = Integer.ref()
    chr_v = Integer.ref()
    sen_v = Integer.ref()
    frl_v = Integer.ref()
    mr_v = Integer.ref()
    model.select(
        sol_idx.alias("solution"),
        AgeBucket.age_years.alias("age_years"),
        chr_v.alias("has_chronic"),
        CoverageBand.coverage_dollars.alias("coverage_dollars"),
        sen_v.alias("is_senior"),
        frl_v.alias("is_frail"),
        mr_v.alias("is_manual_review"),
    ).where(
        age_bucket_var.values(sol_idx, AgeBucket.id),
        chronic_var.values(sol_idx, chr_v),
        coverage_band_var.values(sol_idx, CoverageBand.id),
        senior_var.values(sol_idx, sen_v),
        frail_var.values(sol_idx, frl_v),
        manual_review_var.values(sol_idx, mr_v),
    ).inspect()
