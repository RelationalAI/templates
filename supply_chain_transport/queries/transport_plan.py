"""Transport plan report: reads the deployed supply_chain_transport model.

Run `python -m queries.transport_plan` after `rai models deploy --path model`. Prints the
formulation, the termination status and total cost of the latest refresh's solve, and
tables of the inventory levels, the transport quantities, and the arrival days.
"""

from model import (
    FreightGroup,
    FreightGroup_ref,
    SolveStatus,
    TotalTransportCost,
    TransportType,
    model,
    problem,
    time_period_ref,
    x_inv,
    x_qty_tra,
)

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalTransportCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal transport plan: termination status {status}")
    print(f"• objective: {round(cost[0], 9)}\n")

    print(f"Status: {status[0]}")
    print(f"Total cost: ${cost[0]:.2f}")

    # Extract the solution with model.select(); the solved values are populated.
    print("\n=== Inventory Levels ===")
    model.select(
        FreightGroup.name.alias("freight_group"), time_period_ref.alias("day"),
        x_inv.alias("inventory"),
    ).where(FreightGroup.x_inv(time_period_ref, x_inv)).inspect()

    print("\n=== Transport Quantities ===")
    model.select(
        TransportType.name.alias("type"), FreightGroup_ref.name.alias("freight_group"),
        time_period_ref.alias("day"), x_qty_tra.alias("quantity"),
    ).where(
        TransportType.x_qty_tra(FreightGroup_ref, time_period_ref, x_qty_tra), x_qty_tra > 0.001
    ).inspect()

    print("\n=== Arrival Days ===")
    model.select(
        FreightGroup.name.alias("freight_group"),
        FreightGroup.z_arr_day.alias("arrival_day"),
    ).inspect()
