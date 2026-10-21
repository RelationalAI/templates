"""Curated query catalog for the telco network recovery Cortex agent."""

from __future__ import annotations

import functools

import pandas as pd
from relationalai.agent.cortex import QueryCatalog, ToolRegistry
from relationalai.semantics import Model, distinct
from relationalai.semantics.std import aggregates as aggs

RESULTS_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS"
DEPLOYED_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY"


def _table(model: Model, name: str):
    return model.Table(f"{RESULTS_SCHEMA}.{name}")


def operational_critical_restore_towers(model: Model):
    """List towers flagged by the deployed operational rules: WEST, average equipment health below 0.85, and either DEGRADED status or packet loss above 5%."""
    flagged = model.Table(f"{DEPLOYED_SCHEMA}.CELLTOWER_OPERATIONAL_CRITICAL_RESTORE")
    tower = model.Table(f"{DEPLOYED_SCHEMA}.CELLTOWER")
    df = model.where(flagged.CELLTOWER == tower.ID).select(
        tower.ID.alias("tower_id"),
        tower.NAME.alias("tower_name"),
        tower.REGION.alias("region"),
        tower.STATUS.alias("status"),
        tower.AVG_PACKET_LOSS.alias("avg_packet_loss_pct"),
        tower.AVG_HEALTH_SCORE.alias("avg_equipment_health_score"),
    ).to_df()
    if not df.empty:
        df = df.sort_values(["avg_packet_loss_pct", "tower_id"], ascending=[False, True])
    return df


def plan_summary(model: Model):
    """Return the optimized restore-plan headline: solver status, cost, capacity restored, tier mix, towers covered, and binding constraint."""
    plan = _table(model, "RESTORE_PLAN")
    return model.select(
        plan.PLAN_ID.alias("plan_id"),
        plan.TERMINATION_STATUS.alias("status"),
        plan.TOTAL_COST.alias("total_cost_usd"),
        plan.TOTAL_INSTALL_WEEKS.alias("install_weeks"),
        plan.CAPACITY_RESTORED_GBPS.alias("capacity_restored_gbps"),
        plan.GOLD_COUNT.alias("gold_count"),
        plan.SILVER_COUNT.alias("silver_count"),
        plan.BRONZE_COUNT.alias("bronze_count"),
        plan.TOWERS_COVERED.alias("towers_covered"),
        plan.BINDING_CONSTRAINT.alias("binding_constraint"),
    ).to_df()


def selected_upgrades(model: Model):
    """List every selected tower upgrade with tier, region, cost, install weeks, restored capacity, failure intensity, and customer impact."""
    selected = _table(model, "SELECTED_UPGRADES")
    df = model.select(
        selected.TOWER_ID.alias("tower_id"),
        selected.TIER.alias("tier"),
        selected.REGION.alias("region"),
        selected.CAPACITY_GBPS.alias("capacity_gbps"),
        selected.COST.alias("cost_usd"),
        selected.INSTALL_WEEKS.alias("install_weeks"),
        selected.FAILURE_INTENSITY.alias("failure_intensity"),
        selected.WEIGHTED_IMPACT.alias("weighted_impact"),
    ).to_df()
    if not df.empty:
        df = df.sort_values(["weighted_impact", "failure_intensity"], ascending=False)
    return df


