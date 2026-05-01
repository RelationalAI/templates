"""Synthetic Order Lifecycle (constrained generation) template.

This script demonstrates synthesised banking-event traces in RelationalAI:

- Pre-allocate fixed (order, event-slot) rows; the solver decides each
  event's type (PLACE / MODIFY / CANCEL / FILL), timestamp, venue, quantity,
  and tick price.
- Enforce MiFID II / Reg NMS-flavour sequencing rules: PLACE first, nothing
  after CANCEL, exactly one PLACE per order, fill-quantity conservation
  across the FILL events, venue eligibility per symbol.
- Solve as constraint satisfaction (MiniZinc) and inspect the generated trace.

All decisions are integer: prices are integer ticks (1c), times are integer
milliseconds, quantities are integer shares.

Run:
    `python synthetic_order_lifecycle.py`

Output:
    Prints the formulation, the generated event trace (one row per slot),
    the per-order filled-quantity totals, and post-solve constraint
    verification.
"""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, all_different, implies

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
symbols_csv = read_csv(data_dir / "symbols.csv")
model.define(Symbol.new(model.data(symbols_csv).to_schema()))

# Concept: trading venue
Venue = model.Concept("Venue", identify_by={"id": Integer})
Venue.name = model.Property(f"{Venue} has {String:name}")
venues_csv = read_csv(data_dir / "venues.csv")
model.define(Venue.new(model.data(venues_csv).to_schema()))

# Concept: disallowed (symbol, venue) pairs -- derived from the allowed list
# in symbol_venues.csv. The CSP uses the disallowed dual so the constraint
# stays inside the supported arithmetic (!=, *, +, -, ...).
sv_csv = read_csv(data_dir / "symbol_venues.csv")
all_pairs = [(int(s), int(v)) for s in symbols_csv["id"] for v in venues_csv["id"]]
allowed_pairs = {(int(r.symbol_id), int(r.venue_id)) for r in sv_csv.itertuples()}
disallowed_csv = DataFrame(
    [
        {"symbol_id": s, "venue_id": v}
        for (s, v) in all_pairs
        if (s, v) not in allowed_pairs
    ]
)

NotAllowedSymbolVenue = model.Concept(
    "NotAllowedSymbolVenue",
    identify_by={"symbol_id": Integer, "venue_id": Integer},
)
model.define(NotAllowedSymbolVenue.new(model.data(disallowed_csv).to_schema()))

