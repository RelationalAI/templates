"""Underwriting Audit (multi-property batch, multi-solution witnesses) template: the model.

This package declares property-entailment audit as a *batch* operation: a
single rule pack is checked against a catalog of separately-authored
properties, with one counterexample search per property and witnesses
enumerated per FAIL. This is the shape a real audit takes -- compliance
teams author a property catalog, the rule team authors the rules, and the
solver mediates between them. Bundling them in one model means a single
deploy surfaces the full audit report.

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
  a counterexample builder that returns the property's counterexample ICs.
  The counterexample for a property `P` is the negation of `P`: if the
  solver finds a feasible assignment satisfying the counterexample, the
  property does not hold.
- One `Problem` per property wires in the rule pack and the property's
  counterexample ICs, and solves with `solution_limit=K` (MiniZinc). Each
  property needs its own `Problem` because constraints on a `Problem` are
  add-only, so a previous property's counterexample ICs cannot be detached
  from a reused `Problem`. The deployed model publishes each solve's status
  and number of witnesses; `queries/audit_report.py` classifies the verdict
  and enumerates every distinct witness via `Variable.values(solution_index,
  value)`.

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
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.audit_report` then prints the report from the deployed model.
"""

from .reasoning import (
    MAX_WITNESSES,
    PROPERTIES,
    NumPoints,
    SolveStatus,
    Witness,
)
from .schema import AgeBucket, CoverageBand, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "MAX_WITNESSES",
    "PROPERTIES",
    "AgeBucket",
    "CoverageBand",
    "NumPoints",
    "SolveStatus",
    "Witness",
    "model",
]
