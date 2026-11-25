"""Allocation report: reads the deployed datacenter compute allocation model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.allocation_report

Prints per-stage diagnostics -- ontology load summary, per-workload
utilization probabilities (top / bottom 5 + n>=0.5 count), Compatibility
table size and P0/P1/P2 priority counts, top-10 gating workloads by
downstream reach -- then the status, time and objective of the latest
refresh's solve, the per-cell summary table (INFEASIBLE cells are designed
diagnostic signal; UNSOLVED when the solve stops at its time limit), two Pareto
frontiers (margin x revenue and diversity x revenue at the 100pct envelope),
the AllocationPlan row, and the DemandScenario overlay replaying the chosen
plan under risk scenarios (expected / diffusion_slowdown / scaling_break /
frontier_loss) with realized + stranded revenue.
"""

import pandas as pd
from model import (
    CHOSEN_DIVERSITY,
    CHOSEN_ENVELOPE,
    CHOSEN_MARGIN,
    HIGH_UTILIZATION,
    PRIORITY_TIERS,
    WORKLOAD_TYPES,
    AILab,
    AllocationPlan,
    Assignment,
    CellStatusCount,
    Compatibility,
    DataCenterRequest,
    DemandScenario,
    DemandScenarioOutlook,
    DiversityCap,
    GatingRank,
    GpuPool,
    MarginFloor,
    PowerEnvelopeLevel,
    PriorityTierCount,
    ScenarioCell,
    SolveObjective,
    SolveStatus,
    SolveTime,
    UtilizationSplit,
    Workload,
    WorkloadDependency,
    WorkloadForecast,
    model,
)
from relationalai.semantics import Integer, String, count, select

CELL_KEYS = ["envelope", "margin", "diversity"]
CELL_KEY_COLUMNS = [
    ScenarioCell.envelope.name.alias("envelope"),
    ScenarioCell.margin.name.alias("margin"),
    ScenarioCell.diversity.name.alias("diversity"),
]
TOP_FORECASTS = 5
TOP_GATING = 10


def banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def stage_0_ontology() -> None:
    banner("STAGE 0: ONTOLOGY")
    n = select(
        count(DataCenterRequest).alias("dcs"),
        count(AILab).alias("labs"),
        count(GpuPool).alias("pools"),
        count(Workload).alias("workloads"),
        count(WorkloadDependency).alias("deps"),
        count(PowerEnvelopeLevel).alias("envelopes"),
        count(MarginFloor).alias("margins"),
        count(DiversityCap).alias("diversities"),
        count(ScenarioCell).alias("cells"),
    ).to_df().iloc[0]
    print(f"  Loaded {int(n['dcs'])} DataCenterRequest entries")
    print(f"  Ontology loaded: {int(n['labs'])} labs, {int(n['pools'])} pools, "
          f"{int(n['workloads'])} workloads, {int(n['deps'])} dep edges, "
          f"{int(n['envelopes'])}x{int(n['margins'])}x{int(n['diversities'])}={int(n['cells'])} "
          f"scenario cells")


def forecast_extremes(rank_property):
    """The TOP_FORECASTS workloads with the lowest `rank_property` of the forecast, rank first."""
    return (
        select(
            Workload.name.alias("name"),
            WorkloadForecast.utilization_probability.alias("p"),
            rank_property.alias("rank"),
        )
        .where(WorkloadForecast.workload_id == Workload.id, rank_property <= TOP_FORECASTS)
        .to_df()
        .sort_values("rank")
    )


def stage_1_predictive() -> bool:
    banner("STAGE 1: PREDICT -- per-workload utilization-probability GNN")
    total_ref, high_ref, low_ref = Integer.ref(), Integer.ref(), Integer.ref()
    split = (
        select(total_ref.alias("n_total"), high_ref.alias("n_high"), low_ref.alias("n_low"))
        .where(UtilizationSplit(total_ref, high_ref, low_ref))
        .to_df()
    )
    if split.empty:
        print("  (no predictions returned) Run `python train.py`, then refresh the deployed model.")
        return False
    n_total, n_high, n_low = (int(split[c].iloc[0]) for c in ("n_total", "n_high", "n_low"))
    print(f"  Workload utilization-probability distribution: "
          f"n_total={n_total}, n>={HIGH_UTILIZATION}: {n_high}, n<{HIGH_UTILIZATION}: {n_low}")
    print(f"  Top {TOP_FORECASTS} (most likely to be high-utilization):")
    for _, r in forecast_extremes(WorkloadForecast.high_rank).iterrows():
        print(f"    + {r['name']:<45} p={float(r['p']):.3f}")
    print(f"  Bottom {TOP_FORECASTS} (most likely to stall / be repaced):")
    for _, r in forecast_extremes(WorkloadForecast.low_rank).iterrows():
        print(f"    - {r['name']:<45} p={float(r['p']):.3f}")
    return True


