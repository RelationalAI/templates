# Runbook: Patient Cohort Recruitment — Multi-Reasoner Walkthrough

A clinical-research team must enroll exactly 4 patients into a kinase-pathway study. A patient is eligible only if they carry a mutation in a gene that belongs to the kinase pathway *and* had an adverse event within 90 days after a therapy. The cohort as a whole must be diverse — collectively spanning several pathway genes, therapies, and adverse-event types — so the study generalizes. No single reasoner does this: a graph traces the gene ontology, rules screen eligibility, and an optimizer assembles the diverse cohort.

## The chain

```
A 10-gene ontology and 15 patients with mutation, therapy, and adverse-event
histories. The chain finds the kinase-pathway genes, screens patients to the
eligible set, then picks a diverse 4-patient cohort — OPTIMAL, covering
4 genes / 3 therapies / 3 adverse events (all diversity floors satisfied).

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  KinaseGene                        (7 of 10)
              (reachability) Genes reachable from the kinase root via
                             is_a — EGFR, HER2, BRAF, MEK1, and 3 more;
                             the 3 unrelated genes are excluded.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  EligiblePatient                   (8 of 15)
                             Kinase-mutation carriers who also had an
                             adverse event 0–90 days after a therapy.
                             Plus per-patient coverage facts (gene/therapy/AE).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Patient.is_in_cohort               (4)
              (CSP)          Pick 4 eligible patients covering ≥3 genes,
                             ≥2 therapies, ≥2 adverse events. OPTIMAL —
                             achieves 4 genes / 3 therapies / 3 AEs.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-ontology Build an ontology from the data/ CSVs: genes and gene_is_a (a gene ontology where each is_a edge says a child gene is a kind of a parent gene), therapies, ae_terms (adverse-event terms), patients, and the three patient event tables — mutation_events (patient has a mutation in a gene at a time), therapy_events (patient received a therapy at a time), and adverse_events (patient had an adverse-event term at a time). Model is_a as a relationship between genes and each event as a relationship from a patient.
```

**Response**

Loads `Gene` (10) with an `is_a` self-relationship (8 edges), `Therapy` (5), `AdverseEvent` (4 terms), `Patient` (15), and the three timestamped event relationships (26 mutation events, 15 therapy events, 12 adverse-event occurrences).

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

Concepts: 10 `Gene` (with `is_a`), 5 `Therapy`, 4 `AdverseEvent`, 15 `Patient`, plus the mutation/therapy/adverse-event event relationships. The gene ontology has two trees — a kinase-pathway tree and an unrelated tree.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We need 4 patients who carry a kinase-pathway gene mutation and had an adverse event soon after a therapy, and the 4 together must span several genes, therapies, and adverse events. How should we break this down?
```

**Response**

Routes to a graph step (which genes are in the kinase pathway, via the is_a hierarchy), a rules step (which patients are eligible and what each covers), and a prescriptive step (pick the diverse 4-patient cohort).

### 4. Find the kinase-pathway genes

**Prompt**

```
/rai-graph-analysis Which genes belong to the kinase pathway — every gene reachable from the kinase root gene by following is_a (a kind of) edges, including the root itself? Persist them as a KinaseGene set.
```

**Response**

Reachability over the `is_a` hierarchy from the kinase root returns **7 of the 10 genes** — the kinase root plus SerineThreonineKinase, TyrosineKinase, EGFR, HER2, BRAF, and MEK1 — persisted as the `KinaseGene` sub-concept. The 3 genes in the unrelated tree are correctly excluded.

### 5. Screen for eligible patients

**Prompt**

```
/rai-pyrel A patient is eligible if they (a) carry a mutation in a KinaseGene, and (b) had an adverse event within 0 to 90 days after receiving some therapy. Flag the eligible patients, and for each record which kinase genes, therapies, and adverse-event terms they cover.
```

**Response**

**8 of the 15 patients are eligible** (`EligiblePatient`) — kinase-mutation carriers who also have a qualifying therapy-then-adverse-event pair within the 90-day window. Each eligible patient's covered genes, therapies, and adverse-event terms are written back as coverage facts, and the genes/therapies/AEs reachable by *some* eligible patient become the coverable sets the optimizer can credit.

### 6. Assemble the diverse cohort

**Prompt**

```
/rai-prescriptive-problem Pick exactly 4 eligible patients to form the study cohort such that, collectively, they cover at least 3 distinct kinase genes, at least 2 distinct therapies, and at least 2 distinct adverse-event terms. Persist the chosen patients as Patient.is_in_cohort and the covered genes/therapies/adverse events.
```

**Response**

OPTIMAL (constraint solver) — a valid 4-patient cohort that **exceeds every diversity floor: 4 kinase genes, 3 therapies, and 3 adverse-event terms** (floors were 3 / 2 / 2). `Patient.is_in_cohort` and the covered-gene/therapy/AE flags are written back. (Several equally-valid cohorts of 4 satisfy the floors, so the exact patients can vary; one solution is P_Alpha, P_Bravo, P_Delta, P_Hotel.)

### 7. Read the cohort

**Prompt**

```
/rai-prescriptive-results Which patients are in the cohort, what diversity does it achieve, and what's the binding constraint?
```

**Response**

The cohort is 4 eligible patients whose combined coverage is **4 genes (EGFR, HER2, BRAF, MEK1), 3 therapies, and 3 adverse-event terms** — comfortably above the 3/2/2 floors. The **binding constraint is the cohort-size requirement (exactly 4)**: the diversity floors are slack (the cohort over-covers on every axis), so it's the size limit, not diversity, that pins the solution. Tightening the floors or shrinking the cohort is what would make diversity bind.

## Data

Bundled CSVs in `data/`: 10 genes (8 is_a edges), 5 therapies, 4 adverse-event terms, 15 patients, and 26 / 15 / 12 mutation / therapy / adverse-event events. The kinase root gene, the 90-day window, the cohort size (4), and the diversity floors (3 / 2 / 2) are constants in the script. Full chain in `patient_cohort_recruitment.py`.
