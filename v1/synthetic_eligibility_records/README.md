---
title: "Synthetic Eligibility Records"
description: "Generate K distinct, internally consistent member eligibility records per solve using a CSP solver in multi-solution mode: each record satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Rules-based
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
- A small reference table of representative ages (`AgeBucket`) so age is a categorical decision rather than a per-year integer; this keeps every decision domain compact and similar in size, which is what makes the multi-solution enumeration produce structurally varied records across age, plan, and network
- A pair of CFD ICs encoding the two arms of the age-by-plan rule using the forbidden-pair `implies(Member.age_bucket_id == AgeBucket.id, Member.plan_id != Plan.id)` idiom -- safe under the CSP rewriter
- A PCP-network attribution IC iterating over reference-data `(Plan, Provider)` tuples in different networks and forbidding the cross-network combination
- A pre-solve dense-ID check on `plans.csv`, `providers.csv`, and `age_buckets.csv` so the solver's integer decision bounds line up with the reference rows the CFDs iterate over (sparse IDs would let the solver pick a value with no matching row, leaving the rules unconstrained for that record and silently dropping it from the post-solve display join)
- **Multi-solution enumeration as the primary code path**: `problem.solve(..., solution_limit=MAX_RECORDS)` runs the search in enumeration mode; `Variable.values(solution_index, value)` joins the three decision variables on a shared solution index to reconstruct each record
- An empty-result branch driven by `solve_info().num_points`: when no feasible record exists, the script prints a diagnostic instead of hard-failing, which is the right shape for a reusable generator. (No `problem.verify()` call: every IC uses `implies`, which is solver-only -- passing implies-bodied ICs to `verify()` returns silently-OK without actually evaluating them, so the convention is that they must NOT be passed. The CFD and network-attribution invariants are directly visible in the expected-output block in the Quickstart: every record's `age_years` vs `plan_type` and every record's `network` vs `provider` are printed side-by-side.)

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

6. Expected output. With `MAX_RECORDS = 16` and a bundled feasible set of 8 records, the solver exhausts the search space and returns status `OPTIMAL` with all 8 records. Each row carries its `solution` index. Solver build strings, exact wall times, and per-solution ordering will vary; the structure of the output and the *set* of returned records is stable:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 0
   • solve time: 0.12s
   • num_points: 8
   • solver: MiniZinc_unknown

   Generated member records (up to 16 per run):
   solution age_years         plan_type plan_network provider_network     provider
          0        78 MedicareAdvantage            3                3  Dr_Senior_B
          1        68 MedicareAdvantage            3                3  Dr_Senior_B
          2        78 MedicareAdvantage            3                3  Dr_Senior_A
          3        68 MedicareAdvantage            3                3  Dr_Senior_A
          4        28               HMO            2                2  Dr_East_HMO
          5        50               HMO            2                2  Dr_East_HMO
          6        50               PPO            1                1 Dr_North_PPO
          7        28               PPO            1                1 Dr_North_PPO
   ```

   Each solution row is one full member: a representative age, a plan type, a primary-care provider in the plan's network. The bundled data admits exactly 8 feasible records, so the K=16 cap is more than enough -- the solver returns the full feasible set and `status: OPTIMAL` reports the search is exhausted.

   - The age-by-plan CFD is visible: every record with `age_years >= 65` is on `MedicareAdvantage`; every record with `age_years < 65` is on a non-Medicare plan (PPO or HMO).
   - The PCP-network attribution is visible: every record's `plan_network` equals its `provider_network` -- Senior providers on network 3 with Medicare, `Dr_East_HMO` on network 2 with HMO, `Dr_North_PPO` on network 1 with PPO.

   On a real catalog the feasible set is typically much larger than `MAX_RECORDS`; the solver then returns `status: SOLUTION_LIMIT` once the K cap is hit, and `num_points` reports how many records came back.

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

**1. Categorical age via a small reference table.** Age is *not* a per-year integer decision: instead, the `AgeBucket` reference table holds four representative ages, and `Member.age_bucket_id` picks one. The CFDs walk through `AgeBucket.age_years` to compare against the seniority threshold. This keeps the age decision domain at the same order of magnitude as the plan and provider domains, which is what makes the solver's enumeration produce structurally varied records across all three dimensions:

```python
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
```

**2. Forbidden-pair encoding for CFDs.** The Medicare-Advantage CFD has two arms: senior implies Medicare, non-senior implies non-Medicare. Each arm is encoded as a *forbidden pair* iteration. The where clause filters reference-data tuples at relational time (here, all `(Plan, AgeBucket)` pairs that violate the arm); the implies inside the require gates on the decision-valued match. This sidesteps the rewriter's restriction on decision variables in `where` clauses (`where(Plan.id == Member.plan_id)` would not parse; iteration over `Plan` and `AgeBucket` happens at relational time, the decision check goes inside `implies`):

```python
senior_must_medicare_ic = model.where(
    Plan.plan_type != "MedicareAdvantage",
    AgeBucket.age_years >= SENIOR_THRESHOLD_YEARS,
).require(
    implies(
        Member.age_bucket_id == AgeBucket.id,
        Member.plan_id != Plan.id,
    )
)
```

The non-senior arm uses the same shape with `Plan.plan_type == "MedicareAdvantage"` and `AgeBucket.age_years < SENIOR_THRESHOLD_YEARS` in the where.

**3. PCP-network attribution as forbidden cross-network pairs.** The chosen provider's network must equal the chosen plan's network. Same forbidden-pair shape: iterate over `(Plan, Provider)` tuples in *different* networks at relational time, and forbid that combination if the member picks both:

```python
network_match_ic = model.where(Plan.network_id != Provider.network_id).require(
    implies(Member.plan_id == Plan.id, Member.provider_id != Provider.id)
)
```

**4. Multi-solution enumeration via `Variable.values(solution_index, value)`.** Capturing the variable subconcept from `solve_for(...)` exposes a `.values(sol_idx, val)` relationship that indexes the per-solution outputs. Binding the value slot directly to a reference Concept's `.id` walks the chosen ID back to that record's columns in one step:

```python
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_RECORDS)

