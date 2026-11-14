"""Order trace report: reads the deployed synthetic_order_lifecycle model.

Run `python -m queries.order_trace` after `rai models deploy --path model`. Prints the
formulation, the solve status, the generated event trace (one row per slot), and the
per-order filled-quantity totals.
"""

from model import Order, OrderEvent, SolveStatus, Venue, model, problem
from relationalai.semantics import sum as rai_sum

if __name__ == "__main__":
    problem.display()

    # Status of the latest refresh's solve. A refresh records any termination
    # status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}\n")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No trace: termination status {status}")

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
