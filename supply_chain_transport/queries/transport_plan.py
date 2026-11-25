"""Transport plan report: reads the deployed supply_chain_transport model.

Run `python -m queries.transport_plan` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's solve and tables of the inventory levels, the
transport quantities, and the arrival days.
"""

from model import FreightGroup, SolveStatus, TotalTransportCost, TransportType, model
from relationalai.semantics import Float, Integer

day, inventory, quantity = Integer.ref(), Float.ref(), Float.ref()
shipped_group = FreightGroup.ref()

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(TotalTransportCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")

    print(f"Status: {status[0]}")
    if cost:
        print(f"Total cost: ${cost[0]:.2f}")

    # Extract the solution with model.select(); the solved values are populated.
    print("\n=== Inventory Levels ===")
    model.select(
        FreightGroup.name.alias("freight_group"), day.alias("day"),
        inventory.alias("inventory"),
    ).where(FreightGroup.x_inv(day, inventory)).inspect()

    print("\n=== Transport Quantities ===")
    model.select(
        TransportType.name.alias("type"), shipped_group.name.alias("freight_group"),
        day.alias("day"), quantity.alias("quantity"),
    ).where(
        TransportType.x_qty_tra(shipped_group, day, quantity), quantity > 0.001
    ).inspect()

    print("\n=== Arrival Days ===")
    model.select(
        FreightGroup.name.alias("freight_group"),
        FreightGroup.z_arr_day.alias("arrival_day"),
    ).inspect()
