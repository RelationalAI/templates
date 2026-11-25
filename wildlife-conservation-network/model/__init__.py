"""Wildlife Conservation Network (graph analytics) template: the model.

This package declares a wildlife conservation network and its community structure in
RelationalAI:

- Load a network of conservation organizations and their partnerships from CSV.
- Apply the Louvain algorithm to detect communities (clusters of closely collaborating orgs).
- Calculate degree centrality and degree to identify hub organizations within each community.
- Profile each community (size, hub, primary region, species focus, organization types, member
  order) and summarize the whole network, all as rules the report reads.

The model uses RelationalAI's Graph API to define organizations as nodes and partnerships
as edges.

Modules: `partnership_network.py` (the graph, Louvain communities, degree centrality, degree),
`community_profiles.py` (each community's members, hub, and trait rankings), and
`network_summary.py` (network-wide counts and averages). Each module imports the modules whose
declarations it reads.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.community_report` then prints the community report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from .community_profiles import Community, CommunityTrait
from .network_summary import NetworkSummary
from .partnership_network import degree, degree_centrality, graph, louvain_communities
from .schema import Organization, Partnership, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Community",
    "CommunityTrait",
    "NetworkSummary",
    "Organization",
    "Partnership",
    "degree",
    "degree_centrality",
    "graph",
    "louvain_communities",
    "model",
]
