---
title: "Patient Cohort Recruitment"
description: "Build a clinical-research cohort over a patient knowledge graph: a Graph reasoner closes a kinase-pathway sub-ontology, relational rules lift the closure to per-patient eligibility and coverage facts, and a CSP solver picks K patients whose joint coverage spans enough distinct genes, therapies, and adverse events for the analysis to generalize."
featured: false
experience_level: intermediate
industry: "Healthcare"
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

# Patient Cohort Recruitment

## What this template is for

Clinical research and pharma R&D teams build patient cohorts to power studies. A typical ask: *"find patients with a mutation in some gene from the kinase pathway who received a therapy and developed an adverse event within 90 days, and pick K of them so the cohort spans enough distinct genes, therapies, and toxicity profiles for the analysis to generalize."*

The pieces are recognizable across healthcare data. A gene ontology with `is_a` edges defines the pathway. A patient knowledge graph carries mutations / therapies / adverse events with timestamps. The cohort itself is a small set of patients chosen against multiple coverage criteria.

This template encodes that ask as a three-reasoner pipeline. The **Graph** reasoner runs a single `reachable(full=True)` call to close `is_a` over the gene ontology, returning every gene in the kinase-pathway sub-ontology in one step. Pure relational **Rules** then lift the closure to per-patient eligibility -- represented as a sub-concept `EligiblePatient extends Patient` whose membership is the eligibility conjunction -- and to per-(patient, gene), per-(patient, therapy), and per-(patient, adverse-event) coverage facts. The **Prescriptive** reasoner (CSP, MiniZinc / Chuffed) selects the cohort: binary `is_in_cohort` decisions are scoped to `EligiblePatient` rows only, plus `is_covered` indicators on three sub-concepts (`CoverableGene`, `CoverableTherapy`, `CoverableAdverseEvent`) that the upper-bound ICs link back to the patient decisions.

The same pattern applies to other knowledge-graph cohort / set-cover problems where eligibility is a relational predicate over a labelled subgraph and the chosen set must witness a minimum spread on several attributes: insurance claim audits (find K members spanning N procedures and M comorbidities), grant-applicant diversification (find K applicants spanning institutions, fields, and career stages), security alert triage (find K alerts spanning attack categories and asset classes).

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
- Post-solve verification via `problem.verify()` confirming every IC holds in the returned solution, plus a `termination_status() == "OPTIMAL"` assertion

## What's included

The bundled CSVs are illustrative, fully synthetic demo data (e.g. patient names `P_Alpha`...`P_Oscar`, fictional gene/therapy/AE labels) sized so the pipeline runs end-to-end in a few seconds; swap in your own ontology and patient KG to apply the template to real cohorts.

- `patient_cohort_recruitment.py` -- main script with concepts, the Graph closure, the rules, the decisions and constraints, and the solver call
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
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/patient_cohort_recruitment.zip
   unzip patient_cohort_recruitment.zip
   cd patient_cohort_recruitment
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
   python patient_cohort_recruitment.py
   ```

6. Expected output (the bundled data has eight eligible patients and several feasible cohorts that hit the coverage floors -- the exact choice may vary across solver versions):
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 0
   • solve time: ~1s
   • num_points: 1
   • solver: MiniZinc_unknown

   Kinase-pathway gene closure (reachable from KINASE_ROOT_GENE_ID):
     gene_id              gene_name
           1      KinasePathwayRoot
           2  SerineThreonineKinase
           3         TyrosineKinase
           4                   EGFR
           5                   HER2
           6                   BRAF
           7                   MEK1

   Eligible patients (carry a kinase mutation and have a qualifying pair):
      patient_id patient_name
               1      P_Alpha
               2      P_Bravo
               3    P_Charlie
               4      P_Delta
               5       P_Echo
               7       P_Golf
               8      P_Hotel
               9      P_India

   Selected cohort:
     patient_id patient_name age_years
              2      P_Bravo        61
              7       P_Golf        63
              8      P_Hotel        49
              9      P_India        57

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

   Eight of the 15 patients are eligible (the seven excluded patients each fail either the kinase-mutation test or the qualifying-pair test within the 90-day window). The kinase-pathway closure transitively covers the root, the two sub-roots, and all four leaves. Several four-patient cohorts hit the `MIN_GENES_COVERED = 3` / `MIN_THERAPIES_COVERED = 2` / `MIN_AES_COVERED = 2` floors; the solver returns one of them (the specific cohort can vary across runs). `Statin` and `GLP1_Agonist` (therapies 4 and 5) and `Myalgia` (AE 4) appear in the data but are unreachable for any cohort because no eligible patient has a qualifying-pair on them -- the `Coverable*` sub-concepts correctly exclude them from the count.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── patient_cohort_recruitment.py
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

The pipeline runs three stages in order: Graph closes the ontology, Rules lift the closure to patient-level facts, and the CSP solver selects the cohort.

**Graph reasoner: one call to close the ontology.** The `is_a` CSV is in OMOP / SNOMED convention (child -> parent), but the `Graph` constructor takes the same edge concept with `edge_src_relationship=GeneIsA.parent` and `edge_dst_relationship=GeneIsA.child` -- so reachability from a root flows downwards through the subclass tree onto every member. `reachable(full=True)` returns every (ancestor, descendant) pair, the full transitive closure. The closure is then materialized as a sub-concept `KinaseGene extends Gene`:

```python
gene_reachable = Graph(
    model, directed=True, weighted=False, node_concept=Gene,
    edge_concept=GeneIsA,
    edge_src_relationship=GeneIsA.parent,
    edge_dst_relationship=GeneIsA.child,
).reachable(full=True)

