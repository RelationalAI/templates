"""Recovery report: reads the deployed telco network recovery model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.recovery_report

Prints per-stage diagnostics -- equipment split, advisory landscape, GNN
per-tower failure_intensity distribution and recall, three-branch
critical-restore rule firings, top subscribers by customer value (with PageRank
shown alongside), per-critical-tower customer impact, the call paths from
the highest-PageRank subscriber -- then the status and objective of the latest
refresh's solve, the selected upgrades, and the RestorePlan row.
"""

import pandas as pd
from model import (
    FAILURE_INTENSITY_THRESHOLD,
    PATH_MAX_HOPS,
    POSITIVE_PROBABILITY_CUTOFF,
    AdvisedEquipmentCount,
    AdvisedModelEquipment,
    AdvisoryCount,
    AtRiskBalance,
    CellTower,
    CriticalRegionCount,
    EquipmentSplitSize,
    FailureIntensitySpread,
    GnnRecallCounts,
    ModelAdvisory,
    NetworkEquipment,
    PositiveProbabilitySpread,
    RationaleTally,
    RestoreBranchCounts,
    RestorePlan,
    RoutingTowerCount,
    SelectedRegionCount,
    SimplePathCount,
    SolveObjective,
    SolveStatus,
    Subscriber,
    TopCallPathHop,
    TopCallPathStep,
    TowerFailureScore,
    TowerUpgradeOption,
    model,
)
from relationalai.semantics import Float, Integer, String, select

pd.set_option("display.float_format", lambda v: f"{v:,.4f}")

TOP_TOWERS = 10
TOP_SUBSCRIBERS = 10


def published_row(relationship, **field_types) -> dict:
    """The row a nullary relationship publishes, by field name; the field types name its fields in order."""
    refs = {name: kind.ref() for name, kind in field_types.items()}
    df = model.where(relationship(*refs.values())).select(*(ref.alias(name) for name, ref in refs.items())).to_df()
    return {name: df[name].iloc[0] for name in refs}


def restore_branch_counts() -> dict:
    return published_row(
        RestoreBranchCounts,
        critical=Integer,
        degraded=Integer,
        packet_loss=Integer,
        predictive=Integer,
        only_predictive=Integer,
    )


def region_counts(relationship, first_seen: pd.Series) -> pd.Series:
    """A relationship's towers per region, most first; ties keep the order in which their regions
    first appear in `first_seen`."""
    towers, region = Integer.ref(), String.ref()
    counts = (
        model.where(relationship(towers, region))
        .select(region.alias("region"), towers.alias("towers"))
        .to_df()
        .set_index("region")["towers"]
    )
    order = pd.Index(first_seen.drop_duplicates(), name="region")
    return counts.reindex(order).astype(int).sort_values(ascending=False, kind="stable")


