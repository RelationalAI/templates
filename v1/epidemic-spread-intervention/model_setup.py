"""Shared model setup for Epidemic Spread Intervention analysis.

This module contains the common model configuration, concept definitions,
and data loading logic used by both the CLI script and Streamlit app.
"""

from pathlib import Path
import pandas as pd

from relationalai.semantics import Model, data, define, String, Integer, Float, sum
from relationalai.semantics.reasoners.graph import Graph

DATA_DIR = Path(__file__).parent / "data"


def create_model():
    """Create and configure the RelationalAI model with all concepts and relationships.

    Returns:
        tuple: (model, graph )
    """
    # Create a Semantics model container
    model = Model("epidemic_spread_intervention_2", config=globals().get("config", None))


    # Load people from CSV
    people_df = pd.read_csv(DATA_DIR / "people.csv")
    people_data = data(people_df)

    # Person concept to represent individuals in the population
    Person = model.Concept("Person", identify_by={"person_id": Integer})
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

    # Create direct contact relationships (undirected edges in contact network)
    person_a, person_b = Person.ref("person_a"), Person.ref("person_b")

    define(
        DirectContact.new(
            person_a=person_a.filter_by(person_id=contacts_data.person_a),
            person_b=person_b.filter_by(person_id=contacts_data.person_b),
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
    # Before looking at connections, let's define how vulnerable an individual is.
    # This creates a "node-level" weight that influences how much infection they "absorb" from the graph.
    # Purpose: This scales the impact of every incoming edge. A person with a 0.0 susceptibility effectively acts as a "sink" that stops the spread.
    Person.base_susceptibility = model.Property(f"{Person} has {Float:base_susceptibility}")

    define(Person.base_susceptibility ==(1 - Person.vaccination_level) * (1 + Person.comorbidity_score))


    # The Multi-Layer Edge Projection
    # People are connected in two ways: direct contact and co-location.
    # We need to merge these into a single "risk edge" that captures overall transmission potential.

    # Transmission risk derived from direct contact (Layer 1)
    DirectContact.transmission_risk = model.Property(f"{DirectContact} has {Float:transmission_risk}")
    define(DirectContact.transmission_risk == DirectContact.frequency * (DirectContact.duration / 60))

    # Derive indirect contacts and co-location transmission risk
    # This connects people who never met but visited the same high-risk location.
    p1, p2 = Person.ref("p1"), Person.ref("p2")
    loc = Location.ref("loc")
    visit_1, visit_2 = Visit.ref("visit_1"), Visit.ref("visit_2")

    CoLocationContact = model.Concept(
        "CoLocationContact",
        identify_by={"person_a": Person, "person_b": Person, "location": Location}
    )

    CoLocationContact.visit_a = model.Relationship(f"{CoLocationContact} relates to {Visit:visit_a} from patient_a")
    CoLocationContact.visit_b = model.Relationship(f"{CoLocationContact} relates to {Visit:visit_b} from patient_b")


    define(CoLocationContact.new(
        person_a = p1,
        person_b = p2,
        location = loc,
        visit_a = visit_1,
        visit_b = visit_2
    )).where(
       visit_1.person(p1),
       visit_2.person(p2),
       visit_1.location(loc),
       visit_2.location(loc),
       p1 != p2,
       p1.person_id < p2.person_id  # Avoid duplicates (undirected)
    )

    CoLocationContact.transmission_risk = model.Property(f"{CoLocationContact} has {Float:transmission_risk}")

    define(CoLocationContact.transmission_risk ==
           CoLocationContact.visit_a.weekly_visits * CoLocationContact.visit_b.weekly_visits * CoLocationContact.location.density_score * (1 - CoLocationContact.location.ventilation_score)
    )

    IndirectContact = model.Concept(
        "IndirectContact",
        identify_by={"person_a": Person, "person_b": Person})
    IndirectContact.transmission_risk = model.Property(f"{IndirectContact} has {Float:transmission_risk}")

    # Create IndirectContact simply by projecting person pairs from CoLocationContact
    # The magic of identify_by ensures we only get one per unique (person_a, person_b) pair
    define(IndirectContact.new(
        person_a=CoLocationContact.person_a,
        person_b=CoLocationContact.person_b
    ))

    # Compute aggregated risk per person pair using .per()
    # This aggregates CoLocationContact.transmission_risk grouped by the person pair
    indirect_agg_risk = sum(CoLocationContact.transmission_risk).per(
        CoLocationContact.person_a,
        CoLocationContact.person_b
    )

    # Assign the aggregated risk to each IndirectContact
    define(IndirectContact.transmission_risk == indirect_agg_risk).where(
        IndirectContact.person_a == CoLocationContact.person_a,
        IndirectContact.person_b == CoLocationContact.person_b
    )


    Contact = model.Concept(
        "Contact",
        identify_by={"person_a": Person, "person_b": Person}
    )

    Contact.transmission_risk = model.Property(f"{Contact} has {Float:transmission_risk}")
    Contact.derived_from_direct = model.Property(f"{Contact} derived from {DirectContact}")
    Contact.derived_from_indirect = model.Property(f"{Contact} derived from {IndirectContact}")

    # Create contacts from direct contacts
    define(Contact.new(
        person_a = DirectContact.person_a,
        person_b = DirectContact.person_b,
        derived_from_direct = DirectContact
    ))

    # Create contacts from indirect contacts
    define(Contact.new(
        person_a = IndirectContact.person_a,
        person_b = IndirectContact.person_b,
        derived_from_indirect = IndirectContact
    ))

    # Calculate transmission risk as sum of both types
    # Use the | operator which should default to 0.0 when the property doesn't exist
    define(Contact.transmission_risk ==
           (Contact.derived_from_direct.transmission_risk | 0.0) +
           (Contact.derived_from_indirect.transmission_risk | 0.0)
    )

    # B. Co-Location Exposure (Layer 2 - The "SQL-Impossible" Part)
    # This connects people who never met but visited the same high-risk location.
    # Logic: If Person A and Person B both visited Location X, crrectContact.filter_by(person_a=p1, person_eate a derived edge between them.
    # Formula: $\sum (\text{visits}_A \times \text{visits}_B \times \text{location\_risk})$
    # Why it's advanced: This is a 2-hop projection ($Person \to Location \to Person$).
    # It treats locations as "transmission bridges."

    return model, Person, Location, DirectContact, Visit, CoLocationContact, Contact, IndirectContact
