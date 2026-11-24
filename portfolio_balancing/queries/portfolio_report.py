"""Portfolio report: reads the deployed portfolio model.

Run `python -m queries.portfolio_report` after `rai models deploy --path model`. Prints the
compliance flags, the correlation clusters and representatives, the status and result of the
two anchor solves, the sensitivity-guided frontier of the grid, adaptive, and dichotomic
drivers compared by approximation quality, the per-scenario efficient frontier with its knee,
the base-versus-crisis volatility, and the knee portfolio allocations.
"""

import warnings
from dataclasses import dataclass

from model import (
    ADAPTIVE_SOLVES,
    CORR_THRESHOLD,
    CRISIS_ALPHA,
    DICHOTOMIC_SOLVES,
    GRID_SOLVES,
    N_SOLVES,
    POSITION_LIMIT,
    REFERENCE_SCENARIO,
    SECTOR_LIMIT,
    Account,
    FrontierPoint,
    Holding,
    Regime,
    Scenario,
    Sector,
    SolveStatus,
    Stock,
    User,
    model,
)
from pandas import DataFrame
from relationalai.semantics import Float, String
from relationalai.semantics.std import aggregates as aggs


@dataclass(frozen=True)
class Point:
    """One efficient-frontier portfolio for the reference scenario."""

    solve: str  # the solve that produced it
    ret: float  # achieved expected return (absolute level, not a rate) -- frontier x-coordinate
    variance: float  # portfolio variance -- the value function at this return target
    shadow_price: (
        float  # dual of the return floor = local frontier slope d(variance)/d(return)
    )


def pair_gap(a, b):
    """Chord-vs-tangent gap between two points on the convex frontier, and the tangent
    crossover eps* where it peaks. The value function lies below the chord between two
    points and above each point's supporting tangent (slope = its shadow price). At eps*
    the two tangents cross, so the gap there is chord - tangent >= 0 (either tangent gives
    the same value at the crossover). eps* is also the best place to sample next."""
    de = b.ret - a.ret
    if de <= 1e-9:
        return 0.0, 0.5 * (a.ret + b.ret)
    dl = b.shadow_price - a.shadow_price
    if dl <= 1e-9:  # locally linear: tangents ~parallel, chord hugs them -> ~0 gap
        estar = 0.5 * (a.ret + b.ret)
    else:
        estar = (
            a.variance - a.shadow_price * a.ret - b.variance + b.shadow_price * b.ret
        ) / dl
        estar = min(max(estar, a.ret), b.ret)
    chord = a.variance + (b.variance - a.variance) / de * (estar - a.ret)
    tangent = a.variance + a.shadow_price * (estar - a.ret)
    return max(chord - tangent, 0.0), estar


def max_gap(points):
    return max(
        (pair_gap(points[i], points[i + 1])[0] for i in range(len(points) - 1)),
        default=0.0,
    )


def dedupe(points):
    """Sort by return; drop points that collapse onto a neighbour so the frontier is
    strictly increasing in return."""
    out = []
    for p in sorted(points, key=lambda q: q.ret):
        if not out or p.ret - out[-1].ret > 1e-6:
            out.append(p)
    return out


