"""Load the sample symbols, venues, orders, and event slots into the model."""

from pathlib import Path

from pandas import DataFrame, read_csv

from .schema import NotAllowedSymbolVenue, Order, OrderEvent, Symbol, Venue, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

symbols_csv = read_csv(DATA_DIR / "symbols.csv")
model.define(Symbol.new(model.data(symbols_csv).to_schema()))

venues_csv = read_csv(DATA_DIR / "venues.csv")
model.define(Venue.new(model.data(venues_csv).to_schema()))

# NotAllowedSymbolVenue rows: every (symbol, venue) pair not listed in symbol_venues.csv.
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

# With full venue coverage there are no disallowed pairs and nothing to load.
if not disallowed_csv.empty:
    model.define(NotAllowedSymbolVenue.new(model.data(disallowed_csv).to_schema()))

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

events_csv = read_csv(DATA_DIR / "events.csv")
events_data = model.data(events_csv)
model.define(OrderEvent.new(event_id=events_data.event_id))
model.define(OrderEvent.order(Order)).where(
    OrderEvent.event_id(events_data.event_id),
    Order.id(events_data.order_id),
)
