"""Semantic schema for the humanitarian aid supply chain template: distribution points and the supply routes between them."""

from relationalai.semantics import Float, Integer, Model, String

# Create a Semantics model container
model = Model("humanitarian_aid_supply_chain")

# DistributionPoint concept: airports, warehouses, border crossings, relief camps, etc.
DistributionPoint = model.Concept("DistributionPoint", identify_by={"id": Integer})
DistributionPoint.name = model.Property(f"{DistributionPoint} has {String:name}")
DistributionPoint.type = model.Property(f"{DistributionPoint} has {String:type}")
DistributionPoint.region = model.Property(f"{DistributionPoint} has {String:region}")
DistributionPoint.capacity = model.Property(f"{DistributionPoint} has {Integer:capacity}")
DistributionPoint.population_served = model.Property(f"{DistributionPoint} has {Integer:population_served}")

# SupplyRoute concept to represent edges in the network
SupplyRoute = model.Concept(
    "SupplyRoute",
    identify_by={"from_point": DistributionPoint, "to_point": DistributionPoint}
)
SupplyRoute.route_capacity = model.Property(f"{SupplyRoute} has {Integer:route_capacity}")
SupplyRoute.reliability_score = model.Property(f"{SupplyRoute} has {Float:reliability_score}")
SupplyRoute.distance_km = model.Property(f"{SupplyRoute} has {Float:distance_km}")
