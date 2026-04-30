# Experiments

Local probes used while developing the lead template. Not shipped to
customers; not imported by the lead runner. Kept in-tree because the
findings inform the production form.

## `count_variants.py`

Compares six formulations of the per-(user, candidate) typed
path-count features against the same Open Library slice using
`problem.display()` (no E2E solve). Probes whether `prescriptive`
matches `pyrel` rule semantics around empty-group counting and
union-collision dedup.

Run: `./.venv/bin/python experiments/count_variants.py [A B C D E F]`

| Variant | Form | Result on `sm` slice (1145 candidates) |
|---|---|---|
| A | three counts, each `\| 0`, arithmetic sum (production) | min=2, max=12, 45 user-5 explanation_ic terms |
| B | typed evidence Relationships + three counts `\| 0`, arithmetic sum | identical to A |
| C | single `union_evidence` Relationship, single count of `(kind, key)` `\| 0` | min=2, max=11, 45 terms — set-style counting (loses bag multiplicity) |
| D | three counts, **NO** `\| 0` | min=3, max=12, **only 6** user-5 terms — empty-group cascade-drop |
| E | `count(ekind, ekey).per(ec)` over `model.union(branch1, branch2, branch3)` `\| 0` | identical to C |
| F | `sum(fv).per(fc)` over `model.union(propA, propB, propC)` `\| 0` | min=1, max=12, 45 terms — **silent under-count under value collisions** |

Key takeaways:

1. `\| 0` rule-level default is canonical and required. Variant D
   confirms empty-group cascade-drop. Pinned in PyRel by
   `tests/reasoners/prescriptive/test_e2e_rewriter.py::test_e2e_rewriter_empty_body_with_default_semantics_highs`.

2. `model.union` inside an aggregate body deduplicates on projected
   values (set-style, not bag-style). Pinned by
   `test_e2e_rewriter_semantic_equivalence_highs::u_same_prop`
   (`sum(model.union(X.v, X.v)) == 10`, not 20). Variant F reproduces
   the user-facing footgun: `sum(union(propA, propB, propC))` is
   **not** `propA + propB + propC` when values collide. Use plain
   arithmetic instead.

3. No prescriptive ↔ PyRel discrepancy: prescriptive's `_rewrite_match`
   and `_rewrite_aggregate` (rewriter.py L350-L671) preserve PyRel
   rule semantics end-to-end. Behavior is the spec, not a bug.

References:

- `~/PyRel/src/relationalai/semantics/reasoners/prescriptive/rewriter.py` — the rewriter "matches PyRel semantics" comment block (~L624) and the Match/Union scope-isolation (L350+).
- `~/PyRel/tests/end2end/unified/tests/aggregate_defaults_and_regroup.py` — canonical rule-level `count(...).per(c).where(...) | 0` idiom.
- PyRel PR #1117 (RAI-49485) — scope isolation for sub-aggregates; pins union-dedup with `u_same_prop`.
- PyRel PR #1118 — empty-body emit-time gate (parent of #1213).
- PyRel PR #1213 (RAI-50087) — per-iteration cell wrapper for outer `sum` over inner-`.per(...)` body. Adjacent surface; the kg_aware_slate template stays upstream of it (no nested per-aggregate in objective/constraint).
