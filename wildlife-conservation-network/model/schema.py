"""Semantic schema for the wildlife conservation template: organizations and partnerships."""

from relationalai.semantics import Integer, Model, String

# Create a Semantics model container
model = Model("wildlife_conservation")

# Organization concept: NGOs, research stations, wildlife reserves, veterinary services.
Organization = model.Concept("Organization", identify_by={"id": Integer})
Organization.name = model.Property(f"{Organization} has {String:name}")
Organization.type = model.Property(f"{Organization} has {String:type}")
Organization.region = model.Property(f"{Organization} has {String:region}")
Organization.focus_species = model.Property(f"{Organization} has {String:focus_species}")

# Partnership concept to represent edges in the network
Partnership = model.Concept(
    "Partnership",
    identify_by={"org1": Organization, "org2": Organization}
)
