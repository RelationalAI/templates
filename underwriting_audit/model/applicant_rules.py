"""Applicant rules: the free decisions that describe one applicant, the derived indicators, and the
rule pack that pins each indicator to the decisions."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.prescriptive import implies

from .schema import AgeBucket, model

# --------------------------------------------------
# Parameters
# --------------------------------------------------

# Senior threshold: applicants with bucket age_years >= 70 are flagged
# `is_senior`. Drives both the (correct) `is_frail` and (buggy)
# `is_manual_review` rules.
SENIOR_THRESHOLD_YEARS = 70

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
