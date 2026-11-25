"""Match graph: weakly connected components over the accepted match edges cluster records into one
insured party, closing transitive chains, and the graph's size."""

from relationalai.semantics import Integer
from relationalai.semantics.reasoners.graph import Graph

from .schema import CandidateMatch, Record, model


def cluster_accepted_matches():
    """Cluster records connected by accepted match edges."""
    graph = Graph(model, directed=False, weighted=False, node_concept=Record, name="match_graph")

    match_ref = CandidateMatch.ref()
    rec_a, rec_b = Record.ref(), Record.ref()
    model.where(match_ref.rec_a == rec_a, match_ref.rec_b == rec_b).define(
        graph.Edge.new(src=rec_a, dst=rec_b)
    )

    graph.Node.entity_id = graph.weakly_connected_component()

    rep_node = Record.ref()
    model.where(Record.entity_id == rep_node).define(
        Record.entity_key(rep_node.record_id)
    )

    # The graph's size, which the deployed model publishes for the queries.
    node_count, edge_count = Integer.ref(), Integer.ref()
    num_nodes = model.Relationship(f"the match graph has {Integer:node_count} nodes")
    num_edges = model.Relationship(f"the match graph has {Integer:edge_count} edges")
    model.where(graph.num_nodes()(node_count)).define(num_nodes(node_count))
    model.where(graph.num_edges()(edge_count)).define(num_edges(edge_count))
    return num_nodes, num_edges


num_nodes, num_edges = cluster_accepted_matches()