def stage_2_rules() -> None:
    banner("STAGE 2: RULES -- eligibility + priority classification")
    n_compat = int(select(count(Compatibility).alias("n")).to_df()["n"].iloc[0])
    tier, n_workloads = String.ref(), Integer.ref()
    tier_counts = (
        select(tier.alias("tier"), n_workloads.alias("n"))
        .where(PriorityTierCount(n_workloads, tier))
        .to_df()
    )
    print(f"  Compatibility table: {n_compat} eligible (Workload, GpuPool) pairs")
    print("  Priority tier counts:")
    for _, r in tier_counts.sort_values("tier").iterrows():
        print(f"    {r['tier']}: {int(r['n'])} workloads")


def stage_3_graph() -> None:
    banner("STAGE 3: GRAPH -- workload-dependency PageRank (gating score)")
    top = (
        select(
            Workload.name.alias("name"),
            GatingRank.gating_score.alias("gating_score"),
            GatingRank.gating_rank.alias("rank"),
        )
        .where(GatingRank.workload_id == Workload.id, GatingRank.gating_rank <= TOP_GATING)
        .to_df()
        .sort_values("rank")
    )
    print(f"  Top-{TOP_GATING} gating workloads (frontier pretrains expected to dominate):")
    for _, r in top.iterrows():
        print(f"    {r['name']:<45} score={float(r['gating_score']):.4f}")


def cell_table() -> pd.DataFrame:
    """One row per scenario cell: status, aggregates (0 when the cell has no assignments), and counts."""
    cells_df = select(*CELL_KEY_COLUMNS, ScenarioCell.status.alias("status")).to_df()
    for col, prop in (
        ("n_assigned", ScenarioCell.n_assigned),
        ("revenue_usd", ScenarioCell.revenue_usd),
        ("anchor_revenue_usd", ScenarioCell.anchor_revenue_usd),
        ("total_cost_usd", ScenarioCell.total_cost_usd),
        ("realized_margin", ScenarioCell.realized_margin),
        ("anchor_share", ScenarioCell.anchor_share),
    ):
        part = select(*CELL_KEY_COLUMNS, prop.alias(col)).to_df()
        cells_df = cells_df.merge(part, on=CELL_KEYS, how="left")
    for col in ("n_assigned", "revenue_usd", "anchor_revenue_usd", "total_cost_usd"):
        cells_df[col] = cells_df[col].fillna(0)

    kind, count_ref = String.ref(), Integer.ref()
    for relationship, kinds in (
        (ScenarioCell.n_by_type, WORKLOAD_TYPES),
        (ScenarioCell.n_by_tier, PRIORITY_TIERS),
    ):
        part = select(*CELL_KEY_COLUMNS, kind.alias("kind"), count_ref.alias("n")).where(
            relationship(kind, count_ref)
        ).to_df()
        wide = part.pivot_table(index=CELL_KEYS, columns="kind", values="n", aggfunc="sum").reset_index()
        wide = wide[CELL_KEYS + list(kinds)].rename(columns={k: f"n_{k}" for k in kinds})
        cells_df = cells_df.merge(wide, on=CELL_KEYS, how="left")
        for k in kinds:
            cells_df[f"n_{k}"] = cells_df[f"n_{k}"].astype(int)
    return cells_df.sort_values(CELL_KEYS)


def status_counts(statuses: pd.Series) -> pd.Series:
    """Cells per status label from the model, most first; ties keep the order in which their
    labels first appear in `statuses`."""
    status, n_cells = String.ref(), Integer.ref()
    by_status = (
        select(status.alias("status"), n_cells.alias("n"))
        .where(CellStatusCount(n_cells, status))
        .to_df()
        .set_index("status")["n"]
    )
    order = pd.Index(statuses.drop_duplicates(), name="status")
    return by_status.reindex(order).astype(int).sort_values(ascending=False, kind="stable")


def sweep_cells(cells_df: pd.DataFrame, in_sweep) -> pd.DataFrame:
    """The rows of the cell table for the cells the model places in the sweep `in_sweep`."""
    members = select(*CELL_KEY_COLUMNS).where(in_sweep()).to_df()
    return cells_df.merge(members, on=CELL_KEYS)


