"""Semantic schema for the warehouse allocation template: sites, routes, and demands."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("warehouse_allocation")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# Site concept: distribution sites such as warehouses and stores.
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.region = Property(f"{Site} has {String:region}")
Site.type = Property(f"{Site} has {String:type}")
Site.holding_cost = Property(f"{Site} has {Float:holding_cost}")

# Route concept: transport links between distribution sites.
Route = Concept("Route", identify_by={"id": Integer})
Route.source = Relationship(f"{Route} from {Site}", short_name="source")
Route.dest = Relationship(f"{Route} to {Site}", short_name="dest")
Route.capacity = Property(f"{Route} has {Integer:capacity}")
Route.transport_cost = Property(f"{Route} has {Float:transport_cost}")

# Demand concept: inventory requirements at each site.
Demand = Concept("Demand", identify_by={"id": Integer})
Demand.site = Relationship(f"{Demand} at {Site}")
Demand.quantity = Property(f"{Demand} has {Integer:quantity}")
