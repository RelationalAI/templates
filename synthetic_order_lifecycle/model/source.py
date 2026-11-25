"""Load the sample symbols, venues, orders, and event slots into the model."""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import not_

from .schema import (
    AllowedSymbolVenue,
    NotAllowedSymbolVenue,
    Order,
    OrderEvent,
    Symbol,
    Venue,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

symbols_csv = read_csv(DATA_DIR / "symbols.csv")
model.define(Symbol.new(model.data(symbols_csv).to_schema()))

venues_csv = read_csv(DATA_DIR / "venues.csv")
model.define(Venue.new(model.data(venues_csv).to_schema()))

# The allowed pairs from symbol_venues.csv, and NotAllowedSymbolVenue: every (symbol, venue)
# pair that is not allowed. With full venue coverage there are no disallowed pairs.
sv_data = model.data(read_csv(DATA_DIR / "symbol_venues.csv"))
model.define(AllowedSymbolVenue(Symbol, Venue)).where(
    Symbol.id == sv_data.symbol_id,
    Venue.id == sv_data.venue_id,
)
model.where(Symbol, Venue, not_(AllowedSymbolVenue(Symbol, Venue))).define(
    NotAllowedSymbolVenue.new(symbol_id=Symbol.id, venue_id=Venue.id)
)

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
