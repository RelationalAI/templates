---
title: "Underwriting Audit"
description: "Audit an underwriting ruleset against a catalog of properties. For each property, the solver either proves the property holds (PASS) or returns K distinct counterexample applicants who falsify it (FAIL). Multi-property batch audit, CSP solver in multi-solution mode."
featured: false
experience_level: advanced
industry: "Insurance"
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

The bundled ruleset has a deliberate bug: `is_manual_review` is defined as "senior", but `is_frail` is defined as "senior OR has chronic condition". The bundled property catalog includes two properties the buggy rule violates (frail-implies-review and chronic-implies-review -- both FAIL with chronic non-senior witnesses) and one the buggy rule trivially satisfies (senior-implies-review -- PASS, the rule literally encodes it). The same template structure -- scalar applicant decisions, derived rule indicators via OR-arithmetic equivalences, a property catalog with counterexample-IC builders, fresh-Problem-per-property audit loop -- applies to any rule-based regulated domain: bank AML rules, healthcare prior-auth, manufacturing segregation-of-duties, SaaS retention policy.

## Who this is for

- Insurance actuaries and underwriting governance teams auditing rule libraries
- RegTech / compliance audit harnesses verifying property entailment over rule packs
- Model Risk Management (MRM) reviewers performing rule-level verification before promotion
- Operations researchers learning property-entailment audit as a CSP problem

## What you'll build

- A constraint model with three scalar free decisions (`age_bucket_id`, `has_chronic`, `coverage_band_id`) plus three derived binary indicators (`is_senior`, `is_frail`, `is_manual_review`) tied to the free decisions via solver-side ICs. Each decision is declared as `model.Relationship(f"{Integer:name}")` -- the unparented scalar shape used by the `rosenbrock` prescriptive example -- rather than a property on a singleton `Applicant` concept, because there is exactly one applicant slot and the concept adds identity overhead with no payoff at N=1
- A senior-indicator definition iterating over `AgeBucket` reference rows at relational time and binding `is_senior` via two `implies`-bodied ICs (one for senior buckets, one for non-senior)
- A frail-indicator definition encoding `is_frail = is_senior OR has_chronic` via the standard OR-arithmetic equivalence on binaries (three linear ICs: two lower bounds, one upper bound)
- A buggy `is_manual_review = is_senior` definition encoded as a binary equality (the audit will surface its missing chronic-condition arm)
- A `RULE_PACK_ICS` list bundling every rule IC for one-pass attachment to each per-property `Problem`
- A `PROPERTIES` catalog: a Python list of `(name, description, counterexample_builder)` tuples. The builder is a thunk that returns the property's counterexample ICs on demand; lazy construction is required so the audit loop gets fresh IC handles per iteration
- **A fresh-Problem-per-property audit loop**: constraints on a `Problem` are add-only, so each property gets its own `Problem`, its own `solve_for(...)` re-bindings of the scalar decisions, its own `problem.satisfy(...)` calls for the rule pack and the property's counterexample ICs, and its own `solve()`. The decision variables are model-level scalars; only the `Variable` subconcepts returned by `solve_for(...)` are per-Problem
- **Multi-solution enumeration as the per-property code path**: each `problem.solve(..., solution_limit=MAX_WITNESSES)` runs the search in enumeration mode; `Variable.values(solution_index, value)` joins the decision variables on a shared solution index to reconstruct each witness
- A pre-solve check that reference IDs are dense and contiguous, so `lower=min(id), upper=max(id)` decision bounds line up with the reference rows the relational-time `implies` rules iterate over (sparse IDs would let the solver pick a value with no matching row, leaving the rule indicators unconstrained for that solution)
- A per-property verdict driven by `solve_info().termination_status`: `INFEASIBLE` is **PASS** (property holds under the encoded ruleset), `OPTIMAL` or `SOLUTION_LIMIT` with one or more witnesses is **FAIL** (with the witness count and table), anything else is **INCONCLUSIVE**. Verdicts are stashed in a `results` list and printed as a verdict-matrix table at the end of the run

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

