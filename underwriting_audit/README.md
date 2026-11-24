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

- **Model**: the reference concepts, the scalar applicant decisions, the rule pack, the property catalog, and one counterexample search per property, in the `model/` package (`schema.py` declares the concepts, `source.py` loads the reference data, `reasoning.py` states the decisions, rules, and searches), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs one search per property.
- **Query**: `queries/audit_report.py`, which prints each property's verdict and witness table and the verdict matrix from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/age_buckets.csv` -- 4 representative ages (28, 45, 55, 72) -- three under the 70 senior threshold, one above
- `data/coverage_bands.csv` -- 4 coverage levels ($100k, $250k, $500k, $1M)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.UNDERWRITING_AUDIT_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.UNDERWRITING_AUDIT_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/underwriting_audit.zip), unzip it, and enter the template directory:

   ```bash
   unzip underwriting_audit.zip
   cd underwriting_audit
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: underwriting_audit_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.UNDERWRITING_AUDIT               # published views and tables
     identity:
       internal_schema: <DB>.UNDERWRITING_AUDIT_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs one counterexample search per property. Each refresh of the deployed model runs the searches again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.audit_report
   ```

   ```text
   ===== Auditing property: frail_implies_review =====
   Description: every frail applicant goes through manual review
   Verdict: FAIL  (12 witness(es), status=OPTIMAL)

   Witnesses (up to 16 per run):
       solution  age_years  has_chronic  coverage_dollars  is_senior  is_frail  is_manual_review
   0          0         55            1           1000000          0         1                 0
   1          1         45            1           1000000          0         1                 0
   ...

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

   FAIL is the audit's finding about the ruleset, not a template error; a PASS means the solver proved no counterexample exists. The report also prints each failing property's witness table; `runbook.md` walks through the audit step by step.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.UNDERWRITING_AUDIT_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
underwriting_audit/
├── README.md              # this file
├── runbook.md             # analyst paste-test walkthrough
├── pyproject.toml         # dependencies
├── model/
│   ├── __init__.py        # exports of the deployed model
│   ├── schema.py          # reference concepts
│   ├── source.py          # reference data and its checks
│   └── reasoning.py       # scalar decisions, rule pack, property catalog, one search per property
├── queries/
│   └── audit_report.py    # verdicts, witness tables, and verdict matrix from the deployed model
└── data/
    ├── age_buckets.csv    # representative applicant ages
    └── coverage_bands.csv # representative coverage levels
```

**Start here:** deploy with `rai models deploy --path model` and run `python -m queries.audit_report` for the full batch audit end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The two small reference files describe the applicant space the audit searches over. They are the dimensions of an applicant, not a population of applicants — the solver picks values from them on every solution.

- `data/age_buckets.csv` — 4 representative ages (28, 45, 55, 72), three below the 70-year senior threshold and one above, with the columns `id` and `age_years`.
- `data/coverage_bands.csv` — 4 coverage levels ($100k, $250k, $500k, $1M), with the columns `id` and `coverage_dollars`.

Both files need dense, contiguous `id` values (the model checks this when it loads, so a bad file stops the deploy), because the decision-variable bounds run from the minimum to the maximum id and the rules iterate over the reference rows in between.

## Model overview

Rather than a table of applicants, the model has one applicant slot described by free decisions the solver fills in, plus derived indicators that encode each rule. Two reference concepts, `AgeBucket` and `CoverageBand`, supply the values the decisions can take.

- **Key entities**: `AgeBucket` and `CoverageBand` (reference rows loaded from CSV); the applicant is represented by scalar decisions rather than a concept.
- **Primary identifiers**: `AgeBucket` and `CoverageBand` are each identified by an integer `id`.
- **Important invariants**: reference ids are dense and contiguous; the free decisions `age_bucket_id`, `has_chronic`, and `coverage_band_id` select one reference row (or a binary flag); the rule indicators `is_senior`, `is_frail`, and `is_manual_review` are binaries pinned to those decisions by the rule pack.