KinaseGene = model.Concept("KinaseGene", extends=[Gene])
KinaseRootGene = Gene.ref()
model.define(KinaseGene(Gene)).where(
    KinaseRootGene.id == KINASE_ROOT_GENE_ID,
    gene_reachable(KinaseRootGene, Gene),
)
```

**Rules: lift the closure to patient-level sub-concepts.** Pure relational arithmetic, no decisions. Predicates are encoded as sub-concepts -- their *membership* is the predicate -- so downstream rules and the CSP just check `Sub(Parent)` to test the predicate (cheaper and clearer than Boolean indicator properties). The qualifying-pair AE-window predicate is lifted into a 3-arity `Patient.qualifying_pair(TherapyEvent, AdverseEventOcc)` relationship and the three downstream rules (eligibility, therapy coverage, AE coverage) all project from it -- changing the qualifying-pair definition (severity matching, treatment duration, multi-event sequencing) is then an edit to one rule rather than three:

```python
KinaseMutationCarrier = model.Concept("KinaseMutationCarrier", extends=[Patient])
model.define(KinaseMutationCarrier(Patient)).where(
    MutationEvent.patient == Patient,
    KinaseGene(MutationEvent.gene),
)

Patient.qualifying_pair = model.Relationship(
    f"{Patient} qualifies on {TherapyEvent:therapy_event} and {AdverseEventOcc:ae_occ}"
)
model.define(Patient.qualifying_pair(TherapyEvent, AdverseEventOcc)).where(
    TherapyEvent.patient == Patient,
    AdverseEventOcc.patient == Patient,
    AdverseEventOcc.t_days - TherapyEvent.t_days >= 0,
    AdverseEventOcc.t_days - TherapyEvent.t_days <= MAX_THERAPY_TO_AE_DAYS,
)

QualifyingPairPatient = model.Concept("QualifyingPairPatient", extends=[Patient])
model.define(QualifyingPairPatient(Patient)).where(
    Patient.qualifying_pair(TherapyEvent, AdverseEventOcc),
)

EligiblePatient = model.Concept("EligiblePatient", extends=[Patient])
model.define(EligiblePatient(Patient)).where(
    KinaseMutationCarrier(Patient),
    QualifyingPairPatient(Patient),
)

