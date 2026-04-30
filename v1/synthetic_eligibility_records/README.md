---
title: "Synthetic Eligibility Records"
description: "Generate K distinct, internally consistent member eligibility records per solve using a CSP solver in multi-solution mode: each record satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Rules
  - Prescriptive
tags:
  - constraint-programming
  - multi-solution
  - synthetic-data
  - test-data-generation
  - healthcare
  - regtech
---

# Synthetic Eligibility Records

## What this template is for

Healthcare payer engineering teams, RegTech rule-certification harnesses, and claim-engine fuzzers all need *batches* of internally consistent member eligibility records to test against. Real beneficiary data is gated behind PII rules; sampled production data carries cohort biases; hand-crafted fixtures drift out of sync with the regulations they are meant to exercise. The right alternative is a constrained generative model: declare the eligibility rules once, ask the solver for K records that satisfy every rule simultaneously.

Synthetic-data tooling consumers want a *batch* of K diverse records per solve, not one. A single record can't expose a CFD cascade or a network-attribution corner case; K records spread across age bands, plan types, and provider networks can. This template encodes member eligibility as a constraint satisfaction model and runs the solver in multi-solution mode: pass `solution_limit=K` to `problem.solve(...)`, then enumerate each generated record via `Variable.values(solution_index, value)`. The output is one row per generated member -- ready to drop into a test fixture, a fuzzing oracle, or a coverage matrix.

