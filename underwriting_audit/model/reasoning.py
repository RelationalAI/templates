"""Underwriting rule pack and property audits: one counterexample search per catalog property."""

from relationalai.semantics import Integer, String
from relationalai.semantics.reasoners.prescriptive import Problem, implies

from .schema import AgeBucket, CoverageBand, model
from .source import age_buckets_csv, coverage_bands_csv

# --------------------------------------------------
# Parameters
# --------------------------------------------------

# Senior threshold: applicants with bucket age_years >= 70 are flagged
# `is_senior`. Drives both the (correct) `is_frail` and (buggy)
# `is_manual_review` rules.
SENIOR_THRESHOLD_YEARS = 70
# `chronic_under_50_implies_review` scopes its counterexample to age
# buckets under this threshold. The bundled CSV has two buckets under 50
# (28 and 45), so the property's witness set is 2 buckets * 4 coverage
# bands = 8 -- a strict subset of `frail_implies_review`'s 12.
UNDER_50_THRESHOLD_YEARS = 50
# Solver solution-limit: how many distinct counterexample applicants to
# enumerate per audit run. Real audit workflows want a *batch* of
# witnesses showing the failure modes, not a single one. Set above the
# bundled per-property feasible-set sizes (8 and 12) so the search
# exhausts and the verdict is `OPTIMAL` -- this gives the actuary the
# full failure shape and makes the output stable across runs. Lower it
# (e.g. 4) to demonstrate the `SOLUTION_LIMIT` outcome where more
# witnesses may exist beyond the cap; raise it for production rule packs.
MAX_WITNESSES = 16

# --------------------------------------------------
# Scalar decisions and the rule pack
# --------------------------------------------------

# Free decisions: applicant attributes the audit is allowed to
# vary. Each is a scalar `model.Relationship` (one Integer slot) --
# the unparented scalar shape. No singleton Applicant concept is
# required because there is exactly one applicant slot; the solver
# picks values for these scalars on every solution. To extend to a
# fleet of N applicants, reintroduce
# an `Applicant` concept and lift each scalar to a
# `model.Property(f"{Applicant} has {Integer:foo}")`, then scope
# every IC below (including each property's counterexample ICs)
# with `model.where(Applicant)` (or a tighter filter).
age_bucket_id = model.Relationship(f"{Integer:age_bucket_id}")
has_chronic = model.Relationship(f"{Integer:has_chronic}")
coverage_band_id = model.Relationship(f"{Integer:coverage_band_id}")

# Derived indicators: defined in terms of the free decisions via
# arithmetic-equivalence ICs below. These are also decision
# variables from the solver's point of view so that the
# property-entailment IC can compare them directly.
is_senior = model.Relationship(f"{Integer:is_senior}")
is_frail = model.Relationship(f"{Integer:is_frail}")
is_manual_review = model.Relationship(f"{Integer:is_manual_review}")

# Rule: `is_senior` is 1 iff the applicant's age bucket has age >= 70.
# Encoded as a per-bucket iteration over AgeBucket: for each senior
# bucket, if the applicant picks it, is_senior must be 1; for each
# non-senior bucket, if the applicant picks it, is_senior must be 0.
senior_def_pos_ic = model.where(AgeBucket.age_years >= SENIOR_THRESHOLD_YEARS).require(
    implies(age_bucket_id == AgeBucket.id, is_senior == 1)
)
senior_def_neg_ic = model.where(AgeBucket.age_years < SENIOR_THRESHOLD_YEARS).require(
    implies(age_bucket_id == AgeBucket.id, is_senior == 0)
)

# Rule: `is_frail` is 1 iff the applicant is senior OR has a chronic
# condition. Encoded as the standard OR-arithmetic equivalence on
# binaries (`y = a OR b` is `y >= a, y >= b, y <= a + b`) -- a
# single `==` constraint won't do here because `is_senior +
# has_chronic` can be 2 but `is_frail` is binary. Keep all three
# arms even when one looks redundant under the bundled
# counterexample ICs -- each arm is part of the definition of the
# OR rule, and dropping an arm silently weakens the ruleset against
# a future rule change (the exact silent-pass shape the audit warns
# against).
frail_lb_senior_ic = model.require(is_frail >= is_senior)
frail_lb_chronic_ic = model.require(is_frail >= has_chronic)
frail_ub_ic = model.require(is_frail <= is_senior + has_chronic)

# Rule (BUGGY): `is_manual_review` is 1 iff the applicant is
# senior. The correct rule should also flag frail applicants
# (senior OR chronic), but this version misses the chronic arm --
# which is exactly the bug the audit exposes. Encoded as a single
# equality constraint.
manual_review_eq_ic = model.require(is_manual_review == is_senior)

rule_pack = [
    senior_def_pos_ic,
    senior_def_neg_ic,
    frail_lb_senior_ic,
    frail_lb_chronic_ic,
    frail_ub_ic,
    manual_review_eq_ic,
]

# --------------------------------------------------
# Property catalog (the spec the rule pack must satisfy)
# --------------------------------------------------