def upgrade_plan_with_rationale(model: Model):
    """Answer which towers to upgrade within $5M and why: each selected tier's cost, capacity, failure risk, customer impact, and weighted objective score, plus plan totals."""
    plan = plan_summary(model)
    if len(plan) != 1:
        raise RuntimeError("Expected one restore plan; run the optimization job first.")

    selected = _table(model, "SELECTED_UPGRADES")
    upgrades = model.select(
        selected.TOWER_ID.alias("tower_id"),
        selected.TIER.alias("tier"),
        selected.REGION.alias("region"),
        selected.CAPACITY_GBPS.alias("capacity_gbps"),
        selected.COST.alias("cost_usd"),
        selected.INSTALL_WEEKS.alias("install_weeks"),
        selected.FAILURE_INTENSITY.alias("failure_intensity"),
        selected.WEIGHTED_IMPACT.alias("weighted_impact"),
        (
            selected.CAPACITY_GBPS
            * selected.FAILURE_INTENSITY
            * selected.WEIGHTED_IMPACT
        ).alias("objective_contribution"),
    ).to_df()
    if upgrades.empty:
        raise RuntimeError("The restore plan has no selected upgrades to explain.")

    # RESTORE_PLAN is a singleton; SELECTED_UPGRADES has no plan foreign key.
    summary = plan.iloc[0]
    if (
        len(upgrades) != int(summary["towers_covered"])
        or int(upgrades["cost_usd"].astype("int64").sum()) != int(summary["total_cost_usd"])
        or int(upgrades["install_weeks"].astype("int64").sum()) != int(summary["install_weeks"])
        or int(upgrades["capacity_gbps"].astype("int64").sum())
        != int(summary["capacity_restored_gbps"])
    ):
        raise RuntimeError("Restore plan and selected upgrades disagree; rerun optimization.")

    upgrades["plan_status"] = summary["status"]
    upgrades["plan_total_cost_usd"] = summary["total_cost_usd"]
    upgrades["plan_install_weeks"] = summary["install_weeks"]
    upgrades["plan_capacity_restored_gbps"] = summary["capacity_restored_gbps"]
    upgrades["plan_towers_covered"] = summary["towers_covered"]
    upgrades["binding_constraint"] = summary["binding_constraint"]
    upgrades["failure_intensity"] = upgrades["failure_intensity"].astype(float).round(2)
    upgrades["weighted_impact"] = upgrades["weighted_impact"].astype(float).round(0)
    upgrades["objective_contribution"] = (
        upgrades["objective_contribution"].astype(float).round(0)
    )
    return upgrades.sort_values("objective_contribution", ascending=False)


def regional_upgrade_summary(model: Model):
    """Summarize the selected upgrade plan by region: selected towers, cost, install weeks, and capacity restored."""
    selected = _table(model, "SELECTED_UPGRADES")
    return model.select(
        distinct(
            selected.REGION.alias("region"),
            aggs.count(selected.TOWER_ID).per(selected.REGION).alias("selected_towers"),
            aggs.sum(selected.COST).per(selected.REGION).alias("cost_usd"),
            aggs.sum(selected.INSTALL_WEEKS).per(selected.REGION).alias("install_weeks"),
            aggs.sum(selected.CAPACITY_GBPS).per(selected.REGION).alias("capacity_gbps"),
        )
    ).to_df()


def top_tower_risk_and_impact(model: Model):
    """Show the highest-priority towers by combining predicted failure intensity with customer impact and PageRank-weighted impact."""
    failure = _table(model, "TOWER_FAILURE_SCORE")
    impact = _table(model, "TOWER_CUSTOMER_IMPACT")
    df = model.where(
        failure.TOWER_ID == impact.TOWER_ID,
    ).select(
        failure.TOWER_ID.alias("tower_id"),
        failure.FAILURE_INTENSITY.alias("failure_intensity"),
        impact.IMPACT_COUNT.alias("active_subscriber_count"),
        impact.WEIGHTED_IMPACT.alias("weighted_impact"),
        impact.WEIGHTED_PAGERANK.alias("weighted_pagerank"),
    ).to_df()
    if not df.empty:
        df = df.sort_values(["failure_intensity", "weighted_impact"], ascending=False).head(25)
    return df


def top_tower_customer_impact(model: Model):
    """Rank towers by customer value at risk from the call graph; include active subscriber counts and PageRank-weighted influence."""
    impact = _table(model, "TOWER_CUSTOMER_IMPACT")
    df = model.select(
        impact.TOWER_ID.alias("tower_id"),
        impact.IMPACT_COUNT.alias("active_subscriber_count"),
        impact.WEIGHTED_IMPACT.alias("customer_value_at_risk"),
        impact.WEIGHTED_PAGERANK.alias("pagerank_weighted_influence"),
    ).to_df()
    if not df.empty:
        df = df.sort_values("customer_value_at_risk", ascending=False).head(10)
    return df


def high_risk_equipment_predictions(model: Model):
    """List equipment with the highest GNN-predicted failure probability, its tower, model, and current status."""
    pred = _table(model, "EQUIPMENT_FAILURE_PREDICTION")
    equipment = model.Table(f"{DEPLOYED_SCHEMA}.NETWORKEQUIPMENT")
    df = model.where(
        pred.POS_PROB >= 0.5,
        pred.EQUIPMENT_ID == equipment.ID,
    ).select(
        pred.EQUIPMENT_ID.alias("equipment_id"),
        equipment.TOWER_ID_FK.alias("tower_id"),
        equipment.EQP_MODEL.alias("equipment_model"),
        equipment.STATUS.alias("equipment_status"),
        pred.POS_PROB.alias("failure_probability"),
        pred.PREDICTED_LABEL.alias("predicted_label"),
    ).to_df()
    if not df.empty:
        df = df.sort_values("failure_probability", ascending=False).head(10)
    return df


