"""Warehouse allocation report: reads the deployed warehouse_allocation model.

Run `python -m queries.allocation_report` after `rai models deploy --path model`. Prints
the eigenvector centrality scores, the weakly-connected-component summary, the bridge
routes between regions, the status and objective of the latest refresh's solve, and the
inventory allocation plan.
"""

from model import (
    NetworkComponent,
    NetworkState,
    Route,
    Site,
    SolveStatus,
    TotalHoldingCost,
    model,
    num_components,
)

if __name__ == "__main__":
    # Display centrality scores
    print("=" * 50)
    print("Stage 1a: Eigenvector Centrality")
    print("=" * 50)

    model.select(
        Site.name.alias("site"),
        Site.type.alias("type"),
        Site.region.alias("region"),
        Site.centrality.alias("centrality"),
    ).inspect()

    # Stage 1b: connected components, as the model publishes them
    components = (
        model.select(
            NetworkComponent.component_id.alias("component_id"),
            NetworkComponent.n_sites.alias("n_sites"),
            NetworkComponent.regions.alias("regions"),
        )
        .to_df()
        .sort_values("component_id")
    )
    network_state = model.select(NetworkState).to_df().iloc[0, 0]
    n_components = model.select(num_components).to_df().iloc[0, 0]

    print("\n" + "=" * 50)
    print("Stage 1b: Connected Components")
    print("=" * 50)
    if network_state == "UNIFIED":
        print(f"UNIFIED NETWORK: all {components['n_sites'].iloc[0]} sites in a single component")
    else:
        print(f"FRAGMENTED NETWORK: {n_components} separate components detected")
        for comp in components.itertuples():
            print(f"  Component {comp.component_id}: {comp.n_sites} sites ({comp.regions})")

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

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    holding_cost = model.select(TotalHoldingCost).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if holding_cost:
        print(f"• objective: {round(holding_cost[0], 9)}\n")

    print(f"\nStatus: {', '.join(status)}")
    if not holding_cost:
        raise SystemExit(f"termination status {status}")
    print(f"Total holding cost: ${holding_cost[0]:.2f}")

    print("\nAllocation plan:")
    model.select(
        Site.name.alias("site"),
        Site.type.alias("type"),
        Site.centrality.alias("centrality"),
        Site.x_inventory.alias("allocated"),
        Site.holding_cost.alias("unit_cost"),
    ).where(Site.x_inventory > 0.01).inspect()