def stage_4_prescriptive() -> None:
    banner("STAGE 4: PRESCRIPTIVE -- compute allocation MIP (24-cell sweep)")
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    seconds = model.select(SolveTime).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print("  Latest refresh's solve of the 24-cell scenario sweep:")
    print(f"  Termination status: {', '.join(status)}")
    if seconds:
        print(f"  Solve time:         {float(seconds[0]):.1f}s")
    if objective:
        print(f"  Objective:          {float(objective[0]):,.2f}")
    if status == ["TIME_LIMIT"]:
        print("  Note: TIME_LIMIT means the solve stopped at its time limit; the per-cell "
              "results below are its best solution found, not proven optimal.")

    cells_df = cell_table()
    if cells_df.empty:
        print("  No scenario cells returned.")
        return
    labels = status_counts(cells_df["status"])
    summary = ", ".join(f"{n} {label.lower()}" for label, n in labels.items())
    print(f"\n  Per-cell summary ({len(cells_df)} cells: {summary}):")
    display_cols = (
        CELL_KEYS + ["status", "n_assigned", "revenue_usd", "total_cost_usd",
                     "realized_margin", "anchor_share"]
        + [f"n_{wt}" for wt in WORKLOAD_TYPES]
        + [f"n_{pt}" for pt in PRIORITY_TIERS]
    )
    print(cells_df[display_cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # Two headline Pareto frontiers, both at the headline envelope.
    print(f"\n  Pareto frontier 1: Margin floor <-> Revenue (envelope={CHOSEN_ENVELOPE}, "
          f"diversity={CHOSEN_DIVERSITY})")
    p1 = sweep_cells(cells_df, ScenarioCell.in_margin_sweep).sort_values("margin")
    if len(p1):
        print(p1[["margin", "n_assigned", "revenue_usd", "realized_margin",
                  "anchor_share"]].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    print(f"\n  Pareto frontier 2: Diversity cap <-> Revenue (envelope={CHOSEN_ENVELOPE}, "
          f"margin={CHOSEN_MARGIN})")
    p2 = sweep_cells(cells_df, ScenarioCell.in_diversity_sweep).sort_values("diversity")
    if len(p2):
        print(p2[["diversity", "n_assigned", "revenue_usd", "realized_margin",
                  "anchor_share"] + [f"n_{wt}" for wt in WORKLOAD_TYPES]
              ].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    plan_df = select(
        AllocationPlan.id.alias("plan_id"),
        AllocationPlan.chosen_envelope.alias("envelope"),
        AllocationPlan.chosen_margin.alias("margin"),
        AllocationPlan.chosen_diversity.alias("diversity"),
        AllocationPlan.status.alias("status"),
        AllocationPlan.n_assigned.alias("n_assigned"),
        AllocationPlan.revenue_usd.alias("revenue_usd"),
        AllocationPlan.total_cost_usd.alias("total_cost_usd"),
        AllocationPlan.binding_axis.alias("binding_axis"),
    ).to_df()
    if plan_df.empty:
        print("\n  AllocationPlan has no summary: the chosen cell has no results.")
        return
    # The margin and anchor share exist only for a plan with revenue, so they join on
    # separately and an empty plan still reports its status and counts.
    for col, prop in (
        ("realized_margin", AllocationPlan.realized_margin),
        ("anchor_share", AllocationPlan.anchor_share),
    ):
        part = select(AllocationPlan.id.alias("plan_id"), prop.alias(col)).to_df()
        plan_df = plan_df.merge(part, on="plan_id", how="left")
    plan_df = plan_df[
        ["plan_id", "envelope", "margin", "diversity", "status", "n_assigned", "revenue_usd",
         "total_cost_usd", "realized_margin", "anchor_share", "binding_axis"]
    ]
    print("\n  AllocationPlan singleton (queryable as ontology):")
    print(plan_df.to_string(index=False))

    chosen = select(count(Assignment).alias("n")).where(Assignment.is_chosen()).to_df()["n"]
    n_chosen = int(chosen.iloc[0]) if len(chosen) else 0
    print(f"  Assignment.is_chosen rows: {n_chosen} (matches n_assigned above)")

    overlay_df = select(
        DemandScenario.name.alias("scenario"),
        DemandScenario.factor.alias("factor"),
        DemandScenarioOutlook.realized_revenue_usd.alias("realized_revenue_usd"),
        DemandScenarioOutlook.stranded_revenue_usd.alias("stranded_revenue_usd"),
        DemandScenarioOutlook.stranded_share.alias("stranded_pct"),
    ).where(DemandScenarioOutlook.scenario == DemandScenario).to_df()
    overlay_df = overlay_df.sort_values("factor", ascending=False).reset_index(drop=True)
    overlay_df["stranded_pct"] = overlay_df["stranded_pct"] * 100.0
    print("\n  DemandScenario overlay (chosen plan replayed under risk):")
    print(overlay_df.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


def main() -> None:
    stage_0_ontology()
    has_predictions = stage_1_predictive()
    stage_2_rules()
    stage_3_graph()
    # Only forecast workloads are assignable, so the allocation needs the predictions.
    if has_predictions:
        stage_4_prescriptive()


if __name__ == "__main__":
    main()
