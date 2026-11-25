"""Dependency, bottleneck, and assembly-chain report from the deployed BOM model.

Run after `rai models deploy --path model`:
    python -m queries.dependency_report
"""

from model import (
    MAX_ASSEMBLY_HOPS,
    SKU,
    AssemblyStep,
    ChainLength,
    MaximalChain,
    model,
    num_chains,
    num_edges,
    num_maximal_chains,
    num_nodes,
)
from relationalai.semantics import Hash, Integer, String, where

if __name__ == "__main__":
    print("=== BOM Dependency Graph ===")
    print(f"{model.select(num_nodes).to_df().iloc[0, 0]} SKUs (nodes)")
    print(f"{model.select(num_edges).to_df().iloc[0, 0]} dependency edges")

    src, dst = SKU.ref("src"), SKU.ref("dst")
    all_deps_df = (
        where(src.reaches(dst))
        .select(
            src.id.alias("product_id"),
            src.name.alias("product_name"),
            src.type.alias("product_type"),
            dst.id.alias("dep_id"),
            dst.name.alias("dep_name"),
            dst.type.alias("dep_type"),
        )
        .to_df()
    )

    print(f"\nTotal reachable pairs: {len(all_deps_df)}")

    # --------------------------------------------------
    # Dependencies of each finished good
    # --------------------------------------------------

    # Dependency counts, in total and by type, as the model publishes them.
    n_deps = (
        model.select(SKU.id.alias("sku_id"), SKU.n_dependencies.alias("n"))
        .to_df()
        .set_index("sku_id")["n"]
    )
    n_type, type_ref = Integer.ref(), String.ref()
    n_deps_by_type = (
        model.where(SKU.n_dependencies_by_type(n_type, type_ref))
        .select(SKU.id.alias("sku_id"), type_ref.alias("dep_type"), n_type.alias("n"))
        .to_df()
        .set_index(["sku_id", "dep_type"])["n"]
    )

    finished = all_deps_df[all_deps_df["product_type"] == "FINISHED_GOOD"]
    for product_id in sorted(finished["product_id"].unique()):
        deps = finished[(finished["product_id"] == product_id) & (finished["dep_id"] != product_id)]
        if len(deps) > 0:
            product_name = deps["product_name"].iloc[0]
            print(f"\n--- Dependencies of '{product_name}' ({product_id}) ---")
            print(f"  {n_deps[product_id]} transitive dependencies:")
            for dep_type in ["COMPONENT", "RAW_MATERIAL"]:
                type_deps = deps[deps["dep_type"] == dep_type]
                if len(type_deps) > 0:
                    print(f"\n  {dep_type}s ({n_deps_by_type[product_id, dep_type]}):")
                    for _, row in type_deps.sort_values("dep_name").iterrows():
                        print(f"    - {row['dep_name']} ({row['dep_id']})")

    # --------------------------------------------------
    # Most depended-on components
    # --------------------------------------------------

    # Finished goods have no dependents and no depended_on_by value; list only SKUs something depends on.
    dep_counts = (
        where(SKU.depended_on_by > 0)
        .select(
            SKU.id.alias("dep_id"),
            SKU.name.alias("dep_name"),
            SKU.type.alias("dep_type"),
            SKU.depended_on_by.alias("depended_on_by"),
        )
        .to_df()
        .sort_values(["depended_on_by", "dep_id"], ascending=[False, True])
    )
    if len(dep_counts) > 0:
        print("\n=== Most Depended-On SKUs ===")
        print(dep_counts.to_string(index=False))

    # --------------------------------------------------
    # Betweenness centrality: structural bottlenecks
    # --------------------------------------------------

    btw_df = (
        model.select(
            SKU.id.alias("sku_id"),
            SKU.name.alias("sku_name"),
            SKU.type.alias("type"),
            SKU.category.alias("category"),
            SKU.betweenness.alias("betweenness"),
        )
        .to_df()
        .sort_values("betweenness", ascending=False)
        .reset_index(drop=True)
    )

    print("\n=== Betweenness Centrality (bottleneck components) ===")
    print(btw_df.to_string(index=False))

    top_df = (
        where(SKU.bottleneck_rank == 1)
        .select(SKU.name.alias("sku_name"), SKU.betweenness.alias("betweenness"))
        .to_df()
    )
    if len(top_df) > 0:
        top = top_df.iloc[0]
        print(f"\nTop bottleneck: {top['sku_name']} (betweenness={top['betweenness']:.4f})")
        print("  Sits on the most shortest dependency paths between other SKUs.")

    # --------------------------------------------------
    # Assembly path enumeration
    # --------------------------------------------------

    print("\n=== Assembly Path Enumeration (PREVIEW) ===")

    path, step, hops = Hash.ref(), Integer.ref(), Integer.ref()
    assembly_df = (
        model.where(AssemblyStep(path, SKU, step), ChainLength(path, hops))
        .select(
            path.alias("path"),
            step.alias("step"),
            hops.alias("hops"),
            SKU.name.alias("sku_name"),
        )
        .to_df()
    )
    maximal_ids = set(model.select(MaximalChain).to_df().iloc[:, 0])

    # Order each chain's steps for display: group on the path id, sort by step index.
    paths = []
    for path_id, grp in assembly_df.groupby("path"):
        names = grp.sort_values("step")["sku_name"].tolist()
        paths.append({"names": names, "length": int(grp["hops"].iloc[0]), "maximal": path_id in maximal_ids})

    n_chains = model.select(num_chains).to_df().iloc[0, 0]
    n_maximal = model.select(num_maximal_chains).to_df().iloc[0, 0]
    print(f"\n  Enumerated {n_chains} assembly path(s) (<= {MAX_ASSEMBLY_HOPS} hops).")

    # (a) All assembly paths, longest first.
    print("\n  All assembly chains (feeds-into order):")
    for path in sorted(paths, key=lambda x: -x["length"]):
        print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

    # (b) Maximal chains, as the deployed model marks them: suppressing sub-paths
    # leaves just the end-to-end assembly routes.
    maximal = [path for path in paths if path["maximal"]]

    print(f"\n  Maximal assembly chains ({n_maximal} of {n_chains}, sub-paths suppressed):")
    for path in sorted(maximal, key=lambda x: -x["length"]):
        print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

    print("\n  Assembly depth persisted onto SKU (longest maximal chain ending at each):")
    depth_df = (
        where(SKU.assembly_depth > 0)
        .select(
            SKU.id.alias("sku_id"),
            SKU.name.alias("sku_name"),
            SKU.type.alias("type"),
            SKU.assembly_depth.alias("assembly_depth"),
        )
        .to_df()
        .sort_values(["assembly_depth", "sku_id"], ascending=[False, True], ignore_index=True)
    )
    print(depth_df.to_string(index=False))
    too_deep = where(SKU.exceeds_hop_bound()).select(SKU.id.alias("sku_id")).to_df()["sku_id"]
    if len(too_deep) > 0:
        print(
            f"\n  Deeper than {MAX_ASSEMBLY_HOPS} hops, so no depth is published "
            f"(raise MAX_ASSEMBLY_HOPS): {', '.join(sorted(too_deep))}"
        )
