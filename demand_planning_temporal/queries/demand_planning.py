"""Demand planning report: reads the deployed demand_planning_temporal model.

Run `python -m queries.demand_planning` after `rai models deploy --path model`. For each planning
horizon, prints the status and objective of the latest refresh's solve, the production plan,
inventory levels, and unmet demand, then a summary of the horizons.
"""

from model import PLANS, DemandOrder, OrderInPlan, model, planning_start
from relationalai.semantics import Float, Integer, count

if __name__ == "__main__":
    total_orders = model.select(count(DemandOrder)).to_df().iloc[0, 0]
    scenario_results = []

    for plan in PLANS:
        print(f"\nRunning scenario: planning_end = {plan.planning_end}")

        status = model.select(plan.status).to_df().iloc[:, 0].tolist()
        cost = model.select(plan.cost).to_df().iloc[:, 0].tolist()
        print(f"\nSolve result:\n• status: {', '.join(status)}")
        if cost:
            print(f"• objective: {round(cost[0], 9)}\n")

        scenario_results.append(
            {
                "scenario": plan.planning_end,
                "status": ", ".join(status),
                "objective": cost[0] if cost else None,
            }
        )
        if status != ["OPTIMAL"]:
            print(f"  Status: {', '.join(status)} — skipping results")
            continue
        print(f"  Status: {status[0]}")
        print(f"  Total cost: ${cost[0]:,.2f}")
        print(
            f"  Planning horizon: {planning_start} to {plan.planning_end} ({plan.num_weeks} weeks)"
        )
        orders_in_scope = len(
            model.select(DemandOrder.id).where(OrderInPlan(DemandOrder, plan.planning_end)).to_df()
        )
        print(f"  Demand orders in scope: {orders_in_scope} (of {total_orders} total)")

        value_ref, site_ref, sku_ref, week_ref, order_ref = (
            Float.ref(),
            Integer.ref(),
            Integer.ref(),
            Integer.ref(),
            Integer.ref(),
        )
        prod = model.select(
            site_ref.alias("site_id"),
            sku_ref.alias("sku_id"),
            week_ref.alias("week"),
            value_ref.alias("production"),
        ).where(plan.production(value_ref, site_ref, sku_ref, week_ref), value_ref > 0.01).to_df()
        inv = model.select(
            site_ref.alias("site_id"),
            sku_ref.alias("sku_id"),
            week_ref.alias("week"),
            value_ref.alias("inventory"),
        ).where(plan.inventory(value_ref, site_ref, sku_ref, week_ref)).to_df()
        unmet = model.select(
            order_ref.alias("order_id"),
            value_ref.alias("unmet"),
        ).where(plan.unmet(value_ref, order_ref), value_ref > 0.01).to_df()

        print("\n  === Production Plan (non-zero weeks) ===")
        if not prod.empty:
            print(prod.to_string(index=False))

        print("\n  === Inventory Levels (selected weeks) ===")
        if not inv.empty:
            print(inv.head(20).to_string(index=False))

        print("\n  === Unmet Demand ===")
        if unmet.empty:
            print("  All demand fulfilled!")
        else:
            print(unmet.to_string(index=False))

    # Summary
    print("\n" + "=" * 50)
    print("Scenario Analysis Summary")
    print("=" * 50)
    for result in scenario_results:
        obj = result["objective"]
        obj_str = f"${obj:,.2f}" if obj is not None else "N/A"
        print(f"  planning_end={result['scenario']}: {result['status']}, cost={obj_str}")