def top_call_path(model: Model):
    """Return the most influential enumerated call path and the towers that route its hops."""
    path = _table(model, "TOP_CALL_PATH")
    return model.select(
        path.HUB_SUBSCRIBER_ID.alias("hub_subscriber_id"),
        path.INFLUENCE_LOAD.alias("influence_load"),
        path.SUBSCRIBER_PATH.alias("subscriber_path"),
        path.TOWER_PATH.alias("tower_path"),
    ).to_df()


def _incident_signals(model: Model) -> pd.DataFrame:
    incident = _table(model, "DEMO_INCIDENT_INPUT")
    tower = model.Table(f"{DEPLOYED_SCHEMA}.CELLTOWER")
    failure = _table(model, "TOWER_FAILURE_SCORE")
    impact = _table(model, "TOWER_CUSTOMER_IMPACT")
    df = model.where(
        incident.STATE == "OPEN",
        incident.TOWER_ID == tower.ID,
    ).select(
        incident.INCIDENT_ID.alias("incident_id"),
        incident.TOWER_ID.alias("tower_id"),
        incident.INCIDENT_TYPE.alias("incident_type"),
        incident.SEVERITY.alias("severity"),
        incident.OPENED_AT.alias("opened_at"),
        tower.NAME.alias("tower_name"),
        tower.REGION.alias("region"),
    ).to_df()
    if df.empty:
        return df
    signals = model.where(
        failure.TOWER_ID == impact.TOWER_ID,
    ).select(
        failure.TOWER_ID.alias("tower_id"),
        failure.FAILURE_INTENSITY.alias("failure_intensity"),
        impact.IMPACT_COUNT.alias("active_subscriber_count"),
        impact.WEIGHTED_IMPACT.alias("weighted_impact"),
        impact.WEIGHTED_PAGERANK.alias("weighted_pagerank"),
    ).to_df()
    df = df.merge(signals, on="tower_id", how="left", validate="many_to_one")
    if df["failure_intensity"].isna().any() or df["weighted_impact"].isna().any():
        raise RuntimeError("An open incident tower is missing a materialized reasoner score.")
    selected = selected_upgrades(model)[["tower_id", "tier", "cost_usd", "capacity_gbps"]]
    flagged = set(operational_critical_restore_towers(model)["tower_id"])
    df = df.merge(selected, on="tower_id", how="left", validate="many_to_one")
    df["operational_critical"] = df["tower_id"].isin(flagged)
    df["selected_for_upgrade"] = df["tier"].notna()
    df["plan_coverage_note"] = df["selected_for_upgrade"].map(
        {
            True: "Selected by the pre-incident plan; incident did not affect the solve",
            False: "Not selected by the pre-incident plan; exclusion cause is unknown",
        }
    )
    df["risk_impact_proxy"] = (
        df["failure_intensity"].astype(float) * df["weighted_impact"].astype(float)
    ).round(0)
    return df


def open_incident_risk_and_impact(model: Model):
    """Rank synthetic open incidents by tower failure intensity (sum of equipment GNN scores) times routed-call customer impact; show rule flags and current $5M plan coverage. The product is a ranking proxy, not expected monetary loss."""
    df = _incident_signals(model)
    return df.sort_values("risk_impact_proxy", ascending=False) if not df.empty else df


def unfunded_critical_incidents(model: Model):
    """Find open incidents on towers flagged by the deployed WEST restoration rule but absent from the current $5M plan, with summed equipment GNN scores and routed-call customer impact. This does not reoptimize or explain why the solver excluded a tower."""
    df = _incident_signals(model)
    if df.empty:
        return df
    df = df.loc[df["operational_critical"] & ~df["selected_for_upgrade"], [
        "incident_id",
        "tower_id",
        "tower_name",
        "region",
        "incident_type",
        "severity",
        "failure_intensity",
        "active_subscriber_count",
        "weighted_impact",
        "risk_impact_proxy",
        "operational_critical",
        "selected_for_upgrade",
    ]].sort_values("risk_impact_proxy", ascending=False)
    df["solver_exclusion_cause"] = "UNKNOWN_FROM_STORED_PLAN"
    df["failure_intensity_definition"] = (
        "Sum of equipment GNN scores; not normalized, so a value above 1 is not a risk threshold"
    )
    df["weighted_impact_definition"] = (
        "Active caller value summed over routed call records; PageRank is a separate metric"
    )
    return df


