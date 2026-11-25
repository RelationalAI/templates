"""Semantic schema for the disease outbreak prevention template: facilities and the connections between them."""

from relationalai.semantics import Float, Integer, Model, String

# Create a Semantics model container
model = Model("disease_outbreak_prevention")

# Facility concept: healthcare facilities, testing centers, and community organizations.
Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has {String:name}")
Facility.type = model.Property(f"{Facility} has {String:type}")
Facility.region = model.Property(f"{Facility} has {String:region}")

# Facility connection concept to represent edges in the network
FacilityConnection = model.Concept(
    "FacilityConnection",
    identify_by={"from_facility": Facility, "to_facility": Facility}
)

FacilityConnection.transfer_volume = model.Property(f"{FacilityConnection} has {Float:transfer_volume}")
FacilityConnection.contact_intensity = model.Property(f"{FacilityConnection} has {Float:contact_intensity}")
