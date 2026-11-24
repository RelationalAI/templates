"""Downstream dependency paths: path enumeration and each feature's longest downstream depth."""

from relationalai.semantics import Hash, Integer
from relationalai.semantics.std import aggregates as aggs

from .schema import Feature, model

# Maximum traversal depth (in edges) when enumerating downstream paths. The
# estate is acyclic, so this only needs to cover the longest real chain.
MAX_DEPTH = 8

# --------------------------------------------------
# Paths: enumerate downstream dependency paths
#   PREVIEW capability.
# --------------------------------------------------
# model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)) describes a
# variable-length traversal of 1..MAX_DEPTH contributes_to edges starting from a
# typed source endpoint `src`. .all().paths() enumerates every such path; because
# contributes_to is acyclic, each path is simple. The result is one PathTraversal
# per path -- p.length is its hop count, p.nodes is the ordered sequence of
# Feature nodes it visits, and src is auto-unified with p.nodes(0) (the start).

src = Feature.ref()
p = model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)).all().paths()

# Persist each feature's longest downstream depth back to the ontology so a
# downstream query can rank features by reach without re-enumerating paths.
# aggregates.max(p.length).per(src) takes the max hop count over the paths rooted
# at each src and defines it directly onto Feature -- no pandas groupby and no
# model.data round-trip. Kept SEPARATE from the node projection. It is a
# Relationship, not a Property: deploying a rule over model.path(...) that writes a
# Property onto the concept the path walks fails planning.
Feature.max_downstream_depth = model.Relationship(
    f"{Feature} has {Integer:max_downstream_depth}"
)
model.define(src.max_downstream_depth(aggs.max(p.length).per(src))).where(p)

# The paths, which the deployed model publishes for the queries: the feature at each step of
# each path, keyed by the path id, and the number of paths that start at each feature.
# aggregates.count(p).per(src) groups the enumerated paths by their (typed) source endpoint
# -- a path-level rollup keyed on src, computed IN PyRel rather than via a pandas groupby.
DependencyPathStep = model.Relationship(
    f"dependency path {Hash:path} has {Feature:feature} at step {Integer:step}"
)
model.where(p).define(DependencyPathStep(p, Feature(p.nodes), p.nodes["index"]))
Feature.paths_downstream = model.Relationship(f"{Feature} starts {Integer:paths_downstream} paths")
model.define(src.paths_downstream(aggs.count(p).per(src))).where(p)
