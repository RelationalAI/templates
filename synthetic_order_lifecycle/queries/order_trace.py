"""Order trace report: reads the deployed synthetic_order_lifecycle model.

Run `python -m queries.order_trace` after `rai models deploy --path model`. Prints the
solve status, the generated event trace (one row per slot), and the per-order
filled-quantity totals.
"""

from model import Order, OrderEvent, OrderFill, SolveStatus, Venue, model

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}\n")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")

    # Inspect the generated trace.

    print("\nGenerated event trace (one row per slot, sorted by order then timestamp):")
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
    print(trace_df.sort_values(["order_id", "ts_ms"]).to_string(index=False))

    print("\nFilled quantity per order (cannot exceed Order.original_qty):")
    model.select(
        Order.id.alias("order_id"),
        Order.original_qty.alias("original_qty"),
        OrderFill.filled_qty.alias("filled_qty"),
    ).where(OrderFill.order_id == Order.id).inspect()
