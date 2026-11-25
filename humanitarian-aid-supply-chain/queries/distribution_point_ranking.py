"""Distribution point ranking report: reads the deployed humanitarian_aid_supply_chain model.

Run `python -m queries.distribution_point_ranking` after `rai models deploy --path model`.
Prints the distribution points ranked by PageRank (influence) and Degree Centrality
(connectivity), the strategic categories they fall into, and network and regional
summaries for emergency response planning.
"""

from model import DistributionPoint, NetworkSummary, PointCategory, RegionSummary, model

# How many points each strategic category lists.
TOP_HUBS = 5
TOP_ENDPOINTS = 3
TOP_CONNECTORS = 3

if __name__ == "__main__":
    # Each point's attributes, graph metrics, route counts, strategic category, and ranks, as the
    # deployed model publishes them.
    results = model.select(
        DistributionPoint.id,
        DistributionPoint.name,
        DistributionPoint.type,
        DistributionPoint.region,
        DistributionPoint.capacity,
        DistributionPoint.population_served,
        DistributionPoint.pagerank.alias("pagerank"),
        DistributionPoint.degree_centrality.alias("degree_centrality"),
        DistributionPoint.indegree.alias("incoming_routes"),
        DistributionPoint.outdegree.alias("outgoing_routes"),
        DistributionPoint.total_routes.alias("total_routes"),
        DistributionPoint.category.alias("category"),
        DistributionPoint.influence_rank.alias("rank"),
        DistributionPoint.category_rank.alias("category_rank"),
    ).to_df()

    # Order by influence rank: PageRank (primary), then Degree Centrality (secondary)
    results = results.sort_values("rank")

    # Display header
    print("=" * 140)
    print("HUMANITARIAN AID SUPPLY CHAIN NETWORK - PAGERANK & DEGREE CENTRALITY ANALYSIS")
    print("=" * 140)
    print("\nDistribution points ranked by PageRank (influence in aid flow):")
    print("\n📊 KEY METRICS EXPLAINED:")
    print("  • PageRank: Measures influence in the supply network (0-1 scale)")
    print("    Higher scores indicate points where aid naturally concentrates through the network")
    print("  • Degree Centrality: Flow weight of all connected routes, divided by the number of other points")
    print("    Higher scores indicate highly connected nodes that serve as critical coordination hubs")
    print("\n🎯 STRATEGIC PRIORITIES:")
    print("  High PageRank + High Degree → Critical coordination hubs (maximize capacity & redundancy)")
    print("  High PageRank + Lower Degree → Influential endpoints (optimize throughput)")
    print("  Lower PageRank + High Degree → Network connectors (strengthen to improve overall resilience)")
    print("\n" + "-" * 140)

    # Format the dataframe for display
    display_df = results[['rank', 'name', 'type', 'region', 'capacity', 'population_served',
                          'pagerank', 'degree_centrality', 'incoming_routes', 'outgoing_routes', 'total_routes']].copy()

    # Round scores for readability
    display_df['pagerank'] = display_df['pagerank'].round(4)
    display_df['degree_centrality'] = display_df['degree_centrality'].round(4)

    print(display_df.to_string(index=False))
    print("-" * 140)

    # Identify strategic categories
    print("\n🎯 STRATEGIC ANALYSIS:\n")

    category_counts = (
        model.select(PointCategory.label.alias("category"), PointCategory.n_points.alias("points"))
        .to_df()
        .set_index("category")["points"]
    )

    def category_leaders(category, top):
        """The category's point count and its `top` most influential points."""
        leaders = results[(results['category'] == category) & (results['category_rank'] <= top)]
        return int(category_counts.get(category, 0)), leaders

    # Category 1: Critical Coordination Hubs (High PageRank + High Degree Centrality)
    n_hubs, critical_hubs = category_leaders("Critical Coordination Hub", TOP_HUBS)

    if n_hubs > 0:
        print("  1️⃣  CRITICAL COORDINATION HUBS (High Influence + High Connectivity)")
        print(f"      These {n_hubs} points are both influential AND highly connected:")
        print("      ⚠️  PRIORITY: Maximize capacity, deploy redundancy, ensure resilience\n")
        for _, hub in critical_hubs.iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print(f"        Capacity: {hub['capacity']:,} units | Serves: {hub['population_served']:,} people | Routes: {hub['total_routes']}")
            print()

    # Category 2: Influential Endpoints (High PageRank + Lower Degree Centrality)
    n_endpoints, influential_endpoints = category_leaders("Influential Endpoint", TOP_ENDPOINTS)

    if n_endpoints > 0:
        print("  2️⃣  INFLUENTIAL ENDPOINTS (High Influence + Lower Connectivity)")
        print(f"      These {n_endpoints} points concentrate aid flow despite fewer connections:")
        print("      ✅ PRIORITY: Optimize throughput, increase capacity, monitor closely\n")
        for _, hub in influential_endpoints.iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print()

    # Category 3: Network Connectors (Lower PageRank + High Degree Centrality)
    n_connectors, connectors = category_leaders("Network Connector", TOP_CONNECTORS)

    if n_connectors > 0:
        print("  3️⃣  NETWORK CONNECTORS (Lower Influence + High Connectivity)")
        print(f"      These {n_connectors} points provide critical network connectivity:")
        print("      ⚠️  PRIORITY: Strengthen infrastructure, maintain reliability, prevent failures\n")
        for _, hub in connectors.iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print()

    # Network-wide statistics, as the deployed model totals them
    totals = model.select(
        NetworkSummary.n_points.alias("points"),
        NetworkSummary.n_routes.alias("routes"),
        NetworkSummary.mean_routes.alias("mean_routes"),
        NetworkSummary.total_population.alias("population"),
        NetworkSummary.total_capacity.alias("capacity"),
    ).to_df().iloc[0]
    most_connected = model.where(DistributionPoint.is_most_connected()).select(
        DistributionPoint.name.alias("name"), DistributionPoint.total_routes.alias("routes")
    ).to_df().iloc[0]
    most_central = model.where(DistributionPoint.is_most_central()).select(
        DistributionPoint.name.alias("name"), DistributionPoint.degree_centrality.alias("degree_centrality")
    ).to_df().iloc[0]
    print("\n📊 NETWORK SUMMARY:")
    print(f"  • Total distribution points: {int(totals['points'])}")
    print(f"  • Total supply routes: {int(totals['routes'])}")
    print(f"  • Average routes per point: {float(totals['mean_routes']):.1f}")
    print(f"  • Most connected point: {most_connected['name']} ({int(most_connected['routes'])} routes)")
    print(f"  • Total population served: {int(totals['population']):,} people")
    print(f"  • Total network capacity: {int(totals['capacity']):,} units")
    print(f"  • Most influential (PageRank): {results.iloc[0]['name']} ({results.iloc[0]['pagerank']:.4f})")
    print(f"  • Most connected (Degree Centrality): {most_central['name']} "
          f"({float(most_central['degree_centrality']):.4f})")

    # Regional analysis
    print("\n🌍 REGIONAL DISTRIBUTION:")
    regional_stats = model.select(
        RegionSummary.region.alias("region"),
        RegionSummary.n_points.alias("points"),
        RegionSummary.total_capacity.alias("capacity"),
        RegionSummary.total_population.alias("population_served"),
        RegionSummary.mean_pagerank.alias("pagerank"),
        RegionSummary.mean_degree_centrality.alias("degree_centrality"),
    ).to_df().set_index("region").sort_index().astype(
        {"points": "int64", "capacity": "int64", "population_served": "int64"}
    ).round(4)
    regional_stats.columns = ['Points', 'Total Capacity', 'Population Served', 'Avg PageRank', 'Avg Degree Centrality']
    print(regional_stats.to_string())

    print("\n✅ Analysis complete!")
