"""Facility ranking report: reads the deployed disease_outbreak_prevention model.

Run `python -m queries.facility_ranking` after `rai models deploy --path model`. Prints a
ranked list of healthcare facilities by degree centrality, showing which facilities should
receive priority for vaccines, testing stations, and emergency response teams.
"""

from model import Facility, NetworkSummary, model
from relationalai.semantics import Float, Integer


def ranked_facilities():
    """Every facility's published metrics, in priority-rank order (highest weighted degree
    centrality first).

    Shared by this report and the Streamlit app.
    """
    return (
        model.select(
            Facility.priority_rank.alias("rank"),
            Facility.id.alias("id"),
            Facility.name.alias("name"),
            Facility.type.alias("type"),
            Facility.region.alias("region"),
            Facility.degree_centrality.alias("degree_centrality"),
            Facility.incoming_connections.alias("incoming_connections"),
            Facility.outgoing_connections.alias("outgoing_connections"),
            Facility.total_connections.alias("total_connections"),
        )
        .to_df()
        .sort_values("rank")
        .reset_index(drop=True)
    )


def network_summary():
    """The facility count and the mean centrality and connections per facility, from the model."""
    n_ref, centrality_ref, connections_ref = Integer.ref(), Float.ref(), Float.ref()
    return (
        model.where(NetworkSummary(n_ref, centrality_ref, connections_ref))
        .select(
            n_ref.alias("n_facilities"),
            centrality_ref.alias("mean_centrality"),
            connections_ref.alias("mean_connections"),
        )
        .to_df()
        .iloc[0]
    )


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
    summary = network_summary()
    print("\n📊 NETWORK SUMMARY:")
    print(f"  • Total facilities analyzed: {int(summary['n_facilities'])}")
    print(f"  • Average degree centrality: {float(summary['mean_centrality']):.4f}")
    print(f"  • Average connections per facility: {float(summary['mean_connections']):.1f}")
    print(f"  • Highest weighted centrality: {results.iloc[0]['name']} ({int(results.iloc[0]['total_connections'])} connections)")

    print("\n✅ Analysis complete!")
