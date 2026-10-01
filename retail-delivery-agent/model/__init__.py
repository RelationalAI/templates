"""Import the schema first, then register source bindings on the same model."""

from .schema import (
    DemoState,
    Depot,
    Order,
    OrderDecision,
    PlanSummary,
    Road,
    Store,
    StoreRouteStatus,
    model,
)

# isort: split
from . import sources as sources

__all__ = [
    "DemoState",
    "Depot",
    "Order",
    "OrderDecision",
    "PlanSummary",
    "Road",
    "Store",
    "StoreRouteStatus",
    "model",
    "sources",
]
