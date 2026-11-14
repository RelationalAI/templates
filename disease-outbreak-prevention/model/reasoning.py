"""Facility network graph: risk-weighted degree centrality and in/out connection counts."""

from relationalai.semantics import Float, define
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
    directed=True,
    weighted=True,
    node_concept=Facility,
    edge_concept=FacilityConnection,
    edge_src_relationship=FacilityConnection.from_facility,
    edge_dst_relationship=FacilityConnection.to_facility,
    edge_weight_relationship=FacilityConnection.risk_weight
)

# Calculate weighted degree centrality: measures how connected each facility is in the network,
# considering the risk weight of each connection.
# Higher centrality = more connections with higher risk = more critical for outbreak response coordination.
degree_centrality = graph.degree_centrality()

# Calculate incoming edges: number of facilities that connect TO this facility.
# Indicates facilities that others depend on or report to.
incoming_edges = graph.indegree()

# Calculate outgoing edges: number of facilities this facility connects TO.
# Indicates facilities that coordinate with or refer patients to others.
outgoing_edges = graph.outdegree()
