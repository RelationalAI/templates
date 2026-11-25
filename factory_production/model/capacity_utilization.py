"""Capacity utilization: the hours each factory's plan uses and the hours it leaves idle."""

from relationalai.semantics import Float, sum

# Declares Product.x_quantity, the solved quantity the hours are computed from.
from . import production_plan  # noqa: F401
from .schema import Factory, Product, model

# Each product takes quantity / rate hours of its factory, and a factory uses the sum over its
# products. These are relationships, not Factory properties: the solve reads Factory, and a
# Factory property computed from the solution leaves the solution empty after the first refresh.
FactoryHoursUsed = model.Relationship(f"{Factory} uses {Float:hours_used} hours")
model.define(
    FactoryHoursUsed(
        Factory,
        sum(Product, Product.x_quantity / Product.rate).where(Product.factory == Factory).per(Factory),
    )
)

# The hours a factory's plan leaves unused. A capacity with idle hours is slack, so its
# shadow price is zero.
FactoryIdleHours = model.Relationship(f"{Factory} leaves {Float:idle_hours} hours idle")
hours_used = Float.ref()
model.where(FactoryHoursUsed(Factory, hours_used)).define(
    FactoryIdleHours(Factory, Factory.avail - hours_used)
)
