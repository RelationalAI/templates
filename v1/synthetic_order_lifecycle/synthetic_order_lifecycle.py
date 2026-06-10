"""Synthetic Order Lifecycle (constrained generation) template.

This script demonstrates a CSP-based synthetic order-lifecycle trace generator in RelationalAI:

- Pre-allocate (order, event-slot) rows and load order, symbol, and venue reference data from CSV.
- Model each event slot as a decision over type (PLACE / MODIFY / CANCEL / FILL), timestamp, venue, quantity, and tick price.
- Encode MiFID II / Reg NMS-flavour sequencing rules: PLACE first, nothing after CANCEL, exactly one PLACE per order, fill-quantity conservation, venue eligibility per symbol.
- Solve as constraint satisfaction (MiniZinc) and verify the relational arithmetic ICs against the returned trace.

Event types are modelled as a `model.Enum` (requires relationalai>=1.12):
one enum-indexed binary decision variable per (event slot, type) replaces
four parallel indicator properties, and the trace reads the chosen type
back by member name instead of collapsing indicator columns in pandas.

All decisions are integer: prices are integer ticks (1c, so 17500 reads as
$175.00), times are integer milliseconds, quantities are integer shares.

Run:
    `python synthetic_order_lifecycle.py`

Output:
    Prints the formulation, the generated event trace (one row per slot),
    the per-order filled-quantity totals, and post-solve verification.
"""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Integer, Model, String
from relationalai.semantics import sum as rai_sum
from relationalai.semantics.reasoners.prescriptive import Problem, all_different, implies

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# One solve = one synthetic trace over the fixed (order, event-slot) pool.
# TS_MAX is kept tight (1s horizon) so MiniZinc finishes the demo in <2s;
# bump it to a realistic session window (e.g. 23_400_000 ms = 6.5h) on
# real-shaped data.
TS_MIN = 1
TS_MAX = 1_000

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("synthetic_order_lifecycle")

# Symbol concept: a tradable instrument.
Symbol = model.Concept("Symbol", identify_by={"id": Integer})
Symbol.name = model.Property(f"{Symbol} has {String:name}")
symbols_csv = read_csv(DATA_DIR / "symbols.csv")
model.define(Symbol.new(model.data(symbols_csv).to_schema()))

# Venue concept: a trading venue.
Venue = model.Concept("Venue", identify_by={"id": Integer})
Venue.name = model.Property(f"{Venue} has {String:name}")
venues_csv = read_csv(DATA_DIR / "venues.csv")
model.define(Venue.new(model.data(venues_csv).to_schema()))

# NotAllowedSymbolVenue (encoding artifact, not a domain concept): the
# disallowed dual of the allowed (symbol, venue) pairs in symbol_venues.csv.
# The CSP supports only the arithmetic operators !=, *, +, -, so the rule
# is encoded as "forbid these pairs" rather than "require an allowed pair".
sv_csv = read_csv(DATA_DIR / "symbol_venues.csv")
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

# Order concept: the surveillance subject.
Order = model.Concept("Order", identify_by={"id": Integer})
Order.original_qty = model.Property(f"{Order} has {Integer:original_qty}")
Order.original_tick_price = model.Property(f"{Order} has {Integer:original_tick_price}")
Order.symbol = model.Property(f"{Order} is for {Symbol:symbol}")
orders_csv = read_csv(DATA_DIR / "orders.csv")
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

# OrderEvent concept: a pre-allocated event slot tied to one order. The
# solver decides each slot's type, timestamp, venue, quantity, tick price.
OrderEvent = model.Concept("OrderEvent", identify_by={"event_id": Integer})
OrderEvent.order = model.Property(f"{OrderEvent} belongs to {Order:order}")
events_csv = read_csv(DATA_DIR / "events.csv")
events_data = model.data(events_csv)
model.define(OrderEvent.new(event_id=events_data.event_id))
model.define(OrderEvent.order(Order)).where(
    OrderEvent.event_id(events_data.event_id),
    Order.id(events_data.order_id),
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------


# The event-type vocabulary. Members appear directly in constraints and
# readbacks; the wrapped values are arbitrary distinct integers.
class EventType(model.Enum):
    PLACE = 1
    MODIFY = 2
    CANCEL = 3
    FILL = 4


# Enum-indexed type decision: one binary indicator per (event slot, type).
# Replaces four parallel is_place/is_modify/is_cancel/is_fill properties.
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

problem = Problem(model, Integer)

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
type_sum_ic = model.require(rai_sum(OrderEvent.has_type).per(OrderEvent) == 1)
problem.satisfy(type_sum_ic)

# Exactly one PLACE event per order. The where-clause binds `place_ind` to
# each event's PLACE indicator; the aggregate then sums it per order.
place_ind = Integer.ref()
exactly_one_place_ic = model.where(
    OrderEvent.has_type(EventType.PLACE, place_ind)
).require(rai_sum(place_ind).per(OrderEvent.order) == 1)
problem.satisfy(exactly_one_place_ic)

# At most one CANCEL event per order.
cancel_ind = Integer.ref()
at_most_one_cancel_ic = model.where(
    OrderEvent.has_type(EventType.CANCEL, cancel_ind)
).require(rai_sum(cancel_ind).per(OrderEvent.order) <= 1)
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
qty_upper_ic = model.require(OrderEvent.qty <= OrderEvent.order.original_qty)
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
fill_sum_ic = model.require(
    rai_sum(OrderEvent.fill_qty).per(OrderEvent.order) <= OrderEvent.order.original_qty
)
problem.satisfy(fill_sum_ic)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Re-check the relational arithmetic ICs in the returned solution. The
# all_different- and implies-bodied ICs are solver-only and are NOT passed
# here -- verify() returns silently-OK on them without actually checking.
problem.verify(
    type_sum_ic,
    exactly_one_place_ic,
    at_most_one_cancel_ic,
    qty_upper_ic,
    venue_ok_ic,
    fill_sum_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# Inspect the generated trace.

print("\nGenerated event trace (one row per slot, sorted by order then timestamp):")
# Derived enum-typed property mapping each event to its chosen type: the
# member whose (event, type) indicator the solver set to 1 -- exactly one
# per event, guaranteed by the one-hot IC. The trace then reads the type
# label off the member's built-in `.name`.
OrderEvent.event_type = model.Property(
    f"{OrderEvent} has decided {EventType:event_type}"
)
for member in (EventType.PLACE, EventType.MODIFY, EventType.CANCEL, EventType.FILL):
    chosen_ind = Integer.ref()
    model.define(OrderEvent.event_type(member)).where(
        OrderEvent.has_type(member, chosen_ind), chosen_ind == 1
    )

trace_df = (
    model.select(
        OrderEvent.order.id.alias("order_id"),
        OrderEvent.order.symbol.name.alias("symbol"),
        OrderEvent.event_id.alias("event_id"),
        OrderEvent.ts_ms.alias("ts_ms"),
        OrderEvent.event_type.name.alias("type"),
        OrderEvent.qty.alias("qty"),
        OrderEvent.tick_price.alias("tick_price"),
        Venue.name.alias("venue"),
    )
    .where(Venue.id(OrderEvent.venue_id))
    .to_df()
)
trace_df = (
    trace_df.astype(
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
    rai_sum(OrderEvent.fill_qty).per(Order).alias("filled_qty"),
).where(OrderEvent.order(Order)).inspect()
