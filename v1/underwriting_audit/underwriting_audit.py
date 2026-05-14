"""Underwriting Audit (multi-property batch, multi-solution witnesses) template.

This script demonstrates property-entailment audit as a *batch* operation: a
single rule pack is checked against a catalog of separately-authored
properties, with one verdict (PASS / FAIL / INCONCLUSIVE) emitted per
property and witnesses enumerated per FAIL. This is the shape a real
audit takes -- compliance teams author a property catalog, the rule team
authors the rules, and the solver mediates between them. Bundling them
in one script means a single run surfaces the full audit report.

Modeling shape:

- Two reference concepts (`AgeBucket`, `CoverageBand`) and three scalar
  free decisions (`age_bucket_id`, `has_chronic`, `coverage_band_id`).
  `age_bucket_id` and `has_chronic` drive the indicator rules below;
  `coverage_band_id` enters no rule IC and is a *spread-only* decision
  dimension whose role is to diversify witness output across coverage
  bands (real underwriting rules typically mix coverage in, so the
  column is left in place for customisation). The applicant is a *shape*
  in the scalar decisions, not an `Applicant` concept: with a single
  slot, scalar `model.Relationship`s avoid the identity overhead of a
  one-row concept.
- Three derived binary indicators (`is_senior`, `is_frail`,
  `is_manual_review`), each declared as a scalar `model.Relationship`
  and pinned to functions of the free decisions by solver-side ICs.
  Treating the indicators as decisions (rather than relational-time
  predicates) lets the property-entailment IC compare them directly.
- Author a `PROPERTIES` catalog -- a list of named properties, each with
  a counterexample builder that, given a fresh audit session, returns
  the property's counterexample ICs. The counterexample for a property
  `P` is the negation of `P`: if the solver finds a feasible assignment
  satisfying the counterexample, the property does not hold.
- `run_audit(...)` builds a *fresh* Model per audit session (rule pack,
  concepts, scalar decisions, Problem, all rebuilt from scratch), wires
  in the rule pack and the property's counterexample ICs, solves with
  `solution_limit=K` (MiniZinc), classifies the verdict, and (for FAILs)
  enumerates every distinct witness via `Variable.values(solution_index,
  value)`. Fresh Models per audit are required for two reasons: (1)
  constraints on a `Problem` are add-only, so a previous property's
  counterexample ICs cannot be detached from a reused `Problem`;
  (2) PyRel emits a `"Rules created in a loop"` warning when the
  per-Model internal-rule count crosses a fixed threshold, which a
  shared Model would trip after a few iterations.

The bundled ruleset has a deliberate bug: `is_manual_review` is defined as
"senior", but `is_frail` is defined as "senior OR has chronic condition".
The bundled property catalog mixes verdicts and witness shapes:
`frail_implies_review` FAILs broadly (12 chronic-non-senior witnesses);
`chronic_under_50_implies_review` FAILs on a scoped sub-population (8
chronic-applicants-under-50 witnesses -- a strict subset, illustrating
property scoping); `senior_implies_review` PASSes because the buggy rule
literally encodes it. The mixed verdicts in one run are the demo -- the
audit isn't rigged to always fail; it actually distinguishes properties
the ruleset satisfies from those it violates.

Run:
    `python underwriting_audit.py`

Output:
    Per property: the verdict line and (for FAILs) the witness table. At
    the end: a verdict-matrix recap covering every property in the catalog.
"""

from pathlib import Path
from types import SimpleNamespace

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

# --------------------------------------------------
# Runner-level parameters
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

DATA_DIR = Path(__file__).parent / "data"


# --------------------------------------------------
# Reference data (loaded once; the same DataFrames feed every audit
# session below)
# --------------------------------------------------


# Reference-data contract: integer `id` columns must be dense and
# contiguous so the solver's `lower=min(id), upper=max(id)` decision
# bounds line up exactly with the reference rows. Sparse IDs would let
# the solver pick a missing value: the relational-time `implies(...)`
# ICs gated on the matching reference row would never fire, leaving the
# indicator decisions unconstrained for that solution.
def _assert_dense_ids(df, name):
    ids = sorted(int(v) for v in df["id"].tolist())
    if not ids:
        raise ValueError(f"{name} has no rows; at least one reference row is required.")
    expected = list(range(ids[0], ids[-1] + 1))
    if ids != expected:
        missing = sorted(set(expected) - set(ids))
        raise ValueError(
            f"{name} `id` column must be dense and contiguous integers; "
            f"missing ids {missing} between {ids[0]} and {ids[-1]}."
        )


