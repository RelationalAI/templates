"""Shared model setup for Epidemic Spread Intervention analysis.

This module contains the common model configuration, concept definitions,
and data loading logic used by both the CLI script and Streamlit app.
"""

from pathlib import Path
import pandas as pd

import relationalai.semantics as rai
from relationalai.semantics import Model, where, data, define, String, Integer, Float, sum
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).parent / "data"


def create_model(config=None):
    """Create and configure the RelationalAI model with all concepts and relationships.

    Args:
        config: Optional RAI configuration object. Defaults to None (uses environment config).

    Returns:
        tuple: (model, Person, Location, DirectContact, Visit,
                ColocationContact, ExposureEdge, exposure_graph)
    """
    # Create a Semantics model container
    model = Model("epidemic_spread_intervention_n", config=config)


    # Load people from CSV
    people_df = pd.read_csv(DATA_DIR / "people.csv")
    people_data = data(people_df)

    # Person concept to represent individuals in the population
    Person = model.Concept("Person", identify_by={"person_id": String})
    Person.vaccination_level = model.Property(f"{Person} has {Float:vaccination_level}")
    Person.comorbidity_score = model.Property(f"{Person} has {Float:comorbidity_score}")

    model.define(
        Person.new(
            person_id=people_data.person_id,
            vaccination_level=people_data.vaccination_level,
            comorbidity_score=people_data.comorbidity_score
        )
    )

    # Load locations from CSV
    locations_df = pd.read_csv(DATA_DIR / "locations.csv")
    locations_data = data(locations_df)

    # Location concept to represent places where people interact
    Location = model.Concept("Location", identify_by={"id": String})
    Location.density_score = model.Property(f"{Location} has {Float:density_score}")
    Location.ventilation_score = model.Property(f"{Location} has {Float:ventilation_score}")

    model.define(
        Location.new(
            id=locations_data.location_id,
            density_score=locations_data.density_score,
            ventilation_score=locations_data.ventilation_score
        )
    )

    # Load direct contact data from CSV
    contacts_df = pd.read_csv(DATA_DIR / "direct_contacts.csv")
    contacts_data = data(contacts_df)

    # DirectContact concept to represent edges in the contact network
    DirectContact = model.Concept(
        "DirectContact",
        identify_by={"person_a": Person, "person_b": Person}
    )
    DirectContact.frequency = model.Property(f"{DirectContact} has {Integer:frequency}")
    DirectContact.duration = model.Property(f"{DirectContact} has {Integer:duration} in minutes")

    # Create direct contact relationships with canonical ordering (person_a.person_id < person_b.person_id)
    # to match ColocationContact and prevent duplicate/reversed edges in the exposure graph.
    person_a, person_b = Person.ref("person_a"), Person.ref("person_b")

    where(
        person_a == Person.filter_by(person_id=contacts_data.person_a),
        person_b == Person.filter_by(person_id=contacts_data.person_b),
        person_a.person_id < person_b.person_id,
    ).define(
        DirectContact.new(
            person_a=person_a,
            person_b=person_b,
            frequency=contacts_data.weekly_frequency,
            duration=contacts_data.duration_minutes
        )
    )
    # Mirror case: swap when raw data has person_a > person_b to enforce canonical ordering.
    where(
        person_a == Person.filter_by(person_id=contacts_data.person_a),
        person_b == Person.filter_by(person_id=contacts_data.person_b),
        person_a.person_id > person_b.person_id,
    ).define(
        DirectContact.new(
            person_a=person_b,
            person_b=person_a,
            frequency=contacts_data.weekly_frequency,
            duration=contacts_data.duration_minutes
        )
    )

    # Load visit data from CSV
    visits_df = pd.read_csv(DATA_DIR / "visits.csv")
    visits_data = data(visits_df)

    # Visit concept to represent edges in the location visit network
    Visit = model.Concept(
        "Visit",
        identify_by={"person": Person, "location": Location}
    )
    Visit.weekly_visits = model.Property(f"{Visit} has {Integer:weekly_visits}")

    # Create visit relationships (edges in location visit network)
    define(
        Visit.new(
            person=Person.filter_by(person_id=visits_data.person_id),
            location=Location.filter_by(id=visits_data.location_id),
            weekly_visits=visits_data.weekly_visits
        )
    )

    # Derive Risk-Adjusted Susceptibility
    # Captures how vulnerable an individual is before looking at connections.
    # A fully vaccinated person (vaccination_level=1.0) has susceptibility 0 and cannot be infected;
    # higher comorbidity amplifies susceptibility. This node-level weight scales every incoming edge.
    Person.base_susceptibility = model.Property(f"{Person} has {Float:base_susceptibility}")

    define(Person.base_susceptibility == (1 - Person.vaccination_level) * (1 + Person.comorbidity_score))


    # The Multi-Layer Edge Projection
    # People are connected in two ways: direct contact and co-location.
    # We need to merge these into a single "risk edge" that captures overall transmission potential.

    # Transmission risk derived from direct contact (Layer 1).
    # Formula: contact_intensity (hours/week) * susceptibility of the receiving person (person_b).
    # This reflects that transmission probability depends on both exposure duration and how easily
    # the recipient can be infected.
    DirectContact.transmission_risk = model.Property(f"{DirectContact} has {Float:transmission_risk}")
    define(DirectContact.transmission_risk ==
           DirectContact.frequency * (DirectContact.duration / 60) * DirectContact.person_b.base_susceptibility)

    ColocationContact = model.Concept(
        "ColocationContact",
        identify_by={"person_a": Person, "person_b": Person})

    # Derive ColocationContact from shared Visit locations (2-hop: Person -> Location -> Person)
    p1, p2 = Person.ref("p1"), Person.ref("p2")
    v1_exists, v2_exists = Visit.ref("v1_exists"), Visit.ref("v2_exists")
    loc_exists = Location.ref("loc_exists")

    where(
        v1_exists.person(p1),
        v2_exists.person(p2),
        v1_exists.location(loc_exists),
        v2_exists.location(loc_exists),
        p1.person_id < p2.person_id  # Avoid duplicates (undirected)
    ).define(
        ColocationContact.new(
            person_a=p1,
            person_b=p2
        )
    )

    ColocationContact.transmission_risk = model.Property(f"{ColocationContact} has {Float:transmission_risk}")

    # Transmission risk = sum over shared locations of:
    #   weekly_visits[p1, loc] * weekly_visits[p2, loc] * location_risk[loc]
    # where location_risk = density_score * (1 - ventilation_score)
    cc = ColocationContact.ref("cc")
    v1_risk, v2_risk = Visit.ref("v1_risk"), Visit.ref("v2_risk")
    loc_risk = Location.ref("loc_risk")

    where(
        v1_risk.person(cc.person_a),
        v2_risk.person(cc.person_b),
        v1_risk.location(loc_risk),
        v2_risk.location(loc_risk),
    ).define(
        cc.transmission_risk(
            sum(v1_risk.weekly_visits * v2_risk.weekly_visits
                * loc_risk.density_score * (1 - loc_risk.ventilation_score)).per(cc)
        )
    )

    # Combined Exposure Edge
    # Merges direct contact and colocation contact into a single weighted edge.
    # Formula: w = direct_weight + 0.6 * colocation_weight (defaulting to 0.0 if absent)
    # The 0.6 factor discounts co-location risk relative to direct contact: indirect proximity
    # (sharing a space) carries lower per-encounter transmission probability than face-to-face contact.
    # Only edges with w > 0.0 are kept.
    ExposureEdge = model.Concept(
        "ExposureEdge",
        identify_by={"person_a": Person, "person_b": Person}
    )
    ExposureEdge.weight = model.Property(f"{ExposureEdge} has {Float:weight}")

    # Create ExposureEdge entities from both layers.
    # Both DirectContact and ColocationContact enforce person_a.person_id < person_b.person_id,
    # so ExposureEdge pairs are always canonically ordered — no duplicate/reversed graph edges.
    model.define(ExposureEdge.new(
        person_a=DirectContact.person_a,
        person_b=DirectContact.person_b
    ))
    model.define(ExposureEdge.new(
        person_a=ColocationContact.person_a,
        person_b=ColocationContact.person_b
    ))

    # Compute weight using three mutually exclusive rules to avoid FD violations.
    # Rule 1: Both direct and colocation exist -> w = d + 0.6 * c
    ee1 = ExposureEdge.ref("ee1")
    dc1 = DirectContact.ref("dc1")
    cc_1 = ColocationContact.ref("cc_1")
    where(
        dc1.person_a == ee1.person_a, dc1.person_b == ee1.person_b,
        cc_1.person_a == ee1.person_a, cc_1.person_b == ee1.person_b,
    ).define(ee1.weight(dc1.transmission_risk + 0.6 * cc_1.transmission_risk))

    # Rule 2: Direct only (no colocation) -> w = d
    ee2 = ExposureEdge.ref("ee2")
    dc2 = DirectContact.ref("dc2")
    where(
        dc2.person_a == ee2.person_a, dc2.person_b == ee2.person_b,
        rai.not_(ColocationContact.filter_by(person_a=ee2.person_a, person_b=ee2.person_b)),
    ).define(ee2.weight(dc2.transmission_risk))

    # Rule 3: Colocation only (no direct) -> w = 0.6 * c
    ee3 = ExposureEdge.ref("ee3")
    cc3 = ColocationContact.ref("cc3")
    where(
        cc3.person_a == ee3.person_a, cc3.person_b == ee3.person_b,
        rai.not_(DirectContact.filter_by(person_a=ee3.person_a, person_b=ee3.person_b)),
    ).define(ee3.weight(0.6 * cc3.transmission_risk))


    # --------------------------------------------------
    # Build weighted undirected exposure graph
    # --------------------------------------------------

    exposure_graph = Graph(model, directed=False, weighted=True, node_concept=Person)

    ee = ExposureEdge.ref("ee")
    model.where(
        ee.weight > 0.0
    ).define(
        exposure_graph.Edge.new(
            src=ee.person_a,
            dst=ee.person_b,
            weight=ee.weight
        )
    )

    return model, Person, Location, DirectContact, Visit, ColocationContact, ExposureEdge, exposure_graph