6. Expected output. The audit loop processes the three bundled properties in turn. For each FAIL the witness table prints inline (under the property's verdict line); the verdict matrix follows at the end. With `MAX_WITNESSES = 16` each FAIL solve exhausts the bundled feasible set (3 non-senior age buckets × 4 coverage bands = 12 chronic non-senior counterexamples) and reports `status: OPTIMAL`. Per-solution row ordering and wall times will vary across runs; the *set* of returned witnesses per property is stable because the search exhausts. Abridged output (witness tables for FAILs are shown for property 1 only; property 2's witness set is identical):

   ```text
   ===== Auditing property 1/3: frail_implies_review =====
   Description: every frail applicant goes through manual review
   ... [problem.display() and solve progress] ...
   Verdict: FAIL  (12 witness(es), status=OPTIMAL)

   Witnesses (up to 16 per run):
      solution age_years has_chronic coverage_dollars is_senior is_frail is_manual_review
   0         0        55           1          1000000         0        1                0
   1         1        55           1           500000         0        1                0
   2         2        55           1           250000         0        1                0
   3         3        55           1           100000         0        1                0
   4         4        28           1           250000         0        1                0
   ...      (12 rows total)

   ===== Auditing property 2/3: chronic_implies_review =====
   Description: every chronic-condition applicant goes through manual review
   Verdict: FAIL  (12 witness(es), status=OPTIMAL)
   ... [12 witnesses, same chronic-non-senior set] ...

   ===== Auditing property 3/3: senior_implies_review =====
   Description: every senior applicant goes through manual review
   Verdict: PASS  (0 witness(es), status=INFEASIBLE)

   ================================================================================
   Audit report (3 properties: 1 PASS, 2 FAIL, 0 INCONCLUSIVE)
   ================================================================================
     Property                   Verdict         Witnesses  Description
     ------------------------------------------------------------------------------
     frail_implies_review       FAIL                   12  every frail applicant goes through manual review
     chronic_implies_review     FAIL                   12  every chronic-condition applicant goes through manual review
     senior_implies_review      PASS                    0  every senior applicant goes through manual review
   ```

   Each FAIL witness row is one applicant who falsifies that property: `is_frail == 1` (or `has_chronic == 1`, for property 2) and `is_manual_review == 0` -- because the buggy rule only flags seniors and these applicants are below the 70 threshold. The verdict word **FAIL** means *the ruleset under audit fails the property* -- the audit tool itself ran cleanly; FAIL is the audit's *finding*, not a template error. **PASS** on property 3 means the solver proved no counterexample exists -- the buggy rule literally encodes "manual review = senior", so "every senior gets manual review" is trivially satisfied. The mixed-verdict matrix at the bottom is the audit's headline deliverable: a single run distinguishes properties the ruleset satisfies from those it violates. Lower `MAX_WITNESSES` below the feasible-set size (e.g. 4) to demonstrate the `SOLUTION_LIMIT` outcome where the solver returns a sample and signals that more witnesses may exist.

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

The template builds the rule pack and the property catalog as separate artifacts, then runs a per-property audit loop. Each iteration constructs a fresh `Problem`, wires in the rule pack and that property's counterexample ICs, and solves in multi-solution mode. Verdicts are stashed and printed as a matrix at the end. The script consists of these patterns:

**Free decisions describe what an applicant looks like.** Three integer/binary scalar decisions: which age bucket the applicant falls into, whether they have a chronic condition, which coverage band they sit in. Each is `model.Relationship(f"{Integer:name}")` (the unparented scalar shape used by the `rosenbrock` prescriptive example), not a property on a singleton `Applicant` concept. The solver picks values for these on every solution.

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

The full rule pack is then bundled into a list for one-pass attachment in the audit loop:

```python
RULE_PACK_ICS = [
    senior_def_pos_ic, senior_def_neg_ic,
    frail_lb_senior_ic, frail_lb_chronic_ic, frail_ub_ic,
    manual_review_eq_ic,
]
```

**Property catalog as separately-authored spec.** Each property is a `(name, description, counterexample_builder)` tuple. The builder is a thunk that constructs the property's counterexample ICs on demand -- lazy because the audit loop calls it once per iteration and needs fresh IC handles to pass to `problem.satisfy(...)`. The counterexample for a property `P` is the *negation* of `P`: if the solver finds a feasible assignment satisfying the counterexample, `P` does not hold:

```python
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
```

**Fresh-Problem-per-property audit loop.** Constraints on a `Problem` are add-only -- there is no API to remove a previous property's counterexample ICs. The audit loop builds a fresh `Problem` per property, re-binds every scalar decision via `solve_for(...)`, wires in the rule pack and the property's counterexample ICs, and solves. `populate=False` skips the first-solution write-back to the scalar relationships; every witness is read through `Variable.values(...)`, so the populated state is unused:

```python
for prop_idx, (name, description, counterexample_fn) in enumerate(PROPERTIES):
    problem = Problem(model, Integer)
    age_bucket_var = problem.solve_for(
        age_bucket_id, type="int", name="age_bucket",
        lower=int(age_buckets_csv["id"].min()),
        upper=int(age_buckets_csv["id"].max()),
        populate=False,
    )
    # ... five more solve_for(...) calls for the other scalar decisions ...

    for rule_ic in RULE_PACK_ICS:
        problem.satisfy(rule_ic)
    for counterexample_ic in counterexample_fn():
        problem.satisfy(counterexample_ic)

    problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_WITNESSES)
    si = problem.solve_info()
    verdict = _classify_verdict(si)
    # ... witness query (FAIL only) and stash result for the verdict matrix ...
```

