"""Warehouse allocation report: reads the deployed warehouse_allocation model.

Run `python -m queries.allocation_report` after `rai models deploy --path model`. Prints
the eigenvector centrality ranking, the weakly-connected-component summary, the bridge
routes between regions, the formulation, the status and total holding cost of the latest
refresh's solve, and the inventory allocation plan.
"""

from model import Route, Site, SolveStatus, TotalHoldingCost, graph, model, problem, wcc
from relationalai.semantics import where
from relationalai.semantics.std import aggregates as aggs

if __name__ == "__main__":
    # Display centrality ranking
    print("=" * 50)
    print("Stage 1a: Eigenvector Centrality")
    print("=" * 50)

    model.select(
        Site.name.alias("site"),
        Site.type.alias("type"),
        Site.region.alias("region"),
        Site.centrality.alias("centrality"),
    ).inspect()

    # Stage 1b: connected components
    site_ref = graph.Node.ref("site")
    comp_ref = graph.Node.ref("component_id")

    wcc_df = (
        where(wcc(site_ref, comp_ref))
        .select(
            site_ref.id.alias("site_id"),
            site_ref.name.alias("site"),
            site_ref.region.alias("region"),
            comp_ref.id.alias("component_id"),
            aggs.count(site_ref).per(comp_ref).alias("component_size"),
        )
        .to_df()
    )

    print("\n" + "=" * 50)
    print("Stage 1b: Connected Components")
    print("=" * 50)
    num_components = wcc_df["component_id"].nunique()
    if num_components == 1:
        print(f"UNIFIED NETWORK: all {len(wcc_df)} sites in a single component")
    else:
        print(f"FRAGMENTED NETWORK: {num_components} separate components detected")
        for comp_id in sorted(wcc_df["component_id"].unique()):
            comp_df = wcc_df[wcc_df["component_id"] == comp_id]
            size = int(comp_df["component_size"].iloc[0])
            regions = ", ".join(sorted(comp_df["region"].unique()))
            print(f"  Component {comp_id}: {size} sites ({regions})")

    # Stage 1c: bridge routes
    bridge_df = model.select(
        Route.id.alias("route_id"),
        Route.source.name.alias("from_site"),
        Route.source.region.alias("from_region"),
        Route.dest.name.alias("to_site"),
        Route.dest.region.alias("to_region"),
    ).where(Route.is_cross_region == 1.0).to_df()

    print("\n" + "=" * 50)
    print(f"Stage 1c: Bridge Routes ({len(bridge_df)} cross-region connectors)")
    print("=" * 50)
    if not bridge_df.empty:
        for _, row in bridge_df.iterrows():
            print(f"  {row['from_site']} ({row['from_region']}) -> {row['to_site']} ({row['to_region']})")

    # Stage 2: allocation
    print("\n" + "=" * 50)
    print("Stage 2: Inventory Allocation")
    print("=" * 50)

    problem.display()

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    holding_cost = model.select(TotalHoldingCost).to_df().iloc[:, 0].tolist()
    print(f"\nStatus: {', '.join(status)}")
    if status != ["OPTIMAL"] or not holding_cost:
        raise SystemExit(f"No optimal allocation: termination status {status}, holding cost {holding_cost}")
    print(f"Total holding cost: ${holding_cost[0]:.2f}")

    print("\nAllocation plan:")
    model.select(
        Site.name.alias("site"),
        Site.type.alias("type"),
        Site.centrality.alias("centrality"),
        Site.x_inventory.alias("allocated"),
        Site.holding_cost.alias("unit_cost"),
    ).where(Site.x_inventory > 0.01).inspect()
