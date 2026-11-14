"""Semantic schema for the shift assignment template: workers, shifts, and coverage scenarios."""

from relationalai.semantics import Integer, Model, String

model = Model("shift_assignment")

# Concept: workers
Worker = model.Concept("Worker", identify_by={"id": Integer})
Worker.name = model.Property(f"{Worker} has {String:name}")

# Concept: shifts with capacity limits
Shift = model.Concept("Shift", identify_by={"id": Integer})
Shift.name = model.Property(f"{Shift} has {String:name}")
Shift.capacity = model.Property(f"{Shift} has {Integer:capacity}")

# Relationship: worker availability for shifts
Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")

# Scenario Concept — min_coverage parameter variations
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_coverage = model.Property(f"{Scenario} has {Integer:min_coverage}")
