"""Sourcing report: reads the deployed supplier_reliability model.

Run `python -m queries.sourcing_report` after `rai models deploy --path model`. Prints the
status and objective of the latest refresh's baseline solve, the baseline sourcing plan, the
capacity and demand shadow prices, and each lane's reduced cost and basis status, then an
order plan per disruption scenario and a summary of the scenarios' status and objective.
The marginals are checked against the economics they must satisfy; a failed check stops the
report with an error.
"""

from model import (
    EXCLUDED_SUPPLIERS,
    BaselineCost,
    BaselineOrder,
    BaselineStatus,
    SupplyOrder,
    cap,
    meet,
    model,
    qty_var,
    scenarios,
)
from relationalai.semantics import Float


def solve_result(status_rel, cost_rel):
    """Return the published status and objective (None when the solve has no objective)."""
    status = ", ".join(model.select(status_rel).to_df().iloc[:, 0])
    cost = model.select(cost_rel).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {status}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")
    return status, (cost[0] if cost else None)


if __name__ == "__main__":
    status, baseline_objective = solve_result(BaselineStatus, BaselineCost)
    if baseline_objective is None:
        print(f"\nBaseline status: {status}")
    else:
        print(f"\nBaseline status: {status}, objective: {baseline_objective:.2f}")

    # --- The baseline sourcing plan -------------------------------------------------
    # The solved quantity of every lane, as the deployed model publishes it. (The optimum has
    # cost-equal alternates, so the exact split is solver-build-dependent -- contrast
    # factory_production, whose unique plan is checked.) The plan lists the lanes in use.
    amt = Float.ref()
    lanes_df = (
        model.select(
            SupplyOrder.supplier.name.alias("supplier"),
            SupplyOrder.product.name.alias("product"),
            amt.alias("quantity"),
        )
        .where(BaselineOrder(SupplyOrder, amt))
        .to_df()
        .sort_values(["supplier", "product"], ignore_index=True)
    )
    orders_df = lanes_df[lanes_df["quantity"] > 1e-6].reset_index(drop=True)
    print("\nBaseline orders:")
    print(orders_df.to_string(index=False))

    # --- Reduced costs: which lanes are priced out? ---------------------------------
    # Each marginal reads straight off the variable; the variable's back-pointer
    # (qty_var.supplyorder) joins it to the lane's supplier / product by ENTITY KEY.
    lane_rc_df = (
        model.select(
            qty_var.supplyorder.supplier.name.alias("supplier"),
            qty_var.supplyorder.product.name.alias("product"),
            qty_var.reduced_cost.alias("reduced_cost"),
            qty_var.basis_status.alias("basis_status"),
        )
        .to_df()
        .sort_values(["supplier", "product"], ignore_index=True)
    )
    print("\nLane reduced costs and basis status:")
    print(lane_rc_df.to_string(index=False))
    # A lane in use is BASIC with ~0 reduced cost; a priced-out lane is NONBASIC_AT_LOWER
    # with a positive reduced cost (how far its cost must fall before using it pays off).
    #
    # Complementary slackness, the ALWAYS-TRUE directions only. (1) SupplierA's and
    # SupplierD's lanes are genuinely priced out:
    priced_out = lane_rc_df["supplier"].isin(["SupplierA", "SupplierD"])
    if not (lane_rc_df.loc[priced_out, "reduced_cost"] > 1e-6).all():
        raise SystemExit("SupplierA's and SupplierD's lanes should be priced out (positive reduced cost)")
    # (2) Every lane actually in use prices at ~0. Join each lane's reduced cost to its solved
    # amount and check in Python. The supplier column keeps each row identifiable -- and names
    # the offender if the check ever fails:
    cs_df = lane_rc_df.merge(lanes_df, on=["supplier", "product"])
    if not (cs_df.loc[cs_df["quantity"] > 1e-6, "reduced_cost"].abs() < 1e-4).all():
        raise SystemExit("every lane in use should have a reduced cost of ~0")
    # NOT the converse "every unused lane has rc > 0": SupplierB's lanes are each exactly
    # +2 over SupplierC, so the optimum has alternate optima and some unused B lanes price
    # at ~0. The strict converse holds only under a unique optimum.

    # --- Shadow prices: the marginal value of capacity and demand -------------------
    # A constraint carries its declared entity key as a back-pointer too (cap.supplier /
    # meet.product), so a shadow price joins to that entity's own data by KEY -- no name
    # parsing, no pandas.
    cap_sp_df = (
        model.select(
            cap.supplier.name.alias("supplier"),
            cap.supplier.capacity.alias("capacity"),
            cap.shadow_price.alias("shadow_price"),
        )
        .to_df()
        .sort_values("supplier", ignore_index=True)
    )
    print("\nSupplier capacity shadow prices (d cost / d capacity):")
    print(cap_sp_df.to_string(index=False))
    # Minimize + a <= capacity constraint => shadow_price <= 0: loosening a binding
    # capacity lowers cost. SupplierC is the only binding capacity (cheapest source, fills
    # up), so it carries the marginal value; the others have room to spare and price at 0.
    supplier_c = cap_sp_df["supplier"] == "SupplierC"
    if not (cap_sp_df.loc[supplier_c, "shadow_price"] < -1e-6).all():
        raise SystemExit("SupplierC capacity should be binding with a negative shadow price")
    if not (cap_sp_df.loc[~supplier_c, "shadow_price"].abs() < 1e-6).all():
        raise SystemExit("suppliers with spare capacity should price their capacity at 0")

    demand_sp_df = (
        model.select(
            meet.product.name.alias("product"),
            meet.product.demand.alias("demand"),
            meet.shadow_price.alias("shadow_price"),
        )
        .to_df()
        .sort_values("product", ignore_index=True)
    )
    print("\nProduct demand shadow prices (d cost / d demand):")
    print(demand_sp_df.to_string(index=False))
    # Minimize + a >= demand constraint => shadow_price >= 0: the marginal cost to serve
    # one more unit of that product. Every product's demand binds here, and each demand
    # shadow price is strictly positive because the marginal serving cost of each is > 0.
    if not (demand_sp_df["shadow_price"] > 1e-6).all():
        raise SystemExit("every product's demand shadow price should be positive")

    # --- Acting on it: which supplier capacity is the bottleneck? -------------------
    # The largest-magnitude capacity shadow price is the capacity whose marginal unit
    # moves the bill the most -- the supplier to expand (or protect) first.
    bottleneck = max(
        zip(cap_sp_df["supplier"], cap_sp_df["shadow_price"]),
        key=lambda sp: abs(sp[1]),
    )
    print(
        f"\nMost cost-sensitive capacity: {bottleneck[0]} (d cost / d capacity = {bottleneck[1]:+.2f})"
    )

    # --------------------------------------------------
    # Phase B -- disruption scenarios
    # --------------------------------------------------
    scenario_results = [{"scenario": "baseline", "status": status, "objective": baseline_objective}]

    for excluded in EXCLUDED_SUPPLIERS:
        label = f"without_{excluded}"
        status_rel, cost_rel, orders_rel = scenarios[excluded]
        print(f"\nRunning scenario: {label}")

        scn_status, scn_objective = solve_result(status_rel, cost_rel)
        scenario_results.append({"scenario": label, "status": scn_status, "objective": scn_objective})
        if scn_status != "OPTIMAL":
            print(f"  Status: {scn_status} -- skipping results")
            continue
        print(f"  Status: {scn_status}, Objective: {scn_objective}")

        value_ref = Float.ref()
        qty_df = (
            model.select(
                SupplyOrder.supplier.name.alias("supplier"),
                SupplyOrder.product.name.alias("product"),
                value_ref.alias("quantity"),
            )
            .where(orders_rel(SupplyOrder, value_ref), value_ref > 1e-6)
            .to_df()
            .sort_values(["supplier", "product"], ignore_index=True)
        )
        print("\n  Orders:")
        print(qty_df.to_string(index=False))

    # Summary
    print("\n" + "=" * 50)
    print("Scenario Analysis Summary")
    print("=" * 50)
    for result in scenario_results:
        obj = result["objective"]
        obj_str = f"{obj:.2f}" if obj is not None else "N/A"
        print(f"  {result['scenario']}: {result['status']}, obj={obj_str}")
