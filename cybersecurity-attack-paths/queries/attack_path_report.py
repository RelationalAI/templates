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
    AssetCoverage,
    KillChainCount,
    KillChainExposure,
    KillChainHop,
    KillChainHops,
    KillChainPriority,
    KillChainStep,
    RouteCount,
    RouteStep,
    model,
)
from relationalai.semantics import Hash, Integer, String

if __name__ == "__main__":
    print("=== Cybersecurity Attack Paths: kill-chain into crown jewels ===")
    # The crown-jewel kill-chains the model publishes: the asset at each step, and the
    # technique at each hop (the relationship label), as a separate projection.
    path, step, hop, technique = Hash.ref(), Integer.ref(), Integer.ref(), String.ref()
    kill_df = (
        model.where(KillChainStep(path, Asset, step))
        .select(
            path.alias("path_id"),
            step.alias("step"),
            Asset.name.alias("asset_name"),
        )
        .to_df()
    )
    hop_df = (
        model.where(KillChainHop(path, technique, hop))
        .select(path.alias("path_id"), hop.alias("hop"), technique.alias("technique"))
        .to_df()
    )

    kill_df = kill_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
    hop_df = hop_df.drop_duplicates(["path_id", "hop"]).sort_values(["path_id", "hop"])
    # Each kill-chain's length in hops, and how many kill-chains there are, from the model.
    hops_ref = Integer.ref()
    hops_df = (
        model.where(KillChainHops(path, hops_ref))
        .select(path.alias("path_id"), hops_ref.alias("hops"))
        .to_df()
    )
    hops_by_path = dict(hops_df.itertuples(index=False, name=None))
    n_chains = int(model.select(KillChainCount).to_df().iloc[0, 0])

    # Reassemble each kill-chain: ordered asset names + the technique used at each hop.
    # The technique is the relationship label as-is -- the dotted relationship name,
    # e.g. "Asset.exploit_to".
    chains = []
    for pid, g in kill_df.groupby("path_id"):
        assets = list(g["asset_name"])
        techs = list(hop_df[hop_df["path_id"] == pid]["technique"])
        labelled = assets[0]
        for nm, tech in zip(assets[1:], techs):
            labelled += f"  --[{tech}]-->  {nm}"
        chains.append({"path_id": pid, "hops": int(hops_by_path[pid]), "labelled": labelled})

    print(f"\n{n_chains} kill-chain attack path(s) reach a crown jewel "
          f"(exploit -> cred -> 1-{MAX_PIVOTS} pivots, from an internet-facing asset):")
    for ch in sorted(chains, key=lambda c: c["hops"]):
        print(f"  [{ch['hops']} hops] {ch['labelled']}")

    # --------------------------------------------------
    # Point query: every route between one entry and one crown jewel
    # --------------------------------------------------
    # The model pins both endpoints by id and enumerates all simple routes between them
    # over the technique-agnostic can_reach edge (any technique, 1..MAX_ROUTE_HOPS); see
    # model/entry_to_target_routes.py.
    route_df = (
        model.where(RouteStep(path, Asset, step))
        .select(path.alias("path_id"), step.alias("step"), Asset.id.alias("asset_id"))
        .to_df()
    )
    route_df = route_df.drop_duplicates(["path_id", "step"]).sort_values(["path_id", "step"])
    routes = sorted(
        (tuple(g["asset_id"]) for _, g in route_df.groupby("path_id")),
        key=lambda seq: (len(seq), seq),
    )
    n_routes = int(model.select(RouteCount).to_df().iloc[0, 0])

    print(f"\n=== Point query: all routes from {ENTRY_ASSET} to {TARGET_ASSET} "
          f"(any technique, <= {MAX_ROUTE_HOPS} hops, simple) ===")
    print(f"  {n_routes} route(s):")
    for seq in routes:
        print("    " + " -> ".join(seq))

    # --------------------------------------------------
    # Rank kill-chains by total asset exposure
    # --------------------------------------------------
    # The riskiest chain is the one whose assets carry the most exposure overall -- the
    # first remediation target. The model sums each kill-chain's per-asset exposure along
    # its node sequence and ranks the chains by it (see model/kill_chains.py).
    total, priority = Integer.ref(), Integer.ref()
    ranking = (
        model.where(KillChainExposure(path, total), KillChainPriority(path, priority))
        .select(path.alias("path_id"), total.alias("total_exposure"), priority.alias("priority"))
        .to_df()
    )
    # Join total_exposure and priority onto the assembled chains by path id.
    exposure_by_path = dict(
        ranking[["path_id", "total_exposure"]].itertuples(index=False, name=None)
    )
    priority_by_path = dict(ranking[["path_id", "priority"]].itertuples(index=False, name=None))
    for ch in chains:
        ch["total_exposure"] = int(exposure_by_path[ch["path_id"]])
        ch["priority"] = int(priority_by_path[ch["path_id"]])

    print("\n=== Kill-chains ranked by total asset exposure (highest = remediate first) ===")
    for ch in sorted(chains, key=lambda c: c["priority"]):
        print(f"  exposure {ch['total_exposure']:>3}  ({ch['hops']} hops)  {ch['labelled']}")

    # --------------------------------------------------
    # Assets on a crown-jewel attack path
    # --------------------------------------------------

    n_assets, n_flagged = Integer.ref(), Integer.ref()
    coverage = (
        model.where(AssetCoverage(n_assets, n_flagged))
        .select(n_assets.alias("n_assets"), n_flagged.alias("n_flagged"))
        .to_df()
        .iloc[0]
    )
    x = Asset.ref()
    flagged = (
        model.where(
            x.on_attack_path == "yes",
        )
        .select(x.id.alias("id"), x.name.alias("name"), x.zone.alias("zone"))
        .to_df()
    )

    print("\n=== Assets on a crown-jewel attack path (Asset.on_attack_path persisted) ===")
    print(f"  {int(coverage['n_flagged'])} of {int(coverage['n_assets'])} assets:")
    for _, r in flagged.sort_values("id").iterrows():
        print(f"    {r['id']:<8} {r['name']:<24} ({r['zone']})")
