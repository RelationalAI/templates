"""Semantic schema for the commercial underwriting template: insured entities, policies, locations, and coverages."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("commercial_underwriting")

# InsuredEntity concept: the named insured business at the top of the hierarchy.
InsuredEntity = model.Concept("InsuredEntity", identify_by={"id": Integer})
InsuredEntity.name = model.Property(f"{InsuredEntity} has {String:name}")
InsuredEntity.industry_code = model.Property(f"{InsuredEntity} has {String:industry_code}")
InsuredEntity.years_in_business = model.Property(f"{InsuredEntity} has {Integer:years_in_business}")
InsuredEntity.annual_revenue = model.Property(f"{InsuredEntity} has {Float:annual_revenue}")

# Policy concept: a commercial property/casualty policy bound to one insured entity.
Policy = model.Concept("Policy", identify_by={"id": Integer})
Policy.insured_entity = model.Relationship(f"{Policy} bound to {InsuredEntity}")
Policy.policy_type = model.Property(f"{Policy} has {String:policy_type}")
Policy.effective_date = model.Property(f"{Policy} has {String:effective_date}")
Policy.total_premium = model.Property(f"{Policy} has {Float:total_premium}")

# Location concept: a physical location/building scheduled on a policy.
Location = model.Concept("Location", identify_by={"id": Integer})
Location.policy = model.Relationship(f"{Location} scheduled on {Policy}")
Location.address = model.Property(f"{Location} at {String:address}")
Location.occupancy_class = model.Property(f"{Location} has {String:occupancy_class}")
Location.year_built = model.Property(f"{Location} has {Integer:year_built}")
Location.square_feet = model.Property(f"{Location} has {Integer:square_feet}")
Location.fire_protection_class = model.Property(f"{Location} has {Integer:fire_protection_class}")
Location.replacement_value = model.Property(f"{Location} has {Float:replacement_value}")

# Coverage concept: a coverage line scheduled on a location.
Coverage = model.Concept("Coverage", identify_by={"id": Integer})
Coverage.location = model.Relationship(f"{Coverage} scheduled on {Location}")
Coverage.coverage_type = model.Property(f"{Coverage} has {String:coverage_type}")
Coverage.coverage_limit = model.Property(f"{Coverage} has {Float:coverage_limit}")
Coverage.deductible = model.Property(f"{Coverage} has {Float:deductible}")
