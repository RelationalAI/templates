---
title: "Patient Cohort Query"
description: "Build a clinical-research cohort over a patient knowledge graph using three reasoners: the Graph reasoner closes a kinase-pathway sub-ontology, relational rules lift the closure to per-patient eligibility and per-axis coverage facts, and a CSP solver picks K patients that jointly cover at least MIN_GENES distinct kinase genes, MIN_THERAPIES distinct therapies, and MIN_AES distinct adverse events."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Graph
  - Rules
  - Prescriptive
tags:
  - constraint-programming
  - knowledge-graph
  - subclass-closure
  - healthcare
  - clinical-research
---

# Patient Cohort Query

## What this template is for

Clinical research and pharma R&D teams build patient cohorts to power studies. A typical ask: *"find patients with a mutation in some gene from the kinase pathway who received a therapy and developed an adverse event within 90 days, and pick K of them so the cohort spans enough distinct genes, therapies, and toxicity profiles for the analysis to generalise."* The pieces are recognisable across healthcare data: a gene ontology with `is_a` edges defines the pathway, a patient knowledge graph carries mutations / therapies / adverse events with timestamps, and the cohort itself is a small set of patients chosen against multiple coverage criteria.

This template encodes that ask as a three-pillar pipeline. The **Graph** reasoner runs a single `reachable(full=True)` call to close `is_a` over the gene ontology, returning every gene in the kinase-pathway sub-ontology in one step. Pure relational **Rules** then lift the closure to per-patient eligibility (`has_kinase_mutation` and `has_qualifying_pair`) and to per-(patient, gene), per-(patient, therapy), and per-(patient, adverse-event) coverage facts. The **Prescriptive** reasoner (CSP, MiniZinc / Chuffed) selects the cohort: binary `is_in_cohort` decisions on eligible patients, plus `is_covered` indicators on the three coverage axes that the upper-bound ICs link back to the patient decisions.

The same pattern applies to other knowledge-graph cohort / set-cover problems where eligibility is a relational predicate over a labelled subgraph and the chosen set must witness a minimum spread on several attributes: insurance claim audits (find K members spanning N procedures and M comorbidities), grant-applicant diversification (find K applicants spanning institutions, fields, and career stages), security alert triage (find K alerts spanning attack categories and asset classes).

## Who this is for

- Clinical research teams enrolling cohorts for pathway-targeted studies
- Pharma R&D teams running biomarker-driven feasibility analyses
- Healthcare data engineers building cohort-discovery pipelines on top of patient knowledge graphs
- Operations researchers learning multi-pillar (Graph + Rules + CSP) composition over an OMOP / FHIR-class ontology

## What you'll build

- A gene ontology + patient knowledge graph: `Gene`, `GeneIsA`, `Patient`, `MutationEvent`, `TherapyEvent`, `AdverseEventOcc`, `Therapy`, `AdverseEvent`
- A Graph-reasoner closure of the kinase-pathway sub-ontology via `graph.reachable(full=True)`, producing the `Gene.is_kinase_member` set
- Pure-relational rules that derive `Patient.has_kinase_mutation`, `Patient.has_qualifying_pair`, `Patient.is_eligible`, plus per-axis coverage relations (`Patient.covers_kinase_gene`, `Patient.covers_therapy`, `Patient.covers_ae`) and coverable markers
- A constraint model with four binary decision streams: `Patient.is_in_cohort` (eligible patients only), `Gene.is_covered` (kinase genes the cohort can mutate), `Therapy.is_covered`, and `AdverseEvent.is_covered`
- Per-axis coverage upper-bound ICs that link `is_covered` to in-cohort patient decisions (`is_covered <= sum(is_in_cohort).per(...)`), and lower-bound ICs (`sum(is_covered) >= MIN_*`) that force the cohort to span enough distinct values
- Post-solve verification via `problem.verify()` confirming every IC holds in the returned solution

## What's included

