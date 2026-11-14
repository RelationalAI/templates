"""Downstream dependency report from the deployed IT estate model.

Run after `rai models deploy --path model`:
    python -m queries.dependency_chain_report

Prints the total downstream path count, per-feature path counts and longest
downstream depth, the deepest maximal dependency chains, and the chain of owners
along the single longest chain (the upgrade / incident blast radius).
"""

from model import MAX_DEPTH, Feature, model, p, src
from relationalai.semantics.std import aggregates as aggs

if __name__ == "__main__":
    print("=== IT Dependency Mapping: downstream paths ===")

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
