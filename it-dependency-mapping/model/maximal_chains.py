"""Maximal dependency chains: the paths no other enumerated path extends, and the longest of them."""

from relationalai.semantics import Hash, Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declares the path steps and summaries and the Feature.has_upstream and has_downstream flags.
from .downstream_paths import MAX_DEPTH, DependencyPathStep, PathSummary
from .schema import Feature, model

# A path is maximal when no enumerated path contains it as a contiguous stretch: no feature feeds
# its first feature and none follows its last. A path of MAX_DEPTH hops is maximal too, because no
# longer path is enumerated. In an acyclic estate only a path's last feature can lack a downstream
# feature.
MaximalChain = model.Relationship(f"dependency path {Hash:path} is a maximal chain")
_path, _step = Hash.ref(), Integer.ref()
_first, _last, _end = Feature.ref(), Feature.ref(), Feature.ref()
model.where(
    DependencyPathStep(_path, _first, 0),
    DependencyPathStep(_path, _last, _step),
    model.not_(_first.has_upstream()),
    model.not_(_last.has_downstream()),
).define(MaximalChain(_path))
model.where(DependencyPathStep(_path, _end, MAX_DEPTH)).define(MaximalChain(_path))

# The longest maximal chain: most hops first, ties broken by the chain label. The hop count is
# negated so both keys sort ascending.
LongestChain = model.Relationship(f"dependency path {Hash:path} is the longest maximal chain")
_hops, _n_features, _n_owners, _chain = Integer.ref(), Integer.ref(), Integer.ref(), String.ref()
model.where(
    MaximalChain(_path),
    PathSummary(_path, _hops, _n_features, _n_owners, _chain),
    aggs.rank(-_hops, _chain) == 1,
).define(LongestChain(_path))
