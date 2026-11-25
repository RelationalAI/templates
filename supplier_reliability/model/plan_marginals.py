"""Plan marginals: each lane's reduced cost and basis status, each capacity's and demand's shadow
price, and the ranking of the supplier capacities by shadow price magnitude."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

from .schema import Product, Supplier, SupplyOrder, model
from .sourcing_plan import cap, meet, qty_var

# The sensitivity marginals, which the deployed model publishes for the queries: each lane's
# reduced cost and basis status, and each capacity's and demand's shadow price, keyed by the
# entity they belong to.
lane_reduced_cost, lane_basis, capacity_price, demand_price = Float.ref(), String.ref(), Float.ref(), Float.ref()
LaneReducedCost = model.Relationship(f"supplier_reliability_baseline {SupplyOrder} has reduced cost {Float:reduced_cost}")
LaneBasisStatus = model.Relationship(f"supplier_reliability_baseline {SupplyOrder} has basis status {String:basis_status}")
CapacityShadowPrice = model.Relationship(f"supplier_reliability_baseline {Supplier} has capacity shadow price {Float:shadow_price}")
DemandShadowPrice = model.Relationship(f"supplier_reliability_baseline {Product} has demand shadow price {Float:shadow_price}")
model.where(qty_var.reduced_cost(lane_reduced_cost)).define(LaneReducedCost(qty_var.supplyorder, lane_reduced_cost))
model.where(qty_var.basis_status(lane_basis)).define(LaneBasisStatus(qty_var.supplyorder, lane_basis))
model.where(cap.shadow_price(capacity_price)).define(CapacityShadowPrice(cap.supplier, capacity_price))
model.where(meet.shadow_price(demand_price)).define(DemandShadowPrice(meet.product, demand_price))

# The supplier capacities ranked by the magnitude of their shadow price, largest first, ties
# broken by supplier name. The first is the capacity whose marginal unit moves the bill the
# most. The magnitude is negated so both keys sort ascending, a form every backend ranks.
CapacityPriceRank = model.Relationship(
    f"supplier_reliability_baseline {Supplier} ranks {Integer:rank} by capacity shadow price magnitude"
)
model.where(
    CapacityShadowPrice(Supplier, capacity_price),
    capacity_rank := aggs.rank(-math.abs(capacity_price), Supplier.name),
).define(CapacityPriceRank(Supplier, capacity_rank))