- `patient_cohort_query.py` -- main script with concepts, the Graph closure, the rules, the decisions and constraints, and the solver call
- `data/genes.csv` -- 10 genes: 7 in the kinase pathway sub-ontology (a root plus two intermediate sub-roots and four leaves) and 3 unrelated metabolism genes
- `data/gene_is_a.csv` -- 8 `is_a` edges that lay out the kinase-pathway tree and a parallel unrelated tree
- `data/patients.csv` -- 15 patients with names and ages
- `data/mutation_events.csv` -- 26 mutation events spanning kinase and non-kinase genes; some patients carry only non-kinase mutations and are correctly excluded from the cohort
- `data/therapy_events.csv` -- 15 therapy events across 5 therapies
- `data/adverse_events.csv` -- 12 adverse-event occurrences across 4 AE terms; some patients have AEs outside the 90-day window from any therapy and are excluded by the qualifying-pair rule
- `data/therapies.csv` -- 5 therapy concepts (3 kinase inhibitors, 2 unrelated)
- `data/ae_terms.csv` -- 4 AE terms
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
   curl -O https://docs.relational.ai/templates/zips/v1/patient_cohort_query.zip
   unzip patient_cohort_query.zip
   cd patient_cohort_query
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
   python patient_cohort_query.py
   ```

6. Expected output (the bundled data has eight eligible patients and several feasible cohorts that hit the coverage floors -- the exact choice may vary across solver versions):
   ```text
   Kinase-pathway gene closure (reachable from KINASE_ROOT_GENE_ID):
     gene_id              gene_name
           1      KinasePathwayRoot
           2  SerineThreonineKinase
           3         TyrosineKinase
           4                   EGFR
           5                   HER2
           6                   BRAF
           7                   MEK1

   Per-patient eligibility (1 = both kinase mutation and qualifying pair):
      patient_id patient_name kinase_mutation qualifying_pair eligible
               1      P_Alpha               1               1        1
               2      P_Bravo               1               1        1
               3    P_Charlie               1               1        1
               4      P_Delta               1               1        1
               5       P_Echo               1               1        1
               6    P_Foxtrot            <NA>            <NA>     <NA>
               7       P_Golf               1               1        1
               8      P_Hotel               1               1        1
               9      P_India               1               1        1
              10     P_Juliet               1            <NA>     <NA>
              11       P_Kilo            <NA>            <NA>     <NA>
              12       P_Lima               1            <NA>     <NA>
              13       P_Mike            <NA>            <NA>     <NA>
              14   P_November               1            <NA>     <NA>
              15      P_Oscar               1            <NA>     <NA>

   Selected cohort:
     patient_id patient_name age_years
              1      P_Alpha        52
              3    P_Charlie        47
              4      P_Delta        58
              5       P_Echo        69

   Kinase-pathway genes covered by the cohort:
     gene_id gene_name
           4      EGFR
           5      HER2
           6      BRAF
           7      MEK1

   Therapies covered by the cohort:
     therapy_id    therapy_name
              1  EGFR_Inhibitor
              2  HER2_Inhibitor
              3   MEK_Inhibitor

   Adverse events covered by the cohort:
     ae_id         ae_term
         1            Rash
         2  Hepatotoxicity
         3  Cardiomyopathy
   ```

   Eight of the 15 patients are eligible. The kinase-pathway closure transitively covers the root, the two sub-roots, and all four leaves. The four-patient cohort spans all four leaf kinase genes, three of the three "real" kinase therapies, and three of three AE terms tied to those therapies, comfortably clearing the `MIN_GENES = 3 / MIN_THERAPIES = 2 / MIN_AES = 2` floors. `Statin` and `GLP1_Agonist` (therapies 4 and 5) and `Myalgia` (AE 4) appear in the data but are unreachable for any cohort because no eligible patient has a qualifying-pair on them -- the coverable markers correctly exclude them from the count.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── patient_cohort_query.py
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

## How it works

The pipeline runs three pillars in order: Graph closes the ontology, Rules lift the closure to patient-level facts, and the CSP solver selects the cohort.

**Graph reasoner: one call to close the ontology.** The `is_a` CSV is in OMOP / SNOMED convention (child -> parent), but the `Graph` constructor takes the same edge concept with `src_relationship=GeneIsA.parent` and `dst_relationship=GeneIsA.child` -- so reachability from a root flows downwards through the subclass tree onto every member. `reachable(full=True)` then returns every (ancestor, descendant) pair, which is the full transitive closure:

```python
ontology_graph = Graph(
    model, directed=True, weighted=False, node_concept=Gene,
    edge_concept=GeneIsA,
    edge_src_relationship=GeneIsA.parent,
    edge_dst_relationship=GeneIsA.child,
)
gene_reachable = ontology_graph.reachable(full=True)

