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
    Customer,
    CustomerService,
    DependencyChain,
    EffectiveCapacityCells,
    FirstSolvedIteration,
    Input,
    IterationMargin,
    LastSolvedIteration,
    MultiHopChain,
    NumDependencyChains,
    NumForecastRows,
    PlanDiff,
    Product,
    ShortageAverageDrop,
    Supplier,
    SupplierCapabilityForecast,
    SupplierOfflineImpact,
    allocations,
    gnn,
    model,
)
from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std.path import PathTraversal

pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 200)


def main() -> None:
    products_df = model.select(Product.id.alias("id"), Product.name.alias("name")).to_df()
    forecast_df = model.select(
        SupplierCapabilityForecast.supplier_id.alias("supplier_id"),
        SupplierCapabilityForecast.period_id.alias("period_id"),
        SupplierCapabilityForecast.capability_pct.alias("capability_pct"),
    ).to_df()
    supplier_names = model.select(Supplier.id.alias("id"), Supplier.name.alias("name")).to_df()
    if gnn is not None:
        num_forecast_rows = int(model.select(NumForecastRows).to_df().iloc[0, 0])
        print(f"GNN predictions: {num_forecast_rows} rows for periods 1..{HORIZON_END_PERIOD}")
    print("\nPer-supplier capability_pct summary (post-Stage 2):")
    # Computed here: on the bundled forecast snapshot one supplier's mean lies exactly on a
    # 3-decimal rounding boundary, so an engine's summation order could change the printed digit.
    fc_summary = (
        forecast_df.groupby("supplier_id")["capability_pct"].agg(["mean", "min", "max"]).round(3)
    )
    fc_summary["supplier"] = fc_summary.index.map(supplier_names.set_index("id")["name"])
    print(fc_summary.to_string())

    # --------------------------------------------------
    # Stage 3: rolling-horizon solves
    # --------------------------------------------------
    scenario_results = []

    for spec, status_rel, margin_rel, _ in allocations:
        iter_id = spec["iter_id"]
        horizon_start = spec["horizon_start"]
        print(f"\n{'=' * 60}\nStage 3 iteration {iter_id}: {spec['label']}\n{'=' * 60}")
        n_cells_ref = Integer.ref()
        n_cells = int(
            model.where(EffectiveCapacityCells(iter_id, n_cells_ref))
            .select(n_cells_ref)
            .to_df()
            .iloc[0, 0]
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
            continue

        print(f"  Status: {termination_status}")
        print(
            f"  Total margin over horizon (months {horizon_start}-{HORIZON_END_PERIOD}): "
            f"${objective:,.2f}"
        )

        # Plan-diff vs prior iteration's allocation (only overlapping periods), which the
        # deployed model publishes for every iteration after the first.
        delta_ref = Float.ref()
        per_customer_delta = (
            model.where(PlanDiff(iter_id, Customer, delta_ref))
            .select(
                Customer.id.alias("customer_id"),
                Customer.name.alias("name"),
                delta_ref.alias("delta_usd_total"),
            )
            .to_df()
            .sort_values("customer_id")
        )
        if not per_customer_delta.empty:
            per_customer_delta["delta_$M"] = per_customer_delta["delta_usd_total"] / 1e6
            per_customer_delta = per_customer_delta[["name", "delta_$M"]].sort_values("delta_$M")
            print(
                f"\n  === Plan diff vs prior iteration (months {horizon_start}-{HORIZON_END_PERIOD}) ==="
            )
            print(per_customer_delta.to_string(index=False))

        # Per-customer service level over the current horizon, which the deployed model publishes.
        alloc_ref, demand_ref, level_ref = Float.ref(), Float.ref(), Float.ref()
        per_customer = (
            model.where(CustomerService(iter_id, Customer, alloc_ref, demand_ref, level_ref))
            .select(
                Customer.id.alias("customer_id"),
                Customer.name.alias("name"),
                Customer.industry.alias("industry"),
                alloc_ref.alias("alloc_usd"),
                demand_ref.alias("demand_usd"),
                level_ref.alias("service_level"),
            )
            .to_df()
            .sort_values("customer_id")
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

    chain_ref, hops_ref, route_ref = PathTraversal.ref(), Integer.ref(), String.ref()
    chains = (
        model.where(DependencyChain(chain_ref, hops_ref, route_ref))
        .select(hops_ref.alias("hops"), route_ref.alias("chain"), chain_ref.alias("path_id"))
        .to_df()
        .sort_values(["hops", "chain"])
    )
    num_chains = int(model.select(NumDependencyChains).to_df().iloc[0, 0])
    print(f"\n  Total customer-customer dependency paths (1-3 hops): {num_chains}")
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
    impact_df = (
        model.where(SupplierOfflineImpact.supplier_id == Supplier.id)
        .select(
            Supplier.id.alias("supplier_id"),
            Supplier.name.alias("supplier"),
            SupplierOfflineImpact.n_affected_cells.alias("n_affected_cells"),
            SupplierOfflineImpact.max_cap_drop_pct.alias("max_cap_drop_pct"),
            SupplierOfflineImpact.affected_products.alias("affected_products"),
        )
        .to_df()
        .sort_values("supplier_id")
    )
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
    product_ref, avg_drop_ref = Integer.ref(), Float.ref()
    shortage_df = (
        model.where(ShortageAverageDrop(Input, product_ref, avg_drop_ref))
        .select(
            Input.id.alias("input_id"),
            product_ref.alias("product_id"),
            avg_drop_ref.alias("avg_drop_pct"),
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
            .set_index("product_id")["avg_drop_pct"]
            .sort_index()
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
    multihop = (
        model.where(MultiHopChain(chain_ref), DependencyChain(chain_ref, hops_ref, route_ref))
        .select(hops_ref.alias("hops"), route_ref.alias("chain"))
        .to_df()
        .sort_values(["hops", "chain"])
    )
    if not multihop.empty:
        print("  Multi-hop dependency chains:")
        for chain in multihop["chain"]:
            print(f"    {chain}")
    widest_supplier = (
        model.where(
            SupplierOfflineImpact.has_widest_impact(),
            SupplierOfflineImpact.supplier_id == Supplier.id,
        )
        .select(
            Supplier.name.alias("supplier"),
            SupplierOfflineImpact.n_affected_cells.alias("n_affected_cells"),
            SupplierOfflineImpact.max_cap_drop_pct.alias("max_cap_drop_pct"),
        )
        .to_df()
    )
    if not widest_supplier.empty:
        worst_supplier = widest_supplier.iloc[0]
        print(
            f"  Supplier with widest offline impact: {worst_supplier['supplier']} "
            f"({worst_supplier['n_affected_cells']} affected cells, "
            f"max cap drop {worst_supplier['max_cap_drop_pct'] * 100:.1f}%)"
        )
    else:
        print("  Supplier with widest offline impact: none (no affected cells)")
    widest_input = (
        model.where(Input.has_widest_shortage_impact())
        .select(
            Input.name.alias("input"),
            Input.shortage_impact_cells.alias("n_affected_cells"),
        )
        .to_df()
    )
    if not widest_input.empty:
        worst_input = widest_input.iloc[0]
        print(
            f"  Input with widest shortage impact: {worst_input['input']} "
            f"({worst_input['n_affected_cells']} affected cells)"
        )
    else:
        print("  Input with widest shortage impact: none (no affected cells)")
    # The horizons shrink from one iteration to the next, so the two totals cover
    # different months and their difference is not the disruptions' cost alone.
    first_iter, first_start, last_iter, last_start = (Integer.ref() for _ in range(4))
    first_margin, last_margin = Float.ref(), Float.ref()
    margin_span = (
        model.where(
            FirstSolvedIteration(first_iter),
            IterationMargin(first_iter, first_start, first_margin),
            LastSolvedIteration(last_iter),
            IterationMargin(last_iter, last_start, last_margin),
        )
        .select(
            first_iter.alias("first_iter"),
            first_start.alias("first_start"),
            first_margin.alias("first_margin"),
            last_iter.alias("last_iter"),
            last_start.alias("last_start"),
            last_margin.alias("last_margin"),
        )
        .to_df()
    )
    # One row, or none when no iteration solved; the line needs two different iterations.
    for span in margin_span.itertuples(index=False):
        if span.first_iter != span.last_iter:
            print(
                f"  Horizon margin, iter {span.first_iter} (months {span.first_start}-"
                f"{HORIZON_END_PERIOD}) -> iter {span.last_iter} (months {span.last_start}-"
                f"{HORIZON_END_PERIOD}): ${span.first_margin:,.2f} -> ${span.last_margin:,.2f}"
            )


if __name__ == "__main__":
    main()