The rule structure here is drawn from the public [CMS Medicare](https://www.cms.gov/Medicare/Medicare) and [NCQA](https://www.ncqa.org/) regulatory shape: age-by-plan-type CFDs (over-65 must be on Medicare-Advantage; under-65 must not) and PCP-network attribution (the chosen primary-care provider must be in-network for the chosen plan). The same template structure -- decision-valued tuple per record, reference-data lookups via composition, multi-solution enumeration -- applies to any rule-driven synthetic-data domain: KYC member records (banking), tenant lease attributes (proptech), shipment manifests (logistics).

## Who this is for

- Healthcare payer engineering teams building eligibility-engine test suites
- RegTech / compliance-rules certification harnesses needing rule-coverage fixtures
- Claim-engine and adjudication-engine fuzzers needing diverse, valid input batches
- Data-platform engineers building synthetic-data pipelines that respect domain invariants

## What you'll build

- A constraint model with three integer decision properties on a singleton `Member`: `age_bucket_id`, `plan_id`, `provider_id` -- each solution returns one feasible filling of those three slots
- A small reference table of representative ages (`AgeBucket`) so age is a categorical decision rather than a per-year integer; this keeps every decision domain compact and similar in size, which is what makes the multi-solution enumeration produce structurally diverse records across age, plan, and network
- A pair of CFD ICs encoding the two arms of the age-by-plan rule using the forbidden-pair `implies(Member.plan_id != P.id, ...)` idiom -- safe under the CSP rewriter
- A PCP-network attribution IC iterating over reference-data `(Plan, Provider)` tuples in different networks and forbidding the cross-network combination
- **Multi-solution enumeration as the primary code path**: `problem.solve(..., solution_limit=MAX_RECORDS)` runs the search in enumeration mode; `Variable.values(solution_index, value)` joins the three decision variables on a shared solution index to reconstruct each record
- Post-solve verification via `problem.verify()` (note: every IC in this model is `implies`-bodied -- they are all solver-only -- so `verify()` is called with no arguments to confirm the relational engine has nothing left to check)

## What's included

- `synthetic_eligibility_records.py` -- main script with ontology, decisions, constraints, and solver call
- `data/age_buckets.csv` -- 4 representative ages spanning the adult/senior split (2 under 65, 2 at or above)
- `data/plans.csv` -- 3 plans (PPO, HMO, MedicareAdvantage) each on its own network; the unused `max_dependents` column is retained as a hook for the dependent-cap extension described in *Customize this template*
- `data/providers.csv` -- 4 primary-care providers (1 PPO, 1 HMO, 2 Medicare) so each plan-network has at least one in-network PCP and the bundled K=8 enumeration spans all three plans
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
   curl -O https://docs.relational.ai/templates/zips/v1/synthetic_eligibility_records.zip
   unzip synthetic_eligibility_records.zip
   cd synthetic_eligibility_records
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
   python synthetic_eligibility_records.py
   ```

6. Expected output. With `MAX_RECORDS = 8` the solver enumerates up to 8 distinct feasible member records and each row carries its `solution` index. Solver build strings, exact wall times, and per-solution ordering will vary; the structure of the output and the *set* of returned records is stable:
   ```text
   Solve result:
   • status: SOLUTION_LIMIT
   • objective: 0
   • solve time: 0.08s
   • num_points: 8
   • solver: MiniZinc_nothing

   Generated member records (up to 8 per run):
      solution  age_years          plan_type  network      provider
   0         0         78  MedicareAdvantage        3   Dr_Senior_B
   1         1         78  MedicareAdvantage        3   Dr_Senior_A
   2         2         68  MedicareAdvantage        3   Dr_Senior_B
   3         3         68  MedicareAdvantage        3   Dr_Senior_A
   4         4         50                HMO        2   Dr_East_HMO
   5         5         28                HMO        2   Dr_East_HMO
   6         6         50                PPO        1  Dr_North_PPO
   7         7         28                PPO        1  Dr_North_PPO
   ```

   Each solution row is one full member: a representative age, a plan type, a primary-care provider in the plan's network. The bundled data admits exactly 8 feasible records, so the K=8 batch surfaces all three plans and all four age buckets:

   - The age-by-plan CFD is visible: every record with `age_years >= 65` is on `MedicareAdvantage`; every record with `age_years < 65` is on a non-Medicare plan (PPO or HMO).
   - The PCP-network attribution is visible: every `provider` row is in the network of its `plan` row -- Senior providers on network 3 with Medicare, `Dr_East_HMO` on network 2 with HMO, `Dr_North_PPO` on network 1 with PPO.

   The `status: SOLUTION_LIMIT` line means the solver hit `MAX_RECORDS = 8` before exhausting the search space; for the bundled data the entire feasible set happens to be exactly 8 records, so raising `MAX_RECORDS` to 9 or higher will flip the status to `OPTIMAL` without surfacing additional records.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── synthetic_eligibility_records.py
└── data/
    ├── age_buckets.csv
    ├── plans.csv
    └── providers.csv
```

## How it works

The solver decides three integer attributes of a singleton `Member` -- age bucket, plan, provider -- subject to the eligibility rules. Each solution returned by the solver is one feasible filling of those three slots; multi-solution mode enumerates K of them per solve.

**Categorical age via a small reference table.** Age is *not* a per-year integer decision: instead, the `AgeBucket` reference table holds five representative ages, and `Member.age_bucket_id` picks one. The CFDs walk through `AgeBucket.age_years` to compare against the seniority threshold. This keeps the age decision domain at the same order of magnitude as the plan and provider domains, which is what makes the solver's enumeration produce structurally diverse records across all three dimensions:

```python
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
```

**Forbidden-pair encoding for CFDs.** The Medicare-Advantage CFD has two arms: senior implies Medicare, non-senior implies non-Medicare. Each arm is encoded as a *forbidden pair* iteration. The where clause filters reference-data tuples at relational time (here, all `(Plan, AgeBucket)` pairs that violate the arm); the implies inside the require gates on the decision-valued match. This sidesteps the rewriter's restriction on decision variables in `where` clauses (`where(P.id == Member.plan_id)` would not parse; iteration over P and AB happens at relational time, the decision check goes inside `implies`):

```python
P = Plan.ref()
AB = AgeBucket.ref()
senior_must_medicare_ic = model.where(
    P.plan_type != "MedicareAdvantage",
    AB.age_years >= SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AB.id,
        Member.plan_id != P.id,
    )
)
```

The non-senior arm uses the same shape with `P.plan_type == "MedicareAdvantage"` and `AB.age_years < SENIOR_THRESHOLD_YEARS` in the where.

**PCP-network attribution as forbidden cross-network pairs.** The chosen provider's network must equal the chosen plan's network. Same forbidden-pair shape: iterate over `(Plan, Provider)` tuples in *different* networks at relational time, and forbid that combination if the member picks both:

```python
P = Plan.ref()
PR = Provider.ref()
network_match_ic = model.where(P.network_id != PR.network_id).require(
    implies(Member.plan_id == P.id, Member.provider_id != PR.id)
)
```

**Multi-solution enumeration via `Variable.values(solution_index, value)`.** Capturing the variable subconcept from `solve_for(...)` exposes a `.values(sol_idx, val)` relationship that indexes the per-solution outputs. Joining the three decision variables on a shared `sol_idx` reconstructs each record; reference-data lookups (`bucket_ref.age_years`, `plan_ref.plan_type`, `provider_ref.name`) follow naturally:

```python
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_RECORDS)

sol_idx = Integer.ref()
ab_v = Integer.ref()
pid_v = Integer.ref()
prv_v = Integer.ref()
bucket_ref = AgeBucket.ref()
plan_ref = Plan.ref()
provider_ref = Provider.ref()
model.select(
    sol_idx.alias("solution"),
    bucket_ref.age_years.alias("age_years"),
    plan_ref.plan_type.alias("plan_type"),
    plan_ref.network_id.alias("network"),
    provider_ref.name.alias("provider"),
).where(
    age_bucket_var.values(sol_idx, ab_v),
    plan_id_var.values(sol_idx, pid_v),
    provider_id_var.values(sol_idx, prv_v),
    bucket_ref.id == ab_v,
    plan_ref.id == pid_v,
    provider_ref.id == prv_v,
).inspect()
```

The variable subconcept exposes a back-pointer named after the entity in its property: `age_bucket_var.member` walks back to the `Member` instance; on a singleton-`Member` model that is uninteresting, but the same shape carries over to multi-member templates where each row of `.values(...)` is one (Member, solution) pair.

## Customize this template

- **Use your own plans and providers** by replacing the two CSV files. The constraint structure does not change; the integer ID columns stay required (the script uses them for the `Member.plan_id` / `Member.provider_id` decision domains).
- **Raise the solution limit on a real catalogue.** The bundled `MAX_RECORDS = 8` is sized for the demo. Production test suites typically want 100--10,000 records per solve. `time_limit_sec` is your safety net -- enumeration stops when either the limit or the budget is reached.
- **Change the target year** by adjusting `TARGET_YEAR`. The senior threshold (`SENIOR_THRESHOLD_YEARS = 65`) is read from the CMS Medicare regulation; widen or narrow the seniority gate by changing it.
- **Add coverage-period interval containment** by introducing two more decisions (`coverage_start_days` and `coverage_end_days` as integer days from a notional epoch) and an IC asserting `start <= TARGET_DATE_DAYS <= end` together with a minimum coverage duration. This adds the temporal-interval-containment shape over decision-side bounds, which is useful for fuzzing claim-adjudication date logic.
- **Add a coverage-period-non-overlap-per-(member, plan) IC** by introducing pairwise refs over coverage periods (cf. the `synthetic_order_lifecycle` template's pairwise temporal ICs) and asserting `(start_a > end_b) + (start_b > end_a) >= 1` for each (member, plan) pair.
- **Switch from "all feasible" to "smallest violating instance"** by adding `problem.minimize(...)` over a violation count, dropping a positive IC, and using `solution_limit=1`. This is the negative-mode use case from the constrained-generative-models literature -- handy for finding the cheapest counter-example to a candidate rule.
- **Adapt to a different regulatory regime** by editing the CFD predicates and the network-attribution IC. The shape is identical for KYC member records (banking AML), tenant lease attributes (proptech), shipment manifests (logistics customs) -- declare the rules as forbidden-pair iterations, ask the solver for K diverse records.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The reference data may not admit any feasible record. Confirm at least one plan has `max_dependents >= 0`, at least one provider exists in each plan's network, and the senior-arm of the CFD is satisfiable (a Medicare-Advantage plan must exist if any age >= 65 will be selected).
- Mismatched networks: if `plans.csv` and `providers.csv` reference network IDs that don't intersect, the PCP-network attribution IC has no satisfying assignment. Confirm every `Plan.network_id` value appears in at least one `Provider.network_id` row.
- Out-of-range bounds: tightening `AGE_MIN_YEARS` or `AGE_MAX_YEARS` past the senior threshold can make one arm of the CFD unsatisfiable. If `AGE_MAX_YEARS < 65`, the senior arm has no satisfying birth year, so all picked plans must be non-Medicare; if your data has only Medicare plans, this turns infeasible.

</details>

<details>
  <summary>How many records will the solver return?</summary>

- Up to `MAX_RECORDS` (8 by default) or however many feasible records exist in the reference data, whichever is smaller. `problem.num_points()` reports the actual count after the solve; `solve_info()` reports `status: SOLUTION_LIMIT` when the limit was hit (more records available) and `status: OPTIMAL` when the search has been exhausted.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of returned records may also shift if MiniZinc's branching heuristics see new ties. Treat the `solution` column as a label, not a ranking.
- The K returned records are guaranteed to be *distinct* on at least one decision (birth year, plan, provider, or dependent count) but not maximally diverse: you may see two records that share three of four slots and only differ on birth year by one. For broader spread, restrict birth-year domain to a smaller set of stratified buckets, or add a desirability score and switch to optimisation.

</details>

<details>
  <summary>Adding a where-side filter on a decision variable raises <code>ValueError: Unexpected SymbolicNode result</code></summary>

- `model.where(...)` filters at relational time only -- decision variables are not legal inside it. The rewriter raises this error when it encounters a decision-valued comparison in a `where` clause.
- Move the decision condition into `implies` and use a tautological relational filter (or a real one) to scope any reference-data refs the IC needs. For example, replace `model.where(P.id == Member.plan_id).require(Member.num_dependents <= P.max_dependents)` with `model.where(P.max_dependents >= 0).require(implies(Member.plan_id == P.id, Member.num_dependents <= P.max_dependents))`.
- See the four constraint definitions in `synthetic_eligibility_records.py` for the canonical idiom.

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
- HiGHS is not appropriate here -- this is a discrete satisfaction model with categorical decisions and structural propagation, not LP/MILP.

</details>
