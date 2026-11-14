"""Semantic schema for the patient cohort recruitment template: genes, therapies, adverse events, patients, and their events."""

from relationalai.semantics import Integer, Model, String

model = Model("patient_cohort_recruitment")

# Concept: gene (an ontology node).
Gene = model.Concept("Gene", identify_by={"id": Integer})
Gene.name = model.Property(f"{Gene} has {String:name}")

# Concept: gene-ontology `is_a` edge. The CSV stores child -> parent
# (standard OMOP / SNOMED convention), but we expose the edge to the
# Graph reasoner with src=parent, dst=child, so reachability from the
# kinase root *follows the subclass tree downwards* and lands on every
# member of the pathway.
GeneIsA = model.Concept("GeneIsA", identify_by={"child_id": Integer, "parent_id": Integer})
GeneIsA.parent = model.Property(f"{GeneIsA} has parent {Gene:parent}")
GeneIsA.child = model.Property(f"{GeneIsA} has child {Gene:child}")

# Concept: therapy (drug arm).
Therapy = model.Concept("Therapy", identify_by={"id": Integer})
Therapy.name = model.Property(f"{Therapy} has {String:name}")

# Concept: adverse-event term (toxicity dictionary entry).
AdverseEvent = model.Concept("AdverseEvent", identify_by={"id": Integer})
AdverseEvent.term = model.Property(f"{AdverseEvent} has {String:term}")

# Concept: patient.
Patient = model.Concept("Patient", identify_by={"id": Integer})
Patient.name = model.Property(f"{Patient} has {String:name}")
Patient.age_years = model.Property(f"{Patient} has {Integer:age_years}")

# Concept: mutation event (observed mutation in a patient at a time).
MutationEvent = model.Concept("MutationEvent", identify_by={"id": Integer})
MutationEvent.patient = model.Property(f"{MutationEvent} from {Patient:patient}")
MutationEvent.gene = model.Property(f"{MutationEvent} hits {Gene:gene}")
MutationEvent.t_days = model.Property(f"{MutationEvent} at {Integer:t_days}")

# Concept: therapy event (treatment received by a patient at a time).
TherapyEvent = model.Concept("TherapyEvent", identify_by={"id": Integer})
TherapyEvent.patient = model.Property(f"{TherapyEvent} from {Patient:patient}")
TherapyEvent.therapy = model.Property(f"{TherapyEvent} uses {Therapy:therapy}")
TherapyEvent.t_days = model.Property(f"{TherapyEvent} at {Integer:t_days}")

# Concept: adverse-event occurrence (AE observed in a patient at a time).
AdverseEventOcc = model.Concept("AdverseEventOcc", identify_by={"id": Integer})
AdverseEventOcc.patient = model.Property(f"{AdverseEventOcc} from {Patient:patient}")
AdverseEventOcc.term = model.Property(f"{AdverseEventOcc} is {AdverseEvent:term}")
AdverseEventOcc.t_days = model.Property(f"{AdverseEventOcc} at {Integer:t_days}")
