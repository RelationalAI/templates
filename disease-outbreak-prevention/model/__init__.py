"""Disease Outbreak Prevention Network (graph analytics) template: the model.

This package declares a public health network and its weighted degree centrality in
RelationalAI:

- Load a network of healthcare facilities and their connections from CSV.
- Calculate weighted degree centrality for each facility (considering connection weights).
- Calculate each facility's incoming and outgoing connection counts.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.facility_ranking` then prints the ranked report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Float, Integer, Model, String, data, define
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Create a Semantics model container
model = Model("disease_outbreak_prevention")

# Facility concept: healthcare facilities, testing centers, and community organizations.
Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has {String:name}")
Facility.type = model.Property(f"{Facility} has {String:type}")
Facility.region = model.Property(f"{Facility} has {String:region}")

# Load facilities from CSV
facility_df = pd.read_csv(DATA_DIR / "facilities.csv")
facility_data = data(facility_df)

# Create Facility instances with properties mapped to DataFrame columns
model.define(
    Facility.new(
        id=facility_data.id,
        name=facility_data.name,
        type=facility_data.type,
        region=facility_data.region
    )
)

# Facility connection concept to represent edges in the network
FacilityConnection = model.Concept(
    "FacilityConnection",
    identify_by={"from_facility": Facility, "to_facility": Facility}
)

FacilityConnection.transfer_volume = model.Property(f"{FacilityConnection} has {Float:transfer_volume}")
FacilityConnection.contact_intensity = model.Property(f"{FacilityConnection} has {Float:contact_intensity}")

# Load connection data from CSV
connections_data = data(pd.read_csv(DATA_DIR / "connections.csv"))

# Create facility connections
f_from, f_to = Facility.ref("from_facility"), Facility.ref("to_facility")

define(
    FacilityConnection.new(
        from_facility=f_from.lookup(id=connections_data.from_facility_id),
        to_facility=f_to.lookup(id=connections_data.to_facility_id),
        transfer_volume=connections_data.transfer_volume,
        contact_intensity=connections_data.contact_intensity
    )
)

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
