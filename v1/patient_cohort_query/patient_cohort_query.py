"""Patient cohort query (Graph reachability + Rules + CSP) template.

This script demonstrates a three-pillar pipeline in RelationalAI:

- A clinical-research team needs to enrol K patients in a kinase-pathway
  study. Eligible patients carry a mutation in some gene that is a member
  of the kinase-pathway sub-ontology (transitive subclass closure of
  ``is_a``), received some therapy, and developed an adverse event within
  90 days *after* that therapy. The cohort, taken as a whole, must cover
  at least ``MIN_GENES`` distinct kinase-pathway genes, ``MIN_THERAPIES``
  distinct therapies, and ``MIN_AES`` distinct adverse-event terms, so a
  later study generalises across pathway nodes, treatment arms, and
  toxicity profiles.
- The encoding is split across three pillars: the **Graph** reasoner
  closes ``is_a`` over the gene ontology (one call to
  ``graph.reachable``), pure relational **Rules** lift that closure to
  per-patient eligibility and per-(patient, kinase-gene),
  per-(patient, therapy), per-(patient, adverse-event) coverage facts,
  and the **Prescriptive** reasoner (CSP, MiniZinc / Chuffed) selects
  the cohort and proves the coverage thresholds are reachable.

Modeling approach:
- Four binary decision streams: ``Patient.is_in_cohort`` (which eligible
  patients to enrol), ``Gene.is_covered``, ``Therapy.is_covered``, and
  ``AdverseEvent.is_covered`` (which kinase genes / therapies / AEs the
  cohort, taken together, witnesses).
- Eligibility framing: ``Patient.is_eligible`` is defined (via Rules)
  only on patients with both a kinase-pathway mutation and a qualifying
  therapy/AE pair, and ``problem.solve_for`` is scoped with
  ``where=[Patient.is_eligible == 1]`` so a binary decision is only
  created for eligible patients. Ineligible patients are implicitly out
  of the cohort -- no big-M, no exclusion IC.
- Cohort size: ``sum(Patient.is_in_cohort) == K``.
- Coverage upper bounds (one IC per coverage axis): per kinase gene
  ``g``, ``g.is_covered`` is bounded above by the number of in-cohort
  patients whose mutations cover ``g``. The reverse direction is free,
  so the solver sets ``is_covered`` to 1 wherever the bound permits --
  exactly when at least one chosen patient covers that gene. Same shape
  for therapies and adverse events.
- Coverage lower bounds: ``sum(Gene.is_covered) >= MIN_GENES`` (and
  similarly for therapies and AEs). Together with the upper bounds, the
  solver must pick patients whose joint coverage spans at least
  ``MIN_GENES`` / ``MIN_THERAPIES`` / ``MIN_AES`` distinct values.
- All of these constraints are pure relational arithmetic, so
  ``problem.verify()`` re-evaluates every IC in the returned solution.

Run:
    `python patient_cohort_query.py`

Output:
    Prints the formulation, the kinase-pathway gene closure, per-patient
    eligibility, the chosen cohort, the per-axis coverage tally, and
    post-solve constraint verification.
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

model = Model("patient_cohort_query")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: gene (an ontology node).
Gene = model.Concept("Gene", identify_by={"id": Integer})
Gene.name = model.Property(f"{Gene} has {String:name}")
genes_csv = read_csv(data_dir / "genes.csv")
model.define(Gene.new(genes_csv_data := model.data(genes_csv).to_schema()))

# Concept: gene-ontology `is_a` edge. The CSV stores child -> parent
# (standard OMOP / SNOMED convention), but we expose the edge to the
# Graph reasoner with src=parent, dst=child, so reachability from the
# kinase root *follows the subclass tree downwards* and lands on every
# member of the pathway.
GeneIsA = model.Concept(
    "GeneIsA", identify_by={"child_id": Integer, "parent_id": Integer}
)
GeneIsA.parent = model.Relationship(f"{GeneIsA} has parent {Gene:parent}")
GeneIsA.child = model.Relationship(f"{GeneIsA} has child {Gene:child}")
isa_csv = read_csv(data_dir / "gene_is_a.csv")
isa_data = model.data(isa_csv)
model.define(GeneIsA.new(child_id=isa_data.child_id, parent_id=isa_data.parent_id))
model.define(GeneIsA.parent(Gene)).where(GeneIsA.parent_id == Gene.id)
model.define(GeneIsA.child(Gene)).where(GeneIsA.child_id == Gene.id)

# Concept: therapy (drug arm).
Therapy = model.Concept("Therapy", identify_by={"id": Integer})
Therapy.name = model.Property(f"{Therapy} has {String:name}")
therapies_csv = read_csv(data_dir / "therapies.csv")
model.define(Therapy.new(model.data(therapies_csv).to_schema()))

# Concept: adverse-event term (toxicity dictionary entry).
AdverseEvent = model.Concept("AdverseEvent", identify_by={"id": Integer})
AdverseEvent.term = model.Property(f"{AdverseEvent} has {String:term}")
ae_terms_csv = read_csv(data_dir / "ae_terms.csv")
model.define(AdverseEvent.new(model.data(ae_terms_csv).to_schema()))

# Concept: patient.
Patient = model.Concept("Patient", identify_by={"id": Integer})
Patient.name = model.Property(f"{Patient} has {String:name}")
Patient.age_years = model.Property(f"{Patient} has {Integer:age_years}")
patients_csv = read_csv(data_dir / "patients.csv")
model.define(Patient.new(model.data(patients_csv).to_schema()))

# Concept: mutation event (observed mutation in a patient at a time).
MutationEvent = model.Concept("MutationEvent", identify_by={"id": Integer})
MutationEvent.patient = model.Relationship(f"{MutationEvent} from {Patient:patient}")
MutationEvent.gene = model.Relationship(f"{MutationEvent} hits {Gene:gene}")
MutationEvent.t_days = model.Property(f"{MutationEvent} at {Integer:t_days}")
mut_csv = read_csv(data_dir / "mutation_events.csv")
mut_data = model.data(mut_csv)
model.define(
    me := MutationEvent.new(id=mut_data.id),
    me.t_days(mut_data.t_days),
)
model.define(MutationEvent.patient(Patient)).where(
    MutationEvent.id == mut_data.id,
    Patient.id == mut_data.patient_id,
)
model.define(MutationEvent.gene(Gene)).where(
    MutationEvent.id == mut_data.id,
    Gene.id == mut_data.gene_id,
)

# Concept: therapy event (treatment received by a patient at a time).
TherapyEvent = model.Concept("TherapyEvent", identify_by={"id": Integer})
TherapyEvent.patient = model.Relationship(f"{TherapyEvent} from {Patient:patient}")
TherapyEvent.therapy = model.Relationship(f"{TherapyEvent} uses {Therapy:therapy}")
TherapyEvent.t_days = model.Property(f"{TherapyEvent} at {Integer:t_days}")
th_csv = read_csv(data_dir / "therapy_events.csv")
th_data = model.data(th_csv)
model.define(
    te := TherapyEvent.new(id=th_data.id),
    te.t_days(th_data.t_days),
)
model.define(TherapyEvent.patient(Patient)).where(
    TherapyEvent.id == th_data.id,
    Patient.id == th_data.patient_id,
)
model.define(TherapyEvent.therapy(Therapy)).where(
    TherapyEvent.id == th_data.id,
    Therapy.id == th_data.therapy_id,
)

# Concept: adverse-event occurrence (AE observed in a patient at a time).
AdverseEventOcc = model.Concept("AdverseEventOcc", identify_by={"id": Integer})
AdverseEventOcc.patient = model.Relationship(
    f"{AdverseEventOcc} from {Patient:patient}"
)
AdverseEventOcc.term = model.Relationship(f"{AdverseEventOcc} is {AdverseEvent:term}")
AdverseEventOcc.t_days = model.Property(f"{AdverseEventOcc} at {Integer:t_days}")
ae_csv = read_csv(data_dir / "adverse_events.csv")
ae_data = model.data(ae_csv)
model.define(
    aeo := AdverseEventOcc.new(id=ae_data.id),
    aeo.t_days(ae_data.t_days),
)
model.define(AdverseEventOcc.patient(Patient)).where(
    AdverseEventOcc.id == ae_data.id,
    Patient.id == ae_data.patient_id,
)
model.define(AdverseEventOcc.term(AdverseEvent)).where(
    AdverseEventOcc.id == ae_data.id,
    AdverseEvent.id == ae_data.ae_term_id,
)

# --------------------------------------------------
# Graph pillar: ontology closure via `graph.reachable`
# --------------------------------------------------
# Build a directed graph over the gene ontology with edges parent ->
# child (the reverse of how `is_a` is conventionally stored, so that
# reachability from a root flows outwards onto all descendants). One
# call to `graph.reachable(full=True)` returns every (ancestor,
# descendant) pair, which is the transitive closure we need.

ontology_graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Gene,
    edge_concept=GeneIsA,
    edge_src_relationship=GeneIsA.parent,
    edge_dst_relationship=GeneIsA.child,
)
gene_reachable = ontology_graph.reachable(full=True)

# A gene is a kinase-pathway member if the kinase root reaches it (or
# it *is* the root -- `reachable` is reflexive on connected nodes).
Gene.is_kinase_member = model.Property(f"{Gene} kinase member if {Integer:k}")
KineRootGene = Gene.ref()
model.define(Gene.is_kinase_member(1)).where(
    KineRootGene.id == KINASE_ROOT_GENE_ID,
    gene_reachable(KineRootGene, Gene),
)

# --------------------------------------------------
# Rules pillar: lift the closure to patient-level eligibility and
# per-axis coverage facts. Pure relational arithmetic; no decisions.
# --------------------------------------------------

# A patient has a "kinase mutation" if any of their mutation events
# hits a kinase-pathway-member gene.
Patient.has_kinase_mutation = model.Property(
    f"{Patient} has kinase mutation if {Integer:k}"
)
model.define(Patient.has_kinase_mutation(1)).where(
    MutationEvent.patient == Patient,
    MutationEvent.gene == Gene,
    Gene.is_kinase_member == 1,
)

# A patient has a "qualifying pair" if some therapy event T and some
# adverse-event occurrence E share that patient and
# 0 <= E.t_days - T.t_days <= MAX_THERAPY_TO_AE_DAYS (the AE follows
# the therapy and lies inside the attribution window).
Patient.has_qualifying_pair = model.Property(
    f"{Patient} has qualifying pair if {Integer:q}"
)
TE_pair = TherapyEvent.ref()
AE_pair = AdverseEventOcc.ref()
model.define(Patient.has_qualifying_pair(1)).where(
    TE_pair.patient == Patient,
    AE_pair.patient == Patient,
    AE_pair.t_days - TE_pair.t_days >= 0,
    AE_pair.t_days - TE_pair.t_days <= MAX_THERAPY_TO_AE_DAYS,
)

# An eligible patient has both. `is_eligible` is undefined for
# ineligible patients -- the CSP scopes its decision over
# `Patient.is_eligible == 1`, so no exclusion IC is needed.
Patient.is_eligible = model.Property(f"{Patient} is eligible if {Integer:e}")
model.define(Patient.is_eligible(1)).where(
    Patient.has_kinase_mutation == 1,
    Patient.has_qualifying_pair == 1,
)

# Per-axis coverage facts. `Patient.covers_kinase_gene(Gene)` holds for
# every (patient, kinase-pathway gene) pair where the patient has a
# mutation in that gene. The CSP aggregates `Patient.is_in_cohort` over
# this relation grouped by Gene to derive how many in-cohort patients
# cover each gene.
Patient.covers_kinase_gene = model.Relationship(f"{Patient} covers kinase {Gene:gene}")
model.define(Patient.covers_kinase_gene(Gene)).where(
    MutationEvent.patient == Patient,
    MutationEvent.gene == Gene,
    Gene.is_kinase_member == 1,
)

# `Patient.covers_therapy(Therapy)` and `Patient.covers_ae(AdverseEvent)`
# are restricted to (patient, therapy / AE) pairs that *participate in
# at least one qualifying pair*. A therapy that the patient received
# but whose AE-window neighbour is missing does not count -- only
# therapies and AEs the cohort can demonstrate a qualifying response
# pattern for.
Patient.covers_therapy = model.Relationship(f"{Patient} covers {Therapy:therapy}")
TE_cov = TherapyEvent.ref()
AE_cov = AdverseEventOcc.ref()
model.define(Patient.covers_therapy(Therapy)).where(
    TE_cov.patient == Patient,
    TE_cov.therapy == Therapy,
    AE_cov.patient == Patient,
    AE_cov.t_days - TE_cov.t_days >= 0,
    AE_cov.t_days - TE_cov.t_days <= MAX_THERAPY_TO_AE_DAYS,
)

Patient.covers_ae = model.Relationship(f"{Patient} covers {AdverseEvent:ae}")
TE_cov2 = TherapyEvent.ref()
AE_cov2 = AdverseEventOcc.ref()
model.define(Patient.covers_ae(AdverseEvent)).where(
    AE_cov2.patient == Patient,
    AE_cov2.term == AdverseEvent,
    TE_cov2.patient == Patient,
    AE_cov2.t_days - TE_cov2.t_days >= 0,
    AE_cov2.t_days - TE_cov2.t_days <= MAX_THERAPY_TO_AE_DAYS,
)

# Coverable markers: `Y.is_coverable` holds for genes / therapies / AEs
# that *some* eligible patient covers. Without these, the per-axis
# `is_covered` decisions on rows with no covering patients have no
# upper-bound IC (the per-pair `where` yields no rows there) and float
# free, letting the solver mark them covered to satisfy the lower
# bound trivially. Scoping `solve_for` to `is_coverable == 1` skips
# those rows so the lower-bound count only includes Ys with a real
# upper bound.
Gene.is_coverable = model.Property(f"{Gene} is coverable if {Integer:gv}")
model.define(Gene.is_coverable(1)).where(Patient.covers_kinase_gene(Gene))
Therapy.is_coverable = model.Property(f"{Therapy} is coverable if {Integer:tv}")
model.define(Therapy.is_coverable(1)).where(Patient.covers_therapy(Therapy))
AdverseEvent.is_coverable = model.Property(
    f"{AdverseEvent} is coverable if {Integer:av}"
)
model.define(AdverseEvent.is_coverable(1)).where(Patient.covers_ae(AdverseEvent))

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
# `is_covered` only on Y values the cohort could *actually* cover. The
# coverable scoping is structural, not cosmetic: it is what makes the
# upper-bound ICs below force `is_covered = 0` on non-supported rows
# instead of letting them float.
problem.solve_for(
    Patient.is_in_cohort,
    type="bin",
    where=[Patient.is_eligible == 1],
    name=["is_in_cohort", Patient.id],
)
problem.solve_for(
    Gene.is_covered,
    type="bin",
    where=[Gene.is_coverable == 1],
    name=["gene_covered", Gene.id],
)
problem.solve_for(
    Therapy.is_covered,
    type="bin",
    where=[Therapy.is_coverable == 1],
    name=["therapy_covered", Therapy.id],
)
problem.solve_for(
    AdverseEvent.is_covered,
    type="bin",
    where=[AdverseEvent.is_coverable == 1],
    name=["ae_covered", AdverseEvent.id],
)

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Cohort size = K.
cohort_size_ic = model.require(sum(Patient.is_in_cohort) == COHORT_SIZE)
problem.satisfy(cohort_size_ic)

# Per-gene coverage upper bound: a kinase gene can only be marked
# covered if at least one in-cohort patient mutates it. The reverse
# direction is free and will be saturated by the lower-bound IC below.
gene_cover_ic = model.where(Patient.covers_kinase_gene(Gene)).require(
    Gene.is_covered <= sum(Patient.is_in_cohort).per(Gene)
)
problem.satisfy(gene_cover_ic)

# Per-therapy coverage upper bound.
therapy_cover_ic = model.where(Patient.covers_therapy(Therapy)).require(
    Therapy.is_covered <= sum(Patient.is_in_cohort).per(Therapy)
)
problem.satisfy(therapy_cover_ic)

# Per-AE coverage upper bound.
ae_cover_ic = model.where(Patient.covers_ae(AdverseEvent)).require(
    AdverseEvent.is_covered <= sum(Patient.is_in_cohort).per(AdverseEvent)
)
problem.satisfy(ae_cover_ic)

# Coverage lower bounds: the cohort must witness MIN_* distinct values
# along each axis.
gene_min_ic = model.require(sum(Gene.is_covered) >= MIN_GENES_COVERED)
problem.satisfy(gene_min_ic)
therapy_min_ic = model.require(sum(Therapy.is_covered) >= MIN_THERAPIES_COVERED)
problem.satisfy(therapy_min_ic)
ae_min_ic = model.require(sum(AdverseEvent.is_covered) >= MIN_AES_COVERED)
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

# --------------------------------------------------
# Inspect results
# --------------------------------------------------

print("\nKinase-pathway gene closure (reachable from KINASE_ROOT_GENE_ID):")
model.select(
    Gene.id.alias("gene_id"),
    Gene.name.alias("gene_name"),
).where(Gene.is_kinase_member == 1).inspect()

print("\nPer-patient eligibility (1 = both kinase mutation and qualifying pair):")
model.select(
    Patient.id.alias("patient_id"),
    Patient.name.alias("patient_name"),
    Patient.has_kinase_mutation.alias("kinase_mutation"),
    Patient.has_qualifying_pair.alias("qualifying_pair"),
    Patient.is_eligible.alias("eligible"),
).inspect()

print("\nSelected cohort:")
model.select(
    Patient.id.alias("patient_id"),
    Patient.name.alias("patient_name"),
    Patient.age_years.alias("age_years"),
).where(Patient.is_in_cohort == 1).inspect()

print("\nKinase-pathway genes covered by the cohort:")
model.select(
    Gene.id.alias("gene_id"),
    Gene.name.alias("gene_name"),
).where(Gene.is_covered == 1).inspect()

print("\nTherapies covered by the cohort:")
model.select(
    Therapy.id.alias("therapy_id"),
    Therapy.name.alias("therapy_name"),
).where(Therapy.is_covered == 1).inspect()

print("\nAdverse events covered by the cohort:")
model.select(
    AdverseEvent.id.alias("ae_id"),
    AdverseEvent.term.alias("ae_term"),
).where(AdverseEvent.is_covered == 1).inspect()