def _recalled_equipment_on_incidents(
    model: Model, signals: pd.DataFrame | None = None
) -> pd.DataFrame:
    equipment = model.Table(f"{DEPLOYED_SCHEMA}.NETWORKEQUIPMENT")
    advisory = model.Table("BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE.MODEL_ADVISORIES")
    prediction = _table(model, "EQUIPMENT_FAILURE_PREDICTION")
    df = model.where(
        equipment.STATUS != "RETIRED",
        equipment.ID == prediction.EQUIPMENT_ID,
    ).select(
        equipment.TOWER_ID_FK.alias("tower_id"),
        equipment.ID.alias("equipment_id"),
        equipment.EQP_MODEL.alias("equipment_model"),
        equipment.STATUS.alias("equipment_status"),
        prediction.POS_PROB.alias("gnn_failure_score"),
    ).to_df()
    if df.empty:
        return df
    recalls = model.where(advisory.ADVISORY_TYPE == "RECALL").select(
        advisory.MODEL.alias("equipment_model"),
        advisory.SEVERITY.alias("recall_severity"),
    ).to_df()
    df = df.merge(recalls, on="equipment_model", how="inner", validate="many_to_one")
    if signals is None:
        signals = _incident_signals(model)
    incident_signals = signals[
        ["incident_id", "tower_id", "weighted_impact", "tier", "operational_critical"]
    ]
    df = df.merge(incident_signals, on="tower_id", how="inner", validate="many_to_one")
    df["recall_exposure_proxy"] = (
        df["gnn_failure_score"].astype(float) * df["weighted_impact"].astype(float)
    ).round(0)
    return df.sort_values("recall_exposure_proxy", ascending=False)


def recalled_equipment_on_open_incidents(model: Model):
    """Show installed recalled equipment on towers with open demo incidents, combining source advisories, GNN equipment scores, call-graph impact, and current upgrade coverage. GNN scores are proxy labels, not calibrated future-failure probabilities."""
    return _recalled_equipment_on_incidents(model).head(25)


def call_path_incident_coverage(model: Model):
    """Trace open demo incidents and $5M plan coverage along the highest-influence enumerated call path, with the affected towers' rule flags, GNN failure intensity, and graph impact. Path influence is a graph metric, not guaranteed traffic."""
    path = top_call_path(model)
    if len(path) != 1:
        raise RuntimeError("Expected one top call path; run the path job first.")
    row = path.iloc[0]
    hops = pd.DataFrame(
        {
            "hop": range(1, len(row["tower_path"].split(" -> ")) + 1),
            "tower_id": row["tower_path"].split(" -> "),
        }
    )
    signals = _incident_signals(model)[
        ["incident_id", "tower_id", "severity", "failure_intensity", "weighted_impact", "operational_critical"]
    ]
    hops = hops.merge(signals, on="tower_id", how="left", validate="one_to_many")
    selected = selected_upgrades(model)[["tower_id", "tier"]]
    hops = hops.merge(selected, on="tower_id", how="left", validate="many_to_one")
    hops["has_open_incident"] = hops["incident_id"].notna()
    hops["selected_for_upgrade"] = hops["tier"].notna()
    hops["hub_subscriber_id"] = row["hub_subscriber_id"]
    hops["path_influence_load"] = row["influence_load"]
    return hops.sort_values("hop")


def incident_response_briefing(model: Model):
    """Combine eight open demo incidents with rules, GNN tower scores, graph impact/path, recall counts, and the fixed $5M plan. Comparisons are among demo incidents only, not the fleet; unselected towers have no solver exclusion diagnosis. The incident overlay did not affect the solve."""
    df = _incident_signals(model)
    if df.empty:
        return df
    recalls = _recalled_equipment_on_incidents(model, df)
    if recalls.empty:
        df["recalled_equipment_count"] = 0
    else:
        counts = recalls.groupby("incident_id")["equipment_id"].nunique()
        df["recalled_equipment_count"] = df["incident_id"].map(counts).fillna(0).astype(int)
    path = top_call_path(model)
    if len(path) != 1:
        raise RuntimeError("Expected one top call path; run the path job first.")
    df["on_top_call_path"] = df["tower_id"].isin(path.iloc[0]["tower_path"].split(" -> "))
    plan = plan_summary(model)
    if len(plan) != 1:
        raise RuntimeError("Expected one restore plan; run optimization first.")
    df["plan_total_cost_usd"] = plan.iloc[0]["total_cost_usd"]
    df["plan_capacity_restored_gbps"] = plan.iloc[0]["capacity_restored_gbps"]
    df["comparison_scope"] = "Eight open synthetic demo incidents, not the full fleet"
    return df.sort_values("risk_impact_proxy", ascending=False)


