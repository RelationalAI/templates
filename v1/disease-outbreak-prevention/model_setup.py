"""Shared model setup for Disease Outbreak Prevention Network analysis.

This module contains the common model configuration, concept definitions,
and data loading logic used by both the CLI script and Streamlit app.
"""

from pathlib import Path
import pandas as pd

from relationalai.semantics import Model, data, define, String, Integer, Float
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).parent / "data"


def create_model():
    """Create and configure the RelationalAI model with all concepts and relationships.

    Returns:
        tuple: (model, graph, Facility)
    """
    # Create a Semantics model container
    model = Model("disease_outbreak_prevention", config=globals().get("config", None))

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
            from_facility=f_from.filter_by(id=connections_data.from_facility_id),
            to_facility=f_to.filter_by(id=connections_data.to_facility_id),
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

    return model, graph, Facility