if __name__ == "__main__":
    # ==================================================
    # STAGE 1: Rules -- Compliance Analysis
    # ==================================================

    print("=" * 70)
    print("STAGE 1: COMPLIANCE ANALYSIS (rules)")
    print("=" * 70)

    # ---- Rule 1: Overconcentrated Holdings ----
    StockQ1 = Stock.ref()
    AccountQ1 = Account.ref()
    overconc_df = (
        model.select(
            Holding.holding_id.alias("holding_id"),
            StockQ1.ticker.alias("ticker"),
            AccountQ1.account_id.alias("account_id"),
            Holding.value.alias("value"),
            AccountQ1.balance.alias("balance"),
        )
        .where(
            Holding.is_overconcentrated(),
            Holding.stock(StockQ1),
            Holding.account(AccountQ1),
        )
        .to_df()
    )

    print(
        f"\n--- Rule 1: Overconcentrated Holdings "
        f"(position > {POSITION_LIMIT:.0%} of balance) ---\n"
    )
    if overconc_df.empty:
        print("  No overconcentrated holdings found.")
    else:
        for _, row in overconc_df.iterrows():
            print(
                f"  holding_id={int(row['holding_id'])}, ticker={row['ticker']}, "
                f"account_id={int(row['account_id'])}, "
                f"value={row['value']:.2f}, balance={row['balance']:.2f}, "
                f"pct={row['value'] / row['balance']:.1%}"
            )

    # ---- Rule 2: Sector Concentration ----
    StockQ2 = Stock.ref()
    AccountQ2 = Account.ref()
    SectorQ2 = Sector.ref()
    HoldingQ2 = Holding.ref()

    sector_df = (
        model.select(
            AccountQ2.account_id.alias("account_id"),
            SectorQ2.sector_name.alias("sector"),
            aggs.sum(HoldingQ2.value).per(AccountQ2, SectorQ2).alias("sector_value"),
            AccountQ2.balance.alias("balance"),
        )
        .where(
            HoldingQ2.is_sector_concentrated(),
            HoldingQ2.account(AccountQ2),
            HoldingQ2.stock(StockQ2),
            StockQ2.sector_ref(SectorQ2),
        )
        .to_df()
        .drop_duplicates(subset=["account_id", "sector"])
    )

    print(
        f"\n--- Rule 2: Sector Concentration "
        f"(sector > {SECTOR_LIMIT:.0%} of balance) ---\n"
    )
    if sector_df.empty:
        print("  No sector concentration violations found.")
    else:
        for _, row in sector_df.iterrows():
            print(
                f"  account_id={int(row['account_id'])}, sector={row['sector']}, "
                f"sector_value={row['sector_value']:.2f}, "
                f"balance={row['balance']:.2f}, "
                f"pct={row['sector_value'] / row['balance']:.1%}"
            )

    # ---- Rule 3: High-Risk Traders ----
    high_risk_df = (
        model.select(
            User.user_id.alias("user_id"),
            User.user_name.alias("name"),
            User.risk_score.alias("risk_score"),
        )
        .where(User.is_high_risk_trader())
        .to_df()
    )

    print(
        "\n--- Rule 3: High Risk Traders (risk_score > 0.8 AND >5 flagged txns) ---\n"
    )
    if high_risk_df.empty:
        print("  No high-risk traders found.")
    else:
        for _, row in high_risk_df.iterrows():
            print(
                f"  user_id={int(row['user_id'])}, name={row['name']}, "
                f"risk_score={row['risk_score']:.2f}"
            )

    # ==================================================
    # STAGE 2: Graph -- Covariance Clustering
    # ==================================================

    print(f"\n{'=' * 70}")
    print("STAGE 2: GRAPH -- Covariance Clustering (Louvain)")
    print("=" * 70)

    StockQ3 = Stock.ref()
    cluster_df = model.select(
        StockQ3.index.alias("stock_index"),
        StockQ3.ticker.alias("ticker"),
        StockQ3.sector.alias("sector"),
        StockQ3.cluster.alias("cluster_id"),
    ).to_df()
    num_clusters = cluster_df["cluster_id"].nunique()

    # Query the derived correlation property for stats and edge count.
    StockCQ = Stock.ref()
    PairedCQ = Stock.ref()
    corr_q_ref = Float.ref()
    corr_df = (
        model.select(
            StockCQ.index.alias("i"),
            PairedCQ.index.alias("j"),
            corr_q_ref.alias("correlation"),
        )
        .where(StockCQ.correlation(PairedCQ, corr_q_ref))
        .to_df()
    )
    corr_df["correlation"] = corr_df["correlation"].astype(float)
    # Upper triangle only (i < j) -- correlation is symmetric.
    upper_corr = corr_df[corr_df["i"] < corr_df["j"]].copy()
    num_edges = int((upper_corr["correlation"].abs() >= CORR_THRESHOLD).sum())

    print(
        f"\n  Correlation graph: {num_edges} edges (|correlation| >= {CORR_THRESHOLD})"
    )
    print(f"  Louvain communities: {num_clusters} cluster(s)")
    for cid, group in cluster_df.sort_values("cluster_id").groupby("cluster_id"):
        members = ", ".join(
            f"{row['ticker']} ({row['sector']})" for _, row in group.iterrows()
        )
        print(f"    Cluster {cid} (size {len(group)}): {members}")

    # Intra- vs inter-cluster average correlation (from the derived property).
    cluster_map = dict(zip(cluster_df["stock_index"], cluster_df["cluster_id"]))
    is_intra = upper_corr.apply(
        lambda r: cluster_map.get(int(r["i"])) == cluster_map.get(int(r["j"])), axis=1
    )
    intra_series = upper_corr.loc[is_intra, "correlation"]
    inter_series = upper_corr.loc[~is_intra, "correlation"]
    intra_avg = float(intra_series.mean()) if len(intra_series) else 0.0
    inter_avg = float(inter_series.mean()) if len(inter_series) else 0.0
    print(
        f"\n  Avg correlation: intra-cluster = {intra_avg:+.3f}, "
        f"inter-cluster = {inter_avg:+.3f}"
    )

    # Cluster representatives -- the investable universe after redundancy removal.
    RepStock = Stock.ref()
    rep_df = (
        model.select(
            RepStock.cluster.alias("cluster_id"),
            RepStock.ticker.alias("ticker"),
            RepStock.sector.alias("sector"),
            RepStock.sharpe.alias("sharpe"),
        )
        .where(RepStock.is_representative())
        .to_df()
        .sort_values("cluster_id")
    )
    print(
        f"\n  Cluster representatives ({len(rep_df)} of {len(cluster_df)} stocks, "
        f"picked by highest Sharpe):"
    )
    for _, row in rep_df.iterrows():
        print(
            f"    Cluster {int(row['cluster_id'])}: {row['ticker']} "
            f"({row['sector']}) -- Sharpe = {float(row['sharpe']):.3f}"
        )

    # ==================================================
    # STAGE 3: Bi-Objective Optimization (base + crisis)
    # ==================================================

    # Scenario budget and regime.
    ScenarioQ = Scenario.ref()
    RegimeQ = Regime.ref()
    scenario_df = (
        model.select(
            ScenarioQ.name.alias("name"),
            ScenarioQ.budget.alias("budget"),
            RegimeQ.regime_name.alias("regime"),
        )
        .where(ScenarioQ.regime(RegimeQ))
        .to_df()
    )
    scenario_meta = {
        row["name"]: {"budget": float(row["budget"]), "regime": row["regime"]}
        for _, row in scenario_df.iterrows()
    }
    scenario_names = sorted(
        scenario_meta,
        key=lambda n: (scenario_meta[n]["regime"], scenario_meta[n]["budget"]),
    )
    budgets = sorted({meta["budget"] for meta in scenario_meta.values()})

    # Status of every solve.
    solve_ref = String.ref()
    status_ref = String.ref()
    status_df = (
        model.select(solve_ref.alias("solve"), status_ref.alias("status"))
        .where(SolveStatus(solve_ref, status_ref))
        .to_df()
    )
    status = dict(zip(status_df["solve"], status_df["status"]))
    failed = {name: s for name, s in status.items() if s not in ("OPTIMAL", "LOCALLY_SOLVED")}
    if failed:
        raise SystemExit(f"termination status {failed}")

    # Every solve's return, risk (variance), and shadow price per scenario. The min-risk
    # anchor declares no return floor, so it has no shadow price and its dual is 0.
    return_risk_df = model.select(
        FrontierPoint.scenario_label.alias("scenario"),
        FrontierPoint.solve.alias("solve"),
        FrontierPoint.return_value.alias("ret"),
        FrontierPoint.risk.alias("risk"),
    ).to_df()
    marginal_df = model.select(
        FrontierPoint.scenario_label.alias("scenario"),
        FrontierPoint.solve.alias("solve"),
        FrontierPoint.marginal_risk_per_return.alias("marginal"),
    ).to_df()
    solves = return_risk_df.merge(
        marginal_df, on=["scenario", "solve"], how="left"
    ).set_index(["solve", "scenario"])

    # Every solve publishes one point per scenario; a missing point means that solve
    # returned no solution (infeasible, or the solver handed back an empty result).
    expected_solves = [
        "min_risk",
        "max_return",
        "hi",
        *GRID_SOLVES,
        *ADAPTIVE_SOLVES,
        *DICHOTOMIC_SOLVES,
    ]
    missing = [
        name
        for name in expected_solves
        if name not in status
        or any((name, sn) not in solves.index for sn in scenario_names)
    ]
    if missing:
        raise SystemExit(f"Frontier solve(s) {missing} returned no solution.")

    # Every solve with a return floor should report the floor's shadow price. Without it
    # the point shows a 0 marginal, and the drivers that steer by it lose their guide.
    no_duals = sorted(
        {name for name, _ in solves.index[solves["marginal"].isna()]}
        - {"min_risk", "max_return"}
    )
    if no_duals:
        warnings.warn(
            f"Solve(s) {no_duals} returned no sensitivity duals for the return floor "
            "(e.g. a time-limit exit); their shadow prices show as 0, and the adaptive "
            "and dichotomic frontiers may be incomplete.",
            stacklevel=1,
        )
    solves = solves.fillna({"marginal": 0.0})

    # Stock amounts of every solve, above the solver's 1e-6 noise floor.
    amount_ref = Float.ref()
    allocation_df = (
        model.select(
            FrontierPoint.scenario_label.alias("scenario"),
            FrontierPoint.solve.alias("solve"),
            Stock.ticker.alias("ticker"),
            amount_ref.alias("amount"),
        )
        .where(FrontierPoint.allocates(Stock, amount_ref))
        .to_df()
    )

    print(f"\n{'=' * 70}")
    print("STAGE 3: BI-OBJECTIVE OPTIMIZATION")
    print(
        "(position + sector limits on representative universe; base & crisis regimes)"
    )
    print("=" * 70)

    print("\nANCHOR SOLVE 1: Minimize risk (no return constraint)")
    print("-" * 50)
    print(f"Status: {status['min_risk']}")
    for sn in scenario_names:
        ret, risk = solves.loc[("min_risk", sn), ["ret", "risk"]]
        print(f"  {sn}: return = {ret:.4f}, risk = {risk:.6f}")

    print("\nANCHOR SOLVE 2: Maximize return (swap objective)")
    print("-" * 50)
    print(f"Status: {status['max_return']}")
    for sn in scenario_names:
        print(f"  {sn}: return = {solves.loc[('max_return', sn), 'ret']:.4f}")

    # --------------------------------------------------
    # Sensitivity-guided efficient frontier
    # --------------------------------------------------
    # Each driver's solves price ALL scenarios at once, but the smart drivers (adaptive,
    # dichotomic) steer by a single reference frontier (mid-budget, base regime).

    def point(solve):
        """The reference scenario's point of a solve."""
        ret, risk, marginal = solves.loc[
            (solve, REFERENCE_SCENARIO), ["ret", "risk", "marginal"]
        ]
        return Point(solve, float(ret), float(risk), max(0.0, float(marginal)))

    RETURN_LO = float(solves.loc[("min_risk", REFERENCE_SCENARIO), "ret"])
    RETURN_HI = float(solves.loc[("max_return", REFERENCE_SCENARIO), "ret"])
    lo = point("min_risk")
    hi = point("hi")
    print(
        f"\nReference scenario '{REFERENCE_SCENARIO}': frontier spans expected return "
        f"[{RETURN_LO:.4f}, {RETURN_HI:.4f}]"
    )

    # Three drivers, each the SAME solve budget N (2 shared anchors + N-2 interior); they
    # differ only in how they pick the next return target.
    print(f"\n{'=' * 70}")
    print(
        f"SENSITIVITY-GUIDED FRONTIER  (reference '{REFERENCE_SCENARIO}', "
        f"{N_SOLVES}-solve budget per method)"
    )
    print(f"{'=' * 70}")
    methods = {
        "grid": dedupe([lo, *map(point, GRID_SOLVES), hi]),
        "adaptive": dedupe([lo, *map(point, ADAPTIVE_SOLVES), hi]),
        "dichotomic": dedupe([lo, hi, *map(point, DICHOTOMIC_SOLVES)]),
    }

    # The headline result: at equal solve budget, using the dual to place samples shrinks
    # the worst chord-vs-tangent gap. On a smooth convex frontier (like the bundled data)
    # using it globally (dichotomic) wins -- but that ordering is an empirical expectation,
    # not a theorem: on a near-linear or dual-degenerate frontier the advantage can shrink.
    gaps = {m: max_gap(pts) for m, pts in methods.items()}
    print("\nFrontier approximation quality (same solve budget, lower gap = better):")
    print(f"  {'method':<12}{'solves':>8}{'max chord-gap':>18}")
    print("  " + "-" * 38)
    best = min(gaps.values())
    for m, pts in methods.items():
        flag = "  <- tightest" if gaps[m] == best else ""
        print(f"  {m:<12}{len(pts):>8}{gaps[m]:>18.4f}{flag}")
    # Inform rather than abort: dual-guided beating blind grid is the expected result on the
    # bundled data, but it is not invariant under user data swaps, so a violation is a notice
    # (your frontier is near-linear or degenerate), not a failure of the template.
    if gaps["dichotomic"] > gaps["grid"] + 1e-9:
        warnings.warn(
            f"dichotomic gap ({gaps['dichotomic']:.3e}) exceeds grid ({gaps['grid']:.3e}) at "
            "equal budget. On the bundled data the dual-guided driver is tightest; on a near-"
            "linear or dual-degenerate frontier (e.g. after swapping in your own returns/"
            "covariance) that advantage can shrink or invert. Informational, not an error.",
            stacklevel=2,
        )

    # The shadow price IS the frontier slope: show each point's exact dual next to the
    # finite-difference secant between consecutive points. The secant is bracketed by the
    # two duals -- which is why no finite differencing is needed to recover each point's slope.
    print("\nShadow price = frontier slope (exact dual vs finite-difference secant):")
    print("  (dual = extra variance incurred per unit of additional required return)")
    print(f"  {'return':>10}{'variance':>14}{'dual (lambda)':>16}{'secant':>14}")
    print("  " + "-" * 54)
    dpts = methods["dichotomic"]
    for j, p in enumerate(dpts):
        if j == 0:
            secant_str = f"{'--':>14}"
        else:
            sec = (p.variance - dpts[j - 1].variance) / (p.ret - dpts[j - 1].ret)
            secant_str = f"{sec:>14.2f}"
        print(f"  {p.ret:>10.4f}{p.variance:>14.4f}{p.shadow_price:>16.2f}{secant_str}")

    # ==================================================
    # STAGE 4: Crisis Regime Stress Test
    # ==================================================

    print(f"\n{'=' * 70}")
    print("STAGE 4: CRISIS REGIME STRESS TEST")
    print(f"(PSD-preserving correlation shrinkage, alpha = {CRISIS_ALPHA})")
    print("=" * 70)

    # Production frontier: the dichotomic points for EVERY scenario (each solve already
    # priced all scenarios). The marginals (exact shadow prices) drove the search.
    prod_points = methods[
        "dichotomic"
    ]  # already deduped + sorted by return (reference scenario)

    fp_rows = []
    for sn in scenario_names:
        slopes = []
        rows_for_sn = []
        for k, p in enumerate(prod_points):
            ret, risk, marginal = solves.loc[(p.solve, sn), ["ret", "risk", "marginal"]]
            # k=0 is the min-variance anchor, whose dual is 0.
            label = "min_risk" if k == 0 else f"p{k}"
            marginal = float(marginal)  # EXACT dual; 0 at the min-risk anchor
            slopes.append(marginal)
            rows_for_sn.append(
                {
                    "scenario_label": sn,
                    "eps_label": label,
                    "solve": p.solve,
                    "k": k,
                    "return": float(ret),
                    "risk": float(risk),
                    "marginal_risk_per_return": marginal,
                    "is_knee": False,
                }
            )
        # Knee = the last point before the frontier slope accelerates most: the largest RATIO
        # jump between consecutive exact duals (lambda_j / lambda_{j-1}), marking point j-1 so
        # "cost jumps beyond this point". This applies the ratio-knee principle from
        # rai-prescriptive-results ("Knee from the exact dual sequence") to the exact
        # duals rather than finite-difference secants -- the knee is NOT where the absolute slope is
        # highest (that is always the last point). The min-risk anchor (k=0) declares no return
        # floor so its dual is structurally 0; the scan starts at j=2 to skip that 0->lambda_1
        # transition, whose "jump" would be an absolute magnitude rather than a rate-of-change.
        knee_idx, max_jump = None, 0.0
        for j in range(2, len(slopes)):
            prev, curr = slopes[j - 1], slopes[j]
            if prev <= 1e-9:
                continue
            jump = curr / prev
            if jump > max_jump:
                max_jump, knee_idx = jump, j - 1
        if knee_idx is not None:
            rows_for_sn[knee_idx]["is_knee"] = True
        fp_rows.extend(rows_for_sn)

    # Pair base and crisis rows by (budget, eps_label) so vol_base / vol_crisis carry on
    # BOTH the base-regime row and its matching crisis-regime row.
    risk_by_key = {(r["scenario_label"], r["eps_label"]): r["risk"] for r in fp_rows}
    for r in fp_rows:
        budget_suffix = r["scenario_label"].split("_", 1)[1]
        base_risk = risk_by_key.get((f"base_{budget_suffix}", r["eps_label"]))
        crisis_risk = risk_by_key.get((f"crisis_{budget_suffix}", r["eps_label"]))
        vol_base = base_risk**0.5 if base_risk is not None else 0.0
        vol_crisis = crisis_risk**0.5 if crisis_risk is not None else 0.0
        vol_gap = vol_crisis - vol_base
        r["vol_base"] = vol_base
        r["vol_crisis"] = vol_crisis
        r["vol_gap"] = vol_gap
        r["vol_gap_pct"] = (vol_gap / vol_base * 100.0) if vol_base > 1e-9 else 0.0

    frontier_df = DataFrame(fp_rows).sort_values(["scenario_label", "k"])

    # Along a Pareto-efficient frontier neither return nor risk decreases, so no point
    # dominates another. The interior targets come from the reference scenario only, so
    # under the crisis covariance two adjacent points can price out (near-)equal: the
    # check allows a small relative slack and stops on an actual decrease beyond it.
    MONOTONIC_TOL = 1e-4
    violations = []
    for sn, sub in frontier_df.groupby("scenario_label"):
        rows = sub.to_dict("records")
        for a, b in zip(rows, rows[1:]):
            if b["return"] < (1.0 - MONOTONIC_TOL) * a["return"] or b["risk"] < (
                1.0 - MONOTONIC_TOL
            ) * a["risk"]:
                violations.append(f"{sn} {a['eps_label']}->{b['eps_label']}")
    if violations:
        raise SystemExit(f"Frontier points decrease in return or risk: {violations}")

    # --------------------------------------------------
    # Efficient frontier per scenario (exact dual marginals)
    # --------------------------------------------------
    print(f"\n{'=' * 70}")
    print("EFFICIENT FRONTIER: Risk vs Return (per scenario, exact dual marginals)")
    print(f"{'=' * 70}")
    for sn in scenario_names:
        sub = frontier_df[frontier_df["scenario_label"] == sn]
        if len(sub) < 2:
            continue
        meta = scenario_meta[sn]
        print(f"\n  {sn} (budget={meta['budget']:.0f}, regime={meta['regime']}):")
        print(
            f"  {'#':>3} {'Label':>9} {'Return':>10} {'Risk':>12} {'Marginal':>11} {'Knee':>6}"
        )
        print(f"  {'-' * 56}")
        for _, row in sub.iterrows():
            knee = "  <--" if bool(row["is_knee"]) else ""
            print(
                f"  {int(row['k']) + 1:>3} {row['eps_label']:>9} "
                f"{float(row['return']):>10.2f} {float(row['risk']):>12.4f} "
                f"{float(row['marginal_risk_per_return']):>11.2f}{knee}"
            )

    # --------------------------------------------------
    # Volatility comparison: base vs crisis at each frontier point
    # --------------------------------------------------
    print("\n  Volatility (sqrt risk) -- base vs crisis at each frontier point:")
    for budget in budgets:
        base_rows = frontier_df[
            frontier_df["scenario_label"] == f"base_{budget:.0f}"
        ].sort_values("k")
        if base_rows.empty:
            continue
        print(f"\n  Budget {budget:.0f}:")
        print(
            f"  {'Label':>9} {'vol_base':>12} {'vol_crisis':>12} {'gap':>10} {'gap_%':>8}"
        )
        print(f"  {'-' * 55}")
        for _, row in base_rows.iterrows():
            print(
                f"  {row['eps_label']:>9} {float(row['vol_base']):>12.4f} "
                f"{float(row['vol_crisis']):>12.4f} {float(row['vol_gap']):>+10.4f} "
                f"{float(row['vol_gap_pct']):>+7.1f}%"
            )

    print(
        "\n  Expected pattern: crisis vol > base vol at every point; the gap peaks in the\n"
        "  middle of the frontier and narrows toward the concentrated (high-return) end.\n"
        "  Because Stage 2 already deduplicated the universe, the concentrated end picks\n"
        "  the highest-Sharpe distinct bet per cluster rather than stacking near-\n"
        "  duplicates, so the crisis gap shrinks there instead of widening."
    )

    # --------------------------------------------------
    # Candidate allocations at each scenario's knee
    # --------------------------------------------------
    print(f"\n{'=' * 38}")
    print("KNEE PORTFOLIO ALLOCATIONS BY SCENARIO")
    print("=" * 38)

    for sn in scenario_names:
        knee_rows = frontier_df[
            (frontier_df["scenario_label"] == sn) & frontier_df["is_knee"]
        ]
        if len(knee_rows) != 1:
            print(
                f"\n  {sn}: No unique knee point was found. "
                "Choose a point from the frontier table above."
            )
            continue

        knee_row = knee_rows.iloc[0]
        knee_allocation = allocation_df[
            (allocation_df["scenario"] == sn)
            & (allocation_df["solve"] == knee_row["solve"])
        ]
        allocations = dict(zip(knee_allocation["ticker"], knee_allocation["amount"]))

        meta = scenario_meta[sn]
        budget = meta["budget"]
        volatility = float(knee_row["risk"]) ** 0.5
        print(
            f"\n  {sn} (budget={budget:.0f}, regime={meta['regime']}, point={knee_row['eps_label']})"
        )
        print(
            f"  expected return={float(knee_row['return']):.2f}, "
            f"volatility={volatility:.2f}"
        )
        print(f"  {'Ticker':<8}{'Amount':>12}{'Weight':>10}")
        print(f"  {'-' * 30}")
        ordered_allocations = sorted(
            allocations.items(),
            key=lambda item: (-item[1], item[0]),
        )
        for ticker, quantity in ordered_allocations:
            print(
                f"  {ticker:<8}{float(quantity):>12.2f}{float(quantity) / budget:>9.1%}"
            )

    print(
        "\n  Each knee is a candidate portfolio, not a recommendation. "
        "The amounts apply to\n"
        "  the sample scenario, not to a specific account."
    )
