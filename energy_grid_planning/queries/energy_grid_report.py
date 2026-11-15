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
    DataCenterRequest,
    DemandForecast,
    InvestmentLevel,
    InvestmentPortfolio,
    SolveObjective,
    SolveStatus,
    Substation,
    SubstationUpgrade,
    corridor,
    model,
)
from relationalai.semantics import Float, sum


def main() -> None:
    print(f"\n{'=' * 60}")
    print("STAGE 1: PREDICT -- Substation Load Forecasting")
    print("=" * 60)

    # Query demand forecasts for structured enrichments.
    DemandForecast_ref = DemandForecast.ref()
    SubRef = Substation.ref()
    forecast_df = (
        model.select(
            SubRef.id.alias("sub_id"),
            SubRef.name.alias("sub_name"),
            SubRef.current_load_mw.alias("current_load"),
            SubRef.max_capacity_mw.alias("max_capacity"),
            DemandForecast_ref.forecast_period.alias("forecast_period"),
            DemandForecast_ref.predicted_load_mw.alias("predicted_load"),
            DemandForecast_ref.confidence.alias("confidence"),
        )
        .where(DemandForecast_ref.substation(SubRef))
        .to_df()
    )

    if len(forecast_df) > 0:
        forecast_df["predicted_load"] = forecast_df["predicted_load"].astype(float)
        forecast_df["current_load"] = forecast_df["current_load"].astype(float)
        forecast_df["max_capacity"] = forecast_df["max_capacity"].astype(float)
        forecast_df["forecast_period"] = forecast_df["forecast_period"].astype(int)

        sub_forecast = (
            forecast_df.groupby(["sub_id", "sub_name", "current_load", "max_capacity"])
            .agg(
                predicted_load=("predicted_load", "max"),
                min_breach_period=("forecast_period", "min"),
            )
            .reset_index()
        )

        sub_forecast["growth_rate"] = (
            sub_forecast["predicted_load"] - sub_forecast["current_load"]
        ) / sub_forecast["current_load"].clip(lower=0.1)

        breach_df = forecast_df[forecast_df["predicted_load"] > forecast_df["max_capacity"]]
        breach_months = breach_df.groupby("sub_id")["forecast_period"].min().reset_index()
        breach_months.columns = ["sub_id", "breach_months"]

        sub_forecast = sub_forecast.merge(breach_months, on="sub_id", how="left")
        sub_forecast["breach_months"] = (
            sub_forecast["breach_months"].fillna(999).astype(int)
        )

        at_risk = sub_forecast[sub_forecast["breach_months"] < 999].sort_values("breach_months")
        print("\n  Substations at risk of capacity breach:")
        print(
            f"  {'Substation':<25} {'Current':>10} {'Predicted':>10} {'Max Cap':>10} {'Breach Mo':>10} {'Growth':>8}"
        )
        print(f"  {'-' * 73}")
        for _, r in at_risk.iterrows():
            print(
                f"  {r['sub_name']:<25} {r['current_load']:>10.1f} {r['predicted_load']:>10.1f} "
                f"{r['max_capacity']:>10.1f} {r['breach_months']:>10} {r['growth_rate']:>7.1%}"
            )

        if len(at_risk) == 0:
            print("  (none predicted within forecast horizon)")

        print("\n  All substation forecasts:")
        for _, r in sub_forecast.sort_values("predicted_load", ascending=False).iterrows():
            breach_str = f"{r['breach_months']}mo" if r["breach_months"] < 999 else "safe"
            print(
                f"    {r['sub_name']:<25} pred={r['predicted_load']:.1f} MW  growth={r['growth_rate']:.1%}  breach={breach_str}"
            )
    else:
        print(
            "  No demand forecasts available -- Stage 1 outputs will use current_load as fallback"
        )
        sub_forecast = pd.DataFrame()


    print(f"\n{'=' * 60}")
    print("STAGE 2: GRAPH -- Grid Topology & Structural Vulnerability")
    print("=" * 60)

    wcc_df = (
        model.select(
            Substation.id.alias("substation_id"),
            Substation.name.alias("substation_name"),
            Substation.component.alias("component_id"),
        )
        .to_df()
    )

    num_components = wcc_df["component_id"].nunique()
    total_substations = len(wcc_df)
    print(
        f"\n  Grid connectivity: {total_substations} substations, {num_components} component(s)"
    )
    if num_components == 1:
        print("  CONNECTED: All substations reachable from any other.")
    else:
        print(f"  FRAGMENTED: {num_components} isolated grid segments detected!")

    community_df = model.select(
        Substation.id.alias("substation_id"),
        Substation.name.alias("name"),
        Substation.grid_community.alias("community"),
    ).to_df()
    community_df["community"] = community_df["community"].astype(int)

    num_communities = community_df["community"].nunique()
    print(f"\n  Grid community structure (Louvain): {num_communities} region(s)")
    for comm_id, group in community_df.groupby("community"):
        members = ", ".join(group["name"].tolist())
        print(f"    Region {comm_id}: {members}")

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
    centrality_df["critical_rank"] = centrality_df["critical_rank"].astype(int)

    print(f"\n  All substations by centrality (top {CRITICAL_THRESHOLD} marked CRITICAL):")
    for i, (_, row) in enumerate(centrality_df.iterrows(), 1):
        flag = " [CRITICAL]" if row["critical_rank"] <= CRITICAL_THRESHOLD else ""
        print(
            f"    #{i}: {row['name']} (betw={row['betweenness']:.4f}, "
            f"deg={row['degree_centrality']:.4f}, eig={row['eigenvector_centrality']:.4f}){flag}"
        )

    # Cross-reference: DC-targeted substations that are ALSO critical bottlenecks
    DCRef = DataCenterRequest.ref()
    SubRef2 = Substation.ref()
    dc_sub_df = (
        model.where(DCRef.substation(SubRef2))
        .select(
            DCRef.name.alias("dc_name"),
            DCRef.requested_mw.alias("requested_mw"),
            SubRef2.id.alias("sub_id"),
            SubRef2.name.alias("sub_name"),
        )
        .to_df()
    )

    if len(dc_sub_df) > 0 and len(centrality_df) > 0:
        critical_ids = centrality_df.loc[
            centrality_df["critical_rank"] <= CRITICAL_THRESHOLD, "substation_id"
        ]
        dc_at_bottleneck = dc_sub_df[dc_sub_df["sub_id"].isin(critical_ids)]
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

    # Reassemble corridor node sequences in pandas for human-readable route labels (string-
    # joining names is a pandas job) and for the contingency re-enumeration below. Selecting
    # names alongside the score would fan out rows, so the node-sequence projection is a
    # SEPARATE query from the scoring above.
    corridor_df = model.where(corridor).select(
        corridor.alias("corridor"),
        corridor.nodes["index"].alias("hop"),
        Substation(corridor.nodes).id.alias("substation_id"),
        Substation(corridor.nodes).name.alias("substation_name"),
    ).to_df()
    betw_df = model.select(
        Substation.id.alias("substation_id"),
        Substation.name.alias("substation_name"),
        Substation.betweenness.alias("betweenness"),
    ).to_df()
    betw_by_id = dict(zip(betw_df["substation_id"], betw_df["betweenness"].fillna(0.0)))
    name_by_id = dict(zip(betw_df["substation_id"], betw_df["substation_name"]))
    corridor_df["hop"] = corridor_df["hop"].astype(int)
    corridor_df["betweenness"] = corridor_df["substation_id"].map(betw_by_id).fillna(0.0)


    def most_fragile_corridor_per_dc(removed_id=None):
        """Highest total-betweenness SIMPLE corridor terminating at each DC substation.

        Used to recover each winning corridor's node names (for printing) and for the
        contingency re-enumeration. The baseline per-DC max load is computed natively
        above (fragility_per_dc); this reproduces it and adds the route node sequence.
        """
        best = {}
        for _, grp in corridor_df.groupby("corridor"):
            ordered = grp.sort_values("hop")
            ids = ordered["substation_id"].tolist()
            if len(set(ids)) != len(ids):
                continue  # simple paths only (the grid is cyclic)
            if removed_id is not None and removed_id in ids:
                continue
            load = round(float(ordered["betweenness"].sum()), 3)
            dest = ids[-1]
            if dest not in best or load > best[dest][1]:
                best[dest] = (ordered["substation_name"].tolist(), load)
        return best


    baseline_corridors = most_fragile_corridor_per_dc()
    # Count only SIMPLE corridors (drop node-repeating walks; the grid is cyclic). Kept in
    # pandas via node-sequence reassembly: native count(corridor) fans out over the simple-
    # path filter and count(distinct(corridor)) collapses to all-walks -- neither is the
    # simple-corridor count. `len([...])`, not `sum(...)`: `sum` is shadowed by the relationalai import.
    n_corridors = len([
        cid
        for cid, grp in corridor_df.groupby("corridor")
        if len(set(grp["substation_id"])) == len(grp["substation_id"])
    ])
    print(
        f"\n  {n_corridors} generator-sub -> DC-sub corridors (<= {MAX_CORRIDOR_HOPS} hops, simple); "
        f"most-fragile corridor for {len(baseline_corridors)} DC substation(s):"
    )
    for dest, (route, load) in sorted(baseline_corridors.items(), key=lambda kv: -kv[1][1])[:5]:
        print(f"    betweenness-load {load}: " + " -> ".join(route))

    # Contingency: take the highest-betweenness substation offline and re-enumerate.
    if betw_by_id:
        top_id = max(betw_by_id, key=betw_by_id.get)
        after_corridors = most_fragile_corridor_per_dc(removed_id=top_id)
        # NB: `sum` is shadowed by the relationalai import, so count with len([...]).
        rerouted = len(
            [d for d in baseline_corridors if d in after_corridors and baseline_corridors[d][0] != after_corridors[d][0]]
        )
        lost = [d for d in baseline_corridors if d not in after_corridors]
        print(
            f"\n  Contingency -- highest-betweenness substation offline "
            f"({name_by_id.get(top_id, top_id)}): {len(baseline_corridors)} -> {len(after_corridors)} "
            f"DC substations served, {rerouted} reroute, {len(lost)} lose all corridors."
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

    num_dc = len(compliance_df)
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

    compliant_count = len(compliance_df[compliance_df["is_compliant"] == "Y"])
    flagged_count = len(compliance_df[compliance_df["is_compliant"] == "N"])
    print(
        f"\n  Summary: {compliant_count} compliant, {flagged_count} flagged (out of {num_dc} requests)"
    )


    print(f"\n{'=' * 60}")
    print("STAGE 5: OPTIMIZE -- Joint Interconnection + Upgrade")
    print("=" * 60)

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print("\n  Solving across 5 investment levels ($200M-$600M)...")
    print(f"  Status: {', '.join(status)}")
    if objective:
        print(f"  Objective: {float(objective[0]):,.2f}")

    # --------------------------------------------------
    # Results -- Pareto Frontier from Ontology
    # --------------------------------------------------

    x_a = Float.ref("xa")
    x_u = Float.ref("xu")

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

    # Revenue and cost per level
    rev_per_level = sum(x_a * DataCenterRequest.annual_revenue_per_mw * DataCenterRequest.requested_mw).per(
        InvestmentLevel
    ).where(DataCenterRequest.x_approve(InvestmentLevel, x_a))

    cost_per_level = sum(x_u * SubstationUpgrade.cost_million).per(
        InvestmentLevel
    ).where(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u))

    print("\n  Revenue and upgrade cost by investment level:")
    model.select(
        InvestmentLevel.name.alias("level"),
        InvestmentLevel.budget_cap.alias("budget_cap"),
        rev_per_level.alias("revenue"),
        cost_per_level.alias("upgrade_cost"),
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
            DataCenterRequest.annual_revenue_per_mw.alias("rev_per_mw"),
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
    InvLvlRef = InvestmentLevel.ref()
    PortRef = InvestmentPortfolio.ref()
    portfolio_query_df = (
        model.where(PortRef.investment_level(InvLvlRef))
        .select(
            PortRef.investment_level_name.alias("level"),
            InvLvlRef.budget_cap.alias("budget"),
            PortRef.dc_count.alias("dc_count"),
            PortRef.total_mw.alias("total_mw"),
            PortRef.annual_revenue.alias("annual_revenue"),
            PortRef.upgrade_cost.alias("upgrade_cost"),
            PortRef.net_value.alias("net_value"),
        )
        .to_df()
        .sort_values("budget")
        .reset_index(drop=True)
    )
    portfolio_query_df["budget"] = portfolio_query_df["budget"].astype(float)
    portfolio_query_df["dc_count"] = portfolio_query_df["dc_count"].astype(int)

    # marginal: ($net_value_next - $net_value_this) / ($M_next - $M_this); null at last
    marginal = []
    for j in range(len(portfolio_query_df)):
        if j == len(portfolio_query_df) - 1:
            marginal.append(None)
        else:
            d_val = float(portfolio_query_df.loc[j + 1, "net_value"]) - float(portfolio_query_df.loc[j, "net_value"])
            d_budget = portfolio_query_df.loc[j + 1, "budget"] - portfolio_query_df.loc[j, "budget"]
            marginal.append(d_val / d_budget if abs(d_budget) > 1e-6 else None)
    portfolio_query_df["marginal"] = marginal

    # is_knee: row whose marginal-rate represents the largest jump from the prior row's rate.
    # We measure the "jump" at row j as |rate[j-1]| / |rate[j]| (steepest drop from a high marginal
    # to a lower one, i.e. diminishing-returns inflection). The knee is the row where this ratio peaks.
    is_knee = [False] * len(portfolio_query_df)
    rates = [r for r in marginal if r is not None]
    if len(rates) >= 2:
        max_jump, knee_idx = 0.0, 1
        for j in range(len(rates) - 1):
            prev_rate, next_rate = rates[j], rates[j + 1]
            if abs(next_rate) > 1e-6:
                jump = abs(prev_rate / next_rate)
            elif abs(prev_rate) > 1e-6:
                jump = float("inf")
            else:
                jump = 0.0
            if jump > max_jump:
                max_jump = jump
                knee_idx = j + 1
        is_knee[knee_idx] = True
    portfolio_query_df["is_knee"] = is_knee

    # Per-level totals for the detail sections below.
    pareto_rows = []
    for _, row in portfolio_query_df.iterrows():
        level_upg = upgrade_result_df[upgrade_result_df["level"] == row["level"]]
        pareto_rows.append({
            "level": row["level"],
            "budget": float(row["budget"]),
            "n_approved": int(row["dc_count"]),
            "total_mw": float(row["total_mw"]),
            "revenue": float(row["annual_revenue"]),
            "n_upgrades": len(level_upg),
            "upgrade_cost_m": float(row["upgrade_cost"]) / 1e6,
            "upgrade_mw": float(level_upg["capacity_mw"].astype(float).sum()) if len(level_upg) > 0 else 0.0,
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
                    f"${float(row['requested_mw']) * float(row['rev_per_mw']):,.0f}/yr"
                )

        level_upg = upgrade_result_df[upgrade_result_df["level"] == level_name] if len(upgrade_result_df) > 0 else pd.DataFrame()
        print(f"\n  Selected Upgrades: {pt['n_upgrades']} (${pt['upgrade_cost_m']:,.1f}M, +{pt['upgrade_mw']:,.1f} MW)")
        if len(level_upg) > 0:
            for _, row in level_upg.iterrows():
                print(f"    {row['upgrade_id']}: +{float(row['capacity_mw']):.0f} MW, ${float(row['cost_m']):.1f}M")

    # Marginal analysis + knee detection (read from ontology)
    if len(portfolio_query_df) >= 3:
        print("\n  MARGINAL ANALYSIS (value gained per additional $M budget):")
        for j in range(len(portfolio_query_df) - 1):
            cur = portfolio_query_df.iloc[j]
            nxt = portfolio_query_df.iloc[j + 1]
            d_val = float(nxt["net_value"]) - float(cur["net_value"])
            d_budget = float(nxt["budget"]) - float(cur["budget"])
            d_mw = float(nxt["total_mw"]) - float(cur["total_mw"])
            d_dcs = int(nxt["dc_count"]) - int(cur["dc_count"])
            rate = float(cur["marginal"]) if pd.notna(cur["marginal"]) else 0.0
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


    print(f"\n{'=' * 80}")
    print("  PIPELINE COMPLETE: 5 stages executed on shared Energy Grid ontology")
    print("  Stage 5 solved all investment levels in a single formulation")
    print("  (Scenario Concept pattern -- results in ontology, no re-solve loops)")
    print("=" * 80)


if __name__ == "__main__":
    main()
