"""Semantic schema for the retail markdown template: products, discounts, and weeks."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("retail_markdown")

# Concept: products with inventory and demand info
Product = model.Concept("Product", identify_by={"name": String})
Product.initial_price = model.Property(f"{Product} has {Float:initial_price}")
Product.cost = model.Property(f"{Product} has {Float:cost}")
Product.initial_inventory = model.Property(f"{Product} has {Integer:initial_inventory}")
Product.base_demand = model.Property(f"{Product} has {Float:base_demand}")
Product.salvage_rate = model.Property(f"{Product} has {Float:salvage_rate}")

# Concept: discount levels with percentage and demand lift
Discount = model.Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")

# Concept: weeks with seasonal demand multipliers
Week = model.Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")