# Concept: orders (the surveillance subjects)
Order = model.Concept("Order", identify_by={"id": Integer})
Order.original_qty = model.Property(f"{Order} has {Integer:original_qty}")
Order.original_tick_price = model.Property(f"{Order} has {Integer:original_tick_price}")
Order.symbol = model.Property(f"{Order} is for {Symbol:symbol}")
orders_csv = read_csv(data_dir / "orders.csv")
orders_data = model.data(orders_csv)
model.define(
    o := Order.new(id=orders_data.id),
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
OrderEvent.order = model.Property(f"{OrderEvent} belongs to {Order:order}")
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
# Auxiliary integer: equals qty when is_fill == 1 and 0 when is_fill == 0.
# Lets the per-order fill-conservation aggregate stay purely linear.
OrderEvent.fill_qty = model.Property(f"{OrderEvent} has fill qty {Integer:fill_qty}")

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
problem.solve_for(
    OrderEvent.fill_qty, name=["fill_qty", OrderEvent.event_id], lower=0, upper=qty_max
)

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# Each event has exactly one type.
type_sum_ic = model.require(
    OrderEvent.is_place + OrderEvent.is_modify + OrderEvent.is_cancel + OrderEvent.is_fill == 1
)
problem.satisfy(type_sum_ic)

# Exactly one PLACE event per order.
exactly_one_place_ic = model.require(sum(OrderEvent.is_place).per(OrderEvent.order) == 1)
problem.satisfy(exactly_one_place_ic)

# At most one CANCEL event per order.
at_most_one_cancel_ic = model.require(sum(OrderEvent.is_cancel).per(OrderEvent.order) <= 1)
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
place_first_ic = model.where(
    A.order == B.order,
    A.event_id != B.event_id,
).require(implies(A.is_place == 1, A.ts_ms < B.ts_ms))
problem.satisfy(place_first_ic)

# Nothing-after-CANCEL: if A is a CANCEL event, A.ts_ms > B.ts_ms for every
# other event B in the same order.
no_after_cancel_ic = model.where(
    A.order == B.order,
    A.event_id != B.event_id,
).require(implies(A.is_cancel == 1, A.ts_ms > B.ts_ms))
problem.satisfy(no_after_cancel_ic)

# Quantity bound: every event's qty <= the order's original_qty.
qty_upper_ic = model.require(OrderEvent.qty <= OrderEvent.order.original_qty)
problem.satisfy(qty_upper_ic)

# PLACE event's qty matches the order's original_qty.
place_qty_match_ic = model.require(
    implies(OrderEvent.is_place == 1, OrderEvent.qty == OrderEvent.order.original_qty)
)
problem.satisfy(place_qty_match_ic)

# PLACE event's tick_price matches the order's original_tick_price (so the
# generated trace stays internally consistent with the order's price).
place_price_match_ic = model.require(
    implies(
        OrderEvent.is_place == 1,
        OrderEvent.tick_price == OrderEvent.order.original_tick_price,
    )
)
problem.satisfy(place_price_match_ic)

# Venue eligibility: chosen venue must not match any disallowed pair for the
# order's symbol. The chain `OrderEvent.order.symbol.id` walks event -> order
# -> symbol and joins on the disallowed pair's symbol_id.
NA = NotAllowedSymbolVenue.ref()
venue_ok_ic = model.where(
    OrderEvent.order.symbol.id(NA.symbol_id),
).require(NA.venue_id != OrderEvent.venue_id)
problem.satisfy(venue_ok_ic)

# Channel fill_qty to (qty when is_fill else 0).
fill_qty_match_on_ic = model.require(
    implies(OrderEvent.is_fill == 1, OrderEvent.fill_qty == OrderEvent.qty)
)
problem.satisfy(fill_qty_match_on_ic)

fill_qty_zero_off_ic = model.require(implies(OrderEvent.is_fill == 0, OrderEvent.fill_qty == 0))
problem.satisfy(fill_qty_zero_off_ic)

# Quantity conservation: total filled quantity across an order's FILL events
# cannot exceed the original_qty. Linear in fill_qty.
fill_sum_ic = model.require(
    sum(OrderEvent.fill_qty).per(OrderEvent.order) <= OrderEvent.order.original_qty
)
problem.satisfy(fill_sum_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Re-check the relational arithmetic ICs in the returned solution. The
# all_different- and implies-bodied ICs are solver-only -- never pass them to
# verify(). The relational engine cannot re-evaluate wire-format constraint
# relations and would return silently-OK regardless of whether the constraint
# actually holds in the solution.
problem.verify(
    type_sum_ic,
    exactly_one_place_ic,
    at_most_one_cancel_ic,
    qty_upper_ic,
    venue_ok_ic,
    fill_sum_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect the generated trace
# --------------------------------------------------

print("\nGenerated event trace (one row per slot, sorted by order then timestamp):")
trace_df = (
    model.select(
        OrderEvent.order.id.alias("order_id"),
        OrderEvent.order.symbol.name.alias("symbol"),
        OrderEvent.event_id.alias("event_id"),
        OrderEvent.ts_ms.alias("ts_ms"),
        OrderEvent.is_place.alias("is_place"),
        OrderEvent.is_modify.alias("is_modify"),
        OrderEvent.is_cancel.alias("is_cancel"),
        OrderEvent.is_fill.alias("is_fill"),
        OrderEvent.qty.alias("qty"),
        OrderEvent.tick_price.alias("tick_price"),
        Venue.name.alias("venue"),
    )
    .where(Venue.id(OrderEvent.venue_id))
    .to_df()
)
# Display-side: collapse the four binary indicators into one human-readable label
# and sort by (order, ts) so each order's events appear in temporal order.
type_map = {"is_place": "PLACE", "is_modify": "MODIFY", "is_cancel": "CANCEL", "is_fill": "FILL"}
trace_df["type"] = trace_df[list(type_map)].astype("int64").idxmax(axis=1).map(type_map)
trace_df = (
    trace_df.drop(columns=list(type_map))
    .astype(
        {
            "order_id": "int64",
            "event_id": "int64",
            "ts_ms": "int64",
            "qty": "int64",
            "tick_price": "int64",
        }
    )
    .sort_values(["order_id", "ts_ms"])
    .reset_index(drop=True)[
        ["order_id", "symbol", "event_id", "ts_ms", "type", "qty", "tick_price", "venue"]
    ]
)
print(trace_df.to_string(index=False))

print("\nFilled quantity per order (cannot exceed Order.original_qty):")
model.select(
    Order.id.alias("order_id"),
    Order.original_qty.alias("original_qty"),
    sum(OrderEvent.fill_qty).per(Order).alias("filled_qty"),
).where(OrderEvent.order(Order)).inspect()
