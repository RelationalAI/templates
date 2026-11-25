"""Semantic schema for the diet template: foods, nutrients, and scenarios."""

from relationalai.semantics import Float, Model, String

model = Model("diet")

# Nutrient concept: nutritional requirements with min/max bounds.
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")

# Food concept: foods with cost and per-nutrient content (ternary property).
Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")

# Scenario concept: nutrient_scaling parameter variations.
Scenario = model.Concept("Scenario", identify_by={"scenario_name": String})
Scenario.nutrient_scaling = model.Property(f"{Scenario} has {Float:nutrient_scaling}")
