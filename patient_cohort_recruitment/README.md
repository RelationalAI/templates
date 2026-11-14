---
title: "Patient Cohort Recruitment"
description: "Build a clinical-research cohort over a patient knowledge graph. It selects a small set of eligible patients that together span enough distinct genes, therapies, and adverse events for a study to generalize."
featured: false
experience_level: intermediate
industry: "Healthcare & Life Sciences"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - constraint-programming
  - knowledge-graph
  - subclass-closure
  - healthcare
  - clinical-research
---

## What this template is for

Clinical research and pharma R&D teams build patient cohorts to power studies. A typical ask: find patients who carry a mutation in a gene from a target pathway, received a therapy, and then developed an adverse event within a set window, and pick a handful of them so the cohort spans enough distinct genes, therapies, and toxicity profiles for the later analysis to generalize. Getting this right by hand is slow and error-prone, because eligibility depends on tracing an ontology and the cohort must be balanced across several dimensions at once.

The same shape recurs across knowledge-graph cohort and set-cover problems where eligibility is a rule over a labelled subgraph and the chosen set must span a minimum spread on several attributes: insurance claim audits (members spanning procedures and comorbidities), grant-applicant diversification (applicants spanning institutions, fields, and career stages), or security-alert triage (alerts spanning attack categories and asset classes).

**The template chains three RelationalAI reasoners on one ontology: the graph reasoner closes the gene pathway, relational rules derive per-patient eligibility and coverage, and the prescriptive reasoner selects a cohort that meets every coverage floor.**

## Who this is for

- Clinical research teams enrolling cohorts for pathway-targeted studies
- Pharma R&D teams running biomarker-driven feasibility analyses
- Healthcare data engineers building cohort-discovery pipelines on top of patient knowledge graphs
- Operations researchers learning multi-reasoner (Graph + Rules + CSP) composition over an OMOP / FHIR-class ontology

## What you'll build

- A gene ontology + patient knowledge graph: `Gene`, `GeneIsA`, `Patient`, `MutationEvent`, `TherapyEvent`, `AdverseEventOcc`, `Therapy`, `AdverseEvent`
- A Graph-reasoner closure of the kinase-pathway sub-ontology via `graph.reachable(full=True)`, producing a `KinaseGene extends Gene` sub-concept
- A 3-arity `Patient.qualifying_pair` relationship over `(Patient, TherapyEvent, AdverseEventOcc)` triples where the AE follows the therapy within `MAX_THERAPY_TO_AE_DAYS`, single-sourcing the AE-window predicate
- Pure-relational rules that derive sub-concepts `KinaseMutationCarrier`, `QualifyingPairPatient`, and the eligibility conjunction `EligiblePatient extends Patient`, plus per-axis coverage relations (`Patient.covers_kinase_gene`, `Patient.covers_therapy`, `Patient.covers_ae`) projected from `qualifying_pair`, and the coverable sub-concepts `CoverableGene`, `CoverableTherapy`, `CoverableAdverseEvent` scoped to eligible-patient coverage
- A constraint model with four binary decision streams targeting sub-concepts directly: `EligiblePatient.is_in_cohort` (eligible patients only), `CoverableGene.is_covered` (coverable kinase genes only), `CoverableTherapy.is_covered`, and `CoverableAdverseEvent.is_covered`
- Per-axis coverage upper-bound ICs that link `is_covered` to in-cohort patient decisions (`Sub.is_covered <= sum(EligiblePatient.is_in_cohort).per(Sub)`), and lower-bound ICs (`sum(Sub.is_covered) >= MIN_*`) that force the cohort to span enough distinct values
- Pre-solve Python invariants that catch silent-failure modes (duplicate keys, dangling foreign keys, missing kinase root, negative timestamps) before the solver runs
- A check in the report that stops unless the solve's `termination_status()` is `OPTIMAL`

## What's included

The bundled CSVs are illustrative, fully synthetic demo data (e.g. patient names `P_Alpha`...`P_Oscar`, fictional gene/therapy/AE labels) sized so the solve takes a few seconds; swap in your own ontology and patient KG to apply the template to real cohorts.

