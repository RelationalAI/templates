"""Semantic schema for the synthetic eligibility records template: plans, providers, and age buckets."""

from relationalai.semantics import Integer, Model, String

model = Model("synthetic_eligibility_records")

# Plan concept: an insurance plan offering.
Plan = model.Concept("Plan", identify_by={"id": Integer})
Plan.plan_type = model.Property(f"{Plan} has {String:plan_type}")
Plan.network_id = model.Property(f"{Plan} has {Integer:network_id}")
# Provider concept: a primary-care provider in exactly one network.
Provider = model.Concept("Provider", identify_by={"id": Integer})
Provider.name = model.Property(f"{Provider} has {String:name}")
Provider.network_id = model.Property(f"{Provider} has {Integer:network_id}")
# AgeBucket concept: representative age (years) keyed by integer bucket id.
# Four buckets span the adult/senior split (two under 65, two at or above).
# Categorical age keeps every decision domain compact and similar in size,
# so solver enumeration produces structurally diverse records across all
# three slots; a per-year age would let the solver shift birth year by one
# across solutions and defeat batch diversity.
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")
