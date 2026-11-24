"""Supply chain resilience report: reads the deployed supply_chain_resilience model.

Run `python -m queries.resilience_report` after `rai models deploy --path model`. Prints the
blast-radius pre-analysis, network criticality (clusters, centrality), supplier risk
classification, the status and objective of each network flow problem's latest refresh
(baseline and two disruption scenarios), and a scenario comparison of the cost of disruptions.
"""

from model import (
    Business,
    Demand,
    Operation,
    Shipment,
    Site,
    baseline,
    biz_graph,
    biz_num_edges,
    biz_num_nodes,
    eigenvector,
    graph,
    model,
    num_edges,
    num_nodes,
    reachable_to,
    site_offline,
    target_customer,
    watch_avoid,
    wcc,
)
from relationalai.semantics import Float, String, where
from relationalai.semantics.std import aggregates as aggs


def report_flow(flow, label):
    """Print the flow problem's published result and active flows; return its summary row."""
    status = ", ".join(model.select(flow.status).to_df().iloc[:, 0].tolist())
    cost = model.select(flow.cost).to_df().iloc[:, 0].tolist()
    print(f"Solve result:\n• status: {status}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")
    obj = cost[0] if cost and status in ("OPTIMAL", "LOCALLY_SOLVED") else None

    # Extract active flows.
    if obj is not None:
        value_ref, op_ref, demand_ref = Float.ref(), String.ref(), String.ref()
        flow_df = (
            model.select(
                op_ref.alias("operation_id"),
                value_ref.alias("flow"),
            )
            .where(flow.routes(value_ref, op_ref), value_ref > 0.001)
            .to_df()
        )
        unmet_df = (
            model.select(
                demand_ref.alias("demand_id"),
                value_ref.alias("unmet"),
            )
            .where(flow.unmet(value_ref, demand_ref), value_ref > 0.001)
            .to_df()
        )
        n_active = len(flow_df)
        n_unmet = len(unmet_df)
        total_unmet = unmet_df["unmet"].sum() if len(unmet_df) > 0 else 0.0
    else:
        n_active, n_unmet, total_unmet = 0, 0, None

    print(f"\n  [{label}]")
    print(f"  Status: {status}")
    if obj is not None:
        print(f"  Total cost: {obj:,.2f}")
        print(f"  Active flows: {n_active}")
        if total_unmet > 0:
            print(f"  Unmet demand: {total_unmet:,.0f} units across {n_unmet} orders")
        else:
            print("  All demand satisfied")

    return {"label": label, "status": status, "objective": obj, "unmet": total_unmet}


