"""Plan marginals: each factory capacity's shadow price, each product's reduced cost and basis status,
and the ranking of the capacities by shadow price."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs

from .production_plan import cap, quantity_var
from .schema import Factory, Product, model

# The sensitivity marginals, which the deployed model publishes for the queries: each factory
# capacity's shadow price and each product's reduced cost and basis status, keyed by the entity
# they belong to.
capacity_price, reduced_cost, basis_status = Float.ref(), Float.ref(), String.ref()
CapacityShadowPrice = model.Relationship(f"{Factory} has capacity shadow price {Float:shadow_price}")
ProductReducedCost = model.Relationship(f"{Product} has reduced cost {Float:reduced_cost}")
ProductBasisStatus = model.Relationship(f"{Product} has basis status {String:basis_status}")
model.where(cap.shadow_price(capacity_price)).define(
    CapacityShadowPrice(cap.factory, capacity_price)
)
model.where(quantity_var.reduced_cost(reduced_cost)).define(
    ProductReducedCost(quantity_var.product, reduced_cost)
)
model.where(quantity_var.basis_status(basis_status)).define(
    ProductBasisStatus(quantity_var.product, basis_status)
)

# The capacities ranked by shadow price, largest first, ties broken by factory name. With a
# maximize objective every shadow price is >= 0, so the first is the factory whose marginal
# hour earns the most: the capacity to expand first. The price is negated so both keys sort
# ascending, a form every backend ranks.
CapacityPriceRank = model.Relationship(f"{Factory} ranks {Integer:rank} by capacity shadow price")
model.where(
    CapacityShadowPrice(Factory, capacity_price),
    capacity_rank := aggs.rank(-capacity_price, Factory.name),
).define(CapacityPriceRank(Factory, capacity_rank))
