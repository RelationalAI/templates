"""Network summary: network-wide counts and averages over organizations, communities, and
partnerships, and the most connected organization."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs

from . import partnership_network  # noqa: F401
from .community_profiles import Community
from .schema import Organization, model

# One NetworkSummary instance holds the network-wide figures.
NetworkSummary = model.Concept("NetworkSummary", identify_by={"id": Integer})
NetworkSummary.n_organizations = model.Property(
    f"{NetworkSummary} has {Integer:n_organizations} organizations"
)
NetworkSummary.n_communities = model.Property(
    f"{NetworkSummary} has {Integer:n_communities} communities"
)
NetworkSummary.mean_community_size = model.Property(
    f"{NetworkSummary} has mean community size {Float:mean_community_size}"
)
NetworkSummary.mean_partnerships = model.Property(
    f"{NetworkSummary} has {Float:mean_partnerships} partnerships per organization"
)
NetworkSummary.n_partnerships = model.Property(
    f"{NetworkSummary} has {Integer:n_partnerships} partnerships"
)
NetworkSummary.most_connected = model.Property(
    f"{NetworkSummary} has most connected organization {Organization:most_connected}"
)

model.define(NetworkSummary.new(id=1))
model.define(NetworkSummary.n_organizations(aggs.count(Organization).per(NetworkSummary)))
model.define(NetworkSummary.n_communities(aggs.count(Community).per(NetworkSummary)))
model.define(
    NetworkSummary.mean_community_size(
        aggs.avg(Community, Community.n_organizations).per(NetworkSummary)
    )
)
model.define(
    NetworkSummary.mean_partnerships(
        aggs.avg(Organization, Organization.degree).per(NetworkSummary)
    )
)
# Each undirected partnership adds one to the degree of both partners, so the total is half the
# degree sum; rows listing the same pair in both directions are one partnership of the graph.
model.define(
    NetworkSummary.n_partnerships(
        aggs.sum(Organization, Organization.degree).per(NetworkSummary) // 2
    )
)

# The most connected organization has the highest degree centrality, ties broken by the lower id.
# The centrality is negated so both keys sort ascending.
model.where(aggs.rank(-Organization.degree_centrality, Organization.id) == 1).define(
    NetworkSummary.most_connected(Organization)
)
