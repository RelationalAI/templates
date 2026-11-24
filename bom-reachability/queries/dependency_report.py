"""Dependency, bottleneck, and assembly-chain report from the deployed BOM model.

Run after `rai models deploy --path model`:
    python -m queries.dependency_report
"""

from model import MAX_ASSEMBLY_HOPS, SKU, AssemblyStep, MaximalChain, model, num_edges, num_nodes
from relationalai.semantics import Hash, Integer, where

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

    finished = all_deps_df[all_deps_df["product_type"] == "FINISHED_GOOD"]
    for product_id in sorted(finished["product_id"].unique()):
        deps = finished[(finished["product_id"] == product_id) & (finished["dep_id"] != product_id)]
        if len(deps) > 0:
            product_name = deps["product_name"].iloc[0]
            print(f"\n--- Dependencies of '{product_name}' ({product_id}) ---")
            print(f"  {len(deps)} transitive dependencies:")
            for dep_type in ["COMPONENT", "RAW_MATERIAL"]:
                type_deps = deps[deps["dep_type"] == dep_type]
                if len(type_deps) > 0:
                    print(f"\n  {dep_type}s ({len(type_deps)}):")
                    for _, row in type_deps.sort_values("dep_name").iterrows():
                        print(f"    - {row['dep_name']} ({row['dep_id']})")

    # --------------------------------------------------
    # Most depended-on components
    # --------------------------------------------------

    dep_counts = (
        model.select(
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

    bottlenecks = btw_df[btw_df["betweenness"] > 0]
    if len(bottlenecks) > 0:
        top = bottlenecks.iloc[0]
        print(f"\nTop bottleneck: {top['sku_name']} (betweenness={top['betweenness']:.4f})")
        print("  Sits on the most dependency paths -- disruption here affects the most product lines.")

    # --------------------------------------------------
    # Assembly path enumeration
    # --------------------------------------------------

    print("\n=== Assembly Path Enumeration (PREVIEW) ===")

    path, step = Hash.ref(), Integer.ref()
    assembly_df = (
        model.where(AssemblyStep(path, SKU, step))
        .select(
            path.alias("path"),
            step.alias("step"),
            SKU.name.alias("sku_name"),
        )
        .to_df()
    )
    maximal_ids = set(model.select(MaximalChain).to_df().iloc[:, 0])

    # Order each chain's steps for display: group on the path id, sort by step index.
    paths = []
    for path_id, grp in assembly_df.groupby("path"):
        names = grp.sort_values("step")["sku_name"].tolist()
        paths.append({"names": names, "length": len(names) - 1, "maximal": path_id in maximal_ids})

    print(f"\n  Enumerated {len(paths)} assembly path(s) (<= {MAX_ASSEMBLY_HOPS} hops).")

    # (a) All assembly paths, longest first.
    print("\n  All assembly chains (feeds-into order):")
    for path in sorted(paths, key=lambda x: -x["length"]):
        print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

    # (b) Maximal chains, as the deployed model marks them: suppressing sub-paths
    # leaves just the end-to-end assembly routes.
    maximal = [path for path in paths if path["maximal"]]

    print(f"\n  Maximal assembly chains ({len(maximal)} of {len(paths)}, sub-paths suppressed):")
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
