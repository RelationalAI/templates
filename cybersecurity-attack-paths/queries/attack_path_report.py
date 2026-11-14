"""Attack-path report from the deployed model.

Run after `rai models deploy --path model`:
    python -m queries.attack_path_report

Prints the kill-chain attack paths into crown jewels (with the technique at each
hop), every route between a chosen entry point and a chosen crown jewel, the
kill-chains ranked by total asset exposure, and the assets flagged on a
crown-jewel attack path.
"""

from model import (
    ENTRY_ASSET,
    MAX_PIVOTS,
    MAX_ROUTE_HOPS,
    TARGET_ASSET,
    Asset,
    a,
    dst,
    dst_pt,
    kill,
    model,
    route,
    src_pt,
)
from relationalai.semantics import Integer, not_, where
from relationalai.semantics.std import aggregates as aggs

if __name__ == "__main__":
    print("=== Cybersecurity Attack Paths: kill-chain into crown jewels ===")
    kill_df = (
        model.where(
            kill,
            a.internet_facing == "yes",
            dst.crown_jewel == "yes",
        )
        .select(
            kill.alias("path_id"),
            kill.nodes["index"].alias("step"),
            Asset(kill.nodes).id.alias("asset_id"),
            Asset(kill.nodes).name.alias("asset_name"),
        )
        .to_df()
    )
    # Technique at each hop (the relationship label), as a separate projection.
    hop_df = (
        model.where(
            kill,
            a.internet_facing == "yes",
            dst.crown_jewel == "yes",
        )
        .select(
            kill.alias("path_id"),
            kill.relationships["index"].alias("hop"),
            kill.relationships["relationship"].alias("technique"),
        )
        .to_df()
    )

    kill_df["step"] = kill_df["step"].astype(int)
    kill_df = kill_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
    hop_df["hop"] = hop_df["hop"].astype(int)
    hop_df = hop_df.drop_duplicates(["path_id", "hop"]).sort_values(["path_id", "hop"])

    # Reassemble each kill-chain: ordered asset names + the technique used at each hop.
    # The technique is the relationship label as-is -- the dotted relationship name,
    # e.g. "Asset.exploit_to".
    chains = []
    for pid, g in kill_df.groupby("path_id"):
        assets = list(g.sort_values("step")["asset_name"])
        techs = list(hop_df[hop_df["path_id"] == pid].sort_values("hop")["technique"])
        labelled = assets[0]
        for nm, tech in zip(assets[1:], techs):
            labelled += f"  --[{tech}]-->  {nm}"
        chains.append({"path_id": pid, "hops": len(assets) - 1, "asset_ids": tuple(
            g.sort_values("step")["asset_id"]), "labelled": labelled})

    print(f"\n{len(chains)} kill-chain attack path(s) reach a crown jewel "
          f"(exploit -> cred -> 1-{MAX_PIVOTS} pivots, from an internet-facing asset):")
    for ch in sorted(chains, key=lambda c: c["hops"]):
        print(f"  [{ch['hops']} hops] {ch['labelled']}")

    # --------------------------------------------------
    # Point query: every route between one entry and one crown jewel
    # --------------------------------------------------
    # Pin both endpoints by id and enumerate all simple routes between them over the
    # technique-agnostic can_reach edge (any technique, 1..MAX_ROUTE_HOPS). This is the
    # >=1.15-era native point query (still current) -- src/dst unified to specific assets inside .all().paths().

    i, j = Integer.ref(), Integer.ref()
    # Keep only SIMPLE routes (no asset revisited). .all().paths() has WALK semantics and
    # no native simple-path mode, so drop node-repeating walks with a negated existential
    # over positions -- expressed natively in the route's where() (no pandas).
    route_df = (
        model.where(
            route,
            src_pt.id == ENTRY_ASSET,
            dst_pt.id == TARGET_ASSET,
            not_(where(i < j, route.nodes(i) == route.nodes(j))),
        )
        .select(
            route.alias("path_id"),
            route.nodes["index"].alias("step"),
            Asset(route.nodes).id.alias("asset_id"),
        )
        .to_df()
    )
    route_df["step"] = route_df["step"].astype(int)
    route_df = route_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
    routes = sorted(
        {tuple(g.sort_values("step")["asset_id"]) for _, g in route_df.groupby("path_id")},
        key=len,
    )

    print(f"\n=== Point query: all routes from {ENTRY_ASSET} to {TARGET_ASSET} "
          f"(any technique, <= {MAX_ROUTE_HOPS} hops, simple) ===")
    print(f"  {len(routes)} route(s):")
    for seq in routes:
        print("    " + " -> ".join(seq))

    # --------------------------------------------------
    # Rank kill-chains by total asset exposure
    # --------------------------------------------------
    # The riskiest chain is the one whose assets carry the most exposure overall -- the
    # first remediation target. Exposure is a per-asset score (a stand-in for a CVSS /
    # attack-surface metric) summed ALONG each kill-chain IN PYREL:
    # aggregates.sum(Asset(kill.nodes).exposure_score).per(kill) sums the per-node value
    # over each path's node sequence -- the core paths-only aggregation, reusing the same
    # kill pattern and its internet-facing/crown-jewel endpoint filters. This is a
    # position-sum (every node position, with repetition); it equals the distinct-asset
    # sum because each kill-chain here is a simple path (no asset revisited).
    totals = (
        model.where(
            kill,
            a.internet_facing == "yes",
            dst.crown_jewel == "yes",
            total := aggs.sum(Asset(kill.nodes).exposure_score).per(kill),
        )
        .select(kill.alias("path_id"), total.alias("total_exposure"))
        .to_df()
    )
    # Join total_exposure onto the assembled chains by path id (label string-join is pandas).
    exposure_by_path = dict(
        totals[["path_id", "total_exposure"]].itertuples(index=False, name=None)
    )
    for ch in chains:
        ch["total_exposure"] = int(exposure_by_path[ch["path_id"]])

    print("\n=== Kill-chains ranked by total asset exposure (highest = remediate first) ===")
    for ch in sorted(chains, key=lambda c: c["total_exposure"], reverse=True):
        print(f"  exposure {ch['total_exposure']:>3}  ({ch['hops']} hops)  {ch['labelled']}")

    # --------------------------------------------------
    # Assets on a crown-jewel attack path
    # --------------------------------------------------

    total_assets = len(model.select(Asset.id.alias("id")).to_df())
    x = Asset.ref()
    flagged = (
        model.where(
            x.on_attack_path == "yes",
        )
        .select(x.id.alias("id"), x.name.alias("name"), x.zone.alias("zone"))
        .to_df()
    )

    print("\n=== Assets on a crown-jewel attack path (Asset.on_attack_path persisted) ===")
    print(f"  {len(flagged)} of {total_assets} assets:")
    for _, r in flagged.sort_values("id").iterrows():
        print(f"    {r['id']:<8} {r['name']:<24} ({r['zone']})")
