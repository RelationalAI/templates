"""Synthetic Order Lifecycle (constrained generation) template: the model.

This package demonstrates a CSP-based synthetic order-lifecycle trace generator in RelationalAI:

- Pre-allocate (order, event-slot) rows and load order, symbol, and venue reference data from CSV.
- Model each event slot as a decision over type (PLACE / MODIFY / CANCEL / FILL), timestamp, venue, quantity, and tick price.
- Encode MiFID II / Reg NMS-flavour sequencing rules: PLACE first, nothing after CANCEL, exactly one PLACE per order, fill-quantity conservation, venue eligibility per symbol.
- Solve as constraint satisfaction (MiniZinc) and print the returned trace.

Event types are modelled as a `model.Enum`:
a single enum-indexed property carries one binary decision variable per
(event slot, type), and the trace reads each event's chosen type label
from the member's built-in `.name`.

All decisions are integer: prices are integer ticks (1c, so 17500 reads as
$175.00), times are integer milliseconds, quantities are integer shares.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.order_trace` then prints the report from the deployed
    model.
"""

from .reasoning import SolveStatus, problem
from .schema import Order, OrderEvent, Venue, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "Order", "OrderEvent", "SolveStatus", "Venue", "model", "problem"]
