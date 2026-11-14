"""Wildlife Conservation Network (graph analytics) template: the model.

This package declares a wildlife conservation network and its community structure in
RelationalAI:

- Load a network of conservation organizations and their partnerships from CSV.
- Apply the Louvain algorithm to detect communities (clusters of closely collaborating orgs).
- Calculate degree centrality and degree to identify hub organizations within each community.

The model uses RelationalAI's Graph API to define organizations as nodes and partnerships
as edges.

Run:
    `rai models deploy --path model` deploys this model to the schema in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.community_report` then prints the community report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String, data, define
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Create a Semantics model container
model = Model("wildlife_conservation")

# Organization concept: NGOs, research stations, wildlife reserves, veterinary services.
Organization = model.Concept("Organization", identify_by={"id": Integer})
Organization.name = model.Property(f"{Organization} has {String:name}")
Organization.type = model.Property(f"{Organization} has {String:type}")
Organization.region = model.Property(f"{Organization} has {String:region}")
Organization.focus_species = model.Property(f"{Organization} has {String:focus_species}")

# Load organizations from CSV
org_df = pd.read_csv(DATA_DIR / "organizations.csv")
org_data = data(org_df)

# Create Organization instances with properties mapped to DataFrame columns
model.define(
    Organization.new(
        id=org_data.id,
        name=org_data.name,
        type=org_data.type,
        region=org_data.region,
        focus_species=org_data.focus_species
    )
)

# Partnership concept to represent edges in the network
Partnership = model.Concept(
    "Partnership",
    identify_by={"org1": Organization, "org2": Organization}
)

# Load partnership data from CSV
partnerships_data = data(pd.read_csv(DATA_DIR / "partnerships.csv"))

# Create partnerships (undirected relationships in conservation network)
org_from, org_to = Organization.ref("org1"), Organization.ref("org2")

define(
    Partnership.new(
        org1=org_from.lookup(id=partnerships_data.from_org_id),
        org2=org_to.lookup(id=partnerships_data.to_org_id)
    )
)

# Define undirected, unweighted graph with Organization nodes and Partnership edges
graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Organization,
    edge_concept=Partnership,
    edge_src_relationship=Partnership.org1,
    edge_dst_relationship=Partnership.org2
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
