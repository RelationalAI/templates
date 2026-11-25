"""Downstream dependency paths: path enumeration, each feature's path count and longest downstream
depth, and each path's hop count, feature count, owner count, and chain label."""

from relationalai.semantics import Hash, Integer, String
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

# A feature with no outgoing edge starts no path, so its count and depth are zero.
Feature.has_downstream = model.Relationship(f"{Feature} has a downstream feature")
Feature.has_upstream = model.Relationship(f"{Feature} has an upstream feature")
_next, _previous = Feature.ref(), Feature.ref()
model.where(Feature.contributes_to(_next)).define(Feature.has_downstream())
model.where(_previous.contributes_to(Feature)).define(Feature.has_upstream())
model.where(model.not_(Feature.has_downstream())).define(
    Feature.paths_downstream(0), Feature.max_downstream_depth(0)
)

# The number of enumerated paths.
NumPaths = model.Relationship(f"the estate has {Integer:num_paths} downstream dependency paths")
model.define(NumPaths(aggs.count(p))).where(p)

# Each path's hop count (its last step), number of features, number of distinct owners, and chain
# label: the feature names in step order joined with " -> ".
PathSummary = model.Relationship(
    f"dependency path {Hash:path} has {Integer:hops} hops over {Integer:n_features} features "
    f"with {Integer:n_owners} owners as chain {String:chain}"
)
_path, _node, _step = Hash.ref(), Feature.ref(), Integer.ref()
model.where(DependencyPathStep(_path, _node, _step)).define(
    PathSummary(
        _path,
        aggs.max(_step).per(_path),
        aggs.count(_step).per(_path),
        aggs.count(_node.owner).per(_path),
        aggs.string_join(_node.name, sep=" -> ", index=_step).per(_path),
    )
)
