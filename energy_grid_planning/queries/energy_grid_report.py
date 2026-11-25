"""Energy grid report: the five-stage pipeline's results from the deployed model.

Run after `rai models deploy --path model`:
    python -m queries.energy_grid_report

Prints, stage by stage, the substation load forecasts and capacity breaches,
grid connectivity and centrality, the most fragile transmission corridors and
a contingency, the interconnection compliance table, the status and objective
of the latest refresh's solve, and the Pareto frontier across the five investment
levels with its marginal analysis and knee point.
"""

import pandas as pd
from model import (
    CRITICAL_THRESHOLD,
    MAX_CORRIDOR_HOPS,
    ComplianceSummary,
    CorridorSummary,
    DataCenterRequest,
    GridRegion,
    GridTopology,
    InvestmentLevel,
    InvestmentPortfolio,
    InvestmentRange,
    SolveObjective,
    SolveStatus,
    Substation,
    SubstationUpgrade,
    model,
)
from relationalai.semantics import Float

# How many corridors Stage 3 lists.
TOP_CORRIDORS = 5


def main() -> None:
    print(f"\n{'=' * 60}")
    print("STAGE 1: PREDICT -- Substation Load Forecasting")
    print("=" * 60)

    sub_forecast = (
        model.select(
            Substation.id.alias("sub_id"),
            Substation.name.alias("sub_name"),
            Substation.current_load_mw.alias("current_load"),
            Substation.max_capacity_mw.alias("max_capacity"),
            Substation.predicted_load.alias("predicted_load"),
            Substation.growth_rate.alias("growth_rate"),
        )
        .to_df()
    )
    breach_df = model.select(
        Substation.id.alias("sub_id"),
        Substation.breach_period.alias("breach_months"),
    ).to_df()

    if len(sub_forecast) > 0:
        sub_forecast = sub_forecast.merge(breach_df, on="sub_id", how="left")
        at_risk = sub_forecast.dropna(subset=["breach_months"]).sort_values("breach_months")
        print("\n  Substations at risk of capacity breach:")
        print(
            f"  {'Substation':<25} {'Current':>10} {'Predicted':>10} {'Max Cap':>10} {'Breach Mo':>10} {'Growth':>8}"
        )
        print(f"  {'-' * 73}")
        for _, r in at_risk.iterrows():
            print(
                f"  {r['sub_name']:<25} {r['current_load']:>10.1f} {r['predicted_load']:>10.1f} "
                f"{r['max_capacity']:>10.1f} {int(r['breach_months']):>10} {r['growth_rate']:>7.1%}"
            )

        if len(at_risk) == 0:
            print("  (none predicted within forecast horizon)")

        print("\n  All substation forecasts:")
        for _, r in sub_forecast.sort_values("predicted_load", ascending=False).iterrows():
            breach_str = "safe" if pd.isna(r["breach_months"]) else f"{int(r['breach_months'])}mo"
            print(
                f"    {r['sub_name']:<25} pred={r['predicted_load']:.1f} MW  growth={r['growth_rate']:.1%}  breach={breach_str}"
            )
    else:
        print(
            "  No demand forecasts available -- Stage 1 outputs will use current_load as fallback"
        )


    print(f"\n{'=' * 60}")
    print("STAGE 2: GRAPH -- Grid Topology & Structural Vulnerability")
    print("=" * 60)

    topology = model.select(
        GridTopology.n_substations.alias("substations"),
        GridTopology.n_components.alias("components"),
        GridTopology.n_communities.alias("communities"),
        GridTopology.connectivity.alias("connectivity"),
    ).to_df().iloc[0]

    num_components = int(topology["components"])
    print(
        f"\n  Grid connectivity: {int(topology['substations'])} substations, {num_components} component(s)"
    )
    if topology["connectivity"] == "CONNECTED":
        print("  CONNECTED: All substations reachable from any other.")
    else:
        print(f"  FRAGMENTED: {num_components} isolated grid segments detected!")

    regions = (
        model.select(GridRegion.community.alias("community"), GridRegion.members.alias("members"))
        .to_df()
        .sort_values("community")
    )
    print(f"\n  Grid community structure (Louvain): {int(topology['communities'])} region(s)")
    for _, region in regions.iterrows():
        print(f"    Region {int(region['community'])}: {region['members']}")

    centrality_df = (
        model.select(
            Substation.id.alias("substation_id"),
            Substation.name.alias("name"),
            Substation.betweenness.alias("betweenness"),
            Substation.degree_centrality.alias("degree_centrality"),
            Substation.eigenvector_centrality.alias("eigenvector_centrality"),
            Substation.critical_rank.alias("critical_rank"),
        )
        .to_df()
        .sort_values("critical_rank")
        .reset_index(drop=True)
    )
    critical_ids = set(
        model.where(Substation.is_structurally_critical()).select(Substation.id).to_df().iloc[:, 0]
    )

    print(f"\n  All substations by centrality (top {CRITICAL_THRESHOLD} marked CRITICAL):")
    for i, (_, row) in enumerate(centrality_df.iterrows(), 1):
        flag = " [CRITICAL]" if row["substation_id"] in critical_ids else ""
        print(
            f"    #{i}: {row['name']} (betw={row['betweenness']:.4f}, "
            f"deg={row['degree_centrality']:.4f}, eig={row['eigenvector_centrality']:.4f}){flag}"
        )

    # Cross-reference: DC requests whose substation is a critical bottleneck (Stage 4's structural rule).
    DCRef = DataCenterRequest.ref()
    SubRef2 = Substation.ref()
    dc_at_bottleneck = (
        model.where(DCRef.fails_structural(), DCRef.substation(SubRef2))
        .select(
            DCRef.name.alias("dc_name"),
            DCRef.requested_mw.alias("requested_mw"),
            SubRef2.name.alias("sub_name"),
        )
        .to_df()
    )
    if len(dc_at_bottleneck) > 0:
        print(
            "\n  KEY INSIGHT: DC requests targeting structurally critical substations:"
        )
        for _, row in dc_at_bottleneck.iterrows():
            print(
                f"    {row['dc_name']} ({row['requested_mw']} MW) -> {row['sub_name']} [CRITICAL]"
            )
    else:
        print("\n  No DC requests target structurally critical substations.")


    print(f"\n{'=' * 60}")
    print("STAGE 3: PATHS -- Transmission Corridors & Contingency")
    print("=" * 60)

    # The deployed model publishes the corridor counts, each DC substation's most fragile route, and
    # the contingency's reroutes.
    corridors = model.select(
        CorridorSummary.n_corridors.alias("corridors"),
        CorridorSummary.n_served.alias("served"),
        CorridorSummary.n_served_contingency.alias("served_contingency"),
        CorridorSummary.n_rerouted.alias("rerouted"),
        CorridorSummary.n_lost.alias("lost"),
    ).to_df().iloc[0]
    most_fragile = (
        model.where(Substation.fragility_rank <= TOP_CORRIDORS)
        .select(
            Substation.fragility_rank.alias("rank"),
            Substation.fragility_load.alias("load"),
            Substation.fragile_route.alias("route"),
        )
        .to_df()
        .sort_values("rank")
    )
    print(
        f"\n  {int(corridors['corridors'])} generator-sub -> DC-sub corridors (<= {MAX_CORRIDOR_HOPS} hops, simple); "
        f"most-fragile corridor for {int(corridors['served'])} DC substation(s):"
    )
    for _, row in most_fragile.iterrows():
        print(f"    betweenness-load {round(float(row['load']), 3)}: {row['route']}")

    # Contingency: the highest-betweenness substation goes offline and the corridors are re-enumerated.
    offline = model.where(Substation.is_offline()).select(Substation.name.alias("name")).to_df()
    if len(offline) > 0:
        print(
            f"\n  Contingency -- highest-betweenness substation offline "
            f"({offline['name'].iloc[0]}): {int(corridors['served'])} -> {int(corridors['served_contingency'])} "
            f"DC substations served, {int(corridors['rerouted'])} reroute, {int(corridors['lost'])} lose all corridors."
        )


    print(f"\n{'=' * 60}")
    print("STAGE 4: RULES -- Interconnection Queue Compliance")
    print("=" * 60)

    # Query rule outputs for compliance summary
    compliance_df = (
        model.select(
            DataCenterRequest.id.alias("dc_id"),
            DataCenterRequest.name.alias("dc_name"),
            DataCenterRequest.hyperscaler.alias("hyperscaler"),
            DataCenterRequest.queue_position.alias("queue_pos"),
            DataCenterRequest.requested_mw.alias("requested_mw"),
        )
        .to_df()
        .sort_values("queue_pos")
    )


    def _query_flag(relationship, flag_name):
        df = model.where(relationship()).select(
            DataCenterRequest.id.alias("dc_id"),
        ).to_df()
        if len(df) > 0:
            df[flag_name] = "FAIL"
        else:
            df = pd.DataFrame(columns=["dc_id", flag_name])
        return df


    cap_fail_df = _query_flag(DataCenterRequest.fails_capacity, "capacity_flag")
    struct_fail_df = _query_flag(DataCenterRequest.fails_structural, "structural_flag")
    lc_fail_df = _query_flag(DataCenterRequest.fails_low_carbon, "low_carbon_flag")

    compliant_ids_df = model.where(DataCenterRequest.is_compliant()).select(
        DataCenterRequest.id.alias("dc_id"),
    ).to_df()
    if len(compliant_ids_df) > 0:
        compliant_ids_df["is_compliant"] = "Y"
    else:
        compliant_ids_df = pd.DataFrame(columns=["dc_id", "is_compliant"])

    compliance_df = compliance_df.merge(cap_fail_df, on="dc_id", how="left")
    compliance_df["capacity_flag"] = compliance_df["capacity_flag"].fillna("PASS")
    compliance_df = compliance_df.merge(struct_fail_df, on="dc_id", how="left")
    compliance_df["structural_flag"] = compliance_df["structural_flag"].fillna("PASS")
    compliance_df = compliance_df.merge(lc_fail_df, on="dc_id", how="left")
    compliance_df["low_carbon_flag"] = compliance_df["low_carbon_flag"].fillna("PASS")
    compliance_df = compliance_df.merge(compliant_ids_df, on="dc_id", how="left")
    compliance_df["is_compliant"] = compliance_df["is_compliant"].fillna("N")

    compliance_counts = model.select(
        ComplianceSummary.n_requests.alias("requests"),
        ComplianceSummary.n_compliant.alias("compliant"),
        ComplianceSummary.n_flagged.alias("flagged"),
    ).to_df().iloc[0]
    num_dc = int(compliance_counts["requests"])
    print(f"\n  Evaluating {num_dc} DC requests against 3 declarative compliance rules...")

    print(
        f"\n  {'DC Request':<25} {'Hyper':<12} {'Q#':>3} {'MW':>6} "
        f"{'Cap':>5} {'LowC':>5} {'Crit':>5} {'OK?':>4}"
    )
    print(f"  {'-' * 70}")
    for _, r in compliance_df.iterrows():
        print(
            f"  {r['dc_name']:<25} {r['hyperscaler']:<12} {r['queue_pos']:>3} {float(r['requested_mw']):>6.0f} "
            f"{r['capacity_flag']:>5} {r['low_carbon_flag']:>5} "
            f"{r['structural_flag']:>5} {r['is_compliant']:>4}"
        )

    compliant_count = int(compliance_counts["compliant"])
    flagged_count = int(compliance_counts["flagged"])
    print(
        f"\n  Summary: {compliant_count} compliant, {flagged_count} flagged (out of {num_dc} requests)"
    )


    print(f"\n{'=' * 60}")
    print("STAGE 5: OPTIMIZE -- Joint Interconnection + Upgrade")
    print("=" * 60)

    levels = model.select(
        InvestmentRange.n_levels.alias("n_levels"),
        InvestmentRange.min_budget.alias("min_budget"),
        InvestmentRange.max_budget.alias("max_budget"),
    ).to_df().iloc[0]
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print(
        f"\n  Solved across {int(levels['n_levels'])} investment levels "
        f"(${float(levels['min_budget']):,.0f}M-${float(levels['max_budget']):,.0f}M)"
    )
    print(f"  Status: {', '.join(status)}")
    # Portfolio totals default to zero, so without a solution they would read as an empty plan.
    if not objective:
        raise SystemExit(f"termination status {status}: no solution available")
    print(f"  Objective: {float(objective[0]):,.2f}")

    # --------------------------------------------------
    # Results -- Pareto Frontier from Ontology
    # --------------------------------------------------

    x_a = Float.ref("xa")

    # Approved DCs per level
    print("\n  PARETO FRONTIER (queried from ontology):")
    print("\n  Approved DCs per investment level:")
    model.select(
        InvestmentLevel.name.alias("level"),
        DataCenterRequest.name.alias("dc"),
        DataCenterRequest.requested_mw.alias("mw"),
        x_a.alias("approved"),
    ).where(
        DataCenterRequest.x_approve(InvestmentLevel, x_a), x_a > 0.5
    ).inspect()

    InvLvlRef = InvestmentLevel.ref()
    PortRef = InvestmentPortfolio.ref()
    print("\n  Revenue and upgrade cost by investment level:")
    model.where(PortRef.investment_level(InvLvlRef)).select(
        InvLvlRef.name.alias("level"),
        InvLvlRef.budget_cap.alias("budget_cap"),
        PortRef.annual_revenue.alias("revenue_usd_per_year"),
        (PortRef.upgrade_cost / 1e6).alias("upgrade_cost_million"),
    ).inspect()

    # Per-level detail via pandas
    x_q = Float.ref()
    dc_approval_df = (
        model.where(DataCenterRequest.x_approve(InvestmentLevel, x_q), x_q > 0.5)
        .select(
            InvestmentLevel.name.alias("level"),
            InvestmentLevel.budget_cap.alias("budget"),
            DataCenterRequest.id.alias("dc_id"),
            DataCenterRequest.name.alias("dc_name"),
            DataCenterRequest.hyperscaler.alias("hyperscaler"),
            DataCenterRequest.requested_mw.alias("requested_mw"),
            DataCenterRequest.annual_revenue.alias("revenue"),
        )
        .to_df()
    )

    x_uq = Float.ref()
    upgrade_result_df = (
        model.where(SubstationUpgrade.x_upgrade(InvestmentLevel, x_uq), x_uq > 0.5)
        .select(
            InvestmentLevel.name.alias("level"),
            SubstationUpgrade.id.alias("upgrade_id"),
            SubstationUpgrade.capacity_increase_mw.alias("capacity_mw"),
            SubstationUpgrade.cost_million.alias("cost_m"),
        )
        .to_df()
    )

    # Portfolio rows from the ontology: one per investment level.
    portfolio_query_df = (
        model.where(PortRef.investment_level(InvLvlRef))
        .select(
            PortRef.investment_level_name.alias("level"),
            InvLvlRef.budget_cap.alias("budget"),
            PortRef.dc_count.alias("dc_count"),
            PortRef.total_mw.alias("total_mw"),
            PortRef.annual_revenue.alias("annual_revenue"),
            PortRef.upgrade_cost.alias("upgrade_cost"),
            PortRef.upgrade_count.alias("upgrade_count"),
            PortRef.upgrade_mw.alias("upgrade_mw"),
            PortRef.net_value.alias("net_value"),
        )
        .to_df()
        .sort_values("budget")
        .reset_index(drop=True)
    )
    portfolio_query_df["budget"] = portfolio_query_df["budget"].astype(float)

    # Gains to the next level and the marginal value per added $M (none for the largest budget), and the
    # knee flag.
    marginal_df = model.select(
        PortRef.investment_level_name.alias("level"),
        PortRef.marginal_per_m_to_next_level.alias("marginal"),
        PortRef.value_gain.alias("value_gain"),
        PortRef.budget_gain.alias("budget_gain"),
        PortRef.mw_gain.alias("mw_gain"),
        PortRef.dc_gain.alias("dc_gain"),
    ).to_df()
    knee_levels = model.where(PortRef.is_knee_point()).select(PortRef.investment_level_name.alias("level")).to_df()
    portfolio_query_df = portfolio_query_df.merge(marginal_df, on="level", how="left")
    portfolio_query_df["is_knee"] = portfolio_query_df["level"].isin(knee_levels["level"])

    # Per-level totals for the detail sections below.
    pareto_rows = []
    for _, row in portfolio_query_df.iterrows():
        pareto_rows.append({
            "level": row["level"],
            "budget": float(row["budget"]),
            "n_approved": int(row["dc_count"]),
            "total_mw": float(row["total_mw"]),
            "revenue": float(row["annual_revenue"]),
            "n_upgrades": int(row["upgrade_count"]),
            "upgrade_cost_m": float(row["upgrade_cost"]) / 1e6,
            "upgrade_mw": float(row["upgrade_mw"]),
            "net_value": float(row["net_value"]),
        })

    # Print Pareto frontier (read from ontology, not pareto_rows)
    print(
        f"\n  {'#':>3} {'Level':>8} {'Budget $M':>10} {'DCs':>5} {'DC MW':>8} "
        f"{'Revenue $/yr':>14} {'Upg $M':>8} {'Net Value':>14} {'Knee':>5}"
    )
    print(f"  {'-' * 85}")
    for j, row in portfolio_query_df.iterrows():
        knee_flag = " *" if bool(row["is_knee"]) else ""
        print(
            f"  {j + 1:>3} {row['level']:>8} {float(row['budget']):>10,.0f} "
            f"{int(row['dc_count']):>5} {float(row['total_mw']):>8,.0f} "
            f"{float(row['annual_revenue']):>14,.0f} {float(row['upgrade_cost']) / 1e6:>8,.1f} "
            f"{float(row['net_value']):>14,.0f} {knee_flag:>5}"
        )

    # Detailed results per investment level
    for pt in pareto_rows:
        level_name = pt["level"]
        print(f"\n  --- {level_name} (Budget: ${pt['budget']:,.0f}M) ---")
        print(f"  Net value: ${pt['net_value']:,.0f}")

        level_dcs = dc_approval_df[dc_approval_df["level"] == level_name] if len(dc_approval_df) > 0 else pd.DataFrame()
        print(f"\n  Approved Data Centers: {pt['n_approved']}")
        print(f"  Total MW: {pt['total_mw']:,.1f} | Revenue: ${pt['revenue']:,.0f}/yr")
        if len(level_dcs) > 0:
            for _, row in level_dcs.iterrows():
                print(
                    f"    {row['dc_name']} ({row['hyperscaler']}): "
                    f"{float(row['requested_mw']):.0f} MW, "
                    f"${float(row['revenue']):,.0f}/yr"
                )

        level_upg = upgrade_result_df[upgrade_result_df["level"] == level_name] if len(upgrade_result_df) > 0 else pd.DataFrame()
        print(f"\n  Selected Upgrades: {pt['n_upgrades']} (${pt['upgrade_cost_m']:,.1f}M, +{pt['upgrade_mw']:,.1f} MW)")
        if len(level_upg) > 0:
            for _, row in level_upg.iterrows():
                print(f"    {row['upgrade_id']}: +{float(row['capacity_mw']):.0f} MW, ${float(row['cost_m']):.1f}M")

    # Marginal analysis and knee, from the model
    if len(portfolio_query_df) >= 3:
        print("\n  MARGINAL ANALYSIS (value gained per additional $M budget):")
        for j in range(len(portfolio_query_df) - 1):
            cur = portfolio_query_df.iloc[j]
            nxt = portfolio_query_df.iloc[j + 1]
            d_val = float(cur["value_gain"])
            d_budget = float(cur["budget_gain"])
            d_mw = float(cur["mw_gain"])
            d_dcs = int(cur["dc_gain"])
            rate = float(cur["marginal"])
            print(
                f"    {cur['level']:>6} -> {nxt['level']:<6}: "
                f"dValue={d_val:>+14,.0f}, dBudget={d_budget:>+6,.0f}$M, "
                f"dMW={d_mw:>+8,.0f}, dDCs={d_dcs:>+3}, "
                f"marginal={rate:>+12,.0f}$/M$"
            )

        knee_rows = portfolio_query_df[portfolio_query_df["is_knee"].astype(bool)]
        if len(knee_rows) > 0:
            knee = knee_rows.iloc[0]
            print(
                f"\n  KNEE POINT: {knee['level']} -- ${float(knee['budget']):,.0f}M budget, "
                f"${float(knee['net_value']):,.0f} net value, {int(knee['dc_count'])} DCs, "
                f"{float(knee['total_mw']):,.0f} MW"
            )
            print("  Diminishing returns beyond this investment level.")
        else:
            print("\n  No knee point: the marginal value never falls between budget levels.")


    print(f"\n{'=' * 80}")
    print("  PIPELINE COMPLETE: 5 stages executed on shared Energy Grid ontology")
    print("  Stage 5 solved all investment levels in a single formulation")
    print("  (Scenario Concept pattern -- results in ontology, no re-solve loops)")
    print("=" * 80)


if __name__ == "__main__":
    main()