- `model/__init__.py` -- the deployed model: concepts, the Graph closure, the rules, the decisions and constraints, and the solve configuration. `rai models deploy --path model` deploys it to your Snowflake account, where each refresh runs the solve.
- `queries/cohort_report.py` -- the report, which reads the deployed model
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/genes.csv` -- 10 sample genes: 7 in the kinase pathway sub-ontology (a root plus two intermediate sub-roots and four leaves) and 3 unrelated metabolism genes
- `data/gene_is_a.csv` -- 8 `is_a` edges that lay out the kinase-pathway tree and a parallel unrelated tree
- `data/patients.csv` -- 15 synthetic patients with names and ages
- `data/mutation_events.csv` -- 26 illustrative mutation events spanning kinase and non-kinase genes; some patients carry only non-kinase mutations and are correctly excluded from the cohort
- `data/therapy_events.csv` -- 15 therapy events across 5 therapies
- `data/adverse_events.csv` -- 12 adverse-event occurrences across 4 AE terms; some patients have AEs outside the 90-day window from any therapy and are excluded by the qualifying-pair rule
- `data/therapies.csv` -- 5 therapy concepts (3 kinase inhibitors, 2 unrelated)
- `data/ae_terms.csv` -- 4 AE terms
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 2.1.1`)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.PATIENT_COHORT_RECRUITMENT_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.PATIENT_COHORT_RECRUITMENT_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/patient_cohort_recruitment.zip), unzip it, and enter the template directory:

   ```bash
   unzip patient_cohort_recruitment.zip
   cd patient_cohort_recruitment
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
       name: patient_cohort_recruitment_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.PATIENT_COHORT_RECRUITMENT               # published views and tables
     identity:
       internal_schema: <DB>.PATIENT_COHORT_RECRUITMENT_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.cohort_report
   ```

   ```text
   Solve result:
   • status: OPTIMAL

   Selected cohort:
      patient_id patient_name  age_years
   0           2      P_Bravo         61
   1           4      P_Delta         58
   2           5       P_Echo         69
   3           8      P_Hotel         49
   ```

   The report also prints the formulation, the gene closure, the eligible-patient set, and the per-axis coverage tally, and it stops unless the solve's termination status is OPTIMAL. Eight of the 15 patients are eligible (the seven excluded patients each fail either the kinase-mutation test or the qualifying-pair test within the 90-day window). Several four-patient cohorts hit the `MIN_GENES_COVERED = 3` / `MIN_THERAPIES_COVERED = 2` / `MIN_AES_COVERED = 2` floors; the solver returns one of them, so the specific cohort can vary across runs.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.PATIENT_COHORT_RECRUITMENT_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md
