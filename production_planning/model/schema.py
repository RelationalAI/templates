"""Semantic schema for the production planning template: products, machines, rates, and scenarios."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("production_planning")
Concept, Property = model.Concept, model.Property

# Concept: products with demand and profit margin
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")
Product.profit = Property(f"{Product} has {Float:profit}")

# Concept: machines with available hours
Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.hours_available = Property(f"{Machine} has {Float:hours_available}")

# Relationship: production rates for each machine/product combination
Rate = Concept("ProductionRate")
Rate.machine = Property(f"{Rate} on {Machine}", short_name="machine")
Rate.product = Property(f"{Rate} for {Product}", short_name="product")
Rate.hours_per_unit = Property(f"{Rate} has {Float:hours_per_unit}")

# Scenario concept: demand_multiplier parameter variations
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.demand_multiplier = Property(f"{Scenario} has {Float:demand_multiplier}")
