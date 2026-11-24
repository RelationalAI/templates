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
    CellTower,
    ModelAdvisory,
    NetworkEquipment,
    RestorePlan,
    RoutingTowerCount,
    SimplePathCount,
    SolveObjective,
    SolveStatus,
    Subscriber,
    TestEqTable,
    TopCallPathHop,
    TopCallPathStep,
    TowerFailureScore,
    TowerUpgradeOption,
    TrainEqTable,
    ValEqTable,
    model,
)
from relationalai.semantics import Integer, count, select

pd.set_option("display.float_format", lambda v: f"{v:,.4f}")



def stage_1_predictive() -> bool:
    counts = (
        select(
            count(TrainEqTable).alias("train"),
            count(ValEqTable).alias("val"),
            count(TestEqTable).alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    equipment_df = select(
        NetworkEquipment.id.alias("equipment_id"),
        NetworkEquipment.eqp_model.alias("MODEL"),
        NetworkEquipment.tower_id_fk.alias("TOWER_ID"),
        NetworkEquipment.at_risk.alias("AT_RISK"),
    ).to_df()
    advisories_df = select(
        ModelAdvisory.model.alias("MODEL"),
        ModelAdvisory.advisory_type.alias("ADVISORY_TYPE"),
        ModelAdvisory.severity.alias("SEVERITY"),
        ModelAdvisory.issued_date.alias("ISSUED_DATE"),
    ).to_df()

    print(f"Equipment split: train={counts['train']} val={counts['val']} test={counts['test']} (all)")
    print(f"Label distribution: at_risk=1 {equipment_df['AT_RISK'].sum()} / "
          f"{len(equipment_df)} ({equipment_df['AT_RISK'].mean():.1%})")
    print(f"Advisories: {len(advisories_df)} on {advisories_df['MODEL'].nunique()} distinct models")

    # Descriptive: advisory landscape -- which MODELs are affected, severity,
    # and how many equipment items sit on each. This is the relational
    # neighbor signal the GNN propagates in Stage 1.
    print("\n  Advisory landscape -- equipment count per advised MODEL:")
    adv_landscape = (
        advisories_df
        .merge(equipment_df.groupby("MODEL").size().rename("eq_count").reset_index(), on="MODEL", how="left")
        .sort_values("SEVERITY", ascending=False)
        [["MODEL", "ADVISORY_TYPE", "SEVERITY", "ISSUED_DATE", "eq_count"]]
    )
    print(adv_landscape.to_string(index=False))
    n_on_advised = int(equipment_df["MODEL"].isin(set(advisories_df["MODEL"])).sum())
    print(f"  Equipment on an advised MODEL: {n_on_advised} / {len(equipment_df)} "
          f"({n_on_advised / len(equipment_df):.1%})")

    print(f"\n{'=' * 60}")
    print("STAGE 1: PREDICTIVE -- equipment-failure binary classification GNN")
    print("=" * 60)

    pred_df = (
        select(
            NetworkEquipment.id.alias("equipment_id"),
            NetworkEquipment.predictions.probs.alias("pos_prob"),
            NetworkEquipment.predictions.predicted_labels.alias("predicted_label"),
        )
        .where(NetworkEquipment.predictions)
        .to_df()
    )
    if pred_df.empty:
        print("(no predictions returned)")
        return False
    pred_df["pos_prob"] = pred_df["pos_prob"].astype(float)

    # Per-tower SUM of positive probabilities (= expected count of at-risk
    # equipment on the tower), published by the model as
    # TowerFailureScore.failure_intensity.
    per_tower = (
        select(
            TowerFailureScore.tower_id.alias("TOWER_ID"),
            TowerFailureScore.failure_intensity.alias("FAILURE_INTENSITY"),
        )
        .to_df()
        .sort_values("FAILURE_INTENSITY", ascending=False)
    )
    per_tower["FAILURE_INTENSITY"] = per_tower["FAILURE_INTENSITY"].astype(float)
    print("\n  Top 10 towers by predicted failure intensity (sum of equipment failure probs):")
    print(per_tower.head(10).to_string(index=False))
    print(
        f"\n  failure_intensity distribution: "
        f"min={per_tower['FAILURE_INTENSITY'].min():.2f}, "
        f"median={per_tower['FAILURE_INTENSITY'].median():.2f}, "
        f"max={per_tower['FAILURE_INTENSITY'].max():.2f}"
    )
    print(
        f"  Towers with failure_intensity > {FAILURE_INTENSITY_THRESHOLD}: "
        f"{int((per_tower['FAILURE_INTENSITY'] > FAILURE_INTENSITY_THRESHOLD).sum())} / {len(per_tower)}"
    )

    # GNN end-to-end recall on at-risk items. Two views:
    #   - At the model's built-in argmax (predicted_label == 1).
    #   - At the standard probability threshold (pos_prob >= 0.5).
    # The argmax view answers "what the model says"; the 0.5-threshold view
    # answers "what a downstream rule would catch using the GNN's calibrated
    # probability." They can diverge if the model's calibration is shifted
    # (the argmax can be conservative even when probs are well-separated).
    total_atrisk = int(equipment_df["AT_RISK"].sum())
    if total_atrisk == 0:
        print("\n  GNN recall: no at-risk items in the labels, so recall is undefined.")
    else:
        gnn_flagged_atrisk = pred_df.merge(equipment_df[["equipment_id", "AT_RISK"]], on="equipment_id", how="left")
        gnn_recall_argmax = int(
            gnn_flagged_atrisk[
                (gnn_flagged_atrisk["AT_RISK"] == 1)
                & (gnn_flagged_atrisk["predicted_label"] == 1)
            ].shape[0]
        )
        gnn_recall_p05 = int(
            gnn_flagged_atrisk[
                (gnn_flagged_atrisk["AT_RISK"] == 1)
                & (gnn_flagged_atrisk["pos_prob"] >= 0.5)
            ].shape[0]
        )
        print(
            f"\n  GNN recall on {total_atrisk} true at-risk items:"
            f"\n    argmax (predicted_label == 1):                    "
            f"{gnn_recall_argmax:>4} ({gnn_recall_argmax / total_atrisk:>5.1%})"
            f"\n    p>=0.5 (probabilistic threshold):                 "
            f"{gnn_recall_p05:>4} ({gnn_recall_p05 / total_atrisk:>5.1%})"
        )
    # Per-equipment positive-prediction distribution for transparency.
    print(
        f"\n  GNN per-equipment positive-prob distribution: "
        f"min={pred_df['pos_prob'].min():.3f}, "
        f"median={pred_df['pos_prob'].median():.3f}, "
        f"max={pred_df['pos_prob'].max():.3f}; "
        f"items with pos_prob>=0.5: {int((pred_df['pos_prob'] >= 0.5).sum())} / {len(pred_df)}"
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
    print(f"\n  Flagged critical_restore towers: {len(flagged_df)}")
    print("  Breakdown by region:")
    print(flagged_df["region"].value_counts().to_string())

    # Per-branch contribution, from the branch flags the model publishes.
    _b1 = flagged_df["branch_degraded"]
    _b2 = flagged_df["branch_packet_loss"]
    _b3 = flagged_df["branch_predictive"]
    print("\n  Per-branch contribution (a tower can fire on multiple branches):")
    print(f"    Branch 1 (WEST + DEGRADED + low health):                  {int(_b1.sum())} towers")
    print(f"    Branch 2 (WEST + high packet loss + low health):          {int(_b2.sum())} towers")
    print(f"    Branch 3 (failure_intensity > {FAILURE_INTENSITY_THRESHOLD}, any region):  "
          f"{int(_b3.sum())} towers")
    _only_predictive = (_b3 & ~_b1 & ~_b2).sum()
    print(f"    Towers flagged ONLY by the predictive branch:             {int(_only_predictive)} "
          f"({_only_predictive / len(flagged_df):.0%} of flagged set)")

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
        )
        .to_df()
        .sort_values("customer_value", ascending=False)
        .head(10)
    )
    print("\n  Top 10 subscribers by customer_value (PageRank shown for reference):")
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
    # hub; the smallest ID on an exact tie), call paths up to PATH_MAX_HOPS hops, simple paths only.
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

    # Extract selected upgrades.
    selected_df = (
        model.where(TowerUpgradeOption.is_selected_upgrade())
        .select(
            TowerUpgradeOption.tower_id.alias("tower_id"),
            TowerUpgradeOption.tier.alias("tier"),
            TowerUpgradeOption.capacity_increase_gbps.alias("capacity_gbps"),
            TowerUpgradeOption.cost.alias("cost"),
            TowerUpgradeOption.install_weeks.alias("install_weeks"),
        )
        .to_df()
    )
    selected_df["cost"] = selected_df["cost"].astype(float)

    selected_df = selected_df.merge(
        flagged_df[["tower_id", "region", "status", "failure_intensity",
                    "branch_degraded", "branch_packet_loss", "branch_predictive", "high_value"]],
        on="tower_id",
        how="left",
    ).sort_values(["region", "tier"])

    # Per-tower selection rationale: the upstream signals that flagged the
    # tower, OR-combined, from the flags the model publishes:
    #   - operational       : Stage 2 branch 1 (degraded) or 2 (packet loss)
    #   - advisory/predicted: Stage 2 branch 3 (GNN failure intensity)
    #   - high-value        : weighted_impact in the top quartile of critical towers
    selected_df = selected_df.merge(
        blast_df[["tower_id", "weighted_impact", "weighted_pagerank"]],
        on="tower_id",
        how="left",
    )
    selected_df["sig_operational"] = selected_df["branch_degraded"] | selected_df["branch_packet_loss"]
    selected_df["sig_predictive"] = selected_df["branch_predictive"]
    selected_df["sig_high_value"] = selected_df["high_value"]

    def _rationale(row):
        sigs = []
        if row["sig_operational"]:
            sigs.append("operational")
        if row["sig_predictive"]:
            sigs.append("advisory/predicted")
        if row["sig_high_value"]:
            sigs.append("high-value")
        return ", ".join(sigs) if sigs else "(low signal)"

    selected_df["rationale"] = selected_df.apply(_rationale, axis=1)

    print(f"\n  Selected upgrades: {len(selected_df)}")
    print(
        selected_df[
            ["tower_id", "region", "tier", "capacity_gbps", "cost",
             "install_weeks", "failure_intensity", "weighted_impact",
             "rationale"]
        ].to_string(index=False)
    )
    print(
        f"\n  Rationale tally: "
        f"operational={int(selected_df['sig_operational'].sum())}, "
        f"advisory/predicted={int(selected_df['sig_predictive'].sum())}, "
        f"high-value={int(selected_df['sig_high_value'].sum())} "
        f"(towers can fire on multiple signals)"
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
    if len(plan_df) > 0:
        plan = plan_df.iloc[0]
        print(f"\n  Total cost:               ${float(plan['total_cost']):,.0f}")
        print(f"  Total install crew-weeks: {int(plan['install_weeks'])}")
        print(f"  Capacity restored:        {int(plan['capacity_gbps'])} Gbps")
        print(f"  Tier mix:                 {{'GOLD': {plan['gold']}, 'SILVER': {plan['silver']}, 'BRONZE': {plan['bronze']}}}")
        print(f"  Towers covered:           {plan['towers']} of {len(flagged_df)} critical")
        print(f"  Region breakdown:         {selected_df['region'].value_counts().to_dict()}")

    print("\n  Plan (queryable as ontology):")
    print(plan_df.to_string(index=False))

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE: 5 stages read from the deployed Telco ontology")
    print(f"Plan headline + {len(selected_df)}-row SelectedUpgrade view are queryable")
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