def stage_1_predictive() -> bool:
    split = published_row(EquipmentSplitSize, train_items=Integer, validation_items=Integer, test_items=Integer)
    balance = published_row(AtRiskBalance, items=Integer, at_risk_items=Integer, at_risk_rate=Float)
    advisories = published_row(AdvisoryCount, advisories=Integer, models=Integer)
    n_items = int(balance["items"])
    advisories_df = select(
        ModelAdvisory.model.alias("MODEL"),
        ModelAdvisory.advisory_type.alias("ADVISORY_TYPE"),
        ModelAdvisory.severity.alias("SEVERITY"),
        ModelAdvisory.issued_date.alias("ISSUED_DATE"),
    ).to_df()

    print(
        f"Equipment split: train={int(split['train_items'])} val={int(split['validation_items'])} "
        f"test={int(split['test_items'])} (all)"
    )
    print(f"Label distribution: at_risk=1 {int(balance['at_risk_items'])} / "
          f"{n_items} ({float(balance['at_risk_rate']):.1%})")
    print(f"Advisories: {int(advisories['advisories'])} on {int(advisories['models'])} distinct models")

    # Descriptive: advisory landscape -- which MODELs are affected, severity,
    # and how many equipment items sit on each. This is the relational
    # neighbor signal the GNN propagates in Stage 1.
    print("\n  Advisory landscape -- equipment count per advised MODEL:")
    advised_model, advised_items = String.ref(), Integer.ref()
    eq_counts = (
        model.where(AdvisedModelEquipment(advised_model, advised_items))
        .select(advised_model.alias("MODEL"), advised_items.alias("eq_count"))
        .to_df()
    )
    adv_landscape = (
        advisories_df
        .merge(eq_counts, on="MODEL", how="left")
        .sort_values("SEVERITY", ascending=False)
        [["MODEL", "ADVISORY_TYPE", "SEVERITY", "ISSUED_DATE", "eq_count"]]
    )
    print(adv_landscape.to_string(index=False))
    n_on_advised = int(published_row(AdvisedEquipmentCount, equipment_items=Integer)["equipment_items"])
    print(f"  Equipment on an advised MODEL: {n_on_advised} / {n_items} "
          f"({n_on_advised / n_items:.1%})")

    print(f"\n{'=' * 60}")
    print("STAGE 1: PREDICTIVE -- equipment-failure binary classification GNN")
    print("=" * 60)

    pred_df = select(NetworkEquipment.id.alias("equipment_id")).where(NetworkEquipment.predictions).to_df()
    if pred_df.empty:
        print("(no predictions returned)")
        return False

    # Per-tower SUM of positive probabilities (= expected count of at-risk
    # equipment on the tower), published by the model as
    # TowerFailureScore.failure_intensity and ranked by TowerFailureScore.failure_rank.
    per_tower = (
        select(
            TowerFailureScore.tower_id.alias("TOWER_ID"),
            TowerFailureScore.failure_intensity.alias("FAILURE_INTENSITY"),
            TowerFailureScore.failure_rank.alias("failure_rank"),
        )
        .where(TowerFailureScore.failure_rank <= TOP_TOWERS)
        .to_df()
        .sort_values("failure_rank")
        .drop(columns="failure_rank")
    )
    per_tower["FAILURE_INTENSITY"] = per_tower["FAILURE_INTENSITY"].astype(float)
    print(f"\n  Top {TOP_TOWERS} towers by predicted failure intensity (sum of equipment failure probs):")
    print(per_tower.to_string(index=False))
    spread = published_row(
        FailureIntensitySpread, scored_towers=Integer, minimum=Float, maximum=Float, median=Float
    )
    print(
        f"\n  failure_intensity distribution: "
        f"min={float(spread['minimum']):.2f}, "
        f"median={float(spread['median']):.2f}, "
        f"max={float(spread['maximum']):.2f}"
    )
    print(
        f"  Towers with failure_intensity > {FAILURE_INTENSITY_THRESHOLD}: "
        f"{int(restore_branch_counts()['predictive'])} / {int(spread['scored_towers'])}"
    )

    # GNN end-to-end recall on at-risk items. Two views:
    #   - At the model's built-in argmax (predicted_label == 1).
    #   - At the standard probability threshold (pos_prob >= 0.5).
    # The argmax view answers "what the model says"; the 0.5-threshold view
    # answers "what a downstream rule would catch using the GNN's calibrated
    # probability." They can diverge if the model's calibration is shifted
    # (the argmax can be conservative even when probs are well-separated).
    total_atrisk = int(balance["at_risk_items"])
    if total_atrisk == 0:
        print("\n  GNN recall: no at-risk items in the labels, so recall is undefined.")
    else:
        recall = published_row(GnnRecallCounts, by_label=Integer, by_cutoff=Integer)
        gnn_recall_argmax = int(recall["by_label"])
        gnn_recall_p05 = int(recall["by_cutoff"])
        print(
            f"\n  GNN recall on {total_atrisk} true at-risk items:"
            f"\n    argmax (predicted_label == 1):                    "
            f"{gnn_recall_argmax:>4} ({gnn_recall_argmax / total_atrisk:>5.1%})"
            f"\n    p>={POSITIVE_PROBABILITY_CUTOFF} (probabilistic threshold):                 "
            f"{gnn_recall_p05:>4} ({gnn_recall_p05 / total_atrisk:>5.1%})"
        )
    # Per-equipment positive-prediction distribution for transparency.
    probs = published_row(
        PositiveProbabilitySpread,
        scored_items=Integer,
        minimum=Float,
        maximum=Float,
        median=Float,
        at_cutoff=Integer,
    )
    print(
        f"\n  GNN per-equipment positive-prob distribution: "
        f"min={float(probs['minimum']):.3f}, "
        f"median={float(probs['median']):.3f}, "
        f"max={float(probs['maximum']):.3f}; "
        f"items with pos_prob>={POSITIVE_PROBABILITY_CUTOFF}: {int(probs['at_cutoff'])} / {int(probs['scored_items'])}"
    )
    return True