age_buckets_csv = read_csv(DATA_DIR / "age_buckets.csv")
_assert_dense_ids(age_buckets_csv, "age_buckets.csv")
coverage_bands_csv = read_csv(DATA_DIR / "coverage_bands.csv")
_assert_dense_ids(coverage_bands_csv, "coverage_bands.csv")


# --------------------------------------------------
# Audit session builder (one fresh Model per call)
# --------------------------------------------------


def _build_session():
    """Build a fresh Model with concepts, scalar decisions, and the rule pack.

    Returns a `SimpleNamespace` exposing every artifact the audit needs:
    `model`, the two reference concepts, the six scalar decisions, and
    `rule_pack` (the list of rule IC handles).

    A fresh Model per audit keeps the per-audit internal-rule count low
    enough to stay clear of PyRel's `"Rules created in a loop"` warning;
    a shared Model accumulates rules across iterations and trips the
    warning after a few audits. The build is cheap -- concepts and rule
    ICs are just Python objects on the Model -- and the costly work is
    the solve below.
    """
    model = Model("underwriting_audit")

    # Concept: representative age bucket. Each row maps an integer
    # bucket id to a representative age (in years) used to drive the
    # senior indicator. Categorical age (rather than per-year integer)
    # keeps the decision domain compact and similar in size to coverage
    # band, which is what makes the multi-solution enumeration produce
    # structurally varied witnesses across age and coverage rather than
    # shifting one year at a time.
    AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
    AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
    model.define(AgeBucket.new(model.data(age_buckets_csv).to_schema()))

    # Concept: representative coverage band. Used purely as a
    # categorical decision dimension so witnesses spread across coverage
    # values; coverage does not enter the (buggy) ruleset under audit
    # here, but real underwriting rules typically mix it in -- the
    # column is left in place so customising the ruleset to include
    # coverage thresholds is a one-IC change.
    CoverageBand = model.Concept("CoverageBand", identify_by={"id": Integer})
    CoverageBand.coverage_dollars = model.Property(f"{CoverageBand} has {Integer:coverage_dollars}")
    model.define(CoverageBand.new(model.data(coverage_bands_csv).to_schema()))

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

    return SimpleNamespace(
        model=model,
        AgeBucket=AgeBucket,
        CoverageBand=CoverageBand,
        age_bucket_id=age_bucket_id,
        has_chronic=has_chronic,
        coverage_band_id=coverage_band_id,
        is_senior=is_senior,
        is_frail=is_frail,
        is_manual_review=is_manual_review,
        rule_pack=rule_pack,
    )


# --------------------------------------------------
# Property catalog (the spec the rule pack must satisfy)
# --------------------------------------------------

# Each entry is `(name, description, counterexample_builder)`. The
# builder takes the audit session (`s` -- the `SimpleNamespace`
# returned by `_build_session()`) and returns the property's
# counterexample ICs. The counterexample for a property `P` is the
# *negation* of `P`: if the solver finds a feasible assignment
# satisfying the counterexample, `P` does not hold.
#
# The builder is invoked per audit so the IC handles it returns are
# tied to the freshly-built model (each audit gets its own Model).
#
# Counterexample ICs are unconditional `s.model.require(...)` (no
# `s.model.where(...)` scope) when they bind a single scalar slot to a
# value. Scoped counterexamples (e.g. "force the selected age bucket to
# have age < 50") use a `s.model.where(...)` clause to restrict the
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
# Add a property by appending one tuple; the audit loop picks it up
# automatically.
PROPERTIES = [
    (
        "frail_implies_review",
        "every frail applicant goes through manual review",
        lambda s: [
            s.model.require(s.is_frail == 1),
            s.model.require(s.is_manual_review == 0),
        ],
    ),
    (
        "chronic_under_50_implies_review",
        (
            f"every chronic applicant under age {UNDER_50_THRESHOLD_YEARS} "
            "goes through manual review"
        ),
        lambda s: [
            s.model.require(s.has_chronic == 1),
            s.model.require(s.is_manual_review == 0),
            # Scope: forbid the selected age bucket from being any
            # bucket with age_years >= UNDER_50_THRESHOLD_YEARS. The
            # where-clause is a pure data filter (no decision variable);
            # for each matching AgeBucket row the require body adds one
            # constraint pinning the scalar decision away from that
            # row's id. PyRel rejects decision-variable expressions
            # inside `where`, so the data-filter has to live in `where`
            # and the decision constraint in `require`.
            s.model.where(s.AgeBucket.age_years >= UNDER_50_THRESHOLD_YEARS).require(
                s.age_bucket_id != s.AgeBucket.id
            ),
        ],
    ),
    (
        "senior_implies_review",
        "every senior applicant goes through manual review",
        lambda s: [
            s.model.require(s.is_senior == 1),
            s.model.require(s.is_manual_review == 0),
        ],
    ),
]


