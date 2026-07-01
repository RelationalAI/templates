---
title: "Underwriting Audit"
description: "Audit an underwriting ruleset against a catalog of required properties. For each property, the solver either proves it always holds or returns concrete counterexample applicants that break it."
featured: false
experience_level: advanced
industry: "Financial Services"
reasoning_types:
  - Prescriptive
tags:
  - Constraint Programming
  - Rule Verification
  - Multi-Solution Search
  - Audit
  - Insurance
  - RegTech
---

## What this template is for

Insurance actuaries, regulatory-technology (RegTech) audit teams, and Model Risk Management (MRM) reviewers periodically check underwriting rulesets against the properties those rules are supposed to guarantee: no high-risk applicant is auto-approved, every frail applicant goes through manual review, no policy exceeds the regulatory ceiling without a second sign-off. Hand-checking even a few dozen rules against a property is impractical, and testing on a sample of applicants only catches the failures that happen to be in the sample. The dependable answer is verification: state the ruleset and the property as a constraint model and ask the solver whether any applicant at all can slip through. If one can, the solver hands back the concrete applicant that breaks the rule.

A real audit is a batch job across many properties at once, and the two sides are owned by different teams: the rule team owns the rule pack, and the compliance or MRM team owns the catalog of properties it must satisfy. This template mirrors that shape. It authors a property catalog separately from the ruleset, then runs one audit per property and produces a single report with a verdict for each — the rule holds (PASS), the rule is broken with example applicants shown (FAIL), or the audit could not decide (INCONCLUSIVE). The bundled ruleset carries a deliberate bug so the report comes back mixed rather than all-clear: the manual-review rule flags only seniors, while the frailty rule counts anyone senior or with a chronic condition, so chronic non-seniors slip past review. The mixed report is the point — a single run separates the properties the ruleset satisfies from the ones it violates. And rather than a single example per failure, the audit returns several distinct counterexamples so the reviewer can see the shape of the failure across ages, conditions, and coverage levels without probing by hand.

**Reasoning approach:** each property is audited with prescriptive reasoning — a constraint-satisfaction model whose counterexample is the logical negation of the property, solved in multi-solution mode so the solver returns several distinct applicants that break the rule (or proves none exist).

## Who this is for

- Insurance actuaries and underwriting governance teams auditing rule libraries
- RegTech / compliance audit harnesses verifying property entailment over rule packs
- Model Risk Management (MRM) reviewers performing rule-level verification before promotion
- Operations researchers learning property-entailment audit as a constraint satisfaction problem (CSP)

## What you'll build

- A batch audit report — one verdict (PASS, FAIL, or INCONCLUSIVE) per property, printed as a verdict matrix, distinguishing the rules the ruleset satisfies from the ones it breaks.
- Witness tables for every failing property: several distinct counterexample applicants that break the rule, spread across ages, conditions, and coverage bands.
- A constraint model of the ruleset itself — the applicant's attributes as free decisions and each rule as a derived indicator — built with prescriptive reasoning so a property is checked by asking the solver for any applicant that falsifies it.
- A separately-authored property catalog and a per-property audit routine, so adding a new property to check is a one-line change with no other code touched.

Built using **prescriptive reasoning** (constraint satisfaction with multi-solution enumeration on the MiniZinc solver).

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
- RelationalAI Python SDK (`relationalai == 1.1.0`)

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

6. Expected output. The audit processes the three bundled properties in turn, printing each verdict with its witness table (for FAILs), then a verdict matrix at the end. A few representative lines confirm a successful run:

   ```text
   ===== Auditing property: frail_implies_review =====
   Verdict: FAIL  (12 witness(es), status=OPTIMAL)
   ...
   Audit report (3 properties: 1 PASS, 2 FAIL, 0 INCONCLUSIVE)
   ```

   FAIL is the audit's finding about the ruleset, not a template error; a PASS means the solver proved no counterexample exists. The full printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
underwriting_audit/
├── README.md            # this file
├── runbook.md           # analyst paste-test walkthrough
├── pyproject.toml       # dependencies
├── underwriting_audit.py # main script (ontology, decisions, rule pack, property catalog, audit loop)
└── data/
    ├── age_buckets.csv    # representative applicant ages
    └── coverage_bands.csv # representative coverage levels
