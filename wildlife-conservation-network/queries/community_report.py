"""Community report: reads the deployed wildlife_conservation model.

Run `python -m queries.community_report` after `rai models deploy --path model`. Prints the
conservation communities (Louvain) with centrality metrics, showing which groups work
closely together and which organizations are hubs within those communities. This helps
identify collaboration patterns, partnership opportunities, gaps in cross-community
coordination, and organizations well-positioned for leadership roles.
"""

from model import (
    Community,
    CommunityTrait,
    NetworkSummary,
    degree,
    degree_centrality,
    graph,
    louvain_communities,
    model,
)
from relationalai.semantics import Float, Integer, where

# Create variable references for use in queries.
org = graph.Node.ref("org")
community_id = Integer.ref("community_id")
centr_score = Float.ref("centr_score")
partner_count = Integer.ref("partner_count")
member = graph.Node.ref("member")
member_rank = Integer.ref("member_rank")

# The species focus lists the community's most common species, up to this many.
TOP_SPECIES = 3

if __name__ == "__main__":
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

    # Sort by community, then by centrality within each community, ties by organization id
    results = results.sort_values(
        ["community", "degree_centrality", "id"], ascending=[True, False, True]
    )

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

    # The model publishes the network totals, each community's profile, the ranked region,
    # species, and organization-type values, and each community's member order.
    summary = (
        model.select(
            NetworkSummary.n_organizations.alias("n_organizations"),
            NetworkSummary.n_communities.alias("n_communities"),
            NetworkSummary.mean_community_size.alias("mean_community_size"),
            NetworkSummary.mean_partnerships.alias("mean_partnerships"),
            NetworkSummary.n_partnerships.alias("n_partnerships"),
            NetworkSummary.most_connected.name.alias("most_connected"),
            NetworkSummary.most_connected.degree.alias("most_connected_partnerships"),
        )
        .to_df()
        .iloc[0]
    )
    communities = (
        model.select(
            Community.id.alias("community"),
            Community.n_organizations.alias("size"),
            Community.primary_region.alias("primary_region"),
            Community.hub.name.alias("hub"),
            Community.hub.degree_centrality.alias("hub_centrality"),
        )
        .to_df()
        .sort_values("community")
    )
    traits = (
        model.select(
            CommunityTrait.community.id.alias("community"),
            CommunityTrait.kind.alias("kind"),
            CommunityTrait.value.alias("value"),
            CommunityTrait.n_organizations.alias("n_organizations"),
            CommunityTrait.rank.alias("rank"),
        )
        .to_df()
        .sort_values(["community", "rank"])
    )
    members = (
        model.where(Community.member(member, member_rank))
        .select(
            Community.id.alias("community"),
            member.name.alias("name"),
            member_rank.alias("rank"),
        )
        .to_df()
        .sort_values(["community", "rank"])
    )

    # Analyze each community in detail
    num_communities = int(summary["n_communities"])
    print(f"\n🌍 DETECTED {num_communities} CONSERVATION COMMUNITIES:")
    print()

    for _, comm in communities.iterrows():
        comm_id = int(comm["community"])
        community_traits = traits[traits["community"] == comm_id]

        print(f"  Community {comm_id}:")
        print(f"    Size: {int(comm['size'])} organizations")
        print(f"    Primary Region: {comm['primary_region']}")

        # Most common species first
        species = community_traits[
            (community_traits["kind"] == "species") & (community_traits["rank"] <= TOP_SPECIES)
        ]
        species_summary = ", ".join(species["value"])
        print(f"    Species Focus: {species_summary}")

        # Most common organization types first, with their counts
        types = community_traits[community_traits["kind"] == "type"]
        types_summary = ", ".join(
            f"{t} ({c})" for t, c in zip(types["value"], types["n_organizations"])
        )
        print(f"    Organization Types: {types_summary}")

        # Hub organization (highest centrality) in this community
        # Hub organizations are well-connected within their community and are ideal candidates for leadership,
        # coordination, and resource-sharing coordination roles
        print(f"    Hub Organization: {comm['hub']} (centrality: {comm['hub_centrality']:.4f})")

        # List all members, most central first
        member_names = ", ".join(members[members["community"] == comm_id]["name"])
        print(f"    Members: {member_names}")
        print()

    # Overall network statistics
    print("📊 NETWORK SUMMARY:")
    print(f"  • Total organizations: {int(summary['n_organizations'])}")
    print(f"  • Number of communities detected: {num_communities}")
    print(f"  • Average community size: {summary['mean_community_size']:.1f} organizations")
    print(f"  • Average partnerships per organization: {summary['mean_partnerships']:.1f}")
    print(f"  • Most connected organization: {summary['most_connected']} "
          f"({int(summary['most_connected_partnerships'])} partnerships)")
    print(f"  • Total partnerships in network: {int(summary['n_partnerships'])}")

    print("\n✅ Analysis complete!")
