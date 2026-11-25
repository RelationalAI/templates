"""Humanitarian Aid Supply Chain Network (graph analytics) template: the model.

This package declares a humanitarian aid supply chain and its PageRank and Degree
Centrality metrics in RelationalAI:

- Load a network of distribution points and supply routes from CSV files.
- Apply PageRank to identify the most influential distribution hubs where aid naturally flows.
- Calculate Degree Centrality to find highly connected critical nodes that serve as network hubs.
- Calculate each point's incoming and outgoing route counts.
- Classify each point into a strategic category from its PageRank and Degree Centrality.

`supply_network.py` states the flow weight, the graph, the metrics, and the categories.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.distribution_point_ranking` then prints the ranked report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from .schema import DistributionPoint, SupplyRoute, model
from .source import DATA_DIR
from .supply_network import degree_centrality, graph, indegree, outdegree, pagerank

__all__ = [
    "DATA_DIR",
    "DistributionPoint",
    "SupplyRoute",
    "degree_centrality",
    "graph",
    "indegree",
    "model",
    "outdegree",
    "pagerank",
]
