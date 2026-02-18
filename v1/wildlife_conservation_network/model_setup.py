"""Shared model setup for Wildlife Conservation Network analysis.

This module contains the common model configuration, concept definitions,
and data loading logic used by both the CLI script and Streamlit app.

The model uses RelationalAI's Graph API to:
- Define organizations as nodes and partnerships as edges
- Apply the Louvain community detection algorithm to identify collaboration clusters
- Calculate degree centrality to identify hub organizations within each community
"""

from pathlib import Path
import pandas as pd

from relationalai.semantics import Model, data, define, String, Integer, Float
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).parent / "data"


def create_model():
    """Create and configure the RelationalAI model with all concepts and relationships.

    Returns:
        tuple: (model, graph, Organization)
    """
    # Create a Semantics model container
    model = Model("wildlife_conservation", config=globals().get("config", None))

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
            org1=org_from.filter_by(id=partnerships_data.from_org_id),
            org2=org_to.filter_by(id=partnerships_data.to_org_id)
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

    return model, graph, Organization
