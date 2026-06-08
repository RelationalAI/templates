---
title: "Underwriting Audit"
description: "Audit an underwriting ruleset against a catalog of properties. For each property, the solver either proves the property holds (PASS) or returns K distinct counterexample applicants who falsify it (FAIL). Multi-property batch audit, CSP solver in multi-solution mode."
featured: false
experience_level: advanced
industry: "Financial Services"
reasoning_types:
  - Prescriptive
tags:
  - constraint-programming
  - multi-solution
  - rule-verification
  - audit
  - insurance
  - regtech
---

# Underwriting Audit

## What this template is for

Insurance actuaries, RegTech audit teams, and Model Risk Management (MRM) reviewers periodically audit underwriting rulesets to verify that the rules enforce stated properties: "no high-risk applicant is auto-approved", "every frail applicant goes through manual review", "no policy exceeds the regulatory ceiling without two-signoff". Hand-checking a ruleset of even a few dozen rules against a property is intractable; sampled fixtures only catch the failures that happen to be in the sample. The right answer is verification: declare the ruleset and the property as a constraint model, ask the solver if any feasible applicant falsifies the property, and if so, return the *witness*.

Real audits are a *batch* operation. The rule team owns the rule pack; the compliance / MRM team owns a catalog of properties the rule pack must satisfy. This template demonstrates that shape: a `PROPERTIES` catalog is separately authored from the rule pack, and a single audit run produces one verdict (PASS / FAIL / INCONCLUSIVE) per property plus witness tables for each FAIL. The mixed-verdict output is the point -- the audit is not rigged to always fail; it distinguishes properties the rule pack satisfies from those it violates. Bundling them in one script makes the per-run audit report the natural deliverable.

Audit / counterexample surfacing is plural per property as well. One witness tells the actuary that a property fails; K distinct witnesses surface concrete failure cases across age buckets, condition profiles, and coverage bands the buggy rule misses. A single counterexample is unhelpful for triage because the actuary then has to manually probe variations to understand the failure shape. K distinct witnesses surface the failure shape automatically. The solver guarantees pairwise distinctness, not maximal diversity -- to exhaust the failure space, raise `MAX_WITNESSES` past the size of the feasible set. Each property's audit runs in multi-solution mode (`solution_limit=K`) and reads back witnesses via `Variable.values(solution_index, value)`.