For the full concept and property definitions, see `model/schema.py` and `model/reasoning.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The template factors the audit into three artifacts. The scalar decisions that describe an applicant and the rule pack are declared once in the model. A property catalog pairs each property's name and description with a builder for its counterexample constraints. And one `Problem` per property in the catalog attaches the rule pack and that property's counterexample constraints and solves in multi-solution mode on each refresh of the deployed model. The query classifies each verdict from the published status and number of witnesses, reads back the witnesses, and prints a verdict matrix at the end.

An applicant is described entirely by free decisions the solver fills in — which age bucket they fall into, whether they have a chronic condition, which coverage band they sit in — rather than by a row in an applicant table. On top of those, three rule indicators (`is_senior`, `is_frail`, `is_manual_review`) are also modeled as decisions, so the property check can compare them directly. The rule pack pins each indicator to a function of the free decisions: the senior indicator turns on when the chosen age bucket is at or above the senior threshold; the frailty indicator is the logical OR of senior-or-chronic, encoded as the standard three-constraint arithmetic for OR over binaries; and the manual-review indicator is pinned by the bundled — deliberately buggy — rule to the senior indicator alone, omitting the chronic arm that the audit is designed to expose.

Each property in the catalog is checked by asserting its logical negation and asking the solver for any applicant that satisfies it. If the solver finds one, the property is violated (FAIL) and the assignment is a concrete counterexample; if it proves none exists, the property holds (PASS); if it cannot decide within the time budget, the verdict is INCONCLUSIVE. Scoped properties add a data-filtered constraint to restrict the sub-population searched. Solving in multi-solution mode returns several distinct counterexamples per failure, each read back through the solver's per-solution values so the reviewer sees the shape of the failure across ages, conditions, and coverage bands.

```text
reference CSVs → free decisions + rule indicators → rule pack → per-property: assert negation → solve → PASS/FAIL/INCONCLUSIVE + witnesses → verdict matrix
```

See `model/reasoning.py` and `queries/audit_report.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace `data/age_buckets.csv` and `data/coverage_bands.csv` with the reference dimensions of your own applicant space, keeping the `id` plus attribute columns and dense, contiguous ids.
- Adapt to a different regulated domain by editing the rule pack and the property catalog. The same shape carries to bank anti-money-laundering rules, healthcare prior-authorization, manufacturing segregation-of-duties, and SaaS retention — each is a set of binary indicators and a catalog of properties they must satisfy. Real rule packs in these domains often run to hundreds of rules.

### Tune parameters

- Raise `MAX_WITNESSES` in `model/reasoning.py` to surface more counterexamples per failing property. Production audits typically want 50 to 500 witnesses per failure to cover the rule pack's failure modes. Raising it past the size of the feasible set makes the solver exhaust every distinct case.
- The solve time cap is `time_limit_sec` (default 60) in the `problem.configure("minizinc", ...)` call in `model/reasoning.py`.

### Extend the model

- Add a property to the catalog by appending a `(name, description, counterexample_builder)` tuple to `PROPERTIES` in `model/reasoning.py`. The builder takes no arguments and returns the property's counterexample ICs — the logical negation of the property. For example, to audit "no senior is in the cheapest coverage band", add `("no_senior_cheap_band", "no senior is in the cheapest coverage band", lambda: [model.require(is_senior == 1), model.require(coverage_band_id == 1)])`. The loop below the catalog creates its `Problem`, and the query reports it; redeploy and no other code changes.
- Add a scoped property by adding a `model.where(<data filter>).require(<decision constraint>)` IC alongside the unconditional counterexample ICs. `chronic_under_50_implies_review` shows the pattern: the `where` iterates `AgeBucket` rows outside the scope (a pure data filter), and the `require` body forbids the applicant decision from picking those rows. PyRel rejects decision-variable expressions inside `where`, so the decision-variable constraint must live in `require`.
- Audit a corrected ruleset by changing the buggy rule in `model/reasoning.py`: the manual-review rule pins `is_manual_review == is_senior`; change the right-hand side to `is_frail`. With the fix in place, the failing verdicts in the bundled run turn to PASS and the verdict matrix reports 3 PASS, 0 FAIL.
- Add more rule indicators by introducing additional decisions and their defining ICs in `model/reasoning.py`, then appending them to `rule_pack`. A logical AND over binaries is encoded with the dual of the OR pattern used for `is_frail`.
- Switch from "any counterexample" to "worst counterexample" by adding a `problem.maximize(...)` over a violation-severity score and letting the solve finish `OPTIMAL`, when triage capacity is limited and you want the single most severe failure first; a time-limited solve returns only the most severe counterexample it found.

### Extend to many applicants

- Extend to a fleet of applicants by reintroducing an `Applicant` concept in `model/schema.py` and lifting each scalar decision to a property on it, then scoping every IC — including each property's counterexample ICs — to that concept. The scalar shape used here is the right default for the single-applicant search; the per-applicant shape becomes necessary once the audit binds to a real applicant table.

### Scale up / productionize

- Real rule packs are large. The template gives each property its own `Problem` because constraints on a `Problem` are add-only; as the pack grows, split oversized packs into property-scoped subsets.
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

- The check that runs when the model loads found gaps in the `id` column of `age_buckets.csv` or `coverage_bands.csv`, and stopped the deploy. The solver bounds the corresponding decision by `lower=min(id), upper=max(id)`; without dense IDs it can pick a value with no matching reference row, and the relational-time `implies` rules gated on the matching row will not fire -- leaving the rule indicator unconstrained for that solution.
- Renumber the rows so IDs run consecutively from the minimum to the maximum (e.g., 1, 2, 3, ... or 10, 11, 12, ...). Trailing or leading gaps are fine to delete; mid-table gaps are the problem.

</details>

<details>
  <summary>How many witnesses will the solver return?</summary>

- Up to `MAX_WITNESSES` (16 by default) or however many feasible witnesses exist, whichever is smaller. The deployed model publishes the actual count (`num_points`) and the termination status after each solve, and the verdict line prints both: the status is `SOLUTION_LIMIT` when the limit was hit and `OPTIMAL` when the search has been exhausted.
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
  <summary>Connection errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
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
