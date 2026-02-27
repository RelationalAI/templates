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

model, Person, Location, DirectContact, Visit, indirect_contact_graph, ColocationContact= create_model()
# CoLocationContact, Contact, IndirectContact,

# --------------------------------------------------
# Query and display results
# --------------------------------------------------

def main() -> None:
    """
    Main analysis function that:

    """

    # Query the graph to retrieve:

    length = Integer.ref("length")
    node = indirect_contact_graph.Node.ref("node")
    edge = indirect_contact_graph.Edge.ref("edge")

    dist = indirect_contact_graph.distance(full=True)
    new_results =  select(
        ColocationContact
    ).to_df()

    print(new_results.to_string())

    print("\n✅ Analysis complete!\n")

if __name__ == "__main__":
    main()
