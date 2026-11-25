"""IT dependency mapping (graph paths) template.

Maps the downstream dependency structure of a software / data-pipeline estate
by enumerating variable-length traversal paths over an acyclic dependency DAG:

- Loads Feature nodes (services, pipelines, jobs, dashboards) and a
  contributes_to self-relationship (feeds / contributes to) from CSV.
- Enumerates every downstream dependency path with
  ``model.path(Feature.contributes_to.repeat(1, N)).all().paths()`` -- because the
  estate is acyclic, every enumerated path is simple.
- Publishes each path's steps, the number of paths starting at each feature,
  and each feature's longest downstream depth (Feature.max_downstream_depth).

The report reduces the published paths to their maximal chains (longest
non-extendable dependency chains, with shorter sub-chains dropped) and prints
per-feature path counts, the deepest chains, and the owners along the longest.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.dependency_chain_report` then prints the report from the deployed model.
"""

from .reasoning import MAX_DEPTH, DependencyPathStep
from .schema import Feature, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "MAX_DEPTH", "DependencyPathStep", "Feature", "model"]