**Multi-solution enumeration via `Variable.values(solution_index, value)`.** Inside the loop, the `Variable` subconcepts returned by `solve_for(...)` expose `.values(sol_idx, val)` relationships that index per-solution outputs. Binding the value slot directly to a reference Concept's `.id` walks the chosen ID back to that row's columns in one step; binary indicator decisions read out into Integer placeholders:

```python
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
```

## Customize this template

- **Add a property to the catalog.** Append a new `(name, description, counterexample_builder)` tuple to `PROPERTIES`. The builder is a thunk returning the property's counterexample ICs (the *negation* of the property). Example: to audit "no senior is in the cheapest coverage band", add `("no_senior_cheap_band", "no senior is in the cheapest coverage band", lambda: [model.require(is_senior == 1), model.require(coverage_band_id == 1)])`. The audit loop picks it up automatically -- no other code needs to change.
- **Audit a corrected ruleset** by changing the buggy rule. `is_manual_review` is encoded as a single equality IC (`manual_review_eq_ic`) pinning `is_manual_review == is_senior`; replace it with the OR-arithmetic shape that pins `is_manual_review == is_frail` (i.e. `>= is_senior`, `>= has_chronic`, `<= is_senior + has_chronic`) and remember to update `RULE_PACK_ICS` to match. With the fix in place, the previously FAILing properties flip to PASS and the verdict matrix reports 3 PASS / 0 FAIL.
- **Extend to a fleet of N applicants** by reintroducing an `Applicant` concept and lifting each scalar decision to a property on it (e.g. `Applicant.age_bucket_id = model.Property(f"{Applicant} in age bucket {Integer:age_bucket_id}")`). Then scope every IC -- including each property's counterexample ICs in the catalog -- with `model.where(Applicant)` (or a tighter applicant filter). The scalar shape used here is the right default at N=1; the per-applicant shape becomes mandatory the moment you bind the audit to a real applicant table.
- **Add more rule indicators** by introducing additional decisions and OR/AND-arithmetic ICs, then appending the new ICs to `RULE_PACK_ICS`. Conjunction `y = a AND b` is encoded as `y <= a, y <= b, y >= a + b - 1` -- the dual of the OR pattern.
- **Raise the witness count on a real ruleset** by increasing `MAX_WITNESSES`. Production audits typically want 50--500 witnesses per FAILed property to cover the rule pack's failure modes.
- **Switch from "any witness" to "minimum-violation witness"** by adding `problem.minimize(...)` over a violation severity score and `solution_limit=1`. Useful for ranking failures when triage capacity is limited.
- **Adapt to a different regulated domain** by editing the rule pack and the property catalog. The shape carries directly to bank AML rules (`is_pep AND is_high_velocity AND is_auto_approved`), healthcare prior-auth (`requires_pa AND was_auto_paid`), manufacturing segregation-of-duties (`is_requester AND is_approver AND is_executor`), SaaS retention (`is_paying AND is_churn_risk AND is_in_low_touch_segment`).

## Troubleshooting

<details>
  <summary>A property reports PASS / INFEASIBLE when you expected FAIL</summary>

- The audited property holds: no feasible applicant falsifies it under the bundled ruleset. This is the audit's *pass* signal for that property -- the verdict line reports `Verdict: PASS  (0 witness(es), status=INFEASIBLE)`. For the bundled catalog this is the expected outcome for `senior_implies_review` because the buggy rule literally encodes "manual review = senior".
- If you expected a witness and got none for a different property, double-check the counterexample builder: did the thunk return ICs that assert the *negation* of the property (e.g. `is_frail == 1 AND is_manual_review == 0` for "every frail applicant goes through manual review")? An accidentally-positive IC (`is_frail == 0`) would not match the property's negation.
- Empty reference data: confirm `data/age_buckets.csv` has at least one non-senior bucket (age < `SENIOR_THRESHOLD_YEARS`). The buggy rule's gap is chronic + non-senior applicants slipping past manual review; if every bucket is at or above the threshold, all applicants are flagged as senior and `frail_implies_review` / `chronic_implies_review` correctly find no counterexample (PASS for the wrong reason).

</details>

<details>
  <summary>ValueError: <code>id</code> column must be dense and contiguous</summary>

- The pre-solve check ran on `age_buckets.csv` or `coverage_bands.csv` and found gaps in the `id` column. The solver bounds the corresponding decision by `lower=min(id), upper=max(id)`; without dense IDs it can pick a value with no matching reference row, and the relational-time `implies` rules gated on the matching row will not fire -- leaving the rule indicator unconstrained for that solution.
- Renumber the rows so IDs run consecutively from the minimum to the maximum (e.g., 1, 2, 3, ... or 10, 11, 12, ...). Trailing or leading gaps are fine to delete; mid-table gaps are the problem.
- Alternatively, replace the bound-only `solve_for(..., lower=, upper=)` with explicit ID-membership ICs (one `model.where(AB.id == decision_id).require(...)` per slot) and remove the dense-ID assertion.

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
