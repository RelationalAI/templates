"""Facility ranking report: reads the deployed disease_outbreak_prevention model.

Run `python -m queries.facility_ranking` after `rai models deploy --path model`. Prints a
ranked list of healthcare facilities by degree centrality, showing which facilities should
receive priority for vaccines, testing stations, and emergency response teams.
"""

from model import Facility, model


def ranked_facilities():
    """Every facility's published metrics, ranked by weighted degree centrality.

    Shared by this report and the Streamlit app. Ties rank by facility id.
    """
    results = model.select(
        Facility.id.alias("id"),
        Facility.name.alias("name"),
        Facility.type.alias("type"),
        Facility.region.alias("region"),
        Facility.degree_centrality.alias("degree_centrality"),
        Facility.incoming_connections.alias("incoming_connections"),
        Facility.outgoing_connections.alias("outgoing_connections"),
        Facility.total_connections.alias("total_connections"),
    ).to_df()
    results = results.sort_values(
        ["degree_centrality", "id"], ascending=[False, True]
    ).reset_index(drop=True)
    results.insert(0, "rank", range(1, len(results) + 1))
    return results


if __name__ == "__main__":
    results = ranked_facilities()

    # Display results in a formatted table
    print("=" * 100)
    print("DISEASE OUTBREAK PREVENTION NETWORK - DEGREE CENTRALITY ANALYSIS")
    print("=" * 100)
    print("\nFacilities ranked by weighted degree centrality (highest first):")
    print("\nWeighted Degree Centrality: risk weights (transfer_volume × contact_intensity) of each facility's")
    print("connections, summed and divided by (number of facilities - 1)")
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
    print(f"  • Highest weighted centrality: {results.iloc[0]['name']} ({int(results.iloc[0]['total_connections'])} connections)")

    print("\n✅ Analysis complete!")
