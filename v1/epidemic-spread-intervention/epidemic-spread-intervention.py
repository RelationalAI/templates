"""Epidemic Spread Intervention template.

Run:
    `python epidemic-spread-intervention.py`

Output:
    Displays three ranked tables identifying intervention priorities:
    - Eigenvector Centrality: super-spreaders with multi-layer influence
    - Betweenness Centrality: bridge individuals connecting otherwise-separate communities
    - Louvain Community Detection: tight-knit transmission clusters
"""

from relationalai.semantics import where, Integer, Float

from model_setup import create_model


def main() -> None:
    # --------------------------------------------------
    # Create model
    # --------------------------------------------------

    *_, exposure_graph = create_model()

    # --------------------------------------------------
    # Run graph algorithms
    # --------------------------------------------------

    # Eigenvector Centrality: super-spreaders whose connections are themselves well-connected
    eigenvector_centrality = exposure_graph.eigenvector_centrality()

    # Betweenness Centrality: bridge individuals who connect otherwise-separate communities
    betweenness_centrality = exposure_graph.betweenness_centrality()

    # Louvain Community Detection: tight-knit transmission clusters
    louvain_communities = exposure_graph.louvain()

    # Variable references for querying
    person = exposure_graph.Node.ref("person")
    eig_score = Float.ref("eig_score")
    btw_score = Float.ref("btw_score")
    community_id = Integer.ref("community_id")

    # --------------------------------------------------
    # Query and display results
    # --------------------------------------------------

    print("\n--- Super-Spreaders (Eigenvector Centrality) ---")
    print("Ranks individuals whose connections are themselves highly connected.")
    print("High score = influence amplified across multiple social layers.\n")
    eig_df = where(
        eigenvector_centrality(person, eig_score)
    ).select(
        person.person_id,
        eig_score.alias("eigenvector_score")
    ).to_df().sort_values("eigenvector_score", ascending=False)
    print(eig_df.to_string(index=False))

    print("\n--- Bridge Individuals (Betweenness Centrality) ---")
    print("Ranks individuals who sit on the shortest paths between others.")
    print("High score = removing or vaccinating this person fractures spread routes.\n")
    btw_df = where(
        betweenness_centrality(person, btw_score)
    ).select(
        person.person_id,
        btw_score.alias("betweenness_score")
    ).to_df().sort_values("betweenness_score", ascending=False)
    print(btw_df.to_string(index=False))

    print("\n--- Transmission Clusters (Louvain Communities) ---")
    print("Groups people into tightly-connected communities.")
    print("Clusters with high internal weight are the highest-risk transmission pools.\n")
    com_df = where(
        louvain_communities(person, community_id)
    ).select(
        person.person_id,
        community_id.alias("community")
    ).to_df().sort_values("community")
    print(com_df.to_string(index=False))

    print("\n✅ Analysis complete!\n")

if __name__ == "__main__":
    main()
