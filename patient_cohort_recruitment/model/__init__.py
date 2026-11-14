"""Patient cohort recruitment (Graph reachability + Rules + CSP) template: the model.

This package demonstrates a three-reasoner pipeline in RelationalAI:

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

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.cohort_report` then prints the report from the deployed
    model.
"""

from .reasoning import (
    CoverableAdverseEvent,
    CoverableGene,
    CoverableTherapy,
    EligiblePatient,
    KinaseGene,
    SolveStatus,
    problem,
)
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
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "AdverseEvent",
    "AdverseEventOcc",
    "CoverableAdverseEvent",
    "CoverableGene",
    "CoverableTherapy",
    "EligiblePatient",
    "Gene",
    "GeneIsA",
    "KinaseGene",
    "MutationEvent",
    "Patient",
    "SolveStatus",
    "Therapy",
    "TherapyEvent",
    "model",
    "problem",
]