def critical_tower_measures(**measures) -> pd.DataFrame:
    """Critical towers with each measure and the GNN failure intensity read on its
    own and joined by tower, so a tower missing one measure keeps the others."""
    df = model.where(CellTower.is_critical_restore()).select(CellTower.id.alias("tower_id")).to_df()
    reads = [
        model.where(CellTower.is_critical_restore()).select(CellTower.id.alias("tower_id"), measure.alias(name))
        for name, measure in measures.items()
    ]
    reads.append(
        model.where(CellTower.is_critical_restore(), TowerFailureScore.tower_id == CellTower.id).select(
            CellTower.id.alias("tower_id"),
            TowerFailureScore.failure_intensity.alias("failure_intensity"),
        )
    )
    for read in reads:
        df = df.merge(read.to_df(), on="tower_id", how="left")
    return df


def stage_2_rules() -> pd.DataFrame:
    print(f"\n{'=' * 60}")
    print("STAGE 2: RULES -- flag is_critical_restore towers")
    print("=" * 60)

    flagged_df = critical_tower_measures(
        region=CellTower.region,
        status=CellTower.status,
        capacity_gbps=CellTower.capacity_gbps,
        avg_loss=CellTower.avg_packet_loss,
        avg_health=CellTower.avg_health_score,
    ).sort_values("failure_intensity", ascending=False)
    for column, branch in [
        ("branch_degraded", CellTower.fires_degraded_branch),
        ("branch_packet_loss", CellTower.fires_packet_loss_branch),
        ("branch_predictive", CellTower.fires_predictive_branch),
        ("high_value", CellTower.is_high_value),
    ]:
        fired = set(model.where(branch()).select(CellTower.id).to_df().iloc[:, 0])
        flagged_df[column] = flagged_df["tower_id"].isin(fired)
    branches = restore_branch_counts()
    n_critical = int(branches["critical"])
    print(f"\n  Flagged critical_restore towers: {n_critical}")
    print("  Breakdown by region:")
    print(region_counts(CriticalRegionCount, flagged_df["region"]).to_string())

    # Per-branch contribution, from the branch counts the model publishes.
    only_predictive = int(branches["only_predictive"])
    print("\n  Per-branch contribution (a tower can fire on multiple branches):")
    print(f"    Branch 1 (WEST + DEGRADED + low health):                  {int(branches['degraded'])} towers")
    print(f"    Branch 2 (WEST + high packet loss + low health):          {int(branches['packet_loss'])} towers")
    print(f"    Branch 3 (failure_intensity > {FAILURE_INTENSITY_THRESHOLD}, any region):  "
          f"{int(branches['predictive'])} towers")
    print(f"    Towers flagged ONLY by the predictive branch:             {only_predictive} "
          f"({only_predictive / n_critical:.0%} of flagged set)")

    print("\n  Top 20 by predicted failure intensity:")
    print(flagged_df.head(20).to_string(index=False))
    return flagged_df


