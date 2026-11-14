"""Dependency, bottleneck, and assembly-chain report from the deployed BOM model.

Run after `rai models deploy --path model`:
    python -m queries.dependency_report
"""

from model import (
    MAX_ASSEMBLY_HOPS,
    SKU,
    betweenness,
    graph,
    model,
    num_edges,
    num_nodes,
    p,
    reachable,
)
from relationalai.semantics import Float, where


def _is_contiguous_subsequence(short, long):
    """True if `short` appears as a contiguous run inside `long`."""
    if len(short) >= len(long):
        return False
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


if __name__ == "__main__":
    print("=== BOM Dependency Graph ===")
    num_nodes.inspect()
    num_edges.inspect()

    src, dst = graph.Node.ref("src"), graph.Node.ref("dst")
    all_deps_df = (
        where(reachable(src, dst))
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

    non_self = all_deps_df[all_deps_df["product_id"] != all_deps_df["dep_id"]]
    if len(non_self) > 0:
        dep_counts = (
            non_self.groupby(["dep_id", "dep_name", "dep_type"])
            .size()
            .reset_index(name="depended_on_by")
            .sort_values("depended_on_by", ascending=False)
        )
        print("\n=== Most Depended-On SKUs ===")
        print(dep_counts.to_string(index=False))

    # --------------------------------------------------
    # Betweenness centrality: structural bottlenecks
    # --------------------------------------------------

    node = graph.Node.ref("n")
    score = Float.ref("s")
    btw_df = (
        where(betweenness(node, score))
        .select(
            node.id.alias("sku_id"),
            node.name.alias("sku_name"),
            node.type.alias("type"),
            node.category.alias("category"),
            score.alias("betweenness"),
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

    assembly_df = (
        model.where(p)
        .select(
            p.alias("path"),
            p.nodes["index"].alias("step"),
            SKU(p.nodes).id.alias("sku_id"),
            SKU(p.nodes).name.alias("sku_name"),
        )
        .to_df()
    )

    # Reassemble each path in pandas: group on the path id, order by step index.
    assembly_df["step"] = assembly_df["step"].astype(int)
    paths = []
    for path_id, grp in assembly_df.groupby("path"):
        ordered = grp.sort_values("step")
        ids = ordered["sku_id"].tolist()
        names = ordered["sku_name"].tolist()
        paths.append({"ids": ids, "names": names, "length": len(ids) - 1})

    print(f"\n  Enumerated {len(paths)} assembly path(s) (<= {MAX_ASSEMBLY_HOPS} hops).")

    # (a) All assembly paths, longest first.
    print("\n  All assembly chains (feeds-into order):")
    for path in sorted(paths, key=lambda x: -x["length"]):
        print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

    # (b) Maximal paths: keep only the longest, non-extendable chains -- a chain
    # that is NOT a contiguous sub-sequence (prefix or suffix) of any longer chain.
    # Suppressing these sub-paths leaves just the end-to-end assembly routes.
    maximal = [
        path
        for path in paths
        if not any(other is not path and _is_contiguous_subsequence(path["ids"], other["ids"]) for other in paths)
    ]

    print(f"\n  Maximal assembly chains ({len(maximal)} of {len(paths)}, sub-paths suppressed):")
    for path in sorted(maximal, key=lambda x: -x["length"]):
        print(f"    [{path['length']} hop] " + " -> ".join(path["names"]))

    print("\n  Assembly depth persisted onto SKU (longest chain terminating at each):")
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
