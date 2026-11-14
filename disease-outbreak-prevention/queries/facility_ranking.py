"""Facility ranking report: reads the deployed disease_outbreak_prevention model.

Run `python -m queries.facility_ranking` after `rai models deploy --path model`. Prints a
ranked list of healthcare facilities by degree centrality, showing which facilities should
receive priority for vaccines, testing stations, and emergency response teams.
"""

from model import degree_centrality, graph, incoming_edges, outgoing_edges
from relationalai.semantics import Float, Integer, where

# Create variable references for use in queries.
facility = graph.Node.ref("facility")
centr_score = Float.ref("centr_score")
in_edges = Integer.ref("in_edges")
out_edges = Integer.ref("out_edges")

if __name__ == "__main__":
    # Query the graph to retrieve:
    # - Basic facility information (id, name, type, region)
    # - Weighted degree centrality score (sum of edge weights for all connections)
    # - Incoming edges count (how many facilities connect TO this one)
    # - Outgoing edges count (how many facilities this one connects TO)
    results = where(
        degree_centrality(facility, centr_score),
        incoming_edges(facility, in_edges),
        outgoing_edges(facility, out_edges)
    ).select(
        facility.id,
        facility.name,
        facility.type,
        facility.region,
        centr_score.alias("degree_centrality"),
        in_edges.alias("incoming_connections"),
        out_edges.alias("outgoing_connections")
    ).to_df()

    # Convert integer columns to standard int type for compatibility with pandas operations
    results['incoming_connections'] = results['incoming_connections'].astype(int)
    results['outgoing_connections'] = results['outgoing_connections'].astype(int)

    # Sort by weighted degree centrality (descending) to rank facilities by highest cumulative risk first.
    results = results.sort_values("degree_centrality", ascending=False)
    results.insert(0, "rank", range(1, len(results) + 1))

    # Calculate total connections for each facility
    results['total_connections'] = results['incoming_connections'] + results['outgoing_connections']

    # Display results in a formatted table
    print("=" * 100)
    print("DISEASE OUTBREAK PREVENTION NETWORK - DEGREE CENTRALITY ANALYSIS")
    print("=" * 100)
    print("\nFacilities ranked by degree centrality (most connected first):")
    print("\nWeighted Degree Centrality: Sum of risk-weighted connections (transfer_volume × contact_intensity)")
    print("Higher scores indicate greater cumulative risk and more critical facilities for outbreak response coordination")
    print("\nThese facilities should receive priority for:")
    print("  • Vaccine and medical supply deployment")
    print("  • Testing station setup")
    print("  • Emergency response team positioning")
    print("\n" + "-" * 100)

    # Format the dataframe for display
    display_df = results[['rank', 'name', 'type', 'region', 'degree_centrality',
                          'incoming_connections', 'outgoing_connections', 'total_connections']].copy()

    # Round centrality scores for readability
    display_df['degree_centrality'] = display_df['degree_centrality'].round(2)

    print(display_df.to_string(index=False))
    print("-" * 100)

    # Highlight top 3 facilities with detailed breakdown
    top_facilities = results.head(3)
    print("\n🎯 TOP 3 PRIORITY FACILITIES FOR IMMEDIATE RESOURCE DEPLOYMENT:")
    print()
    for _, row in top_facilities.iterrows():
        print(f"  #{int(row['rank'])} - {row['name']}")
        print(f"       Type: {row['type']}")
        print(f"       Region: {row['region']}")
        print(f"       Weighted Degree Centrality: {row['degree_centrality']:.2f}")
        print(f"       Total Connections: {int(row['total_connections'])} "
              f"({int(row['incoming_connections'])} incoming, {int(row['outgoing_connections'])} outgoing)")
        print()

    # Summary statistics
    print("\n📊 NETWORK SUMMARY:")
    print(f"  • Total facilities analyzed: {len(results)}")
    print(f"  • Average degree centrality: {results['degree_centrality'].mean():.4f}")
    print(f"  • Average connections per facility: {results['total_connections'].mean():.1f}")
    print(f"  • Most connected facility: {results.iloc[0]['name']} ({int(results.iloc[0]['total_connections'])} connections)")

    print("\n✅ Analysis complete!")