# Each entry is `(name, description, counterexample_builder)`. The
# builder takes no arguments and returns the property's counterexample
# ICs. The counterexample for a property `P` is the *negation* of `P`:
# if the solver finds a feasible assignment satisfying the
# counterexample, `P` does not hold.
#
# Counterexample ICs are unconditional `model.require(...)` (no
# `model.where(...)` scope) when they bind a single scalar slot to a
# value. Scoped counterexamples (e.g. "force the selected age bucket to
# have age < 50") use a `model.where(...)` clause to restrict the
# search to the property's sub-population.
#
# The bundled catalog mixes verdicts and witness shapes:
# - `frail_implies_review` -- broad FAIL, 12 chronic-non-senior witnesses
#   covering every (age_under_70 * coverage_band) cell. The canonical
#   bug surfacing.
# - `chronic_under_50_implies_review` -- scoped FAIL, 8 witnesses (a
#   strict subset of #1's witnesses). Demonstrates property scoping:
#   the counterexample restricts the search to chronic applicants
#   below the under-50 threshold via a `where`-bound IC.
# - `senior_implies_review` -- PASS (INFEASIBLE). The buggy rule
#   literally encodes "manual_review = senior", so the negation (a
#   senior who skips manual review) is unsatisfiable.
#
# Add a property by appending one tuple; the audit loop below picks it up
# automatically.
PROPERTIES = [
    (
        "frail_implies_review",
        "every frail applicant goes through manual review",
        lambda: [
            model.require(is_frail == 1),
            model.require(is_manual_review == 0),
        ],
    ),
    (
        "chronic_under_50_implies_review",
        (
            f"every chronic applicant under age {UNDER_50_THRESHOLD_YEARS} "
            "goes through manual review"
        ),
        lambda: [
            model.require(has_chronic == 1),
            model.require(is_manual_review == 0),
            # Scope: forbid the selected age bucket from being any
            # bucket with age_years >= UNDER_50_THRESHOLD_YEARS. The
            # where-clause is a pure data filter (no decision variable);
            # for each matching AgeBucket row the require body adds one
            # constraint pinning the scalar decision away from that
            # row's id. PyRel rejects decision-variable expressions
            # inside `where`, so the data-filter has to live in `where`
            # and the decision constraint in `require`.
            model.where(AgeBucket.age_years >= UNDER_50_THRESHOLD_YEARS).require(
                age_bucket_id != AgeBucket.id
            ),
        ],
    ),
    (
        "senior_implies_review",
        "every senior applicant goes through manual review",
        lambda: [
            model.require(is_senior == 1),
            model.require(is_manual_review == 0),
        ],
    ),
]

# --------------------------------------------------
# One audit Problem per property
# --------------------------------------------------

# Each property gets its own Problem: constraints on a `Problem` are add-only, so a
# previous property's counterexample ICs cannot be detached from a reused `Problem`.
# Each Problem's status, number of witnesses, and witnesses are keyed by the property name.
SolveStatus = {}
NumPoints = {}
Witness = {}

for name, description, counterexample_fn in PROPERTIES:
    problem_name = f"underwriting_audit_{name}"
    problem = Problem(model, Integer, name=problem_name)

    # `populate=False` skips the first-solution write-back to the scalar
    # relationships, which every audit Problem shares; every witness is read through
    # `Variable.values(...)`, published below as the property's `Witness` relationship, so
    # the populated state is unused, and `populate=False` sidesteps the latent FDError
    # under `solution_limit`.
    age_bucket_var = problem.solve_for(
        age_bucket_id,
        type="int",
        name="age_bucket",
        lower=int(age_buckets_csv["id"].min()),
        upper=int(age_buckets_csv["id"].max()),
        populate=False,
    )
    chronic_var = problem.solve_for(has_chronic, type="bin", name="has_chronic", populate=False)
    coverage_band_var = problem.solve_for(
        coverage_band_id,
        type="int",
        name="coverage_band",
        lower=int(coverage_bands_csv["id"].min()),
        upper=int(coverage_bands_csv["id"].max()),
        populate=False,
    )
    senior_var = problem.solve_for(is_senior, type="bin", name="is_senior", populate=False)
    frail_var = problem.solve_for(is_frail, type="bin", name="is_frail", populate=False)
    manual_review_var = problem.solve_for(
        is_manual_review, type="bin", name="is_manual_review", populate=False
    )

    for rule_ic in rule_pack:
        problem.satisfy(rule_ic)
    for counterexample_ic in counterexample_fn():
        problem.satisfy(counterexample_ic)

    # Each refresh of the deployed model runs this solve.
    # `solution_limit=MAX_WITNESSES` asks the solver to enumerate up to
    # that many distinct witnesses; without it, MiniZinc returns just
    # the first witness and stops.
    problem.configure("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)

    # The solve's status and number of witnesses, which the deployed model publishes for the queries.
    SolveStatus[name] = model.Relationship(f"{problem_name} solve status is {String:status}")
    NumPoints[name] = model.Relationship(f"{problem_name} number of solutions is {Integer:count}")
    model.define(
        SolveStatus[name](problem.termination_status()),
        NumPoints[name](problem.num_points()),
    )

    # The witnesses, which the deployed model publishes for the queries: for each solution
    # index, the age bucket and coverage band the solver chose and the 0/1 value of each
    # flag. Binding the value slot to a reference Concept's `id` walks the chosen id back
    # to that row's columns in one step; for binary indicators an Integer placeholder
    # receives the 0/1 value.
    Witness[name] = model.Relationship(
        f"{problem_name} witness {Integer:solution} has {AgeBucket} chronic {Integer:has_chronic} "
        f"{CoverageBand} senior {Integer:is_senior} frail {Integer:is_frail} "
        f"manual review {Integer:is_manual_review}"
    )
    sol_idx, chr_v, sen_v, frl_v, mr_v = (Integer.ref() for _ in range(5))
    model.where(
        age_bucket_var.values(sol_idx, AgeBucket.id),
        chronic_var.values(sol_idx, chr_v),
        coverage_band_var.values(sol_idx, CoverageBand.id),
        senior_var.values(sol_idx, sen_v),
        frail_var.values(sol_idx, frl_v),
        manual_review_var.values(sol_idx, mr_v),
    ).define(Witness[name](sol_idx, AgeBucket, chr_v, CoverageBand, sen_v, frl_v, mr_v))
