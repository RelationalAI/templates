"""Humanitarian Aid Supply Chain Network (graph analytics) template.

Run:
    `python humanitarian_aid_supply_chain.py`

Output:
    Displays ranked distribution points showing both influence (PageRank) and connectivity
    (Degree Centrality), helping emergency response teams optimize aid distribution, identify
    critical network hubs, and make strategic resource allocation decisions.
"""

from relationalai.semantics import select, where, Integer, Float, sum

from model_setup import create_model

# --------------------------------------------------
# Create model and calculate graph metrics
# --------------------------------------------------

model, Person, Location, DirectContact, Visit, CoLocationContact, Contact, IndirectContact= create_model()


# --------------------------------------------------
# Query and display results
# --------------------------------------------------

def main() -> None:
    """
    Main analysis function that:

    """

    # Query the graph to retrieve:
    p1, p2 = Person.ref("p1"), Person.ref("p2")

    print("DirectContact:")
    direct_results = select(
        DirectContact.person_a.person_id,
        DirectContact.person_b.person_id,
        DirectContact.transmission_risk
    ).to_df()
    print(direct_results.head(10).to_string())
    print(f"\nTotal direct contacts: {len(direct_results)}\n")

    print("IndirectContact:")
    indirect_results = select(
        IndirectContact.person_a.person_id,
        IndirectContact.person_b.person_id,
        IndirectContact.transmission_risk
    ).to_df()
    print(indirect_results.head(10).to_string())
    print(f"\nTotal indirect contacts: {len(indirect_results)}\n")

    print("Contact (Combined):")
    results = select(
        Contact.person_a.person_id,
        Contact.person_b.person_id,
        Contact.derived_from_direct.transmission_risk | 0.0,
        Contact.derived_from_indirect.transmission_risk | 0.0
    ).to_df()

    # Compute total risk in pandas
    results.columns = ['person_a', 'person_b', 'direct_risk', 'indirect_risk']
    results['transmission_risk'] = results['direct_risk'] + results['indirect_risk']

    print(results[['person_a', 'person_b', 'transmission_risk']].head(20).to_string())
    print(f"\n{len(results)} total contacts")

    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
