"""Wildlife Conservation Network (graph analytics) template.

This script demonstrates community detection and centrality analysis in a wildlife
conservation network with RelationalAI:

- Load a network of conservation organizations and their partnerships from CSV.
- Apply the Louvain algorithm to detect communities (clusters of closely collaborating orgs).
- Calculate degree centrality to identify hub organizations within each community.
- Identify distinct conservation clusters working on different species/regions.
- Analyze community structure to optimize resource sharing and identify coordination leaders.

Run:
    `python wildlife_conservation_network.py`

Output:
    Prints community clusters of conservation organizations with centrality metrics,
    showing which groups work closely together and which organizations are hubs within
    those communities. This helps identify collaboration patterns, partnership opportunities,
    gaps in cross-community coordination, and organizations well-positioned for leadership
    roles.
"""

from relationalai.semantics import where, Integer, Float

from model_setup import create_model

# --------------------------------------------------
# Create model and calculate graph metrics
# --------------------------------------------------

model, graph, Organization = create_model()

# Apply Louvain algorithm for community detection.
# Louvain identifies clusters (communities) of organizations that work closely together.
# Organizations in the same community have dense connections within the group and
# sparse connections to other groups.
louvain_communities = graph.louvain()

# Calculate degree centrality to identify hub organizations within communities.
# Centrality is a normalized measure (0-1) of how well-connected an organization is,
# making it useful for identifying organizations that could lead coordination efforts,
# manage resource sharing, and bridge different initiatives within their community.
degree_centrality = graph.degree_centrality()

# Calculate degree (number of partnerships) for each organization.
degree = graph.degree()

# Create variable references for use in queries.
org = graph.Node.ref("org")
community_id = Integer.ref("community_id")
centr_score = Float.ref("centr_score")
partner_count = Integer.ref("partner_count")


# --------------------------------------------------
# Query and display results
# --------------------------------------------------

def main() -> None:
    """
    Main analysis function that:
    1. Queries the graph for Louvain community assignments
    2. Combines organization data with community membership
    3. Groups and analyzes conservation clusters
    4. Displays results in a user-friendly format
    """

    # Query the graph to retrieve:
    # - Basic organization information (id, name, type, region, focus_species)
    # - Louvain community assignment (which cluster this org belongs to)
    # - Degree centrality score (normalized connectivity, 0-1, identifying hubs within the community)
    # - Partnership count (total number of collaborations)
    results = where(
        louvain_communities(org, community_id),
        degree_centrality(org, centr_score),
        degree(org, partner_count)
    ).select(
        org.id,
        org.name,
        org.type,
        org.region,
        org.focus_species,
        community_id.alias("community"),
        centr_score.alias("degree_centrality"),
        partner_count.alias("partnerships")
    ).to_df()

    # Convert to standard types
    results['community'] = results['community'].astype(int)
    results['partnerships'] = results['partnerships'].astype(int)

    # Sort by community, then by centrality within each community
    results = results.sort_values(["community", "degree_centrality"], ascending=[True, False])

    # Display overall results
    print("=" * 110)
    print("WILDLIFE CONSERVATION NETWORK - COMMUNITY DETECTION ANALYSIS (LOUVAIN ALGORITHM)")
    print("=" * 110)
    print("\nOrganizations grouped by detected communities (collaboration clusters):")
    print("\nThe Louvain algorithm identifies groups of organizations that work closely together.")
    print("Organizations in the same community share dense connections, indicating:")
    print("  • Active collaboration on shared conservation goals")
    print("  • Geographic or species-based coordination")
    print("  • Opportunities for resource sharing within clusters")
    print("\n" + "-" * 110)

    # Format the dataframe for display
    display_df = results[['community', 'name', 'type', 'region', 'focus_species',
                          'degree_centrality', 'partnerships']].copy()

    # Round centrality scores for readability
    display_df['degree_centrality'] = display_df['degree_centrality'].round(4)

    print(display_df.to_string(index=False))
    print("-" * 110)

    # Analyze each community in detail
    num_communities = results['community'].nunique()
    print(f"\n🌍 DETECTED {num_communities} CONSERVATION COMMUNITIES:")
    print()

    for comm_id in sorted(results['community'].unique()):
        community_orgs = results[results['community'] == comm_id]

        print(f"  Community {comm_id}:")
        print(f"    Size: {len(community_orgs)} organizations")

        # Identify primary region
        regions = community_orgs['region'].value_counts()
        primary_region = regions.index[0]
        print(f"    Primary Region: {primary_region}")

        # Identify primary species focus
        species = community_orgs['focus_species'].value_counts()
        species_summary = ", ".join([f"{sp}" for sp in species.index[:3]])
        print(f"    Species Focus: {species_summary}")

        # Identify organization types
        types = community_orgs['type'].value_counts()
        types_summary = ", ".join([f"{t} ({c})" for t, c in types.items()])
        print(f"    Organization Types: {types_summary}")

        # Identify hub organization (highest centrality) in this community
        # Hub organizations are well-connected within their community and are ideal candidates for leadership,
        # coordination, and resource-sharing coordination roles
        most_central = community_orgs.iloc[0]
        print(f"    Hub Organization: {most_central['name']} (centrality: {most_central['degree_centrality']:.4f})")

        # List all members
        member_names = ", ".join(community_orgs['name'].tolist())
        print(f"    Members: {member_names}")
        print()

    # Overall network statistics
    print("📊 NETWORK SUMMARY:")
    print(f"  • Total organizations: {len(results)}")
    print(f"  • Number of communities detected: {num_communities}")
    print(f"  • Average community size: {len(results) / num_communities:.1f} organizations")
    print(f"  • Average partnerships per organization: {results['partnerships'].mean():.1f}")
    print(f"  • Most connected organization: {results.loc[results['degree_centrality'].idxmax(), 'name']} "
          f"({int(results['partnerships'].max())} partnerships)")

    # Calculate inter-community vs intra-community partnerships
    total_partnerships = results['partnerships'].sum() // 2  # Divide by 2 for undirected graph
    print(f"  • Total partnerships in network: {total_partnerships}")

    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
