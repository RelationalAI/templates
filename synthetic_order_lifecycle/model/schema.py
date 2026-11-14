"""Semantic schema for the synthetic order lifecycle template: orders, events, symbols, venues."""

from relationalai.semantics import Integer, Model, String

model = Model("synthetic_order_lifecycle")

# Symbol concept: a tradable instrument.
Symbol = model.Concept("Symbol", identify_by={"id": Integer})
Symbol.name = model.Property(f"{Symbol} has {String:name}")

# Venue concept: a trading venue.
Venue = model.Concept("Venue", identify_by={"id": Integer})
Venue.name = model.Property(f"{Venue} has {String:name}")

# NotAllowedSymbolVenue (encoding artifact, not a domain concept): the
# disallowed dual of the allowed (symbol, venue) pairs in symbol_venues.csv.
# The CSP supports only the arithmetic operators !=, *, +, -, so the rule
# is encoded as "forbid these pairs" rather than "require an allowed pair".
NotAllowedSymbolVenue = model.Concept(
    "NotAllowedSymbolVenue",
    identify_by={"symbol_id": Integer, "venue_id": Integer},
)

# Order concept: the surveillance subject.
Order = model.Concept("Order", identify_by={"id": Integer})
Order.original_qty = model.Property(f"{Order} has {Integer:original_qty}")
Order.original_tick_price = model.Property(f"{Order} has {Integer:original_tick_price}")
Order.symbol = model.Property(f"{Order} is for {Symbol:symbol}")

# OrderEvent concept: a pre-allocated event slot tied to one order. The
# solver decides each slot's type, timestamp, venue, quantity, tick price.
OrderEvent = model.Concept("OrderEvent", identify_by={"event_id": Integer})
OrderEvent.order = model.Property(f"{OrderEvent} belongs to {Order:order}")


# The event-type vocabulary. Members appear directly in constraints and
# readbacks; the wrapped values are arbitrary distinct integers (here in
# lifecycle order).
class EventType(model.Enum):
    PLACE = 1
    MODIFY = 2
    CANCEL = 3
    FILL = 4
