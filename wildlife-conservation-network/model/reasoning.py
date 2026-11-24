"""Wildlife conservation graph: Louvain communities, degree centrality, and degree."""

from relationalai.semantics.reasoners.graph import Graph

from .schema import Organization, Partnership, model

# Define undirected, unweighted graph with Organization nodes and Partnership edges
graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Organization,
    edge_concept=Partnership,
    edge_src_relationship=Partnership.org1,
    edge_dst_relationship=Partnership.org2,
    name="partnership_network",
)

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

# Attach each result to Organization, so the deployed model publishes it for the queries.
Organization.community = louvain_communities
Organization.degree_centrality = degree_centrality
Organization.degree = degree
