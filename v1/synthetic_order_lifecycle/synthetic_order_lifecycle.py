"""Synthetic Order Lifecycle (constrained generation) template.

This script demonstrates synthesised banking-event traces in RelationalAI:

- Pre-allocate fixed (order, event-slot) rows; the solver decides each event's
  type (PLACE / MODIFY / CANCEL / FILL), timestamp, venue, quantity, and tick
  price.
- Enforce MiFID II / RegNMS-flavour sequencing rules: PLACE first, nothing
  after CANCEL, exactly one PLACE per order, fill-quantity conservation
  across the FILL events, venue eligibility per symbol.
- Solve as constraint satisfaction (MiniZinc / Chuffed) and inspect the
  generated trace.

Modeling approach:
- Status types are encoded as four binary indicators per event
  (is_place / is_modify / is_cancel / is_fill) whose sum is 1.
- All decisions are integer; prices are integer ticks (1c), times are
  integer milliseconds, quantities are integer shares.
- Conditional rules (PLACE-first, nothing-after-CANCEL, PLACE-qty matches the
  original order qty) are encoded with a bounded big-M so the model stays
  linear and CSP-portable.

Run:
    `python synthetic_order_lifecycle.py`

Output:
    Prints the formulation, the generated event trace ordered by order and
    timestamp, and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# One solve = one synthetic trace over the fixed (order, event-slot) pool.
# Bounded ms horizon keeps the search space small for the demo.
TS_MIN = 1
TS_MAX = 1_000

model = Model("synthetic_order_lifecycle")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: tradable symbol
Symbol = model.Concept("Symbol", identify_by={"id": Integer})
Symbol.name = model.Property(f"{Symbol} has {String:name}")
Symbol.tick_size_cents = model.Property(f"{Symbol} has {Integer:tick_size_cents}")
symbols_csv = read_csv(data_dir / "symbols.csv")
model.define(Symbol.new(model.data(symbols_csv).to_schema()))

# Concept: trading venue
Venue = model.Concept("Venue", identify_by={"id": Integer})
Venue.name = model.Property(f"{Venue} has {String:name}")
venues_csv = read_csv(data_dir / "venues.csv")
model.define(Venue.new(model.data(venues_csv).to_schema()))

# Relationship: which venue ids each symbol allows
# Used as a table-style constraint over the event's venue_id decision variable.
Symbol.allows = model.Relationship(f"{Symbol} allows venue {Integer:venue_id}")
sv_csv = read_csv(data_dir / "symbol_venues.csv")
sv_data = model.data(sv_csv)
model.define(Symbol.allows(sv_data.venue_id)).where(
    Symbol.id(sv_data.symbol_id),
)

# Concept: orders (the surveillance subjects)
Order = model.Concept("Order", identify_by={"id": Integer})
Order.side = model.Property(f"{Order} has {String:side}")
Order.original_qty = model.Property(f"{Order} has {Integer:original_qty}")
Order.original_tick_price = model.Property(f"{Order} has {Integer:original_tick_price}")
Order.symbol = model.Relationship(f"{Order} is for {Symbol}")
orders_csv = read_csv(data_dir / "orders.csv")
orders_data = model.data(orders_csv)
model.define(
    o := Order.new(id=orders_data.id),
    o.side(orders_data.side),
    o.original_qty(orders_data.original_qty),
    o.original_tick_price(orders_data.original_tick_price),
)
model.define(Order.symbol(Symbol)).where(
    Order.id(orders_data.id),
    Symbol.id(orders_data.symbol_id),
)

# Concept: pre-allocated event slots (each tied to one order)
# The solver decides each slot's type, timestamp, venue, quantity, tick price.
OrderEvent = model.Concept("OrderEvent", identify_by={"event_id": Integer})
OrderEvent.order = model.Relationship(f"{OrderEvent} belongs to {Order}")
events_csv = read_csv(data_dir / "events.csv")
events_data = model.data(events_csv)
model.define(OrderEvent.new(event_id=events_data.event_id))
model.define(OrderEvent.order(Order)).where(
    OrderEvent.event_id(events_data.event_id),
    Order.id(events_data.order_id),
)

# --------------------------------------------------
# Decision-valued properties on OrderEvent
# --------------------------------------------------

OrderEvent.is_place = model.Property(f"{OrderEvent} is place if {Integer:is_place}")
OrderEvent.is_modify = model.Property(f"{OrderEvent} is modify if {Integer:is_modify}")
OrderEvent.is_cancel = model.Property(f"{OrderEvent} is cancel if {Integer:is_cancel}")
OrderEvent.is_fill = model.Property(f"{OrderEvent} is fill if {Integer:is_fill}")
OrderEvent.ts_ms = model.Property(f"{OrderEvent} occurs at {Integer:ts_ms}")
OrderEvent.venue_id = model.Property(f"{OrderEvent} on venue {Integer:venue_id}")
OrderEvent.qty = model.Property(f"{OrderEvent} has qty {Integer:qty}")
OrderEvent.tick_price = model.Property(f"{OrderEvent} has tick price {Integer:tick_price}")

# Domain bounds derived from data so the model adapts to the CSV pool.
qty_max = int(orders_csv["original_qty"].max())
price_max = int(orders_csv["original_tick_price"].max())
venue_max = int(venues_csv["id"].max())

problem = Problem(model, Integer)

problem.solve_for(OrderEvent.is_place, type="bin", name=["is_place", OrderEvent.event_id])
problem.solve_for(OrderEvent.is_modify, type="bin", name=["is_modify", OrderEvent.event_id])
problem.solve_for(OrderEvent.is_cancel, type="bin", name=["is_cancel", OrderEvent.event_id])
problem.solve_for(OrderEvent.is_fill, type="bin", name=["is_fill", OrderEvent.event_id])
problem.solve_for(OrderEvent.ts_ms, name=["ts", OrderEvent.event_id], lower=TS_MIN, upper=TS_MAX)
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

# Big-M for reified ts_ms ordering rules (any feasible time difference fits).
BIG_M_TS = TS_MAX - TS_MIN + 1
# Big-M for reified PLACE-qty equality (qty domain is [1, qty_max]).
BIG_M_QTY = qty_max

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Each event has exactly one type.
type_sum_ic = model.where(
    OrderEvent.order(Order),
).require(
    OrderEvent.is_place + OrderEvent.is_modify + OrderEvent.is_cancel + OrderEvent.is_fill == 1
)
problem.satisfy(type_sum_ic)

# Exactly one PLACE event per order.
exactly_one_place_ic = model.where(
    OrderEvent.order(Order),
).require(sum(OrderEvent.is_place).per(Order) == 1)
problem.satisfy(exactly_one_place_ic)

# At most one CANCEL event per order.
at_most_one_cancel_ic = model.where(
    OrderEvent.order(Order),
).require(sum(OrderEvent.is_cancel).per(Order) <= 1)
problem.satisfy(at_most_one_cancel_ic)

# Pairwise temporal rules use two refs into OrderEvent.
A = OrderEvent.ref()
B = OrderEvent.ref()

# Distinct ts_ms within an order (every event has its own moment).
distinct_ts_ic = model.where(
    A.order(Order),
    B.order(Order),
    A.event_id < B.event_id,
).require(A.ts_ms != B.ts_ms)
problem.satisfy(distinct_ts_ic)

# PLACE-first: if A is the PLACE event in an order, A.ts_ms < B.ts_ms for every
# other event B in the same order. Reified via big-M so the rule is vacuous
# whenever A.is_place == 0.
place_first_ic = model.where(
    A.order(Order),
    B.order(Order),
    A.event_id != B.event_id,
).require(B.ts_ms - A.ts_ms >= 1 - BIG_M_TS * (1 - A.is_place))
problem.satisfy(place_first_ic)

# Nothing-after-CANCEL: if A is a CANCEL event, A.ts_ms > B.ts_ms for every
# other event B in the same order. Same big-M reification.
no_after_cancel_ic = model.where(
    A.order(Order),
    B.order(Order),
    A.event_id != B.event_id,
).require(A.ts_ms - B.ts_ms >= 1 - BIG_M_TS * (1 - A.is_cancel))
problem.satisfy(no_after_cancel_ic)

# Quantity bound: every event's qty <= the order's original_qty.
qty_upper_ic = model.where(
    OrderEvent.order(Order),
).require(OrderEvent.qty <= Order.original_qty)
problem.satisfy(qty_upper_ic)

# PLACE event's qty equals the order's original_qty. Combined with qty_upper_ic
# above, this enforces equality only when is_place == 1.
place_qty_match_ic = model.where(
    OrderEvent.order(Order),
).require(Order.original_qty - OrderEvent.qty <= BIG_M_QTY * (1 - OrderEvent.is_place))
problem.satisfy(place_qty_match_ic)

# Venue eligibility: the chosen venue_id must be one the symbol allows.
# Symbol.allows is a relationship populated from data; the .require checks the
# decision variable against this relation as a table-style constraint.
venue_ok_ic = model.where(
    OrderEvent.order(Order),
    Order.symbol(Symbol),
).require(Symbol.allows(OrderEvent.venue_id))
problem.satisfy(venue_ok_ic)

# Quantity conservation: total filled quantity across an order's FILL events
# cannot exceed the original_qty.
fill_sum_ic = model.where(
    OrderEvent.order(Order),
).require(sum(OrderEvent.qty * OrderEvent.is_fill).per(Order) <= Order.original_qty)
problem.satisfy(fill_sum_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Confirm constraints hold in the solver's solution.
problem.verify(
    type_sum_ic,
    exactly_one_place_ic,
    at_most_one_cancel_ic,
    distinct_ts_ic,
    place_first_ic,
    no_after_cancel_ic,
    qty_upper_ic,
    place_qty_match_ic,
    venue_ok_ic,
    fill_sum_ic,
)

# Note on termination-status gating: this is a pure satisfaction problem, so
# MiniZinc/Chuffed returns a feasibility status rather than "OPTIMAL". After
# confirming the exact status string from solve_info().display() above, add
# e.g. model.require(problem.termination_status() == "FEASIBLE") to gate.

# --------------------------------------------------
# Inspect the generated trace
# --------------------------------------------------

print("\nGenerated event trace (one row per slot):")
model.select(
    Order.id.alias("order_id"),
    Symbol.name.alias("symbol"),
    OrderEvent.event_id.alias("event_id"),
    OrderEvent.ts_ms.alias("ts_ms"),
    OrderEvent.is_place.alias("is_place"),
    OrderEvent.is_modify.alias("is_modify"),
    OrderEvent.is_cancel.alias("is_cancel"),
    OrderEvent.is_fill.alias("is_fill"),
    OrderEvent.qty.alias("qty"),
    OrderEvent.tick_price.alias("tick_price"),
    OrderEvent.venue_id.alias("venue_id"),
).where(
    OrderEvent.order(Order),
    Order.symbol(Symbol),
).inspect()

print("\nFilled quantity per order (cannot exceed Order.original_qty):")
model.select(
    Order.id.alias("order_id"),
    Order.original_qty.alias("original_qty"),
    sum(OrderEvent.qty * OrderEvent.is_fill).per(Order).alias("filled_qty"),
).where(
    OrderEvent.order(Order),
).inspect()
