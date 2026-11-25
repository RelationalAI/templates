"""IT dependency mapping (graph paths) template.

Maps the downstream dependency structure of a software / data-pipeline estate
by enumerating variable-length traversal paths over an acyclic dependency DAG:

- Loads Feature nodes (services, pipelines, jobs, dashboards) and a
  contributes_to self-relationship (feeds / contributes to) from CSV.
- Enumerates every downstream dependency path with
  ``model.path(Feature.contributes_to.repeat(1, N)).all().paths()`` -- because the
  estate is acyclic, every enumerated path is simple.
- Publishes each path's steps, the number of paths starting at each feature, each
  feature's longest downstream depth (Feature.max_downstream_depth), and each
  path's hop count, feature count, owner count, and chain label.
- Marks the maximal chains (longest non-extendable dependency chains, with
  shorter sub-chains dropped) and the longest of them. `downstream_paths.py`
  holds the paths and their summaries; `maximal_chains.py` holds the maximal and
  longest chains and imports the module whose declarations it reads.

The report prints the path total, per-feature path counts and longest downstream
depth, the maximal chains, and the owners along the longest chain.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_chain_report` then prints the report from the deployed model.
"""

from .downstream_paths import MAX_DEPTH, DependencyPathStep, NumPaths, PathSummary
from .maximal_chains import LongestChain, MaximalChain
from .schema import Feature, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "MAX_DEPTH",
    "DependencyPathStep",
    "Feature",
    "LongestChain",
    "MaximalChain",
    "NumPaths",
    "PathSummary",
    "model",
]
