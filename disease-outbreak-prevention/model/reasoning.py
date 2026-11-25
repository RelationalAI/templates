"""Facility network graph: risk-weighted degree centrality and in/out connection counts."""

from relationalai.semantics import Float, Integer, define
from relationalai.semantics.reasoners.graph import Graph

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
