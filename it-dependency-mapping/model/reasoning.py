"""Downstream dependency paths: path enumeration and each feature's longest downstream depth."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

from .schema import Feature, model

# Maximum traversal depth (in edges) when enumerating downstream paths. The
# estate is acyclic, so this only needs to cover the longest real chain.
MAX_DEPTH = 8

# --------------------------------------------------
# Paths: enumerate downstream dependency paths
#   PREVIEW capability; requires relationalai>=1.15.
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
# Relationship, not a Property: deploying this rule as a Property fails planning
# on relationalai 2.1.1.
Feature.max_downstream_depth = model.Relationship(
    f"{Feature} has {Integer:max_downstream_depth}"
)
model.define(src.max_downstream_depth(aggs.max(p.length).per(src))).where(p)
