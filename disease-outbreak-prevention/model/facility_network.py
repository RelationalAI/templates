"""Facility network: each connection's risk weight, the risk-weighted facility graph, each
facility's weighted degree centrality, connection counts and priority rank, and the network
summary."""

from relationalai.semantics import Float, Integer, define
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import Facility, FacilityConnection, model

# Define risk weight for each connection as a function of transfer volume and contact intensity
FacilityConnection.risk_weight = model.Property(f"{FacilityConnection} has {Float:risk_weight}")
define(
    FacilityConnection.risk_weight == FacilityConnection.transfer_volume * FacilityConnection.contact_intensity
)

# Define directed, weighted graph with Facility nodes and FacilityConnection edges
graph = Graph(
    model,
    name="facility_network",
    directed=True,
    weighted=True,
    node_concept=Facility,
    edge_concept=FacilityConnection,
    edge_src_relationship=FacilityConnection.from_facility,
    edge_dst_relationship=FacilityConnection.to_facility,
    edge_weight_relationship=FacilityConnection.risk_weight
)

# Calculate weighted degree centrality: the risk weights of each facility's connections, summed
# and divided by (number of facilities - 1).
# Higher centrality = more connections with higher risk = more critical for outbreak response coordination.
degree_centrality = graph.degree_centrality()

# Calculate incoming edges: number of facilities that connect TO this facility.
# Indicates facilities that others depend on or report to.
incoming_edges = graph.indegree()

# Calculate outgoing edges: number of facilities this facility connects TO.
# Indicates facilities that coordinate with or refer patients to others.
outgoing_edges = graph.outdegree()

# Each facility's metrics, which the deployed model publishes for the queries.
Facility.degree_centrality = model.Property(f"{Facility} has {Float:degree_centrality}")
Facility.incoming_connections = model.Property(f"{Facility} has {Integer:incoming_connections}")
Facility.outgoing_connections = model.Property(f"{Facility} has {Integer:outgoing_connections}")
Facility.total_connections = model.Property(f"{Facility} has {Integer:total_connections}")
score, n_in, n_out = Float.ref(), Integer.ref(), Integer.ref()
model.where(degree_centrality(Facility, score)).define(Facility.degree_centrality(score))
model.where(incoming_edges(Facility, n_in)).define(Facility.incoming_connections(n_in))
model.where(outgoing_edges(Facility, n_out)).define(Facility.outgoing_connections(n_out))
model.define(
    Facility.total_connections(Facility.incoming_connections + Facility.outgoing_connections)
)

# Priority rank: 1 is the facility with the highest weighted degree centrality, ties broken by
# the lower facility id. The centrality is negated so both keys sort ascending: the Logic
# engine's rank does not mix ascending and descending keys.
Facility.priority_rank = model.Property(f"{Facility} has {Integer:priority_rank}")
model.define(Facility.priority_rank(aggs.rank(-Facility.degree_centrality, Facility.id)))

# The network's facility count and its mean degree centrality and connections per facility.
NetworkSummary = model.Relationship(
    f"the network has {Integer:n_facilities} facilities, a mean degree centrality of "
    f"{Float:mean_centrality}, and a mean of {Float:mean_connections} connections per facility"
)
_scored = (Facility.degree_centrality, Facility.total_connections)
model.define(NetworkSummary(
    aggs.count(Facility).where(*_scored),
    aggs.avg(Facility, Facility.degree_centrality).where(*_scored),
    aggs.avg(Facility, Facility.total_connections).where(*_scored),
))
