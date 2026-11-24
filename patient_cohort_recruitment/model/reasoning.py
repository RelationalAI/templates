"""Cohort selection: gene closure, eligibility and coverage rules, and the cohort CSP."""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import (
    AdverseEvent,
    AdverseEventOcc,
    Gene,
    GeneIsA,
    MutationEvent,
    Patient,
    Therapy,
    TherapyEvent,
    model,
)
from .source import KINASE_ROOT_GENE_ID

# Model parameters.
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
    name="gene_ontology",
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
# count, and vice versa. Only therapies and AEs with a within-window
# qualifying pair are counted.
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

problem = Problem(model, Integer, name="patient_cohort_recruitment")

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
# Configure the solve
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=60)

# The solve's status, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"cohort solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))