# --------------------------------------------------
# Audit infrastructure
# --------------------------------------------------


def _classify_verdict(si):
    """Map solver termination + witness count to an audit verdict.

    - Any status with num_points >= 1 -> FAIL: a counterexample exists,
      which falsifies the property regardless of whether the search was
      exhaustive. The witness count is partial when status is not
      OPTIMAL/SOLUTION_LIMIT, but the verdict itself is conclusive.
    - INFEASIBLE, or OPTIMAL with zero witnesses -> PASS: solver proved
      no counterexample exists (or exhausted the search and found none),
      so the property holds under the encoded rule pack. Soundness is
      bounded by encoding fidelity: missing rule arms can produce a
      silent pass. Local-only statuses (e.g. LOCALLY_SOLVED from an LP
      solver) do not count as exhaustion and route to INCONCLUSIVE
      below.
    - Anything else (TIME_LIMIT, MEMORY_LIMIT, OTHER_ERROR, ... with
      zero witnesses) -> INCONCLUSIVE: the audit did not finish and no
      witness was found, so neither pass nor fail can be concluded.
    """
    n = si.num_points if si.num_points is not None else 0
    if n >= 1:
        return "FAIL"
    if si.termination_status in ("INFEASIBLE", "OPTIMAL"):
        return "PASS"
    return "INCONCLUSIVE"