Gene.is_kinase_member = model.Property(f"{Gene} kinase member if {Integer:k}")
KineRootGene = Gene.ref()
model.define(Gene.is_kinase_member(1)).where(
    KineRootGene.id == KINASE_ROOT_GENE_ID,
    gene_reachable(KineRootGene, Gene),
)
```

**Rules pillar: lift the closure to patient-level eligibility and per-axis coverage facts.** Pure relational arithmetic, no decisions. A patient has a kinase mutation if any mutation event hits a kinase-pathway-member gene; has a qualifying pair if a therapy and an AE share that patient with `0 <= ae.t_days - therapy.t_days <= 90`; is eligible if both. The per-axis coverage relations (`Patient.covers_kinase_gene`, `Patient.covers_therapy`, `Patient.covers_ae`) are joined the same way, with the therapy/AE coverage requiring participation in at least one qualifying pair so a therapy with no within-window AE doesn't count:

```python
model.define(Patient.has_qualifying_pair(1)).where(
    TE_pair.patient == Patient,
    AE_pair.patient == Patient,
    AE_pair.t_days - TE_pair.t_days >= 0,
    AE_pair.t_days - TE_pair.t_days <= MAX_THERAPY_TO_AE_DAYS,
)

model.define(Patient.is_eligible(1)).where(
    Patient.has_kinase_mutation == 1,
    Patient.has_qualifying_pair == 1,
)
```

**Prescriptive pillar: cohort selection as a CSP.** Decisions are scoped to the rows the rules established as meaningful: `is_in_cohort` only on `Patient.is_eligible == 1`, and each `is_covered` only on Y values that are *coverable* (some eligible patient covers them). Without the coverable scoping, `is_covered` decisions on never-covered Ys have no upper-bound IC -- the per-pair `where` in the upper-bound IC yields no rows there, the IC isn't asserted, and the variable floats free, letting the solver mark it covered to satisfy the lower bound trivially.

```python
problem.solve_for(
    Patient.is_in_cohort, type="bin",
    where=[Patient.is_eligible == 1],
    name=["is_in_cohort", Patient.id],
)
problem.solve_for(
    Therapy.is_covered, type="bin",
    where=[Therapy.is_coverable == 1],
    name=["therapy_covered", Therapy.id],
)
```

**Coverage upper bound + lower bound is the CSP signature.** For each coverable Y, `Y.is_covered` is bounded above by the number of in-cohort patients that cover it; the lower bound says at least `MIN_*` Ys must be covered. Together they force the solver to pick patients whose joint coverage spans enough distinct values. The per-axis pattern reads cleanly:

```python
gene_cover_ic = model.where(Patient.covers_kinase_gene(Gene)).require(
    Gene.is_covered <= sum(Patient.is_in_cohort).per(Gene)
)
gene_min_ic = model.require(sum(Gene.is_covered) >= MIN_GENES_COVERED)
```

All seven ICs are pure relational arithmetic, so `problem.verify()` re-evaluates every one in the returned solution -- no constraint is solver-only.

## Customize this template

- **Use your own data** by replacing the eight CSV files with your gene ontology and patient knowledge graph. The constraint structure does not change. If your ontology already stores `is_a` parent -> child, drop the `parent` / `child` flip in the `Graph` constructor. If you don't have ontology data, define `Gene.is_kinase_member(1)` directly on the genes you care about and skip the Graph step.
- **Change the cohort target** by adjusting `COHORT_SIZE` and the three `MIN_*` floors at the top. Tightening any one of them shrinks the feasible region; setting `MIN_GENES = COHORT_SIZE` forces every patient in the cohort to cover a distinct gene (rules out two patients with identical mutation patterns).
- **Move from feasibility to optimisation.** This template is a satisfaction model -- any cohort that hits the floors is correct. To rank, swap `problem.solve(...)` for `problem.maximize(sum(Gene.is_covered) + sum(Therapy.is_covered) + sum(AdverseEvent.is_covered))` to find the cohort with the broadest joint span, or `problem.minimize(sum(Patient.is_in_cohort * Patient.age_years))` for a younger cohort. MiniZinc / Chuffed handles both.
- **Tighten the qualifying window** by editing `MAX_THERAPY_TO_AE_DAYS`. The 90-day window is a common attribution choice for treatment-emergent AEs in oncology trials; some indications use 28 days for acute toxicity, others 180 days for late-onset events.
- **Add patient-level eligibility rules** -- minimum age, treatment-naive status, organ-function thresholds -- by adding more conjuncts to the `Patient.is_eligible` definition. Each extra rule narrows the eligible set; the CSP automatically drops decisions for newly-ineligible patients.
- **Add cohort-level fairness rules.** A balanced-cohort study might require a minimum count from each of two demographic strata. Add a stratum concept (`Patient.stratum`) and an IC `sum(Patient.is_in_cohort).per(Patient.stratum) >= MIN_PER_STRATUM` to enforce minimum representation per stratum.
- **Anchor on a different ontology root** by changing `KINASE_ROOT_GENE_ID`. Multi-pathway studies can run several queries with different roots and union the results.

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

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The data may not contain a feasible cohort under the current floors. Loosen one constraint at a time -- drop `MIN_GENES_COVERED`, drop `MIN_THERAPIES_COVERED`, lower `COHORT_SIZE` -- to confirm whether the data or a specific floor is the bottleneck.
- The kinase-pathway closure may be empty: if `KINASE_ROOT_GENE_ID` doesn't appear in the gene table, `Gene.is_kinase_member` is empty and no patient can be eligible. Print the closure (`Gene.is_kinase_member == 1`) before the solve to confirm.
- The eligible-patient set may be smaller than `COHORT_SIZE`. Print eligibility before the solve; if fewer than `COHORT_SIZE` patients are eligible, lower the floor or relax the qualifying-pair window.
- Coverage floors may be unsatisfiable in principle: if the eligible patients only cover two distinct therapies, `MIN_THERAPIES_COVERED >= 3` is infeasible. Inspect the `Patient.covers_therapy` / `Patient.covers_kinase_gene` / `Patient.covers_ae` relations to see what's actually reachable.

</details>

<details>
  <summary>Multiple feasible cohorts exist; which one does the solver return?</summary>

- This is constraint satisfaction, not optimisation. Any cohort that hits the floors is a correct answer; the solver is free to return different ones across runs.
- To enumerate cohorts (e.g., for clinical-team review), pass `solution_limit=N` to `problem.solve(...)` and iterate over `problem.num_points()` solutions.
- To pin a single answer, switch to optimisation -- e.g. `problem.maximize(sum(Gene.is_covered) + sum(Therapy.is_covered) + sum(AdverseEvent.is_covered))` returns the cohort with the broadest joint span.

</details>

<details>
  <summary>A coverable Y still appears as <code>is_covered = 1</code> with no in-cohort patient covering it</summary>

- This was the central encoding pitfall during development: with a per-pair `where` in the upper-bound IC, rows that no patient covers have *no* IC asserted (the where yields no rows there) and the `is_covered` variable floats free. The `is_coverable` markers and the `where=[Y.is_coverable == 1]` scoping on `solve_for` are the fix -- they remove the unbounded decision entirely. If you re-introduce a row by hand or skip the scoping, the symptom comes back; restore the scoping.

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
