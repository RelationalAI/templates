"""Allocation report: forecast, rolling-horizon plans, dependency chains, and what-ifs.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.allocation_report

Prints the per-supplier capability forecast, the status and total margin of each
rolling-horizon solve of the latest refresh with its plan diff and per-customer
service level, the rolling-horizon summary, customer dependency chains and SPOFs,
the two what-if analyses, and a headline.
"""

import pandas as pd
from model import (
    HORIZON_END_PERIOD,
    OFFLINE_DROP_THRESHOLD,
    SHORTAGE_DROP_THRESHOLD,
    Customer,
    Demand,
    DependencyChainStep,
    EffectiveCapacity,
    Input,
    OfflineDrop,
    Product,
    ShortageDrop,
    Supplier,
    SupplierCapabilityForecast,
    SupplierOfflineImpact,
    allocations,
    gnn,
    model,
)
from relationalai.semantics import Float, Integer
from relationalai.semantics.std.path import PathTraversal

pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 200)


def main() -> None:
    customers_df = model.select(
        Customer.id.alias("id"), Customer.name.alias("name"), Customer.industry.alias("industry")
    ).to_df()
    products_df = model.select(Product.id.alias("id"), Product.name.alias("name")).to_df()
    demand_df = model.select(
        Demand.customer_id.alias("customer_id"),
        Demand.product_id.alias("product_id"),
        Demand.period_id.alias("period_id"),
        Demand.demand_usd.alias("demand_usd"),
    ).to_df()

    forecast_df = model.select(
        SupplierCapabilityForecast.supplier_id.alias("supplier_id"),
        SupplierCapabilityForecast.period_id.alias("period_id"),
        SupplierCapabilityForecast.capability_pct.alias("capability_pct"),
    ).to_df()
    supplier_names = model.select(Supplier.id.alias("id"), Supplier.name.alias("name")).to_df()
    if gnn is not None:
        print(f"GNN predictions: {len(forecast_df)} rows for periods 1..{HORIZON_END_PERIOD}")
    print("\nPer-supplier capability_pct summary (post-Stage 2):")
    fc_summary = (
        forecast_df.groupby("supplier_id")["capability_pct"].agg(["mean", "min", "max"]).round(3)
    )
    fc_summary["supplier"] = fc_summary.index.map(supplier_names.set_index("id")["name"])
    print(fc_summary.to_string())

    # --------------------------------------------------
    # Stage 3: rolling-horizon solves
    # --------------------------------------------------
    scenario_results = []
    prior_alloc_df = None  # for plan-diff between iterations

    for spec, status_rel, margin_rel, allocated in allocations:
        iter_id = spec["iter_id"]
        horizon_start = spec["horizon_start"]
        print(f"\n{'=' * 60}\nStage 3 iteration {iter_id}: {spec['label']}\n{'=' * 60}")
        n_cells = len(
            model.where(EffectiveCapacity.iter_id == iter_id)
            .select(EffectiveCapacity.product_id, EffectiveCapacity.period_id)
            .to_df()
        )
        print(
            f"  Horizon: months {horizon_start}-{HORIZON_END_PERIOD}, "
            f"effective-capacity cells loaded: {n_cells}"
        )

        status = model.select(status_rel).to_df().iloc[:, 0].tolist()
        margin = model.select(margin_rel).to_df().iloc[:, 0].tolist()
        print(f"Solve result:\n• status: {', '.join(status)}")
        if margin:
            print(f"• objective: {round(margin[0], 9)}\n")

        termination_status = ", ".join(status)
        objective = margin[0] if margin else None
        scenario_results.append(
            {
                "iter_id": iter_id,
                "label": spec["label"],
                "horizon_start": horizon_start,
                "status": termination_status,
                "objective": objective,
            }
        )
        if termination_status != "OPTIMAL":
            print(f"  Status: {termination_status} -- skipping detail output.")
            prior_alloc_df = None
            continue

        print(f"  Status: {termination_status}")
        print(
            f"  Total margin over horizon (months {horizon_start}-{HORIZON_END_PERIOD}): "
            f"${objective:,.2f}"
        )

        # This iteration's allocations, which the deployed model publishes.
        value_ref = Float.ref()
        sol = (
            model.where(allocated(value_ref, Demand))
            .select(
                Demand.customer_id.alias("customer_id"),
                Demand.product_id.alias("product_id"),
                Demand.period_id.alias("period_id"),
                value_ref.alias("alloc_usd"),
            )
            .to_df()
        )

        # Plan-diff vs prior iteration's allocation (only overlapping periods).
        if prior_alloc_df is not None:
            overlap = sol.merge(
                prior_alloc_df,
                on=["customer_id", "product_id", "period_id"],
                suffixes=("_now", "_prior"),
            )
            overlap["delta_usd"] = overlap["alloc_usd_now"] - overlap["alloc_usd_prior"]
            per_customer_delta = (
                overlap.groupby("customer_id")["delta_usd"].sum().rename("delta_usd_total")
            )
            per_customer_delta = per_customer_delta.reset_index().merge(
                customers_df[["id", "name"]], left_on="customer_id", right_on="id"
            )
            per_customer_delta["delta_$M"] = per_customer_delta["delta_usd_total"] / 1e6
            per_customer_delta = per_customer_delta[["name", "delta_$M"]].sort_values("delta_$M")
            print(
                f"\n  === Plan diff vs prior iteration (months {horizon_start}-{HORIZON_END_PERIOD}) ==="
            )
            print(per_customer_delta.to_string(index=False))

        prior_alloc_df = sol.copy()

        # Per-customer service level over the current horizon.
        sol_merged = sol.merge(
            demand_df[["customer_id", "product_id", "period_id", "demand_usd"]],
            on=["customer_id", "product_id", "period_id"],
        )
        per_customer = (
            sol_merged.groupby("customer_id")[["alloc_usd", "demand_usd"]]
            .sum()
            .assign(service_level=lambda d: d["alloc_usd"] / d["demand_usd"])
            .join(customers_df.set_index("id")[["name", "industry"]])
            .sort_values("demand_usd", ascending=False)
        )
        per_customer["alloc_$B"] = per_customer["alloc_usd"] / 1e9
        per_customer["demand_$B"] = per_customer["demand_usd"] / 1e9
        per_customer["service_%"] = (per_customer["service_level"] * 100).round(1)
        print("\n  === Per-customer service level (over current horizon) ===")
        print(
            per_customer[["name", "industry", "demand_$B", "alloc_$B", "service_%"]].to_string(
                index=False
            )
        )

    print("\n" + "=" * 60)
    print("Rolling-horizon summary")
    print("=" * 60)
    for r in scenario_results:
        obj_str = f"${r['objective']:,.2f}" if r["objective"] is not None else "N/A"
        print(
            f"  iter={r['iter_id']} months={r['horizon_start']}-{HORIZON_END_PERIOD}: "
            f"{r['status']:12s} margin={obj_str}"
        )

    # --------------------------------------------------
    # Stage 4: Graph (PATHS) -- dependency chains, RCA, and what-if
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("Stage 4: Dependency-chain analysis (PATHS), RCA, and what-if")
    print("=" * 60)

    chain_ref, hops_ref, step_ref = PathTraversal.ref(), Integer.ref(), Integer.ref()
    paths_df = (
        model.where(DependencyChainStep(chain_ref, hops_ref, Customer, step_ref))
        .select(
            chain_ref.alias("path_id"),
            hops_ref.alias("hops"),
            step_ref.alias("step"),
            Customer.name.alias("customer"),
        )
        .to_df()
    )
    paths_df["hops"] = paths_df["hops"].astype(int)
    paths_df["step"] = paths_df["step"].astype(int)

    chains = (
        paths_df.sort_values(["path_id", "step"])
        .groupby("path_id")
        .agg(
            hops=("hops", "first"),
            chain=("customer", lambda s: " -> ".join(s)),
        )
        .reset_index()
        .sort_values(["hops", "chain"])
    )
    print(f"\n  Total customer-customer dependency paths (1-3 hops): {len(chains)}")
    print("\n  === Dependency chains ===")
    print(chains[["hops", "chain"]].to_string(index=False))

    # Read ontology-resident SPOF flag (defined in Stage 1).
    spof_df = (
        model.where(Customer.is_dependency_spof())
        .select(
            Customer.name.alias("spof_customer"),
        )
        .to_df()
    )
    print("\n  === Customers flagged as dependency SPOFs (ontology query) ===")
    print(spof_df.to_string(index=False) if not spof_df.empty else "  (none)")

    # ---- What-if 1: Supplier goes offline ----
    print("\n" + "=" * 60)
    print("What-if 1: supplier-offline impact (no re-solve)")
    print("=" * 60)
    product_names = products_df.set_index("id")["name"]
    product_ref, period_ref, drop_ref = Integer.ref(), Integer.ref(), Float.ref()
    offline_df = (
        model.where(
            OfflineDrop(Supplier, product_ref, period_ref, drop_ref),
            drop_ref > OFFLINE_DROP_THRESHOLD,
        )
        .select(
            Supplier.id.alias("supplier_id"),
            product_ref.alias("product_id"),
            period_ref.alias("period_id"),
        )
        .to_df()
    )
    impact_df = (
        model.where(SupplierOfflineImpact.supplier_id == Supplier.id)
        .select(
            Supplier.id.alias("supplier_id"),
            Supplier.name.alias("supplier"),
            SupplierOfflineImpact.n_affected_cells.alias("n_affected_cells"),
            SupplierOfflineImpact.max_cap_drop_pct.alias("max_cap_drop_pct"),
        )
        .to_df()
        .sort_values("supplier_id")
    )
    impact_df["affected_products"] = [
        ", ".join(
            product_names.loc[
                offline_df.loc[offline_df["supplier_id"] == s, "product_id"].unique()
            ].tolist()
        )
        for s in impact_df["supplier_id"]
    ]
    print("\n  === Supplier-offline impact (each supplier in isolation) ===")
    display_supplier = impact_df.drop(columns=["supplier_id"]).copy()
    display_supplier["max_cap_drop_%"] = (display_supplier["max_cap_drop_pct"] * 100).round(1)
    display_supplier = display_supplier[
        ["supplier", "n_affected_cells", "max_cap_drop_%", "affected_products"]
    ]
    print(display_supplier.to_string(index=False))

    # ---- What-if 2: Raw-material input shortage ----
    print("\n" + "=" * 60)
    print("What-if 2: input-shortage impact (no re-solve)")
    print("=" * 60)
    shortage_df = (
        model.where(
            ShortageDrop(Input, product_ref, period_ref, drop_ref),
            drop_ref > SHORTAGE_DROP_THRESHOLD,
        )
        .select(
            Input.id.alias("input_id"),
            product_ref.alias("product_id"),
            period_ref.alias("period_id"),
            drop_ref.alias("cap_drop_pct"),
        )
        .to_df()
    )
    inputs_df = (
        model.select(
            Input.id.alias("input_id"),
            Input.name.alias("input"),
            Input.shortage_impact_cells.alias("n_affected_cells"),
        )
        .to_df()
        .sort_values("input_id")
    )
    avg_drops = []
    for i in inputs_df["input_id"]:
        by_product = (
            shortage_df[shortage_df["input_id"] == i]
            .groupby("product_id")["cap_drop_pct"]
            .mean()
            .round(3)
        )
        avg_drops.append(
            ", ".join(f"{product_names.loc[pid]}={drop:.0%}" for pid, drop in by_product.items())
        )
    inputs_df["affected_products_avg_drop"] = avg_drops
    print("\n  === Input-shortage impact (each input at 30% availability) ===")
    print(inputs_df.drop(columns=["input_id"]).to_string(index=False))

    # ---- Headline ----
    print("\n" + "=" * 60)
    print("Headline")
    print("=" * 60)
    spof_names = spof_df["spof_customer"].tolist()
    if spof_names:
        print(f"  Customer-graph SPOF(s): {', '.join(spof_names)}")
    multihop = chains[chains["hops"] > 1]
    if not multihop.empty:
        print("  Multi-hop dependency chains:")
        for chain in multihop["chain"]:
            print(f"    {chain}")
    worst_supplier = impact_df.loc[impact_df["n_affected_cells"].idxmax()]
    print(
        f"  Supplier with widest offline impact: {worst_supplier['supplier']} "
        f"({worst_supplier['n_affected_cells']} affected cells, "
        f"max cap drop {worst_supplier['max_cap_drop_pct'] * 100:.1f}%)"
    )
    worst_input = inputs_df.loc[inputs_df["n_affected_cells"].idxmax()]
    print(
        f"  Input with widest shortage impact: {worst_input['input']} "
        f"({worst_input['n_affected_cells']} affected cells)"
    )
    margins = [r["objective"] for r in scenario_results if r["objective"] is not None]
    if len(margins) >= 2:
        erosion = margins[0] - margins[-1]
        print(
            f"  Margin erosion across rolling horizon (iter 0 -> iter "
            f"{len(margins) - 1}): ${erosion:,.2f}"
        )


if __name__ == "__main__":
    main()
