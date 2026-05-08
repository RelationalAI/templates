"""Patient cohort recruitment (Graph reachability + Rules + CSP) template.

This script demonstrates a three-pillar pipeline in RelationalAI:

- A clinical-research team needs to enrol ``COHORT_SIZE`` patients in a
  kinase-pathway study. Eligible patients carry a mutation in some gene
  that is a member of the kinase-pathway sub-ontology (transitive
  subclass closure of ``is_a``), received some therapy, and developed
  an adverse event within ``MAX_THERAPY_TO_AE_DAYS`` *after* that
  therapy. The cohort, taken as a whole, must cover at least
  ``MIN_GENES_COVERED`` distinct kinase-pathway genes,
  ``MIN_THERAPIES_COVERED`` distinct therapies, and
  ``MIN_AES_COVERED`` distinct adverse-event terms, so a later study
  generalises across pathway nodes, treatment arms, and toxicity
  profiles.
- The encoding is split across three pillars: the **Graph** reasoner
  closes ``is_a`` over the gene ontology (one call to
  ``graph.reachable``), pure relational **Rules** lift that closure to
  per-patient eligibility and per-(patient, kinase-gene),
  per-(patient, therapy), per-(patient, adverse-event) coverage facts,
  and the **Prescriptive** reasoner (CSP, MiniZinc / Chuffed) selects
  the cohort and proves the coverage thresholds are reachable.

Modeling approach:
- Four binary decision streams: ``EligiblePatient.is_in_cohort``
  (which eligible patients to enrol), ``CoverableGene.is_covered``,
  ``CoverableTherapy.is_covered``, and
  ``CoverableAdverseEvent.is_covered`` (which kinase genes / therapies
  / AEs the cohort, taken together, witnesses).
- Predicate markers as sub-concepts. ``EligiblePatient`` is a
  sub-concept of ``Patient`` whose membership is the eligibility
  conjunction; ``CoverableGene`` / ``CoverableTherapy`` /
  ``CoverableAdverseEvent`` are sub-concepts whose membership is "some
  *eligible* patient covers this Y". Scoping ``Coverable*`` to
  eligible coverage (rather than any-patient coverage) is structural,
  not cosmetic: a Y covered only by ineligible patients would
  otherwise sit in ``Coverable*`` with no upper-bound IC binding (the
  per-pair ``where`` body has no eligible-patient row for it), and
  the solver would mark it covered for free. Each ``solve_for`` then
  targets the sub-concept directly (``EligiblePatient.is_in_cohort``,
  ``CoverableGene.is_covered``, ...), so a binary decision is only
  created for rows the rules established as meaningful -- ineligible
  patients and never-covered Ys never get a decision, and the
  upper-bound ICs cleanly bind on the rows that do. Sub-concepts are
  cheaper, more readable, and avoid the Boolean-property-as-marker
  pattern entirely.
- Single-sourced qualifying-pair predicate.
  ``Patient.qualifying_pair`` is a 3-arity relationship over
  ``(Patient, TherapyEvent, AdverseEventOcc)`` triples where the AE
  follows the therapy within ``MAX_THERAPY_TO_AE_DAYS`` for the same
  patient. ``QualifyingPairPatient``, ``Patient.covers_therapy``, and
  ``Patient.covers_ae`` are then one-line projections from this
  relation, so the AE-window predicate lives in exactly one place.
  Refining the qualifying-pair definition (severity matching,
  treatment duration, multi-event sequencing) is an edit to one rule
  rather than three.
- Cohort size: ``sum(EligiblePatient.is_in_cohort) == COHORT_SIZE``.
- Coverage upper bounds (one IC per coverage axis): per coverable
  kinase gene ``g``, ``g.is_covered`` is bounded above by the number
  of in-cohort patients whose mutations cover ``g``. The reverse
  direction is free, so the solver sets ``is_covered`` to 1 wherever
  the bound permits -- exactly when at least one chosen patient covers
  that gene. Same shape for therapies and adverse events.
- Coverage lower bounds:
  ``sum(CoverableGene.is_covered) >= MIN_GENES_COVERED`` (and
  similarly for therapies and AEs). Together with the upper bounds,
  the solver must pick patients whose joint coverage spans at least
  ``MIN_GENES_COVERED`` / ``MIN_THERAPIES_COVERED`` /
  ``MIN_AES_COVERED`` distinct values.
- All of these constraints are pure relational arithmetic, so
  ``problem.verify()`` re-evaluates every IC in the returned solution.

Run:
    `python patient_cohort_recruitment.py`

Output:
    Prints the formulation, the kinase-pathway gene closure, the
    eligible patient set, the chosen cohort, the per-axis coverage
    tally, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# The kinase-pathway-root gene anchors the ontology closure. Genes
# reachable from this root via `is_a` edges are the "kinase pathway
# members" -- exactly the genes whose mutations make a patient
# pathway-eligible.
KINASE_ROOT_GENE_ID = 1
# Maximum days between a therapy event and a downstream adverse-event
# occurrence for the pair to count as a "qualifying" treatment-emergent
# AE. 90 days is a common window for treatment-related AE attribution
# in oncology trials.
MAX_THERAPY_TO_AE_DAYS = 90
# Cohort target size and minimum diversity floors. Tuned so the search
# does visible work on the bundled data: with eight eligible patients
# and several feasible cohorts that hit (3 genes, 2 therapies, 2 AEs)
# but not all (4, 3, 3), the solver must reason across coverage axes
# rather than greedily packing the largest single axis.
COHORT_SIZE = 4
MIN_GENES_COVERED = 3
MIN_THERAPIES_COVERED = 2
MIN_AES_COVERED = 2

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Load all CSVs upfront so pre-solve invariants can validate the data
# integrity before any model.define rules are installed.
# --------------------------------------------------

genes_csv = read_csv(DATA_DIR / "genes.csv")
isa_csv = read_csv(DATA_DIR / "gene_is_a.csv")
therapies_csv = read_csv(DATA_DIR / "therapies.csv")
ae_terms_csv = read_csv(DATA_DIR / "ae_terms.csv")
patients_csv = read_csv(DATA_DIR / "patients.csv")
mut_csv = read_csv(DATA_DIR / "mutation_events.csv")
th_csv = read_csv(DATA_DIR / "therapy_events.csv")
ae_csv = read_csv(DATA_DIR / "adverse_events.csv")

# --------------------------------------------------
# Pre-solve invariants
#
# Catch the most common silent-failure modes before the solver runs:
# duplicate keys (would collapse rows), dangling FKs (would silently
# drop joins), a missing kinase-pathway root (would empty the closure
# and produce zero eligible patients), and negative timestamps (would
# break the AE-window predicate). Each helper raises a focused
# ValueError with the offending rows; replace the bundled CSVs with
# your own data and these guards become your first-pass data-quality
# check.
# --------------------------------------------------


def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate {tuple(cols) if len(cols) > 1 else cols[0]}"
            f"={duplicates}. Each key must be unique; remove or merge the conflicting rows."
        )


def _assert_root_gene_exists(genes_csv, root_id):
    if root_id not in set(int(g) for g in genes_csv["id"].tolist()):
        raise ValueError(
            f"KINASE_ROOT_GENE_ID={root_id} is not in genes.csv. The pathway "
            f"closure starts from this gene; supply a valid gene id or pick "
            f"one from genes.csv."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    parent_ids = set(int(v) for v in parent_df[parent_col].unique())
    dangling = sorted({int(v) for v in child_df[child_col].unique() if int(v) not in parent_ids})
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve."
        )


def _assert_nonneg_t_days(df, source):
    bad = sorted({int(v) for v in df["t_days"].tolist() if int(v) < 0})
    if bad:
        raise ValueError(
            f"{source} has negative t_days={bad}. t_days must be >= 0 (days "
            f"since the patient's enrolment / index date)."
        )


_assert_unique_keys(genes_csv, "id", "genes.csv")
_assert_unique_keys(isa_csv, ["child_id", "parent_id"], "gene_is_a.csv")
_assert_unique_keys(therapies_csv, "id", "therapies.csv")
_assert_unique_keys(ae_terms_csv, "id", "ae_terms.csv")
_assert_unique_keys(patients_csv, "id", "patients.csv")
_assert_unique_keys(mut_csv, "id", "mutation_events.csv")
_assert_unique_keys(th_csv, "id", "therapy_events.csv")
_assert_unique_keys(ae_csv, "id", "adverse_events.csv")

_assert_root_gene_exists(genes_csv, KINASE_ROOT_GENE_ID)

_assert_no_dangling_fks(isa_csv, "child_id", genes_csv, "id", "gene_is_a.csv", "genes.csv")
_assert_no_dangling_fks(isa_csv, "parent_id", genes_csv, "id", "gene_is_a.csv", "genes.csv")
_assert_no_dangling_fks(
    mut_csv, "patient_id", patients_csv, "id", "mutation_events.csv", "patients.csv"
)
_assert_no_dangling_fks(mut_csv, "gene_id", genes_csv, "id", "mutation_events.csv", "genes.csv")
_assert_no_dangling_fks(
    th_csv, "patient_id", patients_csv, "id", "therapy_events.csv", "patients.csv"
)
_assert_no_dangling_fks(
    th_csv, "therapy_id", therapies_csv, "id", "therapy_events.csv", "therapies.csv"
)
_assert_no_dangling_fks(
    ae_csv, "patient_id", patients_csv, "id", "adverse_events.csv", "patients.csv"
)
_assert_no_dangling_fks(
    ae_csv, "ae_term_id", ae_terms_csv, "id", "adverse_events.csv", "ae_terms.csv"
)

_assert_nonneg_t_days(mut_csv, "mutation_events.csv")
_assert_nonneg_t_days(th_csv, "therapy_events.csv")
_assert_nonneg_t_days(ae_csv, "adverse_events.csv")

# --------------------------------------------------
# Define semantic model
# --------------------------------------------------

model = Model("patient_cohort_recruitment")

# Concept: gene (an ontology node).
Gene = model.Concept("Gene", identify_by={"id": Integer})
Gene.name = model.Property(f"{Gene} has {String:name}")
model.define(Gene.new(model.data(genes_csv).to_schema()))

# Concept: gene-ontology `is_a` edge. The CSV stores child -> parent
# (standard OMOP / SNOMED convention), but we expose the edge to the
# Graph reasoner with src=parent, dst=child, so reachability from the
# kinase root *follows the subclass tree downwards* and lands on every
# member of the pathway.
GeneIsA = model.Concept("GeneIsA", identify_by={"child_id": Integer, "parent_id": Integer})
GeneIsA.parent = model.Property(f"{GeneIsA} has parent {Gene:parent}")
GeneIsA.child = model.Property(f"{GeneIsA} has child {Gene:child}")
isa_data = model.data(isa_csv)
model.define(GeneIsA.new(child_id=isa_data.child_id, parent_id=isa_data.parent_id))
model.define(GeneIsA.parent(Gene)).where(GeneIsA.parent_id == Gene.id)
model.define(GeneIsA.child(Gene)).where(GeneIsA.child_id == Gene.id)

# Concept: therapy (drug arm).
Therapy = model.Concept("Therapy", identify_by={"id": Integer})
Therapy.name = model.Property(f"{Therapy} has {String:name}")
model.define(Therapy.new(model.data(therapies_csv).to_schema()))

# Concept: adverse-event term (toxicity dictionary entry).
AdverseEvent = model.Concept("AdverseEvent", identify_by={"id": Integer})
AdverseEvent.term = model.Property(f"{AdverseEvent} has {String:term}")
model.define(AdverseEvent.new(model.data(ae_terms_csv).to_schema()))

# Concept: patient.
Patient = model.Concept("Patient", identify_by={"id": Integer})
Patient.name = model.Property(f"{Patient} has {String:name}")
Patient.age_years = model.Property(f"{Patient} has {Integer:age_years}")
model.define(Patient.new(model.data(patients_csv).to_schema()))

# Concept: mutation event (observed mutation in a patient at a time).
MutationEvent = model.Concept("MutationEvent", identify_by={"id": Integer})
MutationEvent.patient = model.Property(f"{MutationEvent} from {Patient:patient}")
MutationEvent.gene = model.Property(f"{MutationEvent} hits {Gene:gene}")
MutationEvent.t_days = model.Property(f"{MutationEvent} at {Integer:t_days}")
mut_data = model.data(mut_csv)
model.define(MutationEvent.new(id=mut_data.id, t_days=mut_data.t_days))
model.define(MutationEvent.patient(Patient)).where(
    MutationEvent.id(mut_data.id),
    Patient.id(mut_data.patient_id),
)
model.define(MutationEvent.gene(Gene)).where(
    MutationEvent.id(mut_data.id),
    Gene.id(mut_data.gene_id),
)

# Concept: therapy event (treatment received by a patient at a time).
TherapyEvent = model.Concept("TherapyEvent", identify_by={"id": Integer})
TherapyEvent.patient = model.Property(f"{TherapyEvent} from {Patient:patient}")
TherapyEvent.therapy = model.Property(f"{TherapyEvent} uses {Therapy:therapy}")
TherapyEvent.t_days = model.Property(f"{TherapyEvent} at {Integer:t_days}")
th_data = model.data(th_csv)
model.define(TherapyEvent.new(id=th_data.id, t_days=th_data.t_days))
model.define(TherapyEvent.patient(Patient)).where(
    TherapyEvent.id(th_data.id),
    Patient.id(th_data.patient_id),
)
model.define(TherapyEvent.therapy(Therapy)).where(
    TherapyEvent.id(th_data.id),
    Therapy.id(th_data.therapy_id),
)

# Concept: adverse-event occurrence (AE observed in a patient at a time).
AdverseEventOcc = model.Concept("AdverseEventOcc", identify_by={"id": Integer})
AdverseEventOcc.patient = model.Property(f"{AdverseEventOcc} from {Patient:patient}")
AdverseEventOcc.term = model.Property(f"{AdverseEventOcc} is {AdverseEvent:term}")
AdverseEventOcc.t_days = model.Property(f"{AdverseEventOcc} at {Integer:t_days}")
ae_data = model.data(ae_csv)
model.define(AdverseEventOcc.new(id=ae_data.id, t_days=ae_data.t_days))
model.define(AdverseEventOcc.patient(Patient)).where(
    AdverseEventOcc.id(ae_data.id),
    Patient.id(ae_data.patient_id),
)
model.define(AdverseEventOcc.term(AdverseEvent)).where(
    AdverseEventOcc.id(ae_data.id),
    AdverseEvent.id(ae_data.ae_term_id),
)

# --------------------------------------------------
# Graph pillar: ontology closure via `graph.reachable`
# --------------------------------------------------
# Build a directed graph over the gene ontology with edges parent ->
# child (the reverse of how `is_a` is conventionally stored, so that
# reachability from a root flows outwards onto all descendants), then
# pull out the (ancestor, descendant) closure relation. One call --
# the rest of the file just consumes the relation.
gene_reachable = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Gene,
    edge_concept=GeneIsA,
    edge_src_relationship=GeneIsA.parent,
    edge_dst_relationship=GeneIsA.child,
).reachable(full=True)

# A `KinaseGene` is a Gene reachable from the kinase-pathway root via
# `is_a` edges (`reachable` is reflexive, so the root itself is
# included). Defining `KinaseGene` as a sub-concept of `Gene` avoids a
# Boolean indicator property: membership of `KinaseGene` *is* the
# predicate, and downstream rules just say `KinaseGene(Gene)` to test
# it.
KinaseGene = model.Concept("KinaseGene", extends=[Gene])
KinaseRootGene = Gene.ref()
model.define(KinaseGene(Gene)).where(
    KinaseRootGene.id == KINASE_ROOT_GENE_ID,
    gene_reachable(KinaseRootGene, Gene),
)

# --------------------------------------------------
# Rules pillar: lift the closure to patient-level eligibility and
# per-axis coverage facts. Pure relational arithmetic; no decisions.
# --------------------------------------------------

# A patient is eligible if they carry a kinase-pathway mutation *and*
# have a qualifying therapy/AE pair (an AE that follows a therapy
# within `MAX_THERAPY_TO_AE_DAYS`). The two halves are split into
# their own sub-concepts so the eligibility rule reads as a plain
# conjunction and so the inspection step can show both halves
# independently.
KinaseMutationCarrier = model.Concept("KinaseMutationCarrier", extends=[Patient])
model.define(KinaseMutationCarrier(Patient)).where(
    MutationEvent.patient == Patient,
    KinaseGene(MutationEvent.gene),
)

# `Patient.qualifying_pair` is a 3-arity relationship over
# `(Patient, TherapyEvent, AdverseEventOcc)` triples where the AE
# follows the therapy within `MAX_THERAPY_TO_AE_DAYS` for the same
# patient. Lifting the AE-window predicate as a first-class relation
# single-sources it: `QualifyingPairPatient` and the per-axis
# coverage relations below are all one-line projections from
# `qualifying_pair`. If the qualifying-pair definition needs
# refinement (severity matching, treatment duration, multi-event
# sequencing), the change lives in this rule only.
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

# Per-axis coverage relationships. Gene coverage is independent of
# the AE window -- a patient covers a kinase gene iff they have a
# mutation in it -- so `Patient.covers_kinase_gene(Gene)` is a direct
# join over MutationEvent.
Patient.covers_kinase_gene = model.Relationship(f"{Patient} covers kinase {Gene:gene}")
model.define(Patient.covers_kinase_gene(Gene)).where(
    MutationEvent.patient == Patient,
    MutationEvent.gene == Gene,
    KinaseGene(Gene),
)

# `Patient.covers_therapy` / `Patient.covers_ae` project from
# `qualifying_pair` -- a therapy with no within-window AE doesn't
# count, and vice versa. Only therapies and AEs the cohort can
# demonstrate a qualifying response pattern for are counted.
Patient.covers_therapy = model.Relationship(f"{Patient} covers {Therapy:therapy}")
model.define(Patient.covers_therapy(Therapy)).where(
    Patient.qualifying_pair(TherapyEvent, AdverseEventOcc),
    TherapyEvent.therapy == Therapy,
)

Patient.covers_ae = model.Relationship(f"{Patient} covers {AdverseEvent:ae}")
model.define(Patient.covers_ae(AdverseEvent)).where(
    Patient.qualifying_pair(TherapyEvent, AdverseEventOcc),
    AdverseEventOcc.term == AdverseEvent,
)

# Coverable sub-concepts: a Gene / Therapy / AdverseEvent is
# `Coverable*` if *some eligible patient* covers it. The eligible
# scoping is structural, not cosmetic: a Y covered only by ineligible
# patients (e.g. a kinase gene mutated only by patients with no
# qualifying therapy/AE pair) would otherwise sit in `Coverable*`
# with no upper-bound IC binding -- the per-pair `where` body has no
# eligible-patient row for it -- and the solver would mark it
# covered for free. Scoping `Coverable*` to eligible coverage closes
# this gap, and scoping `solve_for` to `Coverable*` then ensures
# every `is_covered` decision has a real upper bound.
CoverableGene = model.Concept("CoverableGene", extends=[Gene])
model.define(CoverableGene(Gene)).where(EligiblePatient.covers_kinase_gene(Gene))
CoverableTherapy = model.Concept("CoverableTherapy", extends=[Therapy])
model.define(CoverableTherapy(Therapy)).where(EligiblePatient.covers_therapy(Therapy))
CoverableAdverseEvent = model.Concept("CoverableAdverseEvent", extends=[AdverseEvent])
model.define(CoverableAdverseEvent(AdverseEvent)).where(EligiblePatient.covers_ae(AdverseEvent))

# --------------------------------------------------
# Prescriptive pillar: cohort-selection CSP.
# --------------------------------------------------

Patient.is_in_cohort = model.Property(f"{Patient} is in cohort if {Integer:c}")
Gene.is_covered = model.Property(f"{Gene} is covered if {Integer:gc}")
Therapy.is_covered = model.Property(f"{Therapy} is covered if {Integer:tc}")
AdverseEvent.is_covered = model.Property(f"{AdverseEvent} is covered if {Integer:ac}")

problem = Problem(model, Integer)

# Decisions are scoped to the rows the relational rules established as
# meaningful: `is_in_cohort` only on eligible patients, and each
# `is_covered` only on Y values the cohort could *actually* cover.
# Targeting the sub-concept directly (`EligiblePatient.is_in_cohort`,
# `CoverableGene.is_covered`, ...) creates one binary variable per
# sub-concept row -- the scoping is structural, not cosmetic: it is
# what makes the upper-bound ICs below force `is_covered = 0` on
# non-supported rows instead of letting them float.
problem.solve_for(
    EligiblePatient.is_in_cohort,
    type="bin",
    name=["is_in_cohort", EligiblePatient.id],
)
problem.solve_for(
    CoverableGene.is_covered,
    type="bin",
    name=["gene_covered", CoverableGene.id],
)
problem.solve_for(
    CoverableTherapy.is_covered,
    type="bin",
    name=["therapy_covered", CoverableTherapy.id],
)
problem.solve_for(
    CoverableAdverseEvent.is_covered,
    type="bin",
    name=["ae_covered", CoverableAdverseEvent.id],
)

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# All ICs reference the sub-concept where the decision was created
# (`solve_for(Sub.prop)` keys variables by the sub-concept), so the
# aggregates and per-row binds resolve cleanly.

# Cohort size = K.
cohort_size_ic = model.require(sum(EligiblePatient.is_in_cohort) == COHORT_SIZE)
problem.satisfy(cohort_size_ic)

# Per-gene coverage upper bound: a kinase gene can only be marked
# covered if at least one in-cohort patient mutates it. The reverse
# direction is free and will be saturated by the lower-bound IC below.
gene_cover_ic = model.where(EligiblePatient.covers_kinase_gene(CoverableGene)).require(
    CoverableGene.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableGene)
)
problem.satisfy(gene_cover_ic)

# Per-therapy coverage upper bound.
therapy_cover_ic = model.where(EligiblePatient.covers_therapy(CoverableTherapy)).require(
    CoverableTherapy.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableTherapy)
)
problem.satisfy(therapy_cover_ic)

# Per-AE coverage upper bound.
ae_cover_ic = model.where(EligiblePatient.covers_ae(CoverableAdverseEvent)).require(
    CoverableAdverseEvent.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableAdverseEvent)
)
problem.satisfy(ae_cover_ic)

# Coverage lower bounds: the cohort must witness MIN_* distinct values
# along each axis.
gene_min_ic = model.require(sum(CoverableGene.is_covered) >= MIN_GENES_COVERED)
problem.satisfy(gene_min_ic)
therapy_min_ic = model.require(sum(CoverableTherapy.is_covered) >= MIN_THERAPIES_COVERED)
problem.satisfy(therapy_min_ic)
ae_min_ic = model.require(sum(CoverableAdverseEvent.is_covered) >= MIN_AES_COVERED)
problem.satisfy(ae_min_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# All seven ICs are pure relational arithmetic, so `verify` re-evaluates
# every one in the returned solution.
problem.verify(
    cohort_size_ic,
    gene_cover_ic,
    therapy_cover_ic,
    ae_cover_ic,
    gene_min_ic,
    therapy_min_ic,
    ae_min_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect results
# --------------------------------------------------

print("\nKinase-pathway gene closure (reachable from KINASE_ROOT_GENE_ID):")
model.select(
    KinaseGene.id.alias("gene_id"),
    KinaseGene.name.alias("gene_name"),
).inspect()

print("\nEligible patients (carry a kinase mutation and have a qualifying pair):")
model.select(
    EligiblePatient.id.alias("patient_id"),
    EligiblePatient.name.alias("patient_name"),
).inspect()

print("\nSelected cohort:")
model.select(
    EligiblePatient.id.alias("patient_id"),
    EligiblePatient.name.alias("patient_name"),
    EligiblePatient.age_years.alias("age_years"),
).where(EligiblePatient.is_in_cohort == 1).inspect()

print("\nKinase-pathway genes covered by the cohort:")
model.select(
    CoverableGene.id.alias("gene_id"),
    CoverableGene.name.alias("gene_name"),
).where(CoverableGene.is_covered == 1).inspect()

print("\nTherapies covered by the cohort:")
model.select(
    CoverableTherapy.id.alias("therapy_id"),
    CoverableTherapy.name.alias("therapy_name"),
).where(CoverableTherapy.is_covered == 1).inspect()

print("\nAdverse events covered by the cohort:")
model.select(
    CoverableAdverseEvent.id.alias("ae_id"),
    CoverableAdverseEvent.term.alias("ae_term"),
).where(CoverableAdverseEvent.is_covered == 1).inspect()
