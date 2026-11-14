"""Production plan and sensitivity report: reads the deployed factory_production model.

Run `python -m queries.plan_and_sensitivity` after `rai models deploy --path model`. Prints
the formulation, the status and total profit of the latest refresh's solve, the production
plan, each factory's capacity shadow price, each product's reduced cost and basis status,
and a per-factory capacity-utilization summary. Each section is checked against the bundled
data's known optimum; a failed check stops the report with an error.
"""

from model import (
    EXPECTED_FACTORIES,
    EXPECTED_PRODUCTS,
    Product,
    SolveStatus,
    TotalProfit,
    cap,
    model,
    problem,
    quantity_var,
)

if __name__ == "__main__":
    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    profit = model.select(TotalProfit).to_df().iloc[:, 0].tolist()
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal production plan: termination status {status}")
    # Optimum: steel_factory fills all 40 hrs (bands to its 6000 cap = 30 hrs, coils takes
    # the last 10 hrs = 1400 units); amazing_brewery makes both products to their demand
    # caps in 25 of its 30 hrs. Profit = 192000 + 8000 = 200000.
    if len(profit) != 1 or abs(profit[0] - 200000) >= 0.01:
        raise SystemExit(f"total profit changed: expected 200000, got {profit}")

    print(f"\nBaseline status: {status[0]}, total profit: {profit[0]:.2f}")

    # --- The solved production plan -------------------------------------------------
    # Read populated quantities once for the plan checks and capacity summary.
    plan_df = (
        model.select(
            Product.factory.name.alias("factory"),
            Product.name.alias("product"),
            Product.factory.avail.alias("avail"),
            Product.rate.alias("rate"),
            Product.x_quantity.alias("quantity"),
        )
        .to_df()
        .sort_values(["factory", "product"], ignore_index=True)
    )
    print("\nProduction plan:")
    produced = plan_df.loc[plan_df["quantity"] > 1e-6, ["factory", "product", "quantity"]]
    print(produced.to_string(index=False))

    # Pin the whole plan, not just the objective scalar: in general a matching objective is
    # necessary but not sufficient, because a different product mix could reach the same
    # profit. This LP's optimum happens to be unique (each factory's hours pin its plan), so
    # pinning the quantities both guards against a regression and documents that uniqueness.
    # Check the plan's key set first (one row per product), then each quantity; tolerance is
    # tight because the vertices here are exactly integral.
    EXPECTED_PLAN = {"bands": 6000.0, "coils": 1400.0, "stouts": 1000.0, "ales": 2000.0}
    if sorted(plan_df["product"]) != sorted(EXPECTED_PLAN):
        raise SystemExit(f"expected one plan row per product, got {sorted(plan_df['product'])}")
    for product_name, expected_qty in EXPECTED_PLAN.items():
        actual_qty = plan_df.loc[plan_df["product"] == product_name, "quantity"].iloc[0]
        if abs(actual_qty - expected_qty) >= 0.01:
            raise SystemExit(f"{product_name}: expected {expected_qty}, got {actual_qty}")

    # --- Capacity shadow prices: which factory to expand first ----------------------
    # A constraint carries its declared entity key as a back-pointer (cap.factory), so a
    # shadow price joins to that factory's own data by KEY -- no name parsing, no pandas join.
    cap_df = (
        model.select(
            cap.factory.name.alias("factory"),
            cap.factory.avail.alias("avail"),
            cap.shadow_price.alias("shadow_price"),
        )
        .to_df()
        .sort_values("factory", ignore_index=True)
    )
    if sorted(cap_df["factory"]) != sorted(EXPECTED_FACTORIES):
        raise SystemExit(f"expected one shadow price per factory, got {sorted(cap_df['factory'])}")
    print("\nFactory capacity shadow prices (d profit / d hour):")
    print(cap_df.to_string(index=False))
    # Maximize + a <= capacity => shadow_price >= 0: an extra hour can only help. The
    # implication runs one way: a factory with idle hours prices at 0 (slack -- its
    # bottleneck is demand, not capacity), and a positive price marks a binding capacity.
    # steel_factory is full (binding) and carries the marginal value of an hour; every other
    # factory has spare hours (slack) and prices at 0.
    steel = cap_df["factory"] == "steel_factory"
    if not (cap_df.loc[steel, "shadow_price"] > 1e-6).all():
        raise SystemExit("steel_factory capacity should be binding with a positive shadow price")
    if not (cap_df.loc[~steel, "shadow_price"].abs() < 1e-6).all():
        raise SystemExit("factories with idle hours should price their capacity at 0")

    # --- Reduced costs: which products are demand-capped? ---------------------------
    # Each marginal reads straight off the variable; the variable's back-pointer
    # (quantity_var.product) joins it to the product's factory by ENTITY KEY.
    rc_df = (
        model.select(
            quantity_var.product.factory.name.alias("factory"),
            quantity_var.product.name.alias("product"),
            quantity_var.reduced_cost.alias("reduced_cost"),
            quantity_var.basis_status.alias("basis_status"),
        )
        .to_df()
        .sort_values(["factory", "product"], ignore_index=True)
    )
    if sorted(rc_df["product"]) != sorted(EXPECTED_PRODUCTS):
        raise SystemExit(f"expected one reduced cost per product, got {sorted(rc_df['product'])}")
    print("\nProduct reduced costs and basis status:")
    print(rc_df.to_string(index=False))
    # A product pinned at its demand cap is NONBASIC_AT_UPPER with reduced_cost >= 0 (the
    # extra profit from one more unit of allowed demand); the swing product that sets a
    # binding factory's marginal price is BASIC at ~0. Here bands, stouts and ales sit at
    # their demand caps; coils is the swing product in steel_factory. Check BOTH halves of
    # the lesson -- the reduced cost AND the basis status -- so a regression in either is loud.
    capped = rc_df["product"].isin(["bands", "stouts", "ales"])
    if not (rc_df.loc[capped, "reduced_cost"] > 1e-6).all():
        raise SystemExit("demand-capped products should have a positive reduced cost")
    if not (rc_df.loc[capped, "basis_status"] == "NONBASIC_AT_UPPER").all():
        raise SystemExit("demand-capped products should be NONBASIC_AT_UPPER")
    # coils is basic (interior, between 0 and its demand cap): reduced cost ~0, status BASIC.
    # The zero-check uses a HiGHS float tolerance (1e-4); it is exact-0 here.
    coils = rc_df["product"] == "coils"
    if not (rc_df.loc[coils, "reduced_cost"].abs() < 1e-4).all():
        raise SystemExit("coils, the swing product, should have a reduced cost of ~0")
    if not (rc_df.loc[coils, "basis_status"] == "BASIC").all():
        raise SystemExit("coils, the swing product, should be BASIC")

    # --- Acting on it: which factory's capacity is the bottleneck? ------------------
    # With a maximize objective every capacity shadow price is >= 0, so the largest one is
    # the factory whose marginal hour earns the most -- the capacity to expand first.
    bottleneck = max(zip(cap_df["factory"], cap_df["shadow_price"]), key=lambda fp: fp[1])
    print(
        f"\nMost profit-sensitive capacity: {bottleneck[0]} "
        f"(d profit / d hour = {bottleneck[1]:+.2f})"
    )

    # --------------------------------------------------
    # Summary -- capacity utilization per factory
    # --------------------------------------------------
    # Ties the shadow prices above back to the plan: in this data the binding factory has
    # zero idle hours and a positive shadow price, while idle hours mean slack and a zero
    # price. Only idle => zero-price holds in general; a binding capacity can still price at
    # zero under degeneracy, so read the prices, not just the idle column.
    plan_df["hours"] = plan_df["quantity"] / plan_df["rate"]
    util = (
        plan_df.groupby("factory")
        .agg(avail=("avail", "first"), hours_used=("hours", "sum"))
        .reset_index()
    )
    util["idle"] = util["avail"] - util["hours_used"]
    print("\n" + "=" * 50)
    print("Factory Capacity Summary")
    print("=" * 50)
    print(util.to_string(index=False))
