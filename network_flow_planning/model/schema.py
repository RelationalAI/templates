"""Semantic schema for the network flow planning template: sites, lanes, and demands."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("network_flow_planning")

# Site concept: a node in the distribution network. The `type` property
# differentiates warehouses (have inventory), transit hubs (pass-through),
# fulfillment centers (have capacity + fixed_cost; binary open decision),
# and customers (have demand).
Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has {String:name}")
Site.type = model.Property(f"{Site} has {String:type}")
Site.inventory = model.Property(f"{Site} has {Float:inventory}")
Site.capacity = model.Property(f"{Site} has {Float:capacity}")
Site.fixed_cost = model.Property(f"{Site} has {Float:fixed_cost}")

# Lane concept: directed transport link between two sites with a unit cost
# and a flow capacity.
Lane = model.Concept("Lane", identify_by={"id": Integer})
Lane.source = model.Relationship(f"{Lane} from {Site}", short_name="source")
Lane.dest = model.Relationship(f"{Lane} to {Site}", short_name="dest")
Lane.cost_per_unit = model.Property(f"{Lane} has {Float:cost_per_unit}")
Lane.capacity = model.Property(f"{Lane} has {Float:capacity}")

# Demand concept: a customer order at a particular site with a quantity.
Demand = model.Concept("Demand", identify_by={"id": Integer})
Demand.site = model.Relationship(f"{Demand} placed at {Site}", short_name="site")
Demand.quantity = model.Property(f"{Demand} has {Float:quantity}")
Demand.customer = model.Property(f"{Demand} for {String:customer}")
Demand.priority = model.Property(f"{Demand} has {Integer:priority}")
