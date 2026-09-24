"""Ownership-graph statistics in the shape of P1 §2 (Italian company graph), for generated data.

    python -m data.generator.stats data/sample
"""

import sys

import networkx as nx
import numpy as np
from model.contracts import read_dir


def graph_stats(tables) -> dict:
    sh = tables["shareholdings"]
    g = nx.DiGraph()
    g.add_nodes_from(tables["companies"]["eid"])
    g.add_nodes_from(tables["persons"]["eid"])
    g.add_edges_from(zip(sh.owner_eid, sh.owned_eid))
    n, e = g.number_of_nodes(), g.number_of_edges()
    wcc = [len(c) for c in nx.weakly_connected_components(g)]
    scc = max(len(c) for c in nx.strongly_connected_components(g))
    outdeg = np.array([d for _, d in g.out_degree()])
    ks, counts = np.unique(outdeg[outdeg >= 2], return_counts=True)
    slope = float(np.polyfit(np.log(ks), np.log(counts), 1)[0]) if len(ks) >= 3 else float("nan")
    und = nx.Graph(g)
    und.remove_edges_from(nx.selfloop_edges(und))
    incoming = sh[sh.owner_eid != sh.owned_eid].groupby("owned_eid")["share"].sum()
    return {
        "nodes": n, "edges": e,
        "avg_degree": e / n,
        "wcc_count": len(wcc), "wcc_mean_size": float(np.mean(wcc)), "largest_wcc": max(wcc),
        "largest_scc": scc,
        "self_loops": nx.number_of_selfloops(g), "self_loop_rate": nx.number_of_selfloops(g) / n,
        "avg_clustering": nx.average_clustering(und),
        "max_in_degree": max(d for _, d in g.in_degree()), "max_out_degree": int(outdeg.max()),
        "out_degree_tail_slope": slope,
        "max_incoming_share": float(incoming.max()),
    }


if __name__ == "__main__":
    stats = graph_stats(read_dir(sys.argv[1]))
    width = max(map(len, stats))
    for k, v in stats.items():
        print(f"{k:<{width}}  {v:.4f}" if isinstance(v, float) else f"{k:<{width}}  {v}")