sol_idx = Integer.ref()
records_df = (
    model.select(
        sol_idx.alias("solution"),
        AgeBucket.age_years.alias("age_years"),
        Plan.plan_type.alias("plan_type"),
        Plan.network_id.alias("plan_network"),
        Provider.network_id.alias("provider_network"),
        Provider.name.alias("provider"),
    )
    .where(
        age_bucket_var.values(sol_idx, AgeBucket.id),
        plan_id_var.values(sol_idx, Plan.id),
        provider_id_var.values(sol_idx, Provider.id),
    )
    .to_df()
    .sort_values("solution")
    .reset_index(drop=True)
)
print(records_df.to_string(index=False))
```

The variable subconcept exposes a back-pointer named after the entity in its property: `age_bucket_var.member` walks back to the `Member` instance (not exercised in this single-member template; useful for multi-member variants where each row of `.values(...)` is one `(Member, solution)` pair).

## Customize this template

- **Use your own plans and providers** by replacing the two CSV files. The constraint structure does not change; the integer ID columns stay required (the script uses them for the `Member.plan_id` / `Member.provider_id` decision domains) and IDs must remain dense and contiguous (the pre-solve check enforces this).
- **Raise the solution limit on a real catalog.** The bundled `MAX_RECORDS = 16` is sized so the solver exhausts the small demo feasible set; production test suites typically want 100--10,000 records per solve. `time_limit_sec` is your safety net -- enumeration stops when either the limit or the budget is reached.
- **Adjust the seniority gate** by changing `SENIOR_THRESHOLD_YEARS` (currently 65, the CMS Medicare threshold). Both arms of the age-by-plan CFD read this constant directly.
- **Add a dependent-count decision** by introducing a `Member.num_dependents` integer decision bounded by 0 and the per-plan `max_dependents` cap. The `plans.csv` `max_dependents` column is loaded by the script and `Plan.max_dependents` is declared as a Property hook for this extension. Add `Member.num_dependents = model.Property(...)` and a `problem.solve_for(Member.num_dependents, ...)` call, then encode the cap with the same forbidden-pair idiom: `model.where(Plan.max_dependents >= 0).require(implies(Member.plan_id == Plan.id, Member.num_dependents <= Plan.max_dependents))`.
- **Add a coverage-period decision pair** by introducing `coverage_start_days` and `coverage_end_days` as integer day decisions (counted from a notional epoch) bounded around a target date. The temporal-interval-containment shape needs two ICs: one requiring `Member.coverage_start_days <= TARGET_DATE_DAYS` and one requiring `TARGET_DATE_DAYS <= Member.coverage_end_days`, plus a minimum-duration IC `Member.coverage_end_days - Member.coverage_start_days >= MIN_DAYS`. This is useful for fuzzing claim-adjudication date logic.
- **Switch from "all feasible" to "smallest violating instance"** by adding `problem.minimize(...)` over a violation count, dropping a positive IC, and using `solution_limit=1`. This is the negative-mode use case from the constrained-generative-models literature -- handy for finding the cheapest counter-example to a candidate rule.
- **Adapt to a different regulatory regime** by editing the CFD predicates and the network-attribution IC. The shape is identical for KYC member records (banking AML), tenant lease attributes (proptech), shipment manifests (logistics customs) -- declare the rules as forbidden-pair iterations, ask the solver for K records.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE / no feasible eligibility records</summary>

- Check the solve status the script prints. `INFEASIBLE` means the reference data admits no record; `UNKNOWN` or `TIME_LIMIT` means the budget expired before a record was found (raise `time_limit_sec` or shrink the decision domains).
- For genuine infeasibility: each solution picks one age bucket, so the model is infeasible only when *every* bucket lands on a side of the senior threshold that has no compatible plan-and-provider combination. Confirm there is at least one Medicare-Advantage plan whose network has a provider iff any age bucket has `age_years >= SENIOR_THRESHOLD_YEARS`, and at least one non-Medicare plan whose network has a provider iff any bucket has `age_years < SENIOR_THRESHOLD_YEARS`. The pre-solve coverage check also warns on either-direction asymmetry between `plans.csv` and `providers.csv`; read the startup warnings before assuming the data is sound.

</details>

<details>
  <summary>ValueError: <code>&lt;file&gt;</code> <code>id</code> column must be dense and contiguous</summary>

- The pre-solve check ran on `plans.csv`, `providers.csv`, or `age_buckets.csv` and found gaps in the `id` column (the file name is included in the error message). The solver bounds each decision by `lower=min(id), upper=max(id)`; without dense IDs it can pick a value with no matching reference row, the relational-time `implies` rules gated on the matching row will not fire, and the post-solve display join will silently drop the record.
- Renumber the rows so IDs run consecutively from the minimum to the maximum (e.g., 1, 2, 3, ... or 10, 11, 12, ...).

</details>

<details>
  <summary>Warning: plan network(s) [...] have no providers in providers.csv</summary>

- The pre-solve coverage check found a `network_id` value in `plans.csv` that does not appear in any `providers.csv` row. The PCP-network-attribution IC forbids cross-network `(plan, provider)` combinations, so any record that picks one of the listed plans has no satisfying provider and that plan can never appear in a generated record. The model is still solvable from the records that pick the other plans -- this is a warning, not an error.
- Add at least one provider for the listed network(s), or remove the affected plan rows from `plans.csv`.

</details>

<details>
  <summary>Warning: provider network(s) [...] have no plans in plans.csv</summary>

- The script's symmetric coverage check found a `network_id` value in `providers.csv` that does not appear in any `plans.csv` row. The PCP-network-attribution IC forbids cross-network `(plan, provider)` combinations, so providers in those networks can never be matched to any plan and will never appear in a generated record. The model is still solvable -- this is a warning, not an error.
- Add a plan on the listed network(s) to make those providers reachable, or remove the dead provider rows from `providers.csv`.

</details>

<details>
  <summary>How many records will the solver return?</summary>

- Up to `MAX_RECORDS` (16 by default) or however many feasible records exist in the reference data, whichever is smaller. `solve_info().num_points` reports the actual count after the solve; `solve_info().status` reports `SOLUTION_LIMIT` when the limit was hit (more records available) and `OPTIMAL` when the search has been exhausted.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of returned records may also shift if MiniZinc's branching heuristics see new ties. Treat the `solution` column as a label, not a ranking.
- The K returned records are guaranteed to be pairwise *distinct* on at least one decision (age bucket, plan, or provider) but not maximally diverse and not ranked. For broader spread, raise `MAX_RECORDS` past the size of the feasible set so the solver exhausts every distinct case, or add stratification buckets and re-solve per stratum.

</details>

<details>
  <summary>Adding a where-side filter on a decision variable raises <code>ValueError: Unexpected SymbolicNode result</code></summary>

- `model.where(...)` filters at relational time only -- decision variables are not legal inside it. The rewriter raises this error when it encounters a decision-valued comparison in a `where` clause.
- Move the decision condition into `implies` and use a tautological relational filter (or a real one) to scope any reference-data Concepts the IC needs. For example, replace `model.where(Plan.id == Member.plan_id).require(Member.num_dependents <= Plan.max_dependents)` with `model.where(Plan.max_dependents >= 0).require(implies(Member.plan_id == Plan.id, Member.num_dependents <= Plan.max_dependents))`.
- See the three constraint definitions in `synthetic_eligibility_records.py` (`network_match_ic`, `senior_must_medicare_ic`, `non_senior_no_medicare_ic`) for the canonical idiom.

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
