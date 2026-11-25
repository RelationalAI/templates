"""Lifecycle trace: the decision problem that yields one valid event trace for the pre-allocated slots."""

from relationalai.semantics import Integer, String
from relationalai.semantics import sum as rai_sum
from relationalai.semantics.reasoners.prescriptive import Problem, all_different, implies

from .schema import EventType, NotAllowedSymbolVenue, Order, OrderEvent, model
from .source import orders_csv, venues_csv

# One solve = one synthetic trace over the fixed (order, event-slot) pool.
# TS_MAX is kept tight (1s horizon) so MiniZinc finishes the demo in <2s;
# bump it to a realistic session window (e.g. 23_400_000 ms = 6.5h) on
# real-shaped data.
TS_MIN = 1
TS_MAX = 1_000

# Enum-indexed type decision: one binary indicator per (event slot, type).
OrderEvent.has_type = model.Property(
    f"{OrderEvent} is {EventType:event_type} if {Integer:indicator}"
)
OrderEvent.ts_ms = model.Property(f"{OrderEvent} occurs at {Integer:ts_ms}")
OrderEvent.venue_id = model.Property(f"{OrderEvent} on venue {Integer:venue_id}")
OrderEvent.qty = model.Property(f"{OrderEvent} has qty {Integer:qty}")
OrderEvent.tick_price = model.Property(f"{OrderEvent} has tick price {Integer:tick_price}")
# Auxiliary integer: equals qty when the FILL indicator is 1, else 0.
# Lets the per-order fill-conservation aggregate stay purely linear.
OrderEvent.fill_qty = model.Property(f"{OrderEvent} has fill qty {Integer:fill_qty}")

# Domain bounds derived from data so the model adapts to the CSV pool.
qty_max = int(orders_csv["original_qty"].max())
price_max = int(orders_csv["original_tick_price"].max())
venue_max = int(venues_csv["id"].max())

problem = Problem(model, Integer, name="synthetic_order_lifecycle")

problem.solve_for(
    OrderEvent.has_type, type="bin", name=["is_type", OrderEvent.event_id]
)
problem.solve_for(
    OrderEvent.ts_ms, name=["ts", OrderEvent.event_id], lower=TS_MIN, upper=TS_MAX
)
problem.solve_for(
    OrderEvent.venue_id, name=["venue", OrderEvent.event_id], lower=1, upper=venue_max
)
problem.solve_for(OrderEvent.qty, name=["qty", OrderEvent.event_id], lower=1, upper=qty_max)
problem.solve_for(
    OrderEvent.tick_price,
    name=["price", OrderEvent.event_id],
    lower=1,
    upper=price_max,
)
problem.solve_for(
    OrderEvent.fill_qty, name=["fill_qty", OrderEvent.event_id], lower=0, upper=qty_max
)

# Each event has exactly one type: its four (event, type) indicators sum to 1.
type_sum_ic = model.where(OrderEvent).require(rai_sum(OrderEvent.has_type).per(OrderEvent) == 1)
problem.satisfy(type_sum_ic)

# Exactly one PLACE event per order. The where-clause binds `place_ind` to
# each event's PLACE indicator; the aggregate sums it per order, one term per event.
place_ind = Integer.ref()
exactly_one_place_ic = model.where(
    OrderEvent.has_type(EventType.PLACE, place_ind), OrderEvent.order == Order
).require(rai_sum(OrderEvent, place_ind).per(Order) == 1)
problem.satisfy(exactly_one_place_ic)

# At most one CANCEL event per order.
cancel_ind = Integer.ref()
at_most_one_cancel_ic = model.where(
    OrderEvent.has_type(EventType.CANCEL, cancel_ind), OrderEvent.order == Order
).require(rai_sum(OrderEvent, cancel_ind).per(Order) <= 1)
problem.satisfy(at_most_one_cancel_ic)

# Distinct ts_ms within an order (every event has its own moment).
# Lowers to MiniZinc's native alldifferent propagator.
distinct_ts_ic = model.require(all_different(OrderEvent.ts_ms).per(OrderEvent.order))
problem.satisfy(distinct_ts_ic)

