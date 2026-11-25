"""Order fills: the quantity filled across each order's events in the generated trace."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

# Declares OrderEvent.fill_qty, the decision the filled quantity sums.
from . import lifecycle_trace  # noqa: F401
from .schema import Order, OrderEvent, model

# The total lives on a concept of its own, not on Order: a value computed from the solution on
# a concept the solve reads leaves the solution empty after the first refresh. An order with no
# event has no fill total.
OrderFill = model.Concept("OrderFill", identify_by={"order_id": Integer})
OrderFill.filled_qty = model.Property(f"{OrderFill} has filled qty {Integer:filled_qty}")
model.where(OrderEvent.order(Order)).define(OrderFill.new(order_id=Order.id))
model.define(
    OrderFill.filled_qty(
        aggs.sum(OrderEvent, OrderEvent.fill_qty)
        .per(OrderFill)
        .where(OrderEvent.order.id == OrderFill.order_id)
    )
)
