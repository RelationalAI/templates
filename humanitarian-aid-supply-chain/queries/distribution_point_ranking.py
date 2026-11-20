"""Distribution point ranking report: reads the deployed humanitarian_aid_supply_chain model.

Run `python -m queries.distribution_point_ranking` after `rai models deploy --path model`.
Prints the distribution points ranked by PageRank (influence) and Degree Centrality
(connectivity), the strategic categories they fall into, and network and regional
summaries for emergency response planning.
"""

from model import degree_centrality, graph, indegree, outdegree, pagerank
from relationalai.semantics import Float, Integer, where

# Create variable references for use in queries
point = graph.Node.ref("point")
pr_score = Float.ref("pr_score")
dc_score = Float.ref("dc_score")
in_routes = Integer.ref("in_routes")
out_routes = Integer.ref("out_routes")

if __name__ == "__main__":
    # Query the graph to retrieve:
    # - Basic distribution point information (id, name, type, region, capacity, population)
    # - PageRank score (influence/importance in aid flow)
    # - Degree Centrality score (connectivity/hub importance)
    # - Incoming and outgoing route counts
    results = where(
        pagerank(point, pr_score),
        degree_centrality(point, dc_score),
        indegree(point, in_routes),
        outdegree(point, out_routes)
    ).select(
        point.id,
        point.name,
        point.type,
        point.region,
        point.capacity,
        point.population_served,
        pr_score.alias("pagerank"),
        dc_score.alias("degree_centrality"),
        in_routes.alias("incoming_routes"),
        out_routes.alias("outgoing_routes")
    ).to_df()

    # Convert to standard types
    results['incoming_routes'] = results['incoming_routes'].astype(int)
    results['outgoing_routes'] = results['outgoing_routes'].astype(int)
    results['capacity'] = results['capacity'].astype(int)
    results['population_served'] = results['population_served'].astype(int)

    # Calculate total routes
    results['total_routes'] = results['incoming_routes'] + results['outgoing_routes']

    # Sort by PageRank (primary) then Degree Centrality (secondary)
    results = results.sort_values(["pagerank", "degree_centrality"], ascending=False)
    results.insert(0, 'rank', range(1, len(results) + 1))

    # Display header
    print("=" * 140)
    print("HUMANITARIAN AID SUPPLY CHAIN NETWORK - PAGERANK & DEGREE CENTRALITY ANALYSIS")
    print("=" * 140)
    print("\nDistribution points ranked by PageRank (influence in aid flow):")
    print("\n📊 KEY METRICS EXPLAINED:")
    print("  • PageRank: Measures influence in the supply network (0-1 scale)")
    print("    Higher scores indicate points where aid naturally concentrates through the network")
    print("  • Degree Centrality: Sum of flow weights for all connected routes (higher = more influential hub)")
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

    pr_threshold = results['pagerank'].quantile(0.70)
    dc_threshold = results['degree_centrality'].quantile(0.70)

    # Category 1: Critical Coordination Hubs (High PageRank + High Degree Centrality)
    critical_hubs = results[
        (results['pagerank'] >= pr_threshold) &
        (results['degree_centrality'] >= dc_threshold)
    ]

    if len(critical_hubs) > 0:
        print("  1️⃣  CRITICAL COORDINATION HUBS (High Influence + High Connectivity)")
        print(f"      These {len(critical_hubs)} points are both influential AND highly connected:")
        print("      ⚠️  PRIORITY: Maximize capacity, deploy redundancy, ensure resilience\n")
        for _, hub in critical_hubs.head(5).iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print(f"        Capacity: {hub['capacity']:,} units | Serves: {hub['population_served']:,} people | Routes: {hub['total_routes']}")
            print()

    # Category 2: Influential Endpoints (High PageRank + Lower Degree Centrality)
    influential_endpoints = results[
        (results['pagerank'] >= pr_threshold) &
        (results['degree_centrality'] < dc_threshold)
    ]

    if len(influential_endpoints) > 0:
        print("  2️⃣  INFLUENTIAL ENDPOINTS (High Influence + Lower Connectivity)")
        print(f"      These {len(influential_endpoints)} points concentrate aid flow despite fewer connections:")
        print("      ✅ PRIORITY: Optimize throughput, increase capacity, monitor closely\n")
        for _, hub in influential_endpoints.head(3).iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print()

    # Category 3: Network Connectors (Lower PageRank + High Degree Centrality)
    connectors = results[
        (results['pagerank'] < pr_threshold) &
        (results['degree_centrality'] >= dc_threshold)
    ]

    if len(connectors) > 0:
        print("  3️⃣  NETWORK CONNECTORS (Lower Influence + High Connectivity)")
        print(f"      These {len(connectors)} points provide critical network connectivity:")
        print("      ⚠️  PRIORITY: Strengthen infrastructure, maintain reliability, prevent failures\n")
        for _, hub in connectors.head(3).iterrows():
            print(f"      • {hub['name']} ({hub['type']})")
            print(f"        Region: {hub['region']} | PageRank: {hub['pagerank']:.4f} | Degree Centrality: {hub['degree_centrality']:.4f}")
            print()

    # Network-wide statistics
    print("\n📊 NETWORK SUMMARY:")
    print(f"  • Total distribution points: {len(results)}")
    print(f"  • Total supply routes: {results['incoming_routes'].sum()}")
    print(f"  • Average routes per point: {results['total_routes'].mean():.1f}")
    print(f"  • Most connected point: {results.loc[results['total_routes'].idxmax(), 'name']} ({int(results['total_routes'].max())} routes)")
    print(f"  • Total population served: {results['population_served'].sum():,} people")
    print(f"  • Total network capacity: {results['capacity'].sum():,} units")
    print(f"  • Most influential (PageRank): {results.iloc[0]['name']} ({results.iloc[0]['pagerank']:.4f})")
    print(f"  • Most connected (Degree Centrality): {results.loc[results['degree_centrality'].idxmax(), 'name']} "
          f"({results['degree_centrality'].max():.4f})")

    # Regional analysis
    print("\n🌍 REGIONAL DISTRIBUTION:")
    regional_stats = results.groupby('region').agg({
        'name': 'count',
        'capacity': 'sum',
        'population_served': 'sum',
        'pagerank': 'mean',
        'degree_centrality': 'mean'
    }).round(4)
    regional_stats.columns = ['Points', 'Total Capacity', 'Population Served', 'Avg PageRank', 'Avg Degree Centrality']
    print(regional_stats.to_string())

    print("\n✅ Analysis complete!")