if __name__ == "__main__":
    # Verify source_business derived relationship populates correctly.
    sb_df = (
        model.select(Operation.id.alias("op"), Business.id.alias("biz"))
        .where(Operation.source_business(Operation, Business))
        .to_df()
    )
    print(f"Source-business links: {len(sb_df)}")
    if len(sb_df) == 0:
        print("WARNING: source_business derived relationship is empty!")
    else:
        print(f"  Sample: {sb_df.head(5).to_string(index=False)}")

    # --------------------------------------------------
    # Stage 0: Blast-radius pre-analysis (directed Business graph)
    # --------------------------------------------------

    print("=" * 70)
    print("STAGE 0: Blast-Radius Pre-Analysis (directed Business graph)")
    print("=" * 70)

    biz_num_nodes.inspect()
    biz_num_edges.inspect()

    supplier_node = biz_graph.Node.ref()
    blast_df = (
        where(
            reachable_to(supplier_node, target_customer),
            supplier_node.business_type == "SUPPLIER",
        )
        .select(
            target_customer.name.alias("customer"),
            supplier_node.id.alias("supplier_id"),
            supplier_node.name.alias("supplier"),
            supplier_node.reliability_score.alias("supplier_reliability"),
        )
        .to_df()
    )

    print("\nUpstream supplier dependencies for high-priority customers:")
    if blast_df.empty:
        print("  (no high-priority demands or no SUPPLIER-typed upstream)")
    else:
        for cust in sorted(blast_df["customer"].unique()):
            cust_rows = blast_df[blast_df["customer"] == cust]
            print(f"\n  {cust} depends on {len(cust_rows)} supplier(s):")
            for _, row in cust_rows.sort_values("supplier").iterrows():
                rel = row["supplier_reliability"]
                rel_str = f"{rel:.0%}" if rel == rel else "N/A"  # NaN check
                print(f"    - {row['supplier']} (reliability: {rel_str})")

    # --------------------------------------------------
    # Stage 1: Graph -- network criticality
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("STAGE 1: Graph -- Network Criticality")
    print("=" * 70)

    num_nodes.inspect()
    num_edges.inspect()

    node_ref = graph.Node.ref("n")
    comp_ref = graph.Node.ref("comp")

    wcc_df = (
        where(wcc(node_ref, comp_ref))
        .select(
            node_ref.id.alias("site_id"),
            node_ref.name.alias("site_name"),
            node_ref.site_type.alias("site_type"),
            node_ref.region.alias("region"),
            comp_ref.id.alias("component_id"),
            aggs.count(node_ref).per(comp_ref).alias("cluster_size"),
        )
        .to_df()
    )

    num_components = wcc_df["component_id"].nunique()
    print(f"\nConnected components: {num_components}")
    if num_components == 1:
        print("UNIFIED NETWORK: All sites in a single connected component")
    for comp_id in sorted(wcc_df["component_id"].unique()):
        comp_df = wcc_df[wcc_df["component_id"] == comp_id]
        size = int(comp_df["cluster_size"].iloc[0])
        regions = ", ".join(sorted(comp_df["region"].unique()))
        print(f"  Component {comp_id}: {size} sites ({regions})")

    node_eig = graph.Node.ref("ne")
    eig_score = Float.ref("es")

    eig_df = (
        where(
            eigenvector(node_eig, eig_score),
            node_eig.site_type != "STORE",
            node_eig.site_type != "OFFICE",
        )
        .select(
            node_eig.id.alias("site_id"),
            node_eig.name.alias("site_name"),
            node_eig.site_type.alias("site_type"),
            node_eig.region.alias("region"),
            eig_score.alias("centrality_score"),
        )
        .to_df()
        .sort_values("centrality_score", ascending=False)
        .reset_index(drop=True)
    )

    print("\nTop critical sites (eigenvector centrality):")
    for _, row in eig_df.head(8).iterrows():
        print(
            f"  {row['site_id']} {row['site_name']} ({row['site_type']}, {row['region']}): "
            f"centrality={row['centrality_score']:.4f}"
        )

    # --------------------------------------------------
    # Stage 2: Rules -- supplier risk classification
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("STAGE 2: Rules -- Supplier Risk Classification")
    print("=" * 70)

    # Late shipment analysis.
    supplier_ref = Business.ref()
    shipments_df = (
        model.select(
            Shipment.id.alias("id"),
            supplier_ref.id.alias("supplier_id"),
            Shipment.delay_days.alias("delay_days"),
        )
        .where(Shipment.supplier(supplier_ref))
        .to_df()
    )
    late_shipments = shipments_df[shipments_df["delay_days"] > 0]
    total_n = len(shipments_df)
    late_n = len(late_shipments)
    late_pct = f" ({100 * late_n / total_n:.0f}%)" if total_n else ""
    print(f"\nLate shipments: {late_n} of {total_n}{late_pct}")
    late_by_supplier = (
        late_shipments.groupby("supplier_id")
        .size()
        .reset_index(name="late_count")
        .sort_values("late_count", ascending=False)
    )
    for _, row in late_by_supplier.head(5).iterrows():
        print(f"  {row['supplier_id']}: {row['late_count']} late shipments")

    # Read the risk classes from the same rules the solves block and surcharge on:
    # avoid (both flags) and watch level (either flag, a superset of avoid).
    avoid_ids = set(model.select(Business.id).where(Business.is_avoid()).to_df().iloc[:, 0])
    watch_ids = set(
        model.select(Business.id).where(Business.is_watch_level()).to_df().iloc[:, 0]
    )

    rel_score_ref = Float.ref()
    all_biz_df = (
        model.select(Business.id.alias("id"), Business.name.alias("name"),
                     rel_score_ref.alias("reliability"))
        .where(Business.reliability_score(rel_score_ref))
        .to_df()
    )

    print("\nSupplier risk classification:")
    for _, row in all_biz_df.sort_values("reliability").iterrows():
        biz_id = row["id"]
        if biz_id in avoid_ids:
            rc, marker = "avoid", "[X]"
        elif biz_id in watch_ids:
            rc, marker = "watch", "[!]"
        else:
            rc, marker = "reliable", "[ ]"
        print(
            f"  {marker} {biz_id} {row['name']}: "
            f"reliability={row['reliability']:.2f}, class={rc}"
        )

    esc_df = (
        model.select(aggs.count(Demand).alias("count"))
        .where(Demand.is_escalated())
        .to_df()
    )
    esc_n = int(esc_df["count"].iloc[0]) if len(esc_df) > 0 else 0
    print(f"\nEscalated demands (HIGH priority): {esc_n}")

    # --------------------------------------------------
    # Stage 3: Prescriptive -- risk-adjusted network flow
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("STAGE 3: Prescriptive -- Risk-Adjusted Network Flow")
    print("=" * 70)

    results = [report_flow(baseline, "Baseline")]
    print(f"  Blocked businesses (avoid): {sorted(avoid_ids) if avoid_ids else 'none'}")

    # --------------------------------------------------
    # Scenario analysis
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("SCENARIO ANALYSIS")
    print("=" * 70)

    # Scenario 1: the highest-centrality site goes offline. Sites tied at the highest
    # score all go offline together, so name every one.
    top_df = (
        model.select(Site.id.alias("site_id"), Site.name.alias("site_name"))
        .where(Site.is_most_critical())
        .to_df()
        .sort_values("site_id")
    )
    top_site_id = "+".join(top_df["site_id"]) or "none"
    top_site_name = ", ".join(top_df["site_name"]) or "no scored site"
    print(f"\nScenario: {top_site_name} ({top_site_id}) goes offline")
    results.append(report_flow(site_offline, f"Site {top_site_id} offline"))

    # Scenario 2: all "watch" suppliers are downgraded to "avoid".
    print("\nScenario: All 'watch' suppliers downgraded to 'avoid'")
    print(f"  Blocked businesses: {sorted(watch_ids)}")
    results.append(report_flow(watch_avoid, "Watch->Avoid"))

    # --------------------------------------------------
    # Scenario comparison
    # --------------------------------------------------

    canonical_names = {
        "Baseline": "Baseline",
        f"Site {top_site_id} offline": f"{top_site_id}-offline",
        "Watch->Avoid": "Watch-Avoid",
    }

    print(f"\n{'=' * 70}")
    print("SCENARIO COMPARISON")
    print(f"{'=' * 70}")
    print(f"  {'Scenario':<25} {'Status':<18} {'Cost':>12} {'Unmet':>10}")
    print(f"  {'-' * 65}")

    baseline_obj = results[0]["objective"]
    for r in results:
        name = canonical_names[r["label"]]
        # A scenario with no solution has no cost or unmet demand to compare.
        cost_str = f"{float(r['objective']):,.2f}" if r["objective"] is not None else "N/A"
        unmet_str = f"{r['unmet']:,.0f}" if r["unmet"] is not None else "N/A"
        delta = ""
        if r["label"] != "Baseline":
            if baseline_obj and r["objective"] is not None:
                pct = (r["objective"] - baseline_obj) / baseline_obj * 100
                delta = f" (+{pct:.1f}%)" if pct > 0 else f" ({pct:.1f}%)"
            else:
                delta = " (N/A)"
        print(f"  {name:<25} {r['status']:<18} {cost_str:>12}{delta} {unmet_str:>10}")