# Pairwise temporal rules use two refs into OrderEvent.
A = OrderEvent.ref()
B = OrderEvent.ref()

# PLACE-first: if A is a PLACE event, A.ts_ms < B.ts_ms for every other
# event B in the same order.
a_place_ind = Integer.ref()
place_first_ic = model.where(
    A.order == B.order,
    A.event_id != B.event_id,
    A.has_type(EventType.PLACE, a_place_ind),
).require(implies(a_place_ind == 1, A.ts_ms < B.ts_ms))
problem.satisfy(place_first_ic)

# Nothing-after-CANCEL: if A is a CANCEL event, A.ts_ms > B.ts_ms for every
# other event B in the same order.
a_cancel_ind = Integer.ref()
no_after_cancel_ic = model.where(
    A.order == B.order,
    A.event_id != B.event_id,
    A.has_type(EventType.CANCEL, a_cancel_ind),
).require(implies(a_cancel_ind == 1, A.ts_ms > B.ts_ms))
problem.satisfy(no_after_cancel_ic)

# Quantity bound: every event's qty <= the order's original_qty.
qty_upper_ic = model.where(OrderEvent).require(OrderEvent.qty <= OrderEvent.order.original_qty)
problem.satisfy(qty_upper_ic)

# PLACE event's qty matches the order's original_qty.
place_qty_ind = Integer.ref()
place_qty_match_ic = model.where(
    OrderEvent.has_type(EventType.PLACE, place_qty_ind)
).require(implies(place_qty_ind == 1, OrderEvent.qty == OrderEvent.order.original_qty))
problem.satisfy(place_qty_match_ic)

# PLACE event's tick_price matches the order's original_tick_price (so the
# generated trace stays internally consistent with the order's price).
place_price_ind = Integer.ref()
place_price_match_ic = model.where(
    OrderEvent.has_type(EventType.PLACE, place_price_ind)
).require(
    implies(
        place_price_ind == 1,
        OrderEvent.tick_price == OrderEvent.order.original_tick_price,
    )
)
problem.satisfy(place_price_match_ic)

# Venue eligibility: chosen venue must not match any disallowed pair for the
# order's symbol. The chain `OrderEvent.order.symbol.id` walks event -> order
# -> symbol and joins on the disallowed pair's symbol_id.
venue_ok_ic = model.where(OrderEvent.order.symbol.id(NotAllowedSymbolVenue.symbol_id)).require(
    NotAllowedSymbolVenue.venue_id != OrderEvent.venue_id
)
problem.satisfy(venue_ok_ic)

# Channel fill_qty to (qty when the FILL indicator is 1, else 0).
fill_on_ind = Integer.ref()
fill_qty_match_on_ic = model.where(
    OrderEvent.has_type(EventType.FILL, fill_on_ind)
).require(implies(fill_on_ind == 1, OrderEvent.fill_qty == OrderEvent.qty))
problem.satisfy(fill_qty_match_on_ic)

fill_off_ind = Integer.ref()
fill_qty_zero_off_ic = model.where(
    OrderEvent.has_type(EventType.FILL, fill_off_ind)
).require(implies(fill_off_ind == 0, OrderEvent.fill_qty == 0))
problem.satisfy(fill_qty_zero_off_ic)

# Quantity conservation: total filled quantity across an order's FILL events
# cannot exceed the original_qty. Linear in fill_qty.
fill_sum_ic = model.where(OrderEvent.order == Order).require(
    rai_sum(OrderEvent, OrderEvent.fill_qty).per(Order) <= Order.original_qty
)
problem.satisfy(fill_sum_ic)

# Derived enum-typed relationship mapping each event to its chosen type: the
# member whose (event, type) indicator the solver set to 1 -- exactly one
# per event, guaranteed by the one-hot IC. The trace then reads the type
# label off the member's built-in `.name`.
OrderEvent.event_type = model.Relationship(
    f"{OrderEvent} has decided {EventType:event_type}"
)
for member in EventType:
    chosen_ind = Integer.ref()
    model.define(OrderEvent.event_type(member)).where(
        OrderEvent.has_type(member, chosen_ind), chosen_ind == 1
    )

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=60)

# The solve's status, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"synthetic order lifecycle solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))
