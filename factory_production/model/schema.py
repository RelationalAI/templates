"""Semantic schema for the factory production template: factories and the products each one makes."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("factory_production")
Concept, Property = model.Concept, model.Property

# Factory concept: factories with total resource availability (hours).
Factory = Concept("Factory", identify_by={"name": String})
Factory.avail = Property(f"{Factory} has {Float:avail}")

# Product concept: products with production rate, unit profit, demand cap, and parent factory.
Product = Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = Property(f"{Product} is produced by {Factory}")
Product.rate = Property(f"{Product} has {Float:rate}")
Product.profit = Property(f"{Product} has {Float:profit}")
Product.demand = Property(f"{Product} has {Integer:demand}")