def stage_3_graph() -> pd.DataFrame:
    print(f"\n{'=' * 60}")
    print("STAGE 3: GRAPH -- Customer impact (revenue x churn; PageRank shown alongside)")
    print("=" * 60)

    top_subs = (
        model.select(
            Subscriber.id.alias("sub_id"),
            Subscriber.subscriber_type.alias("type"),
            Subscriber.segment.alias("segment"),
            Subscriber.lifetime_value.alias("ltv"),
            Subscriber.churn_risk_score.alias("churn"),
            Subscriber.customer_value.alias("customer_value"),
            Subscriber.influence_score.alias("pagerank"),
            Subscriber.customer_rank.alias("customer_rank"),
        )
        .where(Subscriber.customer_rank <= TOP_SUBSCRIBERS)
        .to_df()
        .sort_values("customer_rank")
        .drop(columns="customer_rank")
    )
    print(f"\n  Top {TOP_SUBSCRIBERS} subscribers by customer_value (PageRank shown for reference):")
    print(top_subs.to_string(index=False))

    blast_df = critical_tower_measures(
        region=CellTower.region,
        impact_count=CellTower.impact_count,
        weighted_impact=CellTower.weighted_impact,
        weighted_pagerank=CellTower.weighted_pagerank,
    ).sort_values("weighted_impact", ascending=False)
    print("\n  Per-critical-tower customer impact "
          "(weighted_impact = sum of caller customer_value; "
          "weighted_pagerank shown as secondary):")
    print(blast_df.to_string(index=False))
    return blast_df


def stage_4_paths() -> None:
    print(f"\n{'=' * 60}")
    print("STAGE 4: PATHS -- Call-path enumeration from the seed hub")
    print("=" * 60)

    # The model enumerates the paths: from the highest-PageRank subscriber (the seed
    # hub; the largest ID on an exact tie), call paths up to PATH_MAX_HOPS hops, simple paths only.
    hub_df = model.where(Subscriber.is_seed_hub()).select(Subscriber.id.alias("sub_id")).to_df()
    hubs = sorted(hub_df["sub_id"].tolist())
    n_paths = model.select(SimplePathCount).to_df().iloc[:, 0].tolist()
    n_towers = model.select(RoutingTowerCount).to_df().iloc[:, 0].tolist()
    print(
        f"\n  Seed scope: {len(hubs)} highest-PageRank hub(s) {hubs}; "
        f"enumeration <= {PATH_MAX_HOPS} hops, simple paths only."
    )
    print(f"  Simple call paths enumerated from the seed hub(s): {n_paths[0] if n_paths else 0}")
    print(f"  Distinct routing towers recovered across those paths: {n_towers[0] if n_towers else 0}")

    # The winning route the model publishes: its subscribers in step order and the
    # routing tower on each hop.
    step, hop = Integer.ref(), Integer.ref()
    route = (
        model.where(TopCallPathStep(Subscriber, step))
        .select(step.alias("step"), Subscriber.id.alias("sub_id"))
        .to_df()
        .sort_values("step")["sub_id"]
        .tolist()
    )
    hops_df = (
        model.where(TopCallPathHop(hop, CellTower))
        .select(hop.alias("hop"), CellTower.id.alias("tower_id"))
        .to_df()
        .sort_values("hop")
    )
    names_df = model.select(CellTower.id.alias("tower_id"), CellTower.name.alias("tower")).to_df()
    # A tower without a name is shown by its ID.
    hops_df = hops_df.merge(names_df, on="tower_id", how="left")
    towers = hops_df["tower"].fillna(hops_df["tower_id"]).tolist()
    top_load = model.select(Subscriber.top_call_path_influence).to_df().iloc[:, 0].tolist()
    if route and top_load:
        tower_str = " via towers [" + ", ".join(towers) + "]" if towers else ""
        print(
            f"  Top influence-weighted call path (PageRank sum {round(float(top_load[0]), 6)}): "
            + " -> ".join(route)
            + tower_str
        )


