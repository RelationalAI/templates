"""Patient cohort recruitment (Graph reachability + Rules + CSP) template.

This script demonstrates a three-reasoner pipeline in RelationalAI:

- A clinical-research team needs to enroll ``COHORT_SIZE`` patients in a
  kinase-pathway study. Eligible patients carry a mutation in some gene
  that is a member of the kinase-pathway sub-ontology (transitive
  subclass closure of ``is_a``), received some therapy, and developed
  an adverse event within ``MAX_THERAPY_TO_AE_DAYS`` *after* that
  therapy. The cohort, taken as a whole, must cover at least
  ``MIN_GENES_COVERED`` distinct kinase-pathway genes,
  ``MIN_THERAPIES_COVERED`` distinct therapies, and
  ``MIN_AES_COVERED`` distinct adverse-event terms, so a later study
  generalizes across pathway nodes, treatment arms, and toxicity
  profiles.
- The encoding is split across three reasoners: the **Graph** reasoner
  closes ``is_a`` over the gene ontology (one call to
  ``graph.reachable``), pure relational **Rules** lift that closure to
  per-patient eligibility and per-(patient, kinase-gene),
  per-(patient, therapy), per-(patient, adverse-event) coverage facts,
  and the **Prescriptive** reasoner (CSP, MiniZinc / Chuffed) selects
  the cohort and proves the coverage thresholds are reachable.

Modeling approach:
- Four binary decision streams: ``EligiblePatient.is_in_cohort``
  (which eligible patients to enroll), ``CoverableGene.is_covered``,
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
- Per-axis coverage upper bound: ``Y.is_covered <= sum(in_cohort).per(Y)``
  -- a Y can only be marked covered if at least one in-cohort
  eligible patient covers it.
- Per-axis coverage lower bound (per pair):
  ``Y.is_covered >= EligiblePatient.is_in_cohort`` for each
  ``(EligiblePatient, Y)`` pair where the eligible patient covers Y
  -- if any in-cohort eligible patient covers Y, then ``is_covered``
  must saturate to 1. Without this, the satisfaction solver is free
  to leave indicators at 0 even when the cohort actually covers
  them, which would make the inspect() output underreport. The
  per-pair form forces ``is_covered`` to equal the actual coverage.
- Coverage floors:
  ``sum(CoverableGene.is_covered) >= MIN_GENES_COVERED`` (and
  similarly for therapies and AEs). Combined with the upper and
  lower bounds, ``sum(Y.is_covered)`` is the actual coverage count,
  so the floor constrains the cohort to span at least
  ``MIN_GENES_COVERED`` / ``MIN_THERAPIES_COVERED`` /
  ``MIN_AES_COVERED`` distinct values.
- All ten ICs (cohort size + 3 upper + 3 lower + 3 floor) are pure
  relational arithmetic, so ``problem.verify()`` re-evaluates every
  one in the returned solution.

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


def _assert_no_nulls(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    null_cols = [c for c in cols if df[c].isna().any()]
    if null_cols:
        raise ValueError(
            f"{source} has null/NaN values in column(s) {null_cols}. Required "
            f"columns must be fully populated; drop or impute the offending rows."
        )


def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    _assert_no_nulls(df, cols, source)
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate ({', '.join(cols)})={duplicates}. "
            f"Each key must be unique; remove or merge the conflicting rows."
        )


def _assert_root_gene_exists(genes_csv, root_id):
    _assert_no_nulls(genes_csv, "id", "genes.csv")
    if root_id not in set(int(g) for g in genes_csv["id"].tolist()):
        raise ValueError(
            f"KINASE_ROOT_GENE_ID={root_id} is not in genes.csv. The pathway "
            f"closure starts from this gene; supply a valid gene id or pick "
            f"one from genes.csv."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    _assert_no_nulls(child_df, child_col, source)
    parent_ids = set(int(v) for v in parent_df[parent_col].unique())
    dangling = sorted({int(v) for v in child_df[child_col].unique() if int(v) not in parent_ids})
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve."
        )


def _assert_nonneg_column(df, col, source):
    _assert_no_nulls(df, col, source)
    bad = sorted({int(v) for v in df[col].tolist() if int(v) < 0})
    if bad:
        raise ValueError(
            f"{source} has negative {col}={bad}. {col} must be >= 0 (days "
            f"since the patient's enrollment / index date)."
        )


# Validate primary-key uniqueness on every table.
for _df, _key, _src in [
    (genes_csv, "id", "genes.csv"),
    (isa_csv, ["child_id", "parent_id"], "gene_is_a.csv"),
    (therapies_csv, "id", "therapies.csv"),
    (ae_terms_csv, "id", "ae_terms.csv"),
    (patients_csv, "id", "patients.csv"),
    (mut_csv, "id", "mutation_events.csv"),
    (th_csv, "id", "therapy_events.csv"),
    (ae_csv, "id", "adverse_events.csv"),
]:
    _assert_unique_keys(_df, _key, _src)

_assert_root_gene_exists(genes_csv, KINASE_ROOT_GENE_ID)

# Foreign-key edges in the schema. Each row says "<source>.<col>
# references <parent_source>.<parent_col>". Update this table when
# you add a new event table or rewire a FK; the loop below validates
# every edge in one place.
_FK_EDGES = [
    (isa_csv, "child_id", genes_csv, "id", "gene_is_a.csv", "genes.csv"),
    (isa_csv, "parent_id", genes_csv, "id", "gene_is_a.csv", "genes.csv"),
    (mut_csv, "patient_id", patients_csv, "id", "mutation_events.csv", "patients.csv"),
    (mut_csv, "gene_id", genes_csv, "id", "mutation_events.csv", "genes.csv"),
    (th_csv, "patient_id", patients_csv, "id", "therapy_events.csv", "patients.csv"),
    (th_csv, "therapy_id", therapies_csv, "id", "therapy_events.csv", "therapies.csv"),
    (ae_csv, "patient_id", patients_csv, "id", "adverse_events.csv", "patients.csv"),
    (ae_csv, "ae_term_id", ae_terms_csv, "id", "adverse_events.csv", "ae_terms.csv"),
]
for _cdf, _ccol, _pdf, _pcol, _csrc, _psrc in _FK_EDGES:
    _assert_no_dangling_fks(_cdf, _ccol, _pdf, _pcol, _csrc, _psrc)

# Non-negativity check on event timestamps.
for _df, _col, _src in [
    (mut_csv, "t_days", "mutation_events.csv"),
    (th_csv, "t_days", "therapy_events.csv"),
    (ae_csv, "t_days", "adverse_events.csv"),
]:
    _assert_nonneg_column(_df, _col, _src)

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
# Graph reasoner: ontology closure via `graph.reachable`
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
# Rules: lift the closure to patient-level eligibility and
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
# Prescriptive reasoner: cohort-selection CSP.
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

# Per-axis coverage upper bound: a Y can only be marked covered if at
# least one in-cohort eligible patient covers it.
gene_cover_ub_ic = model.where(EligiblePatient.covers_kinase_gene(CoverableGene)).require(
    CoverableGene.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableGene)
)
problem.satisfy(gene_cover_ub_ic)

therapy_cover_ub_ic = model.where(EligiblePatient.covers_therapy(CoverableTherapy)).require(
    CoverableTherapy.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableTherapy)
)
problem.satisfy(therapy_cover_ub_ic)

ae_cover_ub_ic = model.where(EligiblePatient.covers_ae(CoverableAdverseEvent)).require(
    CoverableAdverseEvent.is_covered <= sum(EligiblePatient.is_in_cohort).per(CoverableAdverseEvent)
)
problem.satisfy(ae_cover_ub_ic)

# Per-axis coverage lower bound (per pair): if any in-cohort eligible
# patient covers Y, then `Y.is_covered` must be 1. Without these,
# `is_covered` is only upper-bounded by the count of covering
# in-cohort patients, so the solver is free to leave indicators at 0
# even when the cohort actually covers them -- the floor IC below
# would still be satisfied by any sufficient subset of the truly
# covered Ys, but the inspect() output would underreport. The
# per-pair `is_covered >= is_in_cohort` form forces saturation.
gene_cover_lb_ic = model.where(EligiblePatient.covers_kinase_gene(CoverableGene)).require(
    CoverableGene.is_covered >= EligiblePatient.is_in_cohort
)
problem.satisfy(gene_cover_lb_ic)

therapy_cover_lb_ic = model.where(EligiblePatient.covers_therapy(CoverableTherapy)).require(
    CoverableTherapy.is_covered >= EligiblePatient.is_in_cohort
)
problem.satisfy(therapy_cover_lb_ic)

ae_cover_lb_ic = model.where(EligiblePatient.covers_ae(CoverableAdverseEvent)).require(
    CoverableAdverseEvent.is_covered >= EligiblePatient.is_in_cohort
)
problem.satisfy(ae_cover_lb_ic)

# Coverage floors: the cohort must witness MIN_* distinct values
# along each axis. With the per-pair upper and lower bounds above,
# `sum(Y.is_covered)` equals the cohort's actual coverage count, so
# this constraint is on the true coverage, not on a free-floating
# indicator subset.
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

# All ten ICs are pure relational arithmetic, so `verify` re-evaluates
# every one in the returned solution.
problem.verify(
    cohort_size_ic,
    gene_cover_ub_ic,
    therapy_cover_ub_ic,
    ae_cover_ub_ic,
    gene_cover_lb_ic,
    therapy_cover_lb_ic,
    ae_cover_lb_ic,
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