```

**Start here:** `underwriting_audit.py` runs the whole batch audit end to end.

## Sample data

The two small reference files describe the applicant space the audit searches over. They are the dimensions of an applicant, not a population of applicants — the solver picks values from them on every solution.

- `data/age_buckets.csv` — 4 representative ages (28, 45, 55, 72), three below the 70-year senior threshold and one above, with the columns `id` and `age_years`.
- `data/coverage_bands.csv` — 4 coverage levels ($100k, $250k, $500k, $1M), with the columns `id` and `coverage_dollars`.

Both files need dense, contiguous `id` values (the audit checks this before solving), because the decision-variable bounds run from the minimum to the maximum id and the rules iterate over the reference rows in between.

## Model overview

Rather than a table of applicants, the model has one applicant slot described by free decisions the solver fills in, plus derived indicators that encode each rule. Two reference concepts, `AgeBucket` and `CoverageBand`, supply the values the decisions can take.

- **Key entities**: `AgeBucket` and `CoverageBand` (reference rows loaded from CSV); the applicant is represented by scalar decisions rather than a concept.
- **Primary identifiers**: `AgeBucket` and `CoverageBand` are each identified by an integer `id`.
- **Important invariants**: reference ids are dense and contiguous; the free decisions `age_bucket_id`, `has_chronic`, and `coverage_band_id` select one reference row (or a binary flag); the rule indicators `is_senior`, `is_frail`, and `is_manual_review` are binaries pinned to those decisions by the rule pack.

### AgeBucket

A representative applicant age. The senior-indicator rule iterates over these rows to decide whether the chosen age counts as senior.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Bucket identifier, loaded from `data/age_buckets.csv` |
| `age_years` | Integer | No | Representative age for the bucket |

### CoverageBand

A representative coverage level. It is a spread-only dimension in the bundled ruleset — no rule reads it — so it diversifies the witnesses across coverage levels and leaves room for coverage-based rules later.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Band identifier, loaded from `data/coverage_bands.csv` |
| `coverage_dollars` | Integer | No | Coverage amount in dollars |

### Decisions and indicators

The applicant is described by scalar decisions and rule indicators declared as standalone relationships rather than properties on a concept, because there is exactly one applicant slot. The solver assigns all of them on every solution.

| Relationship | Reads as | Notes |
|---|---|---|
| `age_bucket_id` | which age bucket the applicant is in | Free decision, bounded to the `AgeBucket` id range |
| `has_chronic` | whether the applicant has a chronic condition | Free binary decision |
| `coverage_band_id` | which coverage band the applicant is in | Free decision, bounded to the `CoverageBand` id range |
| `is_senior` | the applicant is at or above the senior age threshold | Derived binary, pinned by the senior rule |
| `is_frail` | the applicant is senior or has a chronic condition | Derived binary, pinned by the frailty rule (a logical OR) |
| `is_manual_review` | the applicant is routed to manual review | Derived binary; the bundled (buggy) rule pins it to `is_senior` only |

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

### Use your own data

- Replace `data/age_buckets.csv` and `data/coverage_bands.csv` with the reference dimensions of your own applicant space, keeping the `id` plus attribute columns and dense, contiguous ids.
- Adapt to a different regulated domain by editing the rule pack and the property catalog. The same shape carries to bank anti-money-laundering rules, healthcare prior-authorization, manufacturing segregation-of-duties, and SaaS retention — each is a set of binary indicators and a catalog of properties they must satisfy. Real rule packs in these domains often run to hundreds of rules; if a single audit's rule count exceeds PyRel's per-model `"Rules created in a loop"` threshold, decompose it into smaller property-scoped packs.

### Tune parameters

- Raise `MAX_WITNESSES` to surface more counterexamples per failing property. Production audits typically want 50 to 500 witnesses per failure to cover the rule pack's failure modes. Raising it past the size of the feasible set makes the solver exhaust every distinct case.
- The solve time cap is `time_limit_sec` (default 60) in the `problem.solve("minizinc", ...)` call inside `run_audit(...)`.

### Extend the model

- Add a property to the catalog by appending a `(name, description, counterexample_builder)` tuple to `PROPERTIES`. The builder takes the audit session and returns the property's counterexample ICs — the logical negation of the property. For example, to audit "no senior is in the cheapest coverage band", add `("no_senior_cheap_band", "no senior is in the cheapest coverage band", lambda s: [s.model.require(s.is_senior == 1), s.model.require(s.coverage_band_id == 1)])`. `run_audit` picks it up automatically; no other code changes.
- Add a scoped property by adding a `s.model.where(<data filter>).require(<decision constraint>)` IC alongside the unconditional counterexample ICs. `chronic_under_50_implies_review` shows the pattern: the `where` iterates `AgeBucket` rows outside the scope (a pure data filter), and the `require` body forbids the applicant decision from picking those rows. PyRel rejects decision-variable expressions inside `where`, so the decision-variable constraint must live in `require`.
- Audit a corrected ruleset by changing the buggy rule inside `_build_session()`: the manual-review rule pins `is_manual_review == is_senior`; change the right-hand side to `is_frail`. With the fix in place, the failing verdicts in the bundled run turn to PASS and the verdict matrix reports 3 PASS, 0 FAIL.
- Add more rule indicators by introducing additional decisions and their defining ICs inside `_build_session()`, then appending them to `rule_pack`. A logical AND over binaries is encoded with the dual of the OR pattern used for `is_frail`.
- Switch from "any counterexample" to "worst counterexample" by adding a `problem.minimize(...)` over a violation-severity score with `solution_limit=1`, when triage capacity is limited and you want the single most severe failure first.

### Extend to many applicants

- Extend to a fleet of applicants by reintroducing an `Applicant` concept inside `_build_session()` and lifting each scalar decision to a property on it, then scoping every IC — including each property's counterexample ICs — to that concept. The scalar shape used here is the right default for the single-applicant search; the per-applicant shape becomes necessary once the audit binds to a real applicant table.

### Scale up / productionize

- Real rule packs are large. The template rebuilds a fresh model per audit precisely so the per-model rule count stays bounded across many properties; keep that factory pattern as the pack grows, and split oversized packs into property-scoped subsets.
- Cross-check the encoding against the source rule pack before trusting a PASS: a pass is sound only for the rules and properties as encoded, so a missing rule arm can pass silently. See the Troubleshooting notes on audit soundness.

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

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, and constraints that model the ruleset.
- [Constraint satisfaction and multi-solution search](https://docs.relational.ai/) — solving in enumeration mode and reading back several solutions.

### Language / modeling reference

- [Integrity constraints and `require`](https://docs.relational.ai/) — encoding rule bodies and property negations as ICs.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, relationships, and the standalone scalar-relationship shape used for the applicant decisions.

### CLI / SDK guides

- [RelationalAI Python SDK](https://docs.relational.ai/) — installing and configuring the `relationalai` package and connecting to Snowflake.

## Support

- File issues at the RelationalAI templates repository.