def stage_5_prescriptive(flagged_df: pd.DataFrame, blast_df: pd.DataFrame) -> None:
    print(f"\n{'=' * 60}")
    print("STAGE 5: PRESCRIPTIVE -- tower upgrade selection MIP")
    print("=" * 60)

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if objective:
        print(f"• objective: {round(objective[0], 9)}\n")

    # Extract selected upgrades. Each carries the rationale the model publishes: the upstream
    # signals that flagged its tower, OR-combined:
    #   - operational       : Stage 2 branch 1 (degraded) or 2 (packet loss)
    #   - advisory/predicted: Stage 2 branch 3 (GNN failure intensity)
    #   - high-value        : weighted_impact in the top quartile of critical towers
    selected_df = (
        model.where(TowerUpgradeOption.is_selected_upgrade())
        .select(
            TowerUpgradeOption.tower_id.alias("tower_id"),
            TowerUpgradeOption.tier.alias("tier"),
            TowerUpgradeOption.capacity_increase_gbps.alias("capacity_gbps"),
            TowerUpgradeOption.cost.alias("cost"),
            TowerUpgradeOption.install_weeks.alias("install_weeks"),
            TowerUpgradeOption.rationale.alias("rationale"),
        )
        .to_df()
    )
    selected_df["cost"] = selected_df["cost"].astype(float)

    selected_df = selected_df.merge(
        flagged_df[["tower_id", "region", "failure_intensity"]],
        on="tower_id",
        how="left",
    ).sort_values(["region", "tier"])

    selected_df = selected_df.merge(
        blast_df[["tower_id", "weighted_impact", "weighted_pagerank"]],
        on="tower_id",
        how="left",
    )

    # The plan headline, published by the model as ontology.
    plan_df = (
        model.select(
            RestorePlan.id.alias("plan_id"),
            RestorePlan.total_cost.alias("total_cost"),
            RestorePlan.total_install_weeks.alias("install_weeks"),
            RestorePlan.capacity_restored_gbps.alias("capacity_gbps"),
            RestorePlan.gold_count.alias("gold"),
            RestorePlan.silver_count.alias("silver"),
            RestorePlan.bronze_count.alias("bronze"),
            RestorePlan.towers_covered.alias("towers"),
            RestorePlan.binding_constraint.alias("binding"),
        )
        .to_df()
    )
    n_selected = int(plan_df["towers"].iloc[0]) if len(plan_df) > 0 else 0

    print(f"\n  Selected upgrades: {n_selected}")
    print(
        selected_df[
            ["tower_id", "region", "tier", "capacity_gbps", "cost",
             "install_weeks", "failure_intensity", "weighted_impact",
             "rationale"]
        ].to_string(index=False)
    )
    tally = published_row(RationaleTally, operational=Integer, predictive=Integer, high_value=Integer)
    print(
        f"\n  Rationale tally: "
        f"operational={int(tally['operational'])}, "
        f"advisory/predicted={int(tally['predictive'])}, "
        f"high-value={int(tally['high_value'])} "
        f"(towers can fire on multiple signals)"
    )

    if len(plan_df) > 0:
        plan = plan_df.iloc[0]
        print(f"\n  Total cost:               ${float(plan['total_cost']):,.0f}")
        print(f"  Total install crew-weeks: {int(plan['install_weeks'])}")
        print(f"  Capacity restored:        {int(plan['capacity_gbps'])} Gbps")
        print(f"  Tier mix:                 {{'GOLD': {plan['gold']}, 'SILVER': {plan['silver']}, 'BRONZE': {plan['bronze']}}}")
        print(f"  Towers covered:           {plan['towers']} of {int(restore_branch_counts()['critical'])} critical")
        by_region = region_counts(SelectedRegionCount, selected_df["region"])
        region_mix = {region: int(n) for region, n in by_region.items()}
        print(f"  Region breakdown:         {region_mix}")

    print("\n  Plan (queryable as ontology):")
    print(plan_df.to_string(index=False))

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE: 5 stages read from the deployed Telco ontology")
    print(f"Plan headline + {n_selected}-row SelectedUpgrade view are queryable")
    print("as ontology -- RestorePlan and TowerUpgradeOption.is_selected_upgrade.")
    print("=" * 60)


def main() -> None:
    if not stage_1_predictive():
        return
    flagged_df = stage_2_rules()
    blast_df = stage_3_graph()
    stage_4_paths()
    stage_5_prescriptive(flagged_df, blast_df)


if __name__ == "__main__":
    main()