The bundled ruleset has a deliberate bug: `is_manual_review` is defined as "senior", but `is_frail` is defined as "senior OR has chronic condition". The bundled property catalog mixes verdicts and witness shapes: `frail_implies_review` FAILs broadly (12 chronic-non-senior witnesses across all four coverage bands and three non-senior age buckets); `chronic_under_50_implies_review` FAILs on a scoped sub-population (8 witnesses -- a strict subset of #1 restricted to age < 50, illustrating property scoping); `senior_implies_review` PASSes (INFEASIBLE) because the buggy rule literally encodes it. The same template structure -- scalar applicant decisions, derived rule indicators via OR-arithmetic equivalences, a property catalog with counterexample-IC builders, fresh-Model-per-audit factory -- adapts to any rule-based regulated domain (bank AML rules, healthcare prior-auth, manufacturing segregation-of-duties, SaaS retention). Real rule packs in those domains often contain hundreds of rules; the per-audit fresh-Model factory only isolates the rule count across iterations, so a single audit's rule pack still needs to stay under PyRel's per-Model `"Rules created in a loop"` threshold -- decompose into smaller property-scoped rule packs if it doesn't.

## Who this is for

- Insurance actuaries and underwriting governance teams auditing rule libraries
- RegTech / compliance audit harnesses verifying property entailment over rule packs
- Model Risk Management (MRM) reviewers performing rule-level verification before promotion
- Operations researchers learning property-entailment audit as a CSP problem

## What you'll build

- A constraint model with three scalar free decisions (`age_bucket_id`, `has_chronic`, `coverage_band_id`) plus three derived binary indicators (`is_senior`, `is_frail`, `is_manual_review`) tied to the free decisions via solver-side ICs. `age_bucket_id` and `has_chronic` drive the indicator rules; `coverage_band_id` enters no rule IC and is a spread-only decision dimension whose role is to diversify witness output across coverage bands. Each decision is declared as `model.Relationship(f"{Integer:name}")` -- the unparented scalar shape -- rather than a property on a singleton `Applicant` concept, because there is exactly one applicant slot and the concept adds identity overhead with no payoff at N=1
- A senior-indicator definition iterating over `AgeBucket` reference rows at relational time and binding `is_senior` via two `implies`-bodied ICs (one for senior buckets, one for non-senior)
- A frail-indicator definition encoding `is_frail = is_senior OR has_chronic` via the standard OR-arithmetic equivalence on binaries (three linear ICs: two lower bounds, one upper bound)
- A buggy `is_manual_review = is_senior` definition encoded as a binary equality (the audit will surface its missing chronic-condition arm)
- A `_build_session()` factory that constructs a fresh `Model` per audit, bundling the concepts, scalar decisions, and rule pack into a `SimpleNamespace`. Returning a fresh model per audit (not per property *Problem*) is necessary because PyRel emits a `"Rules created in a loop"` warning when the per-Model internal-rule count crosses a fixed threshold; cumulative `problem.satisfy(...)` calls across iterations of a shared model trip it
- A `PROPERTIES` catalog: a Python list of `(name, description, counterexample_builder)` tuples. The builder takes the audit session and returns the property's counterexample ICs against its freshly-built model. Scoped properties (e.g. "chronic applicants under age 50") use a `model.where(...)` data filter plus a decision-variable constraint in `require` to restrict the search sub-population
- **A `run_audit(...)` helper that owns the per-property lifecycle**: build session, create `Problem`, re-bind every scalar decision via `solve_for(...)`, attach the rule pack and the property's counterexample ICs via `problem.satisfy(...)`, solve, classify, print witnesses (FAIL only), return the result. Each call is a fully isolated audit -- the model, decisions, rule pack, and Problem are all per-audit. The main loop is then a list comprehension over `PROPERTIES`
- **Multi-solution enumeration as the per-property code path**: each `problem.solve(..., solution_limit=MAX_WITNESSES)` runs the search in enumeration mode; `Variable.values(solution_index, value)` joins the decision variables on a shared solution index to reconstruct each witness
- A pre-solve check that reference IDs are dense and contiguous, so `lower=min(id), upper=max(id)` decision bounds line up with the reference rows the relational-time `implies` rules iterate over (sparse IDs would let the solver pick a value with no matching row, leaving the rule indicators unconstrained for that solution)
- A per-property verdict driven by `solve_info().termination_status`: any status with one or more witnesses is **FAIL** (one witness falsifies the property regardless of whether the search exhausted), `INFEASIBLE` (or `OPTIMAL` with zero witnesses) is **PASS**, and anything else (`TIME_LIMIT`, `MEMORY_LIMIT`, ... with zero witnesses) is **INCONCLUSIVE**. Local-only statuses from continuous solvers (e.g. `LOCALLY_SOLVED`) are not exhaustion proofs and route to `INCONCLUSIVE`. Verdicts are stashed in a `results` list and printed as a verdict-matrix table at the end of the run

## What's included

- `underwriting_audit.py` -- main script with ontology, decisions, constraints, and solver call
- `data/age_buckets.csv` -- 4 representative ages (28, 45, 55, 72) -- three under the 70 senior threshold, one above
- `data/coverage_bands.csv` -- 4 coverage levels ($100k, $250k, $500k, $1M)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/underwriting_audit.zip
   unzip underwriting_audit.zip
   cd underwriting_audit
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python underwriting_audit.py
   ```

6. Expected output. The audit loop processes the three bundled properties in turn. For each FAIL the witness table prints inline (under the property's verdict line); the verdict matrix follows at the end. With `MAX_WITNESSES = 16` each FAIL solve exhausts its feasible set and reports `status: OPTIMAL`: 12 witnesses for the broad `frail_implies_review`, 8 for the scoped `chronic_under_50_implies_review` (restricted to age < 50). Per-solution row ordering and wall times will vary across runs; the *set* of witnesses per property is stable because the search exhausts. Abridged output:

   ```text
   ===== Auditing property: frail_implies_review =====
   Description: every frail applicant goes through manual review
   ... [problem.display() and solve progress] ...
   Verdict: FAIL  (12 witness(es), status=OPTIMAL)

   Witnesses (up to 16 per run):
      solution age_years has_chronic coverage_dollars is_senior is_frail is_manual_review
   0         0        55           1          1000000         0        1                0
   1         1        55           1           500000         0        1                0
   ...      (12 rows total: has_chronic is forced to 1 by the counterexample, so the spread is over 3 non-senior age buckets × 4 coverage bands)

   ===== Auditing property: chronic_under_50_implies_review =====
   Description: every chronic applicant under age 50 goes through manual review
   Verdict: FAIL  (8 witness(es), status=OPTIMAL)

   Witnesses (up to 16 per run):
     solution age_years has_chronic coverage_dollars is_senior is_frail is_manual_review
   0        0        45           1          1000000         0        1                0
   1        1        28           1          1000000         0        1                0
   ...     (8 rows total, covering 2 under-50 age buckets × 4 coverage bands -- a strict subset of property 1's witnesses)

   ===== Auditing property: senior_implies_review =====
   Description: every senior applicant goes through manual review
   Verdict: PASS  (0 witness(es), status=INFEASIBLE)

   ================================================================================
   Audit report (3 properties: 1 PASS, 2 FAIL, 0 INCONCLUSIVE)
   ================================================================================
     Property                         Verdict         Witnesses  Description
     ------------------------------------------------------------------------------------------
     frail_implies_review             FAIL                   12  every frail applicant goes through manual review
     chronic_under_50_implies_review  FAIL                    8  every chronic applicant under age 50 goes through manual review
     senior_implies_review            PASS                    0  every senior applicant goes through manual review
   ```

   Each FAIL witness row is one applicant who falsifies that property: chronic (`has_chronic == 1`), frail under the rule book (`is_frail == 1`, via the OR rule), but missed by manual review (`is_manual_review == 0`) because the buggy rule only flags seniors and these applicants are below the 70 threshold. **FAIL** means *the ruleset under audit fails the property* -- the audit tool itself ran cleanly; FAIL is the audit's *finding*, not a template error. **PASS** on `senior_implies_review` means the solver proved no counterexample exists -- the buggy rule literally encodes "manual review = senior", so "every senior gets manual review" is trivially satisfied. The witness-count gap (12 vs 8) demonstrates *property scoping*: `chronic_under_50_implies_review` restricts its counterexample to a sub-population, and the audit reports a correspondingly narrower failure shape. The mixed-verdict matrix at the bottom is the audit's headline deliverable: a single run distinguishes properties the ruleset satisfies from those it violates. Lower `MAX_WITNESSES` below the feasible-set size (e.g. 4) to demonstrate the `SOLUTION_LIMIT` outcome where the solver returns a sample and signals that more witnesses may exist.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── underwriting_audit.py
└── data/
    ├── age_buckets.csv
    └── coverage_bands.csv
```

## How it works

The template factors the audit into three artifacts: a `_build_session()` factory that constructs a fresh `Model` per audit (with the concepts, scalar decisions, and rule pack bundled into a `SimpleNamespace`); a `PROPERTIES` catalog that pairs each property's name and description with a counterexample-IC builder; and a `run_audit(...)` helper that owns one property's full lifecycle (build session, create `Problem`, satisfy ICs, solve, verdict, witnesses). The main script is a list comprehension over `PROPERTIES`, then a verdict-matrix recap. The script consists of these patterns:

**Free decisions describe what an applicant looks like.** Three integer/binary scalar decisions: which age bucket the applicant falls into, whether they have a chronic condition, which coverage band they sit in. Each is `model.Relationship(f"{Integer:name}")` (the unparented scalar shape), not a property on a singleton `Applicant` concept. The solver picks values for these on every solution. `age_bucket_id` and `has_chronic` drive the rules below; `coverage_band_id` enters no rule IC and is left in as a spread-only dimension that diversifies witness output (and gives customisation room when coverage thresholds need to enter the rule pack).

```python
age_bucket_id = model.Relationship(f"{Integer:age_bucket_id}")
has_chronic = model.Relationship(f"{Integer:has_chronic}")
coverage_band_id = model.Relationship(f"{Integer:coverage_band_id}")
```

**Derived indicators encode the rule body.** Three more scalar binaries -- `is_senior`, `is_frail`, `is_manual_review` -- defined via solver-side ICs that pin them to functions of the free decisions. Treating the indicators as decisions (rather than as relational-time predicates) lets the property-entailment IC compare them directly:

```python
is_senior = model.Relationship(f"{Integer:is_senior}")
is_frail = model.Relationship(f"{Integer:is_frail}")
is_manual_review = model.Relationship(f"{Integer:is_manual_review}")
```

**Senior indicator via per-bucket iteration.** `is_senior` is 1 iff the applicant's age bucket has age >= 70. Iterate over `AgeBucket` reference rows at relational time and gate on the decision-valued `age_bucket_id == AgeBucket.id` inside `implies`. Two ICs cover both directions of the equivalence:

```python
senior_def_pos_ic = model.where(AgeBucket.age_years >= SENIOR_THRESHOLD_YEARS).require(
    implies(age_bucket_id == AgeBucket.id, is_senior == 1)
)
senior_def_neg_ic = model.where(AgeBucket.age_years < SENIOR_THRESHOLD_YEARS).require(
    implies(age_bucket_id == AgeBucket.id, is_senior == 0)
)
```

**Frail indicator via OR-arithmetic equivalence.** `is_frail = is_senior OR has_chronic`. The standard CSP encoding for OR over binaries is three linear ICs -- `y >= a`, `y >= b`, `y <= a + b` -- which together force `y` to equal `max(a, b)`. All three are pure relational arithmetic:

```python
frail_lb_senior_ic = model.require(is_frail >= is_senior)
frail_lb_chronic_ic = model.require(is_frail >= has_chronic)
frail_ub_ic = model.require(is_frail <= is_senior + has_chronic)
```

**Buggy manual-review rule via equality.** The bundled ruleset has `is_manual_review = is_senior`, encoded as a single equality. The intended rule was `is_manual_review = is_frail`; the missing chronic arm is exactly what the audit exposes:

```python
manual_review_eq_ic = model.require(is_manual_review == is_senior)
```

The rule pack is then bundled into a list inside the session-builder for one-pass attachment in `run_audit(...)`:

```python
rule_pack = [
    senior_def_pos_ic, senior_def_neg_ic,
    frail_lb_senior_ic, frail_lb_chronic_ic, frail_ub_ic,
    manual_review_eq_ic,
]
```

**Audit session factory: fresh Model per audit.** `_build_session()` is the single entry point that constructs a fresh `Model`, defines the concepts, scalar decisions, and rule pack on it, and returns a `SimpleNamespace` exposing every artifact the per-property audit needs. Fresh model per audit -- not per Problem -- is necessary because PyRel emits a `"Rules created in a loop"` warning when the per-Model internal-rule count crosses a fixed threshold; cumulative `problem.satisfy(...)` calls across iterations of a shared model would trip it after a few audits. The build is cheap (concepts + relationships + IC handles, no solver work); the costly path is the solve below.

```python
def _build_session():
    model = Model("underwriting_audit")
    AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
    # ... CoverageBand, scalar decisions, rule pack ICs ...
    return SimpleNamespace(
        model=model,
        AgeBucket=AgeBucket, CoverageBand=CoverageBand,
        age_bucket_id=age_bucket_id, has_chronic=has_chronic,
        coverage_band_id=coverage_band_id,
        is_senior=is_senior, is_frail=is_frail, is_manual_review=is_manual_review,
        rule_pack=rule_pack,
    )
```

**Property catalog as separately-authored spec.** Each property is a `(name, description, counterexample_builder)` tuple. The builder takes the session `s` (the fresh-model namespace) and returns the property's counterexample ICs. The counterexample for a property `P` is the *negation* of `P`: if the solver finds a feasible assignment satisfying the counterexample, `P` does not hold. Scoped properties (`chronic_under_50_implies_review` below) add a `s.model.where(...)`-bound IC to restrict the search sub-population -- the data filter goes in `where`, the decision-variable constraint in `require` (PyRel rejects decision-variable expressions inside `where`):

```python
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
        f"every chronic applicant under age {UNDER_50_THRESHOLD_YEARS} goes through manual review",
        lambda s: [
            s.model.require(s.has_chronic == 1),
            s.model.require(s.is_manual_review == 0),
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
```

**`run_audit(...)` runs one isolated audit and returns its verdict.** Each call builds a fresh session, creates a `Problem` over that session's model, re-binds every scalar decision via `solve_for(...)`, attaches the rule pack and the property's counterexample ICs via `problem.satisfy(...)`, solves, classifies the verdict, prints the witness table (FAIL only), and returns a result dict. `populate=False` skips the first-solution write-back to the scalar relationships; every witness is read through `Variable.values(...)`, so the populated state is unused, and `populate=False` also sidesteps the latent FDError under `solution_limit`. The main code is then a list comprehension over `PROPERTIES`:

```python
def run_audit(name, description, counterexample_fn, show_formulation):
    s = _build_session()
    problem = Problem(s.model, Integer)
    age_bucket_var = problem.solve_for(
        s.age_bucket_id, type="int", name="age_bucket",
        lower=int(age_buckets_csv["id"].min()),
        upper=int(age_buckets_csv["id"].max()),
        populate=False,
    )
    # ... five more solve_for(...) calls for the other scalar decisions ...

    for rule_ic in s.rule_pack:
        problem.satisfy(rule_ic)
    for counterexample_ic in counterexample_fn(s):
        problem.satisfy(counterexample_ic)

    problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)
    si = problem.solve_info()
    verdict = _classify_verdict(si)
    # ... witness query (FAIL only) and return result dict ...

results = [
    run_audit(name, description, fn, show_formulation=(idx == 0))
    for idx, (name, description, fn) in enumerate(PROPERTIES)
]
```

**Multi-solution enumeration via `Variable.values(solution_index, value)`.** Inside `run_audit`, the `Variable` subconcepts returned by `solve_for(...)` expose `.values(sol_idx, val)` relationships that index per-solution outputs. Binding the value slot directly to a reference Concept's `.id` walks the chosen ID back to that row's columns in one step; binary indicator decisions read out into Integer placeholders:

```python
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
```

## Customize this template

- **Add a property to the catalog.** Append a new `(name, description, counterexample_builder)` tuple to `PROPERTIES`. The builder takes the session `s` (a fresh-model namespace) and returns the property's counterexample ICs (the *negation* of the property). Example: to audit "no senior is in the cheapest coverage band", add `("no_senior_cheap_band", "no senior is in the cheapest coverage band", lambda s: [s.model.require(s.is_senior == 1), s.model.require(s.coverage_band_id == 1)])`. `run_audit` picks it up automatically -- no other code needs to change.
- **Add a scoped property.** Add a `s.model.where(<data filter>).require(<decision constraint>)` IC alongside the unconditional counterexample ICs. `chronic_under_50_implies_review` shows the pattern: the where iterates AgeBucket rows with `age_years >= UNDER_50_THRESHOLD_YEARS` (pure data filter), and the require body adds `s.age_bucket_id != s.AgeBucket.id` per matching row to forbid the scalar decision from picking those rows. PyRel rejects decision-variable expressions inside `where`, so the decision-variable constraint must live in `require`.
- **Audit a corrected ruleset** by changing the buggy rule inside `_build_session()`. `is_manual_review` is encoded as a single equality IC (`manual_review_eq_ic`) pinning `is_manual_review == is_senior`; replace the right-hand side with `is_frail` (i.e. `model.require(is_manual_review == is_frail)`). Both sides are already pinned binaries, so a single equality suffices -- no three-IC OR re-derivation is needed because the `is_frail` rule pack already encodes the OR shape. With the fix in place, the FAIL verdicts in the bundled run become PASS and the verdict matrix reports 3 PASS / 0 FAIL.
- **Extend to a fleet of N applicants** by reintroducing an `Applicant` concept inside `_build_session()` and lifting each scalar decision to a property on it (e.g. `Applicant.age_bucket_id = model.Property(f"{Applicant} in age bucket {Integer:age_bucket_id}")`). Then scope every IC -- including each property's counterexample ICs in the catalog -- with `s.model.where(s.Applicant)` (or a tighter applicant filter). The scalar shape used here is the right default at N=1; the per-applicant shape becomes mandatory the moment you bind the audit to a real applicant table.
- **Add more rule indicators** by introducing additional decisions and OR/AND-arithmetic ICs inside `_build_session()`, then appending the new ICs to `rule_pack`. Conjunction `y = a AND b` is encoded as `y <= a, y <= b, y >= a + b - 1` -- the dual of the OR pattern.
- **Raise the witness count on a real ruleset** by increasing `MAX_WITNESSES`. Production audits typically want 50--500 witnesses per FAILed property to cover the rule pack's failure modes.
- **Switch from "any witness" to "minimum-violation witness"** by adding `problem.minimize(...)` inside `run_audit(...)` over a violation severity score and `solution_limit=1`. Useful for ranking failures when triage capacity is limited.
- **Adapt to a different regulated domain** by editing the rule pack and the property catalog. The shape carries directly to bank AML rules (`is_pep AND is_high_velocity AND is_auto_approved`), healthcare prior-auth (`requires_pa AND was_auto_paid`), manufacturing segregation-of-duties (`is_requester AND is_approver AND is_executor`), SaaS retention (`is_paying AND is_churn_risk AND is_in_low_touch_segment`). Real rule packs in these domains often contain hundreds of rules; decompose into smaller property-scoped rule packs if a single audit's count exceeds PyRel's per-Model `"Rules created in a loop"` threshold.

## Troubleshooting

<details>
  <summary>A property reports PASS / INFEASIBLE when you expected FAIL</summary>

- The audited property holds: no feasible applicant falsifies it under the bundled ruleset. This is the audit's *pass* signal for that property -- the verdict line reports `Verdict: PASS  (0 witness(es), status=INFEASIBLE)`. For the bundled catalog this is the expected outcome for `senior_implies_review` because the buggy rule literally encodes "manual review = senior".
- If you expected a witness and got none for a different property, double-check the counterexample builder: did the thunk return ICs that assert the *negation* of the property (e.g. `is_frail == 1 AND is_manual_review == 0` for "every frail applicant goes through manual review")? An accidentally-positive IC (`is_frail == 0`) would not match the property's negation.
- Empty reference data: confirm `data/age_buckets.csv` has at least one non-senior bucket (age < `SENIOR_THRESHOLD_YEARS`). The buggy rule's gap is chronic + non-senior applicants slipping past manual review; if every bucket is at or above the threshold, all applicants are flagged as senior and `frail_implies_review` / `chronic_under_50_implies_review` correctly find no counterexample (PASS for the wrong reason).

</details>

<details>
  <summary>ValueError: <code>id</code> column must be dense and contiguous</summary>

- The pre-solve check ran on `age_buckets.csv` or `coverage_bands.csv` and found gaps in the `id` column. The solver bounds the corresponding decision by `lower=min(id), upper=max(id)`; without dense IDs it can pick a value with no matching reference row, and the relational-time `implies` rules gated on the matching row will not fire -- leaving the rule indicator unconstrained for that solution.
- Renumber the rows so IDs run consecutively from the minimum to the maximum (e.g., 1, 2, 3, ... or 10, 11, 12, ...). Trailing or leading gaps are fine to delete; mid-table gaps are the problem.

</details>

<details>
  <summary>How many witnesses will the solver return?</summary>

- Up to `MAX_WITNESSES` (16 by default) or however many feasible witnesses exist, whichever is smaller. `solve_info().num_points` reports the actual count after the solve; `solve_info().termination_status` reports `SOLUTION_LIMIT` when the limit was hit and `OPTIMAL` when the search has been exhausted.
- When `status == OPTIMAL`, the search exhausted the feasible set: the *set* of returned witnesses is stable across runs and only the row ordering may vary. When `status == SOLUTION_LIMIT`, the solver stopped early and the specific K-subset of witnesses returned can vary across runs and solver versions -- only the existence of K witnesses is stable.
- Treat the `solution` column as a label, not a ranking.
- The K returned witnesses are guaranteed to be pairwise *distinct* on at least one decision (age, chronic flag, coverage, or any indicator) but not maximally diverse, and they are not ranked by severity or any objective. For systematic spread across the failure-mode space, raise `MAX_WITNESSES` past the size of the feasible set so the solver exhausts every distinct case; for ranking, add `problem.minimize(...)` over a severity score and post-process.

</details>

<details>
  <summary>"Property holds" -- how do I know the audit was sound?</summary>

- A pass result (no witness) means the solver could not find a feasible applicant satisfying the counterexample IC under the modelled ruleset. This is sound *for the ruleset as encoded* -- if your encoding misses a rule arm, the audit will silently pass on the unencoded gap. Always cross-check the encoding against the source rule pack: for every rule arm, there should be a corresponding `model.require(...)` or `implies(...)`.
- A pass result is also sound only *for the property as encoded*. Cross-check that the property itself matches the regulation -- auditing the wrong property PASSes for the wrong reason.
- Bounded model-checking caveat: this template enumerates K witnesses up to a `MAX_WITNESSES` limit. That is a search-space cap, not a soundness cap -- the solver still proves INFEASIBLE (or returns the full feasible set) when the search exhausts within the time limit. Watch for `status: SOLUTION_LIMIT`: that means more witnesses may exist beyond the K reported.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS is not appropriate here -- the model is discrete satisfaction with categorical decisions and binary indicator equivalences, not LP/MILP.

</details>