├── pyproject.toml
├── model/
│   └── __init__.py
├── queries/
│   └── cohort_report.py
└── data/
    ├── genes.csv
    ├── gene_is_a.csv
    ├── patients.csv
    ├── mutation_events.csv
    ├── therapy_events.csv
    ├── adverse_events.csv
    ├── therapies.csv
    └── ae_terms.csv
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.cohort_report` for the full three-stage pipeline (graph closure, rules, then the cohort-selection solve) end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled CSVs are illustrative, fully synthetic demo data (patient names `P_Alpha`...`P_Oscar`, fictional gene / therapy / adverse-event labels) sized so the pipeline runs end-to-end in a few seconds. The shape mirrors an OMOP / FHIR-class patient store: a gene ontology with `is_a` edges, plus event tables (mutations, therapies, adverse events) that reference patients and dictionary concepts by foreign key.

- **`genes.csv`** (10 rows) — 7 genes in the kinase-pathway sub-ontology (a root, two intermediate sub-roots, four leaves) and 3 unrelated metabolism genes.
- **`gene_is_a.csv`** (8 rows) — `is_a` edges (child, parent) laying out the kinase-pathway tree and a parallel unrelated tree.
- **`patients.csv`** (15 rows) — synthetic patients with names and ages.
- **`mutation_events.csv`** (26 rows) — mutation events spanning kinase and non-kinase genes; some patients carry only non-kinase mutations and are correctly excluded.
- **`therapy_events.csv`** (15 rows) — therapy events across 5 therapies.
- **`adverse_events.csv`** (12 rows) — adverse-event occurrences across 4 AE terms; some fall outside the 90-day window from any therapy and are excluded by the qualifying-pair rule.
- **`therapies.csv`** (5 rows) — therapy concepts (3 kinase inhibitors, 2 unrelated).
- **`ae_terms.csv`** (4 rows) — adverse-event terms.

Event timestamps are integer `t_days` (days since the patient's index date); a pre-solve pass validates unique keys, foreign-key integrity, the presence of the pathway root, and non-negative timestamps before the rules install.

## Model overview

One ontology threads all three stages: the graph closure writes a `KinaseGene` sub-concept, the rules derive eligibility and coverage sub-concepts, and the CSP scopes its decisions to those sub-concepts.

- **Key entities**: base concepts — `Gene` (an ontology node), `GeneIsA` (a gene-ontology `is_a` edge, stored child-to-parent), `Therapy` and `AdverseEvent` (small dictionary concepts), `Patient` (a patient), and the event tables `MutationEvent`, `TherapyEvent`, `AdverseEventOcc` (a mutation, therapy, or adverse-event observed in a patient at a point in time); derived sub-concepts — `KinaseGene` (genes reachable from the pathway root, from the graph closure), `KinaseMutationCarrier` and `QualifyingPairPatient` (the two eligibility halves), `EligiblePatient` (their conjunction, and the target of the `is_in_cohort` decision), and `CoverableGene`, `CoverableTherapy`, `CoverableAdverseEvent` (values coverable by an eligible patient, each the target of an `is_covered` decision).
- **Primary identifiers**: integer `id` on each base concept, loaded from the corresponding CSV; `GeneIsA` is keyed by the composite `(child_id, parent_id)`.
- **Important invariants**: every foreign key resolves (event tables reference real patients and dictionary concepts); event `t_days` values are non-negative; the pathway root gene exists; a sub-concept's membership *is* its predicate (a patient is eligible exactly when they are a `KinaseMutationCarrier` and a `QualifyingPairPatient`).

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline runs three stages in order: Graph closes the ontology, Rules lift the closure to patient-level facts, and the CSP solver selects the cohort.

```text
gene ontology → graph closure (KinaseGene) → rules (eligibility + coverage sub-concepts) → CSP cohort selection → deploy → report
```

**Graph reasoner: one call to close the ontology.** The `is_a` CSV is in OMOP / SNOMED convention (child -> parent), but the graph is built with source and destination swapped, so reachability from the pathway root flows *downwards* through the subclass tree onto every descendant gene. The full transitive closure (every ancestor-descendant pair) is materialized as a sub-concept `KinaseGene extends Gene` — the genes reachable from the configured pathway root.

**Rules: lift the closure to patient-level sub-concepts.** Pure relational arithmetic, no decisions. Predicates are encoded as sub-concepts — a patient's *membership* in `KinaseMutationCarrier`, `QualifyingPairPatient`, or `EligiblePatient` is the predicate itself, which downstream rules and the CSP test by a simple membership check. The AE-window predicate ("an adverse event follows a therapy within `MAX_THERAPY_TO_AE_DAYS`") is lifted once into a 3-arity `Patient.qualifying_pair` relationship, and the three downstream rules (eligibility, therapy coverage, AE coverage) all project from it — so redefining the qualifying pair is an edit to one rule rather than three. A patient is eligible exactly when they are both a kinase-mutation carrier and a qualifying-pair patient.

**Prescriptive reasoner: cohort selection as a CSP.** Decisions target the sub-concepts directly (`EligiblePatient.is_in_cohort`, `CoverableTherapy.is_covered`, and the gene/AE analogues), creating one binary variable per sub-concept row. The `Coverable*` sub-concepts are scoped to *eligible-patient* coverage, not any-patient coverage: a value covered only by ineligible patients would otherwise have no upper-bound constraint binding it and the solver could mark it covered for free. Scoping coverage to eligible patients, and scoping the decisions to `Coverable*`, ensures every `is_covered` decision has a real upper bound.

The CSP signature is coverage upper bound + per-pair lower bound + floor. For each coverable value, `is_covered` is bounded above by the number of in-cohort patients that cover it (an unsupported value can't be marked covered) and bounded below per pair by each covering in-cohort patient (any in-cohort patient covering it forces `is_covered` to 1). The two bounds pin the indicator to the actual coverage; the floor constraint (`sum(is_covered) >= MIN_*`) then forces the cohort to span at least the required number of distinct genes, therapies, and adverse events.

For the exact PyRel formulation, see `model/__init__.py`; `runbook.md` reproduces the three stages step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace the eight CSV files with your gene ontology and patient knowledge graph. The constraint structure does not change.
- If your ontology already stores `is_a` parent-to-child, drop the `parent` / `child` flip in the `Graph` constructor.
- If you don't have ontology data, define `KinaseGene` membership directly on the genes you care about and skip the Graph step.
- Anchor on a different ontology root by changing `KINASE_ROOT_GENE_ID`. Multi-pathway studies can run several queries with different roots and union the results.

### Tune parameters

- **Cohort target** — adjust `COHORT_SIZE` and the three `MIN_*_COVERED` floors at the top. Tightening any one shrinks the feasible region; setting `MIN_GENES_COVERED = COHORT_SIZE` forces every patient in the cohort to cover a distinct gene (rules out two patients with identical mutation patterns).
- **Qualifying window** — edit `MAX_THERAPY_TO_AE_DAYS`. The 90-day window is a common attribution choice for treatment-emergent AEs in oncology trials; some indications use 28 days for acute toxicity, others 180 days for late-onset events.

### Extend the model

- **Move from feasibility to optimization.** This template is a satisfaction model — any cohort that hits the floors is correct. To rank, add `problem.maximize(sum(CoverableGene.is_covered) + sum(CoverableTherapy.is_covered) + sum(CoverableAdverseEvent.is_covered))` to find the cohort with the broadest joint span, or `problem.minimize(sum(EligiblePatient.is_in_cohort * EligiblePatient.age_years))` for a younger cohort. MiniZinc / Chuffed handles both.
- **Add patient-level eligibility rules** — minimum age, treatment-naive status, organ-function thresholds — by adding more conjuncts to the `EligiblePatient` definition (or by introducing further `extends=[Patient]` sub-concepts). Each extra rule narrows the eligible set; the CSP automatically drops decisions for newly-ineligible patients.
- **Add cohort-level fairness rules.** A balanced-cohort study might require a minimum count from each of two demographic strata. Add a stratum property (`Patient.stratum`) and an IC `sum(EligiblePatient.is_in_cohort).per(EligiblePatient.stratum) >= MIN_PER_STRATUM` to enforce minimum representation per stratum. The decision-side aggregate must key on the sub-concept (`EligiblePatient`), not the parent (`Patient`).
- **Keep aggregates on a single sub-concept.** Aggregations over a decision must reference the sub-concept the decision was scoped to — mixing parent and sub-concept references in a single aggregate triggers a TypeError.

### Scale up / productionize

- For a live patient store, replace the `read_csv(...)` loads with `model.data(snowflake_table)` calls so the ontology reads directly from your OMOP / FHIR tables; the rules and CSP are unchanged.
- The pre-solve invariants (unique keys, foreign-key integrity, root presence, non-negative timestamps) become your first-pass data-quality gate on real feeds — keep them.
- The bundled data runs in seconds; larger cohorts scale to whatever the constraint solver's budget allows. Raise `time_limit_sec` in the `problem.configure(...)` call for bigger eligible sets.
- Pin `relationalai` (see Prerequisites) so runs stay reproducible across environments.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The data may not contain a feasible cohort under the current floors. Loosen one constraint at a time -- drop `MIN_GENES_COVERED`, drop `MIN_THERAPIES_COVERED`, lower `COHORT_SIZE` -- to confirm whether the data or a specific floor is the bottleneck.
- The kinase-pathway closure may be empty: if `KINASE_ROOT_GENE_ID` doesn't appear in the gene table, `KinaseGene` is empty and no patient can be eligible. Print the closure (`model.select(KinaseGene.id).inspect()`) before the solve to confirm.
- The eligible-patient set may be smaller than `COHORT_SIZE`. Print `EligiblePatient.id` before the solve; if fewer than `COHORT_SIZE` patients are eligible, lower the floor or relax the qualifying-pair window.
- Coverage floors may be unsatisfiable in principle: if the eligible patients only cover two distinct therapies, `MIN_THERAPIES_COVERED >= 3` is infeasible. Inspect the `Patient.covers_therapy` / `Patient.covers_kinase_gene` / `Patient.covers_ae` relations to see what's actually reachable.

</details>

<details>
  <summary>Multiple feasible cohorts exist; which one does the solver return?</summary>

- This is constraint satisfaction, not optimization. Any cohort that hits the floors is a correct answer; the solver is free to return different ones across runs.
- To enumerate cohorts (e.g., for clinical-team review), pass `solution_limit=N` to `problem.configure(...)` and iterate over `problem.num_points()` solutions.
- To pin a single answer, switch to optimization -- e.g. `problem.maximize(sum(CoverableGene.is_covered) + sum(CoverableTherapy.is_covered) + sum(CoverableAdverseEvent.is_covered))` returns the cohort with the broadest joint span.

</details>

<details>
  <summary>A coverable Y still appears as <code>is_covered = 1</code> with no in-cohort patient covering it</summary>

Two encoding pitfalls produce this symptom; both must be guarded against.

- **Pitfall 1 — `solve_for` targets the parent concept.** With a per-pair `where` in the upper-bound IC, rows that no patient covers have no IC asserted (the `where` yields no rows there) and `is_covered` floats free. *Fix:* target the sub-concept directly in `solve_for(CoverableGene.is_covered, ...)` so unbounded decisions never get created. If you accidentally drop the sub-concept (`solve_for(Gene.is_covered, ...)`), the symptom comes back -- restore the sub-concept target.
- **Pitfall 2 — `Coverable*` is scoped to any-patient coverage.** A kinase gene mutated only by patients with no qualifying therapy/AE pair sits in `Coverable*` but has no eligible covering patient in the upper-bound IC's `where` body, so its decision floats free again. *Fix:* scope `Coverable*` to *eligible-patient* coverage:

  ```python
  model.define(CoverableGene(Gene)).where(EligiblePatient.covers_kinase_gene(Gene))
  ```

  If you scope to `Patient.covers_kinase_gene` instead, the symptom comes back -- swap the sub-concept's `where` back to `EligiblePatient.covers_*`.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) to update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS is not appropriate here -- this is a discrete satisfaction model with categorical decisions and structural propagation, not LP/MILP.

</details>

## Learn more

**Cohort discovery and patient knowledge graphs** (the domain background for relational cohort enumeration on a labelled patient graph):
- Wang, W. et al., [*Building Patient Cohorts with NLP and Knowledge Graphs*](https://www.databricks.com/blog/building-patient-cohorts-nlp-and-knowledge-graphs). End-to-end pipeline shape, ontology-driven cohort enumeration.
- Xu et al., [*Enhanced pre-recruitment framework through KG + LLMs*](https://www.nature.com/articles/s41598-025-11876-0). Knowledge-graph-driven trial-eligibility screening.

**Subgraph and set-cover techniques** (the academic backbone for "find K nodes whose joint coverage spans enough labels"):
- McCreesh, Prosser & Trimble, [*The Glasgow Subgraph Solver*](https://link.springer.com/chapter/10.1007/978-3-030-51372-6_19). State-of-the-art constraint-based subgraph isomorphism.
- Caprara, Toth & Fischetti, [*Algorithms for the Set Covering Problem*](https://link.springer.com/article/10.1023/A:1018984712387). The classical IP/CP encoding behind the coverage upper-bound + lower-bound pattern.

**Healthcare data standards** (the data shapes the patient KG mirrors):
- OHDSI, [*OMOP Common Data Model v6*](https://ohdsi.github.io/CommonDataModel/). The standardised relational schema for observational patient data.
- HL7, [*FHIR R5*](https://hl7.org/fhir/R5/). The FHIR resource graph for clinical data exchange.

## Support

- File issues at the RelationalAI templates repository.
