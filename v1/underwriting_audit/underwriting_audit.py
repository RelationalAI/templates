"""Underwriting Audit (multi-property batch, multi-solution witnesses) template.

This script demonstrates property-entailment audit as a *batch* operation: a
single rule pack is checked against a catalog of separately-authored
properties, with one verdict (PASS / FAIL / INCONCLUSIVE) emitted per
property and witnesses enumerated per FAIL. This is the shape a real
audit takes -- compliance teams author a property catalog, the rule team
authors the rules, and the solver mediates between them. Bundling them
in one script means a single run surfaces the full audit report.

Modeling shape:

- Define the ruleset as scalar binary indicators (`is_senior`, `is_frail`,
  `is_manual_review`), each tied to the applicant-shaped free decisions
  (`age_bucket_id`, `has_chronic`, `coverage_band_id`) via OR-arithmetic
  equivalences. The applicant is a *shape* in the decisions, not an
  Applicant concept: with a single slot, scalar `model.Relationship`s
  match the prescriptive `rosenbrock` example pattern and avoid the
  identity overhead of a one-row concept.
- Author a `PROPERTIES` catalog -- a list of named properties, each with
  a thunk that constructs the property's counterexample ICs. The
  counterexample for a property `P` is the negation of `P`: if the
  solver finds a feasible assignment satisfying the counterexample, the
  property does not hold.
- Audit loop: for each property, build a *fresh* `Problem`, wire in
  every rule IC and the property's counterexample ICs, solve with
  `solution_limit=K` (MiniZinc), classify the verdict, and (for FAILs)
  enumerate every distinct witness via `Variable.values(solution_index,
  value)`. A fresh Problem per property is mandatory because constraints
  on a Problem are add-only -- you cannot remove a previous property's
  counterexample ICs from a reused Problem.

The bundled ruleset has a deliberate bug: `is_manual_review` is defined as
"senior", but `is_frail` is defined as "senior OR has chronic condition".
Two of the three bundled properties (frail-implies-review and
chronic-implies-review) FAIL with chronic non-senior witnesses; the
third (senior-implies-review) PASSes because the buggy rule literally
encodes it. The mixed verdicts in one run are the demo -- the audit
isn't rigged to always fail; it actually distinguishes properties the
ruleset satisfies from those it violates.

Run:
    `python underwriting_audit.py`

Output:
    Per property: the verdict line and (for FAILs) the witness table. At
    the end: a verdict-matrix recap covering every property in the catalog.
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

DATA_DIR = Path(__file__).parent / "data"


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
age_buckets_csv = read_csv(DATA_DIR / "age_buckets.csv")
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
coverage_bands_csv = read_csv(DATA_DIR / "coverage_bands.csv")
_assert_dense_ids(coverage_bands_csv, "coverage_bands.csv")
model.define(CoverageBand.new(model.data(coverage_bands_csv).to_schema()))

# --------------------------------------------------
# Scalar decision variables (the applicant shape)
# --------------------------------------------------

# Free decisions: applicant attributes the audit is allowed to vary.
# Each is a scalar `model.Relationship` (one Integer slot), mirroring the
# `rosenbrock` prescriptive example. No singleton Applicant concept is
# required because there is exactly one applicant slot; the solver picks
# values for these scalars on every solution. To extend to a fleet of N
# applicants, reintroduce an `Applicant` concept and lift each scalar to
# a `model.Property(f"{Applicant} has {Integer:foo}")`, then scope every
# IC below with `model.where(Applicant)` (or a tighter filter).
age_bucket_id = model.Relationship(f"{Integer:age_bucket_id}")
has_chronic = model.Relationship(f"{Integer:has_chronic}")
coverage_band_id = model.Relationship(f"{Integer:coverage_band_id}")

# Derived indicators: defined in terms of the free decisions via
# arithmetic-equivalence ICs below. These are also decision variables
# from the solver's point of view so that the property-entailment IC
# can compare them directly.
is_senior = model.Relationship(f"{Integer:is_senior}")
is_frail = model.Relationship(f"{Integer:is_frail}")
is_manual_review = model.Relationship(f"{Integer:is_manual_review}")

# --------------------------------------------------
# Rule pack (the underwriting ruleset under audit)
# --------------------------------------------------

# Every rule below is registered on the model via `model.require(...)`.
# It is NOT wired into a Problem here -- the per-property audit loop
# constructs a fresh Problem per property and calls `problem.satisfy(...)`
# for each rule IC. Constraints on a Problem are add-only, so reusing a
# single Problem across properties would mean each property's
# counterexample ICs would accumulate on top of the previous property's,
# which is wrong.

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
# binaries (`y = a OR b` is `y >= a, y >= b, y <= a + b`) -- a single
# `==` constraint won't do here because `is_senior + has_chronic` can
# be 2 but `is_frail` is binary. Keep all three arms even when one
# looks redundant under the bundled counterexample ICs -- each arm is
# part of the definition of the OR rule, and dropping an arm silently
# weakens the ruleset against a future rule change (the exact
# silent-pass shape the audit warns against).
frail_lb_senior_ic = model.require(is_frail >= is_senior)
frail_lb_chronic_ic = model.require(is_frail >= has_chronic)
frail_ub_ic = model.require(is_frail <= is_senior + has_chronic)

# Rule (BUGGY): `is_manual_review` is 1 iff the applicant is senior. The
# correct rule should also flag frail applicants (senior OR chronic), but
# this version misses the chronic arm -- which is exactly the bug the
# audit exposes. Encoded as a single equality constraint.
manual_review_eq_ic = model.require(is_manual_review == is_senior)

# The full rule pack: every IC the audit must enforce as part of "the
# ruleset under test". Used by the audit loop below to wire all rule ICs
# into each property's Problem in one pass.
RULE_PACK_ICS = [
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

# Each entry is `(name, description, counterexample_builder)`. The builder
# is a thunk that constructs the property's counterexample ICs *on demand*
# -- the audit loop calls it once per iteration so the IC handles it
# returns are exactly the ICs to wire into that property's Problem via
# `problem.satisfy(...)`. The negation-of-property pattern is the heart
# of the audit: if the solver finds a feasible assignment satisfying the
# counterexample, the property does NOT hold under the rule pack.
#
# Accumulation note: `model.require(...)` registers the IC on the model.
# ICs from previous iterations stay registered (the model is a
# declaration store, not an enforcer), but they do not affect subsequent
# solves because the solver only enforces what `problem.satisfy(...)`
# wires in. As long as no model-level `verify(...)` is run over the
# union, the accumulation is inert.
#
# Counterexample ICs are unconditional `model.require(...)` (no
# `model.where(...)` scope) because each decision is a single scalar
# slot, so the IC binds to that single value. When extending to a fleet
# of N applicants (lifting the scalars to `Applicant.foo` properties),
# scope each counterexample IC with `model.where(Applicant)` (or a
# tighter filter): the unconditional require would otherwise demand
# that *every* applicant be a counterexample rather than finding a
# single applicant that is.
#
# The bundled catalog is intentionally mixed-verdict to demonstrate that
# the audit distinguishes. The buggy rule (`is_manual_review = is_senior`)
# FAILs the frail- and chronic-driven properties (witnesses are chronic
# non-seniors) but trivially PASSes the senior-driven property (the rule
# literally encodes it). Adding a property to the catalog is a one-tuple
# append; no other code needs to change.
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
        "chronic_implies_review",
        "every chronic-condition applicant goes through manual review",
        lambda: [
            model.require(has_chronic == 1),
            model.require(is_manual_review == 0),
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


def _classify_verdict(si):
    """Map solver termination + witness count to an audit verdict.

    - INFEASIBLE -> PASS: solver proved no counterexample exists, so the
      property holds under the encoded rule pack. Soundness is bounded
      by encoding fidelity: missing rule arms can produce a silent pass.
    - OPTIMAL or SOLUTION_LIMIT with num_points >= 1 -> FAIL: at least
      one counterexample exists, so the property does not hold. Each
      witness is a concrete failure mode for triage.
    - Anything else -> INCONCLUSIVE: the audit did not finish. Surface
      explicitly rather than treating it as a pass.
    """
    if si.termination_status == "INFEASIBLE":
        return "PASS"
    if si.num_points is not None and si.num_points >= 1:
        return "FAIL"
    return "INCONCLUSIVE"


# --------------------------------------------------
# Audit loop (fresh Problem per property)
# --------------------------------------------------

# Each iteration builds a fresh Problem, wires in the full rule pack and
# the property's counterexample ICs, and solves. A fresh Problem is
# mandatory because constraints on a Problem are add-only -- there is no
# API to remove the previous property's counterexample ICs from a reused
# Problem. `populate=False` skips the first-solution write-back to the
# scalar relationships; every witness is read through `Variable.values(...)`
# below so the populated state is unused, and `populate=False` also
# sidesteps the latent FDError under `solution_limit`. (`verify()` is
# dropped from the loop for the same reason -- it requires populated
# values, and the per-iteration spot-check would add noise without
# adding signal in a batch audit.)

results = []
for prop_idx, (name, description, counterexample_fn) in enumerate(PROPERTIES):
    print(f"\n===== Auditing property {prop_idx + 1}/{len(PROPERTIES)}: {name} =====")
    print(f"Description: {description}")

    problem = Problem(model, Integer)
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

    for rule_ic in RULE_PACK_ICS:
        problem.satisfy(rule_ic)
    for counterexample_ic in counterexample_fn():
        problem.satisfy(counterexample_ic)

    # Display the formulation only on the first iteration. The rule-pack
    # ICs are identical across properties; only the counterexample IC
    # pair differs (and is visible in the property name and verdict
    # below), so repeating the full display would add noise.
    if prop_idx == 0:
        problem.display()

    # `solution_limit=MAX_WITNESSES` asks the solver to enumerate up to
    # that many distinct witnesses; without it, MiniZinc returns just
    # the first witness and stops.
    problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)
    si = problem.solve_info()
    verdict = _classify_verdict(si)
    n_witnesses = si.num_points if si.num_points is not None else 0
    print(f"Verdict: {verdict}  ({n_witnesses} witness(es), status={si.termination_status})")

    # Per-FAIL witness table -- inline so we read each property's
    # variables while its Problem is still the most recent solve.
    # `Variable.values(sol_idx, value)` indexes the solver's outputs
    # across every returned solution; binding the value slot to a
    # reference Concept's `.id` walks the chosen ID back to that row's
    # columns in one step. For binary indicators an Integer placeholder
    # receives the 0/1 value for display.
    if verdict == "FAIL":
        print(f"\nWitnesses (up to {MAX_WITNESSES} per run):")
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

    results.append(
        {
            "name": name,
            "description": description,
            "verdict": verdict,
            "num_witnesses": n_witnesses,
            "status": si.termination_status,
        }
    )

# --------------------------------------------------
# Audit report (verdict matrix across the catalog)
# --------------------------------------------------

# The verdict matrix is the audit's headline deliverable: one line per
# property, grouped by outcome. The PASS-and-FAIL mix in a single run is
# the demo -- the audit isn't rigged to always fail; it distinguishes
# properties the ruleset satisfies from those it violates. Cross-
# referencing FAIL witness tables for shared decision values (e.g. all
# witnesses with `has_chronic=1`) usually surfaces the common root cause.
fail_count = sum(1 for r in results if r["verdict"] == "FAIL")
pass_count = sum(1 for r in results if r["verdict"] == "PASS")
incon_count = sum(1 for r in results if r["verdict"] == "INCONCLUSIVE")
print("\n" + "=" * 80)
print(
    f"Audit report ({len(results)} properties: "
    f"{pass_count} PASS, {fail_count} FAIL, {incon_count} INCONCLUSIVE)"
)
print("=" * 80)
print(f"  {'Property':<26} {'Verdict':<14} {'Witnesses':>10}  Description")
print("  " + "-" * 78)
for r in results:
    print(f"  {r['name']:<26} {r['verdict']:<14} {r['num_witnesses']:>10}  {r['description']}")
