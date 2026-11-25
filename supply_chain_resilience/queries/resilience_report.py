"""Supply chain resilience report: reads the deployed supply_chain_resilience model.

Run `python -m queries.resilience_report` after `rai models deploy --path model`. Prints the
blast-radius pre-analysis, network criticality (clusters, centrality), supplier risk
classification, the status and objective of each network flow problem's latest refresh
(baseline and two disruption scenarios), and a scenario comparison of the cost of disruptions.
"""

from model import (
    Business,
    CostChangePct,
    Operation,
    Site,
    SiteCluster,
    baseline,
    biz_num_edges,
    biz_num_nodes,
    eigenvector,
    graph,
    model,
    num_components,
    num_edges,
    num_escalated,
    num_late_shipments,
    num_nodes,
    num_shipments,
    num_source_links,
    site_offline,
    watch_avoid,
)
from relationalai.semantics import Float, where

# How many of the top-ranked sites and late-shipment suppliers the report lists.
TOP_SITES = 8
TOP_LATE_SUPPLIERS = 5


def report_flow(flow, label):
    """Print the flow problem's published result and active flows; return its summary row."""
    status = ", ".join(model.select(flow.status).to_df().iloc[:, 0].tolist())
    cost = model.select(flow.cost).to_df().iloc[:, 0].tolist()
    print(f"Solve result:\n• status: {status}")
    if cost:
        print(f"• objective: {round(cost[0], 9)}\n")
    obj = cost[0] if cost and status in ("OPTIMAL", "LOCALLY_SOLVED") else None

    # The published count of active flows and the unmet orders and units.
    if obj is not None:
        n_active = int(model.select(flow.active_flows).to_df().iloc[0, 0])
        n_unmet = int(model.select(flow.unmet_orders).to_df().iloc[0, 0])
        total_unmet = float(model.select(flow.unmet_units).to_df().iloc[0, 0])
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

    return {
        "label": label,
        "problem": flow.name,
        "status": status,
        "objective": obj,
        "unmet": total_unmet,
    }


if __name__ == "__main__":
    # Verify source_business derived relationship populates correctly.
    n_links = int(model.select(num_source_links).to_df().iloc[0, 0])
    print(f"Source-business links: {n_links}")
    if n_links == 0:
        print("WARNING: source_business derived relationship is empty!")
    else:
        sb_df = (
            model.select(Operation.id.alias("op"), Business.id.alias("biz"))
            .where(Operation.source_business(Operation, Business))
            .to_df()
        )
        print(f"  Sample: {sb_df.head(5).to_string(index=False)}")

    # --------------------------------------------------
    # Stage 0: Blast-radius pre-analysis (directed Business graph)
    # --------------------------------------------------

    print("=" * 70)
    print("STAGE 0: Blast-Radius Pre-Analysis (directed Business graph)")
    print("=" * 70)

    biz_num_nodes.inspect()
    biz_num_edges.inspect()

    customer, supplier = Business.ref(), Business.ref()
    blast_df = (
        model.select(
            customer.name.alias("customer"),
            supplier.id.alias("supplier_id"),
            supplier.name.alias("supplier"),
        )
        .where(Business.upstream_supplier(customer, supplier))
        .to_df()
    )
    reliability_df = model.select(
        Business.id.alias("supplier_id"),
        Business.reliability_score.alias("supplier_reliability"),
    ).to_df()
    blast_df = blast_df.merge(reliability_df, on="supplier_id", how="left")

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

    n_clusters = int(model.select(num_components).to_df().iloc[0, 0])
    print(f"\nConnected components: {n_clusters}")
    if n_clusters == 1:
        print("UNIFIED NETWORK: All sites in a single connected component")
    cluster_df = model.select(
        SiteCluster.id.alias("component_id"),
        SiteCluster.n_sites.alias("n_sites"),
        SiteCluster.regions.alias("regions"),
    ).to_df()
    for _, row in cluster_df.sort_values("component_id").iterrows():
        print(f"  Component {row['component_id']}: {int(row['n_sites'])} sites ({row['regions']})")

    node_eig = graph.Node.ref("ne")
    eig_score = Float.ref("es")

    eig_df = (
        where(
            eigenvector(node_eig, eig_score),
            node_eig.centrality_rank <= TOP_SITES,
        )
        .select(
            node_eig.id.alias("site_id"),
            node_eig.name.alias("site_name"),
            node_eig.site_type.alias("site_type"),
            node_eig.region.alias("region"),
            eig_score.alias("centrality_score"),
            node_eig.centrality_rank.alias("rank"),
        )
        .to_df()
        .sort_values("rank")
    )

    print("\nTop critical sites (eigenvector centrality):")
    for _, row in eig_df.iterrows():
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
    total_n = int(model.select(num_shipments).to_df().iloc[0, 0])
    late_n = int(model.select(num_late_shipments).to_df().iloc[0, 0])
    late_pct = f" ({100 * late_n / total_n:.0f}%)" if total_n else ""
    print(f"\nLate shipments: {late_n} of {total_n}{late_pct}")
    late_by_supplier = (
        model.select(
            Business.id.alias("supplier_id"),
            Business.late_shipment_count.alias("late_count"),
            Business.late_rank.alias("rank"),
        )
        .where(Business.late_rank <= TOP_LATE_SUPPLIERS)
        .to_df()
        .sort_values("rank")
    )
    for _, row in late_by_supplier.iterrows():
        print(f"  {row['supplier_id']}: {int(row['late_count'])} late shipments")

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

    risk_df = model.select(Business.id.alias("id"), Business.risk_class.alias("risk_class")).to_df()
    all_biz_df = all_biz_df.merge(risk_df, on="id", how="left")
    markers = {"avoid": "[X]", "watch": "[!]", "reliable": "[ ]"}

    print("\nSupplier risk classification:")
    for _, row in all_biz_df.sort_values("reliability").iterrows():
        print(
            f"  {markers[row['risk_class']]} {row['id']} {row['name']}: "
            f"reliability={row['reliability']:.2f}, class={row['risk_class']}"
        )

    esc_n = int(model.select(num_escalated).to_df().iloc[0, 0])
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

    # Scenario 1: the highest-centrality site goes offline (none when no site is scored,
    # which leaves this solve equal to the baseline).
    top_df = (
        model.select(Site.id.alias("site_id"), Site.name.alias("site_name"))
        .where(Site.is_most_critical())
        .to_df()
        .sort_values("site_id")
    )
    if top_df.empty:
        top_site_id = "none"
        print("\nScenario: no site is scored, so no site goes offline")
    else:
        top_site_id = top_df.iloc[0]["site_id"]
        print(f"\nScenario: {top_df.iloc[0]['site_name']} ({top_site_id}) goes offline")
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
    pct_ref = Float.ref()
    for r in results:
        name = canonical_names[r["label"]]
        # A scenario with no solution has no cost or unmet demand to compare.
        cost_str = f"{float(r['objective']):,.2f}" if r["objective"] is not None else "N/A"
        unmet_str = f"{r['unmet']:,.0f}" if r["unmet"] is not None else "N/A"
        delta = ""
        if r["label"] != "Baseline":
            if baseline_obj and r["objective"] is not None:
                pct = float(
                    model.where(CostChangePct(r["problem"], pct_ref))
                    .select(pct_ref)
                    .to_df()
                    .iloc[0, 0]
                )
                delta = f" (+{pct:.1f}%)" if pct > 0 else f" ({pct:.1f}%)"
            else:
                delta = " (N/A)"
        print(f"  {name:<25} {r['status']:<18} {cost_str:>12}{delta} {unmet_str:>10}")
