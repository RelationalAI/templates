"""Humanitarian Aid Supply Chain Network (graph analytics) template.

Run:
    `python humanitarian_aid_supply_chain.py`

Output:
    Displays ranked distribution points showing both influence (PageRank) and connectivity
    (Degree Centrality), helping emergency response teams optimize aid distribution, identify
    critical network hubs, and make strategic resource allocation decisions.
"""

from math import dist
from tracemalloc import start
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

    # length = Integer.ref("length")
    # start, end = indirect_contact_graph.Node.ref("start"), indirect_contact_graph.Node.ref("end")

    # dist = indirect_contact_graph.distance(full=True)
    # new_results =  where(
    #     dist(start, end, length),
    #     length == 2).select(
    #     start.id,
    #     end.id,
    #     length
    # ).to_df()

    new_results = select(
        ColocationContact.person_a,
        ColocationContact.person_b
    ).to_df()

    print(new_results.to_string())

    print("\n✅ Analysis complete!\n")

if __name__ == "__main__":
    main()