def _bind(fn, *args):
    @functools.wraps(fn)
    def wrapper():
        return fn(*args)

    return wrapper


def build_tool_registry(model: Model) -> ToolRegistry:
    """Build the ToolRegistry for the telco recovery agent."""
    def optimize_upgrades_for_budget(budget_usd: int) -> pd.DataFrame:
        """Re-optimize tower upgrades for a requested budget in whole US dollars. Return every selected tower and tier, risk, customer impact, objective contribution, and plan totals. The 200 install-week limit and precomputed risk/impact inputs stay fixed; this does not overwrite the stored $5M plan."""
        from run_optimization import INSTALL_WEEKS_BUDGET, optimize

        selected, plan = optimize(budget_usd, config=model.config)
        summary = plan.iloc[0]
        upgrades = selected.rename(
            columns={
                "TOWER_ID": "tower_id",
                "TIER": "tier",
                "REGION": "region",
                "CAPACITY_GBPS": "capacity_gbps",
                "COST": "cost_usd",
                "INSTALL_WEEKS": "install_weeks",
                "FAILURE_INTENSITY": "failure_intensity",
                "WEIGHTED_IMPACT": "weighted_impact",
            }
        )
        upgrades["objective_contribution"] = (
            upgrades["capacity_gbps"]
            * upgrades["failure_intensity"]
            * upgrades["weighted_impact"]
        )
        if upgrades.empty:
            upgrades = pd.DataFrame([{"tower_id": None, "tier": None}])
        upgrades["requested_budget_usd"] = budget_usd
        upgrades["plan_status"] = summary["TERMINATION_STATUS"]
        upgrades["plan_total_cost_usd"] = summary["TOTAL_COST"]
        upgrades["plan_install_weeks"] = summary["TOTAL_INSTALL_WEEKS"]
        upgrades["install_week_limit"] = INSTALL_WEEKS_BUDGET
        upgrades["plan_capacity_restored_gbps"] = summary["CAPACITY_RESTORED_GBPS"]
        upgrades["plan_towers_covered"] = summary["TOWERS_COVERED"]
        upgrades["binding_constraint"] = summary["BINDING_CONSTRAINT"]
        return upgrades.sort_values("objective_contribution", ascending=False) if "objective_contribution" in upgrades else upgrades

    return ToolRegistry().add(
        model=model,
        description=(
            "Telco network recovery model for a regional operator. It answers "
            "questions about operational rule-flagged towers, GNN-predicted "
            "equipment failure risk, customer impact and paths from the call "
            "graph, and the optimized tower-upgrade plan. Catalog queries read "
            "deployed semantic tables and precomputed reasoner results; chat "
            "does not rerun the GNN, graph, or path jobs. For a user-specified "
            "upgrade budget, call optimize_upgrades_for_budget with budget_usd "
            "as an integer number of dollars (for example, $3M is 3000000). "
            "This reruns only the optimization with the fixed 200-week limit; "
            "it does not change the saved $5M baseline plan. For the "
            "demo incident questions, DEMO_INCIDENT_INPUT is synthetic and "
            "overlaid on the fixed baseline results; use the five incident "
            "catalog queries for cross-reasoner answers. For the $5M tower "
            "decision, use upgrade_plan_with_rationale; its objective "
            "score is restored Gbps times failure intensity times customer impact. "
            "Failure intensity is a sum of equipment GNN scores, not a "
            "calibrated probability or an above-average rating. Weighted impact "
            "is routed-call customer value and may repeat subscribers; the "
            "PageRank metric is separate, not part of weighted impact. The "
            "stored optimization does not explain why any individual tower was "
            "excluded; do not infer a specific cause. Compare incident scores "
            "only within the eight open demo incidents, never the whole fleet. "
            "When asked which towers, include every selected tower ID and tier."
        ),
        queries=QueryCatalog(
            _bind(operational_critical_restore_towers, model),
            optimize_upgrades_for_budget,
            _bind(upgrade_plan_with_rationale, model),
            _bind(plan_summary, model),
            _bind(selected_upgrades, model),
            _bind(regional_upgrade_summary, model),
            _bind(top_tower_risk_and_impact, model),
            _bind(top_tower_customer_impact, model),
            _bind(high_risk_equipment_predictions, model),
            _bind(top_call_path, model),
            _bind(open_incident_risk_and_impact, model),
            _bind(unfunded_critical_incidents, model),
            _bind(recalled_equipment_on_open_incidents, model),
            _bind(call_path_incident_coverage, model),
            _bind(incident_response_briefing, model),
        ),
    )
