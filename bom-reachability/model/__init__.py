"""BOM Reachability (graph analysis) template.

Answers:
  "What components does Product X transitively depend on?"
  "Which components are bottleneck dependencies across products?"

Data: supply chain (SKUs + BillOfMaterials).
Graph: directed, unweighted. SKU nodes, BOM rows as edges (output -> input).
  Edge direction: output_sku -> input_sku ("depends on").
Algorithms: reachable(full=True) for transitive dependency tracing,
  betweenness_centrality() for identifying structural bottlenecks.

Assembly path enumeration (PREVIEW, requires relationalai>=1.15): enumerate the
  bottom-up assembly chains that build each finished good. Derives a binary
  SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (input feeds
  output), enumerates every assembly path with model.path(...).all().paths(),
  filters to the maximal (longest non-extendable) chains so sub-paths are
  suppressed, and persists the longest assembly depth of each SKU that ends a
  chain (feeds nothing further) back onto the SKU ontology.

Deploy:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_report` then prints the report from the deployed model.
"""

from .reasoning import MAX_ASSEMBLY_HOPS, betweenness, graph, num_edges, num_nodes, p, reachable
from .schema import SKU, BillOfMaterials, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "MAX_ASSEMBLY_HOPS",
    "SKU",
    "BillOfMaterials",
    "betweenness",
    "graph",
    "model",
    "num_edges",
    "num_nodes",
    "p",
    "reachable",
]
