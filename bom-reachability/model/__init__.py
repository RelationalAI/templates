"""BOM Reachability (graph analysis) template.

Answers:
  "What components does Product X transitively depend on?"
  "Which components are bottleneck dependencies across products?"

Data: supply chain (SKUs + BillOfMaterials).
Graph: directed, unweighted. SKU nodes, BOM rows as edges (output -> input).
  Edge direction: output_sku -> input_sku ("depends on").
Algorithms: reachable(full=True) for transitive dependency tracing,
  betweenness_centrality() for identifying structural bottlenecks.

Assembly path enumeration (PREVIEW): enumerate the
  bottom-up assembly chains that build each finished good. Derives a binary
  SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (input feeds
  output), enumerates every assembly path with model.path(...).all().paths(),
  marks the maximal (non-extendable) chains so sub-paths can be suppressed, and
  persists the longest maximal chain ending at each SKU as its assembly depth,
  flagging instead a finished SKU reached by a chain longer than MAX_ASSEMBLY_HOPS.

The model has two rule modules: `dependency_graph.py` (reachability,
dependency counts, betweenness, bottleneck rank) and `assembly_chains.py` (chain
enumeration, maximal chains, chain counts, assembly depth).

Deploy:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_report` then prints the report from the deployed model.
"""

from .assembly_chains import (
    MAX_ASSEMBLY_HOPS,
    AssemblyStep,
    ChainLength,
    MaximalChain,
    num_chains,
    num_maximal_chains,
)
from .dependency_graph import betweenness, graph, num_edges, num_nodes, reachable
from .schema import SKU, BillOfMaterials, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "MAX_ASSEMBLY_HOPS",
    "AssemblyStep",
    "ChainLength",
    "MaximalChain",
    "SKU",
    "BillOfMaterials",
    "betweenness",
    "graph",
    "model",
    "num_chains",
    "num_edges",
    "num_maximal_chains",
    "num_nodes",
    "reachable",
]