# Per-axis coverage projects from `qualifying_pair`:
Patient.covers_therapy = model.Relationship(f"{Patient} covers {Therapy:therapy}")
model.define(Patient.covers_therapy(Therapy)).where(
    Patient.qualifying_pair(TherapyEvent, AdverseEventOcc),
    TherapyEvent.therapy == Therapy,
)
```

**Prescriptive reasoner: cohort selection as a CSP.** Decisions target the sub-concept directly (`EligiblePatient.is_in_cohort`, `CoverableTherapy.is_covered`, ...), which creates one binary variable per sub-concept row. The `Coverable*` sub-concepts are themselves scoped to *eligible-patient* coverage, not any-patient coverage: a Y covered only by ineligible patients would otherwise sit in `Coverable*` with no upper-bound IC binding (the per-pair `where` body has no eligible-patient row for it), and the solver would mark it covered to satisfy the lower bound trivially. Scoping `Coverable*` to `EligiblePatient.covers_*` closes that gap; scoping `solve_for` to `Coverable*` then ensures every `is_covered` decision has a real upper bound.

```python
problem.solve_for(
    EligiblePatient.is_in_cohort, type="bin",
    name=["is_in_cohort", EligiblePatient.id],
)
problem.solve_for(
    CoverableTherapy.is_covered, type="bin",
    name=["therapy_covered", CoverableTherapy.id],
)
```

**Coverage upper bound + per-pair lower bound + floor is the CSP signature.** For each coverable Y, `Y.is_covered` is bounded above by the number of in-cohort patients that cover it (so an unsupported Y cannot be marked covered) AND bounded below per pair by `EligiblePatient.is_in_cohort` (so any in-cohort patient covering Y forces `is_covered` to saturate to 1). The two bounds together pin `is_covered` to the actual coverage. The floor IC `sum(is_covered) >= MIN_*` then constrains the cohort to span at least `MIN_*` distinct values. Without the per-pair lower bound the solver could leave indicators at 0 even when the cohort actually covers them, making the inspect() output underreport.

```python
gene_cover_ub_ic = model.where(EligiblePatient.covers_kinase_gene(CoverableGene)).require(
    CoverableGene.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableGene)
)
gene_cover_lb_ic = model.where(EligiblePatient.covers_kinase_gene(CoverableGene)).require(
    CoverableGene.is_covered >= EligiblePatient.is_in_cohort
)
gene_min_ic = model.require(sum(CoverableGene.is_covered) >= MIN_GENES_COVERED)
```

All ten ICs are pure relational arithmetic, so `problem.verify()` re-evaluates every one in the returned solution -- no constraint is solver-only.

## Customize this template

- **Use your own data** by replacing the eight CSV files with your gene ontology and patient knowledge graph. The constraint structure does not change. If your ontology already stores `is_a` parent -> child, drop the `parent` / `child` flip in the `Graph` constructor. If you don't have ontology data, define `KinaseGene` membership directly on the genes you care about and skip the Graph step.
- **Change the cohort target** by adjusting `COHORT_SIZE` and the three `MIN_*_COVERED` floors at the top. Tightening any one of them shrinks the feasible region; setting `MIN_GENES_COVERED = COHORT_SIZE` forces every patient in the cohort to cover a distinct gene (rules out two patients with identical mutation patterns).
- **Move from feasibility to optimization.** This template is a satisfaction model -- any cohort that hits the floors is correct. To rank, swap `problem.solve(...)` for `problem.maximize(sum(CoverableGene.is_covered) + sum(CoverableTherapy.is_covered) + sum(CoverableAdverseEvent.is_covered))` to find the cohort with the broadest joint span, or `problem.minimize(sum(EligiblePatient.is_in_cohort * EligiblePatient.age_years))` for a younger cohort. MiniZinc / Chuffed handles both.
- **Keep aggregates on a single sub-concept.** Aggregations over a decision must reference the sub-concept the decision was scoped to -- mixing parent and sub-concept references in a single aggregate triggers a TypeError.
- **Tighten the qualifying window** by editing `MAX_THERAPY_TO_AE_DAYS`. The 90-day window is a common attribution choice for treatment-emergent AEs in oncology trials; some indications use 28 days for acute toxicity, others 180 days for late-onset events.
- **Add patient-level eligibility rules** -- minimum age, treatment-naive status, organ-function thresholds -- by adding more conjuncts to the `EligiblePatient` definition (or by introducing further `extends=[Patient]` sub-concepts). Each extra rule narrows the eligible set; the CSP automatically drops decisions for newly-ineligible patients.
- **Add cohort-level fairness rules.** A balanced-cohort study might require a minimum count from each of two demographic strata. Add a stratum property (`Patient.stratum`) and an IC `sum(EligiblePatient.is_in_cohort).per(EligiblePatient.stratum) >= MIN_PER_STRATUM` to enforce minimum representation per stratum. The decision-side aggregate must key on the sub-concept (`EligiblePatient`), not the parent (`Patient`).
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
- The kinase-pathway closure may be empty: if `KINASE_ROOT_GENE_ID` doesn't appear in the gene table, `KinaseGene` is empty and no patient can be eligible. Print the closure (`model.select(KinaseGene.id).inspect()`) before the solve to confirm.
- The eligible-patient set may be smaller than `COHORT_SIZE`. Print `EligiblePatient.id` before the solve; if fewer than `COHORT_SIZE` patients are eligible, lower the floor or relax the qualifying-pair window.
- Coverage floors may be unsatisfiable in principle: if the eligible patients only cover two distinct therapies, `MIN_THERAPIES_COVERED >= 3` is infeasible. Inspect the `Patient.covers_therapy` / `Patient.covers_kinase_gene` / `Patient.covers_ae` relations to see what's actually reachable.

</details>

<details>
  <summary>Multiple feasible cohorts exist; which one does the solver return?</summary>

- This is constraint satisfaction, not optimization. Any cohort that hits the floors is a correct answer; the solver is free to return different ones across runs.
- To enumerate cohorts (e.g., for clinical-team review), pass `solution_limit=N` to `problem.solve(...)` and iterate over `problem.num_points()` solutions.
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

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS is not appropriate here -- this is a discrete satisfaction model with categorical decisions and structural propagation, not LP/MILP.

</details>
