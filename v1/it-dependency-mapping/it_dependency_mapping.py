"""IT dependency mapping (graph paths) template.

Maps the downstream dependency structure of a software / data-pipeline estate
by enumerating variable-length traversal paths over an acyclic dependency DAG:

- Loads Feature nodes (services, pipelines, jobs, dashboards) and a
  contributes_to self-relationship (feeds / contributes to) from CSV.
- Enumerates every downstream dependency path with
  ``model.path(Feature.contributes_to.repeat(1, N)).all_paths()`` -- because the
  estate is acyclic, every enumerated path is simple.
- Reduces the full path set to its maximal chains (longest non-extendable
  dependency chains, with shorter sub-chains dropped).
- Persists each feature's longest downstream depth back to the ontology as
  Feature.max_downstream_depth, then reports per-feature path counts, the
  deepest dependency chains, and the owners that sit along the longest chain.

Run:
    /opt/homebrew/bin/python3.11 it_dependency_mapping.py

Output:
    Prints the total downstream path count, per-feature path counts and longest
    downstream depth, the deepest maximal dependency chains, and the chain of
    owners along the single longest chain (the upgrade / incident blast radius).
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Maximum traversal depth (in edges) when enumerating downstream paths. The
# estate is acyclic, so this only needs to cover the longest real chain.
MAX_DEPTH = 8


def load_csv(path):
    return pd.read_csv(path)


# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("it_dependency_mapping")

# Feature concept: a service, data pipeline, feature job, or dashboard.
Feature = model.Concept("Feature", identify_by={"id": String})
Feature.name = model.Property(f"{Feature} has {String:name}")
Feature.owner = model.Property(f"{Feature} owned by {String:owner}")
Feature.deploy_tier = model.Property(f"{Feature} has deploy tier {String:deploy_tier}")

# Feature.contributes_to: a self-relationship -- the upstream feature feeds /
# contributes to the downstream feature, forming an acyclic dependency DAG.
Feature.contributes_to = model.Relationship(
    f"{Feature} contributes to {Feature}", short_name="contributes_to"
)

# Load feature data from CSV.
feature_data = model.data(load_csv(DATA_DIR / "features.csv"))
model.define(Feature.new(id=feature_data["id"]))
model.where(Feature.id == feature_data["id"]).define(
    Feature.name(feature_data["name"]),
    Feature.owner(feature_data["owner"]),
    Feature.deploy_tier(feature_data["deploy_tier"]),
)

# Load dependency edges from CSV (upstream feature -> downstream feature).
dependency_data = model.data(load_csv(DATA_DIR / "dependencies.csv"))
upstream, downstream = Feature.ref(), Feature.ref()
model.where(
    upstream.id == dependency_data["from_feature"],
    downstream.id == dependency_data["to_feature"],
).define(upstream.contributes_to(downstream))

# --------------------------------------------------
# Paths: enumerate downstream dependency paths
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)) describes a
# variable-length traversal of 1..MAX_DEPTH contributes_to edges starting from a
# typed source endpoint `src`. all_paths() enumerates every such path; because
# contributes_to is acyclic, each path is simple. The result is one PathTraversal
# per path -- p.length is its hop count, p.nodes is the ordered sequence of
# Feature nodes it visits, and src is auto-unified with p.nodes(0) (the start).

print("=== IT Dependency Mapping: downstream paths ===")

src = Feature.ref()
p = model.path(src, Feature.contributes_to.repeat(1, MAX_DEPTH)).all_paths()

# Project the node sequence of each path (for display-side reassembly). Keep this
# its own query: selecting p.length or a path aggregate alongside p.nodes fans the
# node rows out (known paths issue), so the per-path rollups below are SEPARATE
# model.where(...) queries.
paths_df = (
    model.where(p)
    .select(
        p.alias("path_id"),
        p.nodes["index"].alias("step"),
        Feature(p.nodes).id.alias("feature_id"),
        Feature(p.nodes).name.alias("feature_name"),
    )
    .to_df()
)
paths_df["step"] = paths_df["step"].astype(int)
# Projecting p.nodes can emit duplicate (path, step) rows -- dedupe to one node
# per step before reassembly.
paths_df = paths_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])

# Reassemble each path: order steps by node index, join the visited features into
# an ordered chain. The hop count is the max node index (a path over N edges has
# nodes at indices 0..N). String-joining names into a chain label is a pandas job.
chains = (
    paths_df.groupby("path_id")
    .agg(
        hops=("step", "max"),
        node_ids=("feature_id", lambda s: tuple(s)),
        chain=("feature_name", lambda s: " -> ".join(s)),
    )
    .reset_index()
)

print(f"\nTotal downstream dependency paths (1-{MAX_DEPTH} hops): {len(chains)}")

# --------------------------------------------------
# Per-feature path counts and longest downstream depth (in-PyRel aggregates)
# --------------------------------------------------

feature_df = model.select(
    Feature.id.alias("feature_id"),
    Feature.name.alias("feature_name"),
    Feature.owner.alias("owner"),
    Feature.deploy_tier.alias("deploy_tier"),
).to_df()

# Paths starting at each feature: aggregates.count(p).per(src) groups the
# enumerated paths by their (typed) source endpoint -- a path-level rollup keyed
# on src, computed IN PyRel rather than via a pandas groupby on the chains frame.
paths_started_df = (
    model.where(p, n := aggs.count(p).per(src))
    .select(src.id.alias("feature_id"), n.alias("paths_downstream"))
    .to_df()
)
# Count column arrives as Int128 -- cast before pandas merge/arithmetic.
paths_started_df["paths_downstream"] = paths_started_df["paths_downstream"].astype(int)

# Persist each feature's longest downstream depth back to the ontology so a
# downstream query can rank features by reach without re-enumerating paths.
# aggregates.max(p.length).per(src) takes the max hop count over the paths rooted
# at each src and defines it directly onto the Feature property -- no pandas
# groupby and no model.data round-trip. Kept SEPARATE from the node projection.
Feature.max_downstream_depth = model.Property(
    f"{Feature} has {Integer:max_downstream_depth}"
)
model.define(src.max_downstream_depth(aggs.max(p.length).per(src))).where(p)

# Read the persisted depth back for the display table. Features with no outgoing
# path (the leaf dashboards) have no max_downstream_depth row -- fill them as 0.
max_depth_df = model.select(
    Feature.id.alias("feature_id"),
    Feature.max_downstream_depth.alias("max_downstream_depth"),
).to_df()
max_depth_df["max_downstream_depth"] = max_depth_df["max_downstream_depth"].astype(
    "Int64"
)

# Build the per-feature display table from the query results above (NOT from a
# pandas groupby on chains): paths_downstream from the count query, depth from the
# persisted property.
feature_summary = feature_df.merge(
    paths_started_df, on="feature_id", how="left"
).merge(max_depth_df, on="feature_id", how="left")
feature_summary["paths_downstream"] = (
    feature_summary["paths_downstream"].fillna(0).astype(int)
)
feature_summary["max_downstream_depth"] = (
    feature_summary["max_downstream_depth"].fillna(0).astype(int)
)

print("\n=== Per-feature downstream reach ===")
print(
    f"  {'Feature':<30} {'Tier':<9} {'Paths':>6} {'Max Depth':>10}"
)
print(f"  {'-' * 57}")
for _, r in feature_summary.sort_values(
    ["max_downstream_depth", "paths_downstream"], ascending=False
).iterrows():
    print(
        f"  {r['feature_name']:<30} {r['deploy_tier']:<9} "
        f"{r['paths_downstream']:>6} {r['max_downstream_depth']:>10}"
    )

# --------------------------------------------------
# Maximal chains: longest non-extendable dependency chains
# --------------------------------------------------
# A path is maximal when its node sequence is not a contiguous sub-chain of any
# other enumerated path -- i.e. it cannot be extended upstream or downstream.
# This collapses the full path set to the small set of end-to-end chains.

all_sequences = list(chains["node_ids"])


def is_sub_chain(short, long):
    """True if `short` is a contiguous sub-sequence of the longer `long`."""
    if len(short) >= len(long):
        return False
    return any(
        long[i : i + len(short)] == short
        for i in range(len(long) - len(short) + 1)
    )


maximal = chains[
    chains["node_ids"].apply(
        lambda seq: not any(
            is_sub_chain(seq, other) for other in all_sequences if other != seq
        )
    )
].copy()
maximal = maximal.sort_values(["hops", "chain"], ascending=[False, True])

print(
    f"\n=== Maximal dependency chains ({len(maximal)} of {len(chains)} paths) ==="
)
for _, r in maximal.iterrows():
    print(f"  {r['hops']} hops: {r['chain']}")

# --------------------------------------------------
# Owners along the single longest chain (blast radius)
# --------------------------------------------------
# The longest chain is the worst-case propagation path: a change at its root has
# to clear every owner along the way. Join owner metadata onto its features.

owner_by_id = dict(zip(feature_df["feature_id"], feature_df["owner"]))
name_by_id = dict(zip(feature_df["feature_id"], feature_df["feature_name"]))
tier_by_id = dict(zip(feature_df["feature_id"], feature_df["deploy_tier"]))

longest = maximal.iloc[0]
longest_ids = longest["node_ids"]
distinct_owners = len({owner_by_id[i] for i in longest_ids})

print(f"\n=== Longest dependency chain: {longest['hops']} hops ===")
print(f"  Chain: {longest['chain']}")
print(f"  Spans {len(longest_ids)} features and {distinct_owners} owners:")
for i in longest_ids:
    print(f"    - {name_by_id[i]:<30} owner={owner_by_id[i]:<14} tier={tier_by_id[i]}")
print(
    f"\n  A change at '{name_by_id[longest_ids[0]]}' propagates through "
    f"{len(longest_ids) - 1} downstream feature(s) before reaching "
    f"'{name_by_id[longest_ids[-1]]}'."
)
