"""Downstream dependency report from the deployed IT estate model.

Run after `rai models deploy --path model`:
    python -m queries.dependency_chain_report

Prints the total downstream path count, per-feature path counts and longest
downstream depth, the deepest maximal dependency chains, and the chain of owners
along the single longest chain (the upgrade / incident blast radius).
"""

from model import (
    MAX_DEPTH,
    DependencyPathStep,
    Feature,
    LongestChain,
    MaximalChain,
    NumPaths,
    PathSummary,
    model,
)
from relationalai.semantics import Hash, Integer, String

if __name__ == "__main__":
    print("=== IT Dependency Mapping: downstream paths ===")

    total_paths = int(model.select(NumPaths).to_df().iloc[0, 0])
    print(f"\nTotal downstream dependency paths (1-{MAX_DEPTH} hops): {total_paths}")

    # --------------------------------------------------
    # Per-feature path counts and longest downstream depth (in-PyRel aggregates)
    # --------------------------------------------------

    feature_df = model.select(
        Feature.id.alias("feature_id"),
        Feature.name.alias("feature_name"),
        Feature.owner.alias("owner"),
        Feature.deploy_tier.alias("deploy_tier"),
    ).to_df()

    # Paths starting at each feature, counted in the model (see model/downstream_paths.py).
    paths_started = Integer.ref()
    paths_started_df = (
        model.where(Feature.paths_downstream(paths_started))
        .select(Feature.id.alias("feature_id"), paths_started.alias("paths_downstream"))
        .to_df()
    )

    # Read the persisted depth back for the display table; leaf features carry 0.
    max_depth_df = model.select(
        Feature.id.alias("feature_id"),
        Feature.max_downstream_depth.alias("max_downstream_depth"),
    ).to_df()

    # Build the per-feature display table from the query results above: paths_downstream
    # from the count query, depth from the persisted property.
    feature_summary = feature_df.merge(
        paths_started_df, on="feature_id", how="left"
    ).merge(max_depth_df, on="feature_id", how="left")

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
    # The model marks the paths no other enumerated path extends upstream or downstream,
    # collapsing the full path set to the small set of end-to-end chains.

    path, hops, n_features, n_owners, chain = (
        Hash.ref(),
        Integer.ref(),
        Integer.ref(),
        Integer.ref(),
        String.ref(),
    )
    summary_columns = (
        hops.alias("hops"),
        n_features.alias("n_features"),
        n_owners.alias("n_owners"),
        chain.alias("chain"),
    )
    maximal = (
        model.where(MaximalChain(path), PathSummary(path, hops, n_features, n_owners, chain))
        .select(*summary_columns)
        .to_df()
        .sort_values(["hops", "chain"], ascending=[False, True])
    )

    print(
        f"\n=== Maximal dependency chains ({len(maximal)} of {total_paths} paths) ==="
    )
    for _, r in maximal.iterrows():
        print(f"  {r['hops']} hops: {r['chain']}")

    # --------------------------------------------------
    # Owners along the single longest chain (blast radius)
    # --------------------------------------------------
    # The longest chain is the worst-case propagation path: a change at its root has
    # to clear every owner along the way. The model publishes its span; its features
    # are read back in step order.

    longest = (
        model.where(LongestChain(path), PathSummary(path, hops, n_features, n_owners, chain))
        .select(*summary_columns)
        .to_df()
        .iloc[0]
    )
    step = Integer.ref()
    longest_features = (
        model.where(LongestChain(path), DependencyPathStep(path, Feature, step))
        .select(
            step.alias("step"),
            Feature.name.alias("feature_name"),
            Feature.owner.alias("owner"),
            Feature.deploy_tier.alias("deploy_tier"),
        )
        .to_df()
        .sort_values("step")
    )

    print(f"\n=== Longest dependency chain: {longest['hops']} hops ===")
    print(f"  Chain: {longest['chain']}")
    print(f"  Spans {longest['n_features']} features and {longest['n_owners']} owners:")
    for _, f in longest_features.iterrows():
        print(f"    - {f['feature_name']:<30} owner={f['owner']:<14} tier={f['deploy_tier']}")
    print(
        f"\n  A change at '{longest_features['feature_name'].iloc[0]}' propagates through "
        f"{longest['hops']} downstream feature(s) before reaching "
        f"'{longest_features['feature_name'].iloc[-1]}'."
    )