def run_audit(name, description, counterexample_fn, show_formulation):
    """Run one property audit against a fresh Model + Problem.

    Builds a fresh audit session (concepts, scalar decisions, rule
    pack), attaches the rule pack and the property's counterexample
    ICs to a new Problem, and solves in multi-solution mode. Prints
    the verdict line and (on FAIL) the witness table. Returns a result
    dict for the verdict-matrix recap.

    `populate=False` skips the first-solution write-back to the scalar
    relationships; every witness is read through `Variable.values(...)`
    below, so the populated state is unused, and `populate=False`
    sidesteps the latent FDError under `solution_limit`. `verify()` is
    intentionally not called: a per-iteration spot-check would add
    noise without adding signal in a batch audit, and `verify()`
    requires populated values anyway.
    """
    print(f"\n===== Auditing property: {name} =====")
    print(f"Description: {description}")

    s = _build_session()
    problem = Problem(s.model, Integer)

    age_bucket_var = problem.solve_for(
        s.age_bucket_id,
        type="int",
        name="age_bucket",
        lower=int(age_buckets_csv["id"].min()),
        upper=int(age_buckets_csv["id"].max()),
        populate=False,
    )
    chronic_var = problem.solve_for(s.has_chronic, type="bin", name="has_chronic", populate=False)
    coverage_band_var = problem.solve_for(
        s.coverage_band_id,
        type="int",
        name="coverage_band",
        lower=int(coverage_bands_csv["id"].min()),
        upper=int(coverage_bands_csv["id"].max()),
        populate=False,
    )
    senior_var = problem.solve_for(s.is_senior, type="bin", name="is_senior", populate=False)
    frail_var = problem.solve_for(s.is_frail, type="bin", name="is_frail", populate=False)
    manual_review_var = problem.solve_for(
        s.is_manual_review, type="bin", name="is_manual_review", populate=False
    )

    for rule_ic in s.rule_pack:
        problem.satisfy(rule_ic)
    for counterexample_ic in counterexample_fn(s):
        problem.satisfy(counterexample_ic)

    # Show the formulation on the first audit only. The rule pack is
    # identical across audits (each session rebuilds the same rule
    # pack); only the counterexample ICs differ per property. One
    # display() pass surfaces the model shape; repeating it would add
    # noise.
    if show_formulation:
        problem.display()

    # `solution_limit=MAX_WITNESSES` asks the solver to enumerate up to
    # that many distinct witnesses; without it, MiniZinc returns just
    # the first witness and stops.
    problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)
    si = problem.solve_info()
    verdict = _classify_verdict(si)
    n_witnesses = si.num_points if si.num_points is not None else 0
    print(f"Verdict: {verdict}  ({n_witnesses} witness(es), status={si.termination_status})")
    if verdict == "FAIL" and si.termination_status == "SOLUTION_LIMIT":
        print(
            f"Note: hit MAX_WITNESSES={MAX_WITNESSES}; raise it to enumerate more counterexamples."
        )

    # Per-FAIL witness table: `Variable.values(sol_idx, value)` indexes
    # the solver's outputs across every returned solution. Binding the
    # value slot to a reference Concept's `.id` walks the chosen ID
    # back to that row's columns in one step; for binary indicators an
    # Integer placeholder receives the 0/1 value.
    if verdict == "FAIL":
        print(f"\nWitnesses (up to {MAX_WITNESSES} per run):")
        sol_idx = Integer.ref()
        chr_v = Integer.ref()
        sen_v = Integer.ref()
        frl_v = Integer.ref()
        mr_v = Integer.ref()
        s.model.select(
            sol_idx.alias("solution"),
            s.AgeBucket.age_years.alias("age_years"),
            chr_v.alias("has_chronic"),
            s.CoverageBand.coverage_dollars.alias("coverage_dollars"),
            sen_v.alias("is_senior"),
            frl_v.alias("is_frail"),
            mr_v.alias("is_manual_review"),
        ).where(
            age_bucket_var.values(sol_idx, s.AgeBucket.id),
            chronic_var.values(sol_idx, chr_v),
            coverage_band_var.values(sol_idx, s.CoverageBand.id),
            senior_var.values(sol_idx, sen_v),
            frail_var.values(sol_idx, frl_v),
            manual_review_var.values(sol_idx, mr_v),
        ).inspect()

    return {
        "name": name,
        "description": description,
        "verdict": verdict,
        "num_witnesses": n_witnesses,
        "status": si.termination_status,
    }


# --------------------------------------------------
# Main: audit every property, then print the verdict matrix
# --------------------------------------------------

results = [
    run_audit(name, description, fn, show_formulation=(idx == 0))
    for idx, (name, description, fn) in enumerate(PROPERTIES)
]

# The verdict matrix is the audit's headline deliverable: one line per
# property, grouped by outcome. The PASS-and-FAIL mix in a single run
# is the demo -- the audit isn't rigged to always fail; it
# distinguishes properties the ruleset satisfies from those it
# violates. Cross-referencing FAIL witness tables for shared decision
# values (e.g. all witnesses with `has_chronic=1`) usually surfaces the
# common root cause; comparing witness counts across FAILs surfaces
# which sub-populations the bug touches.
fail_count = sum(1 for r in results if r["verdict"] == "FAIL")
pass_count = sum(1 for r in results if r["verdict"] == "PASS")
incon_count = sum(1 for r in results if r["verdict"] == "INCONCLUSIVE")
print("\n" + "=" * 80)
print(
    f"Audit report ({len(results)} properties: "
    f"{pass_count} PASS, {fail_count} FAIL, {incon_count} INCONCLUSIVE)"
)
print("=" * 80)
print(f"  {'Property':<32} {'Verdict':<14} {'Witnesses':>10}  Description")
print("  " + "-" * 90)
for r in results:
    print(f"  {r['name']:<32} {r['verdict']:<14} {r['num_witnesses']:>10}  {r['description']}")
