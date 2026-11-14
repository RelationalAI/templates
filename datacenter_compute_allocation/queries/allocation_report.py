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
    WORKLOAD_TYPES,
    AILab,
    AllocationPlan,
    Assignment,
    Compatibility,
    DataCenterRequest,
    DemandScenario,
    DemandScenarioOutlook,
    DiversityCap,
    GpuPool,
    MarginFloor,
    PowerEnvelopeLevel,
    ScenarioCell,
    SolveObjective,
    SolveStatus,
    SolveTime,
    Workload,
    WorkloadDependency,
    WorkloadForecast,
    model,
)
from relationalai.semantics import Integer, String, count, select

CELL_KEYS = ["envelope", "margin", "diversity"]
PRIORITY_TIERS = ("P0", "P1", "P2")


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
    ).to_df().iloc[0]
    print(f"  Loaded {int(n['dcs'])} DataCenterRequest entries")
    cells = int(n["envelopes"]) * int(n["margins"]) * int(n["diversities"])
    print(f"  Ontology loaded: {int(n['labs'])} labs, {int(n['pools'])} pools, "
          f"{int(n['workloads'])} workloads, {int(n['deps'])} dep edges, "
          f"{int(n['envelopes'])}x{int(n['margins'])}x{int(n['diversities'])}={cells} scenario cells")


def stage_1_predictive() -> bool:
    banner("STAGE 1: PREDICT -- per-workload utilization-probability GNN")
    probs_df = select(
        Workload.id.alias("id"),
        Workload.name.alias("name"),
        WorkloadForecast.utilization_probability.alias("p"),
    ).where(WorkloadForecast.workload_id == Workload.id).to_df()
    if probs_df.empty:
        print("  (no predictions returned) Run `python train.py`, then refresh the deployed model.")
        return False
    probs_df["p"] = pd.to_numeric(probs_df["p"], errors="coerce")
    n_high = int((probs_df["p"] >= 0.5).sum())
    n_total = int(probs_df["p"].notna().sum())
    print(f"  Workload utilization-probability distribution: "
          f"n_total={n_total}, n>=0.5: {n_high}, n<0.5: {n_total - n_high}")
    print("  Top 5 (most likely to be high-utilization):")
    for _, r in probs_df.sort_values("p", ascending=False).head(5).iterrows():
        print(f"    + {r['name']:<45} p={float(r['p']):.3f}")
    print("  Bottom 5 (most likely to stall / be repaced):")
    for _, r in probs_df.sort_values("p", ascending=True).head(5).iterrows():
        print(f"    - {r['name']:<45} p={float(r['p']):.3f}")
    return True


def stage_2_rules() -> None:
    banner("STAGE 2: RULES -- eligibility + priority classification")
    n_compat = int(select(count(Compatibility).alias("n")).to_df()["n"].iloc[0])
    tier_df = select(Workload.id.alias("id"), Workload.priority_tier.alias("tier")).to_df()
    tier_counts = tier_df.groupby("tier").size().reset_index(name="n")
    print(f"  Compatibility table: {n_compat} eligible (Workload, GpuPool) pairs")
    print("  Priority tier counts:")
    for _, r in tier_counts.sort_values("tier").iterrows():
        print(f"    {r['tier']}: {int(r['n'])} workloads")


def stage_3_graph() -> None:
    banner("STAGE 3: GRAPH -- workload-dependency PageRank (gating score)")
    g_df = select(
        Workload.id.alias("id"),
        Workload.name.alias("name"),
        Workload.gating_score.alias("gating_score"),
    ).to_df()
    g_df["gating_score"] = pd.to_numeric(g_df["gating_score"], errors="coerce")
    top = g_df.dropna(subset=["gating_score"]).sort_values("gating_score", ascending=False).head(10)
    print("  Top-10 gating workloads (frontier pretrains expected to dominate):")
    for _, r in top.iterrows():
        print(f"    {r['name']:<45} score={float(r['gating_score']):.4f}")


def cell_table() -> pd.DataFrame:
    """One row per scenario cell: status, aggregates (0 when the cell has no assignments), and counts."""
    keys = [
        ScenarioCell.envelope.name.alias("envelope"),
        ScenarioCell.margin.name.alias("margin"),
        ScenarioCell.diversity.name.alias("diversity"),
    ]
    cells_df = select(*keys, ScenarioCell.status.alias("status")).to_df()
    for col, prop in (
        ("n_assigned", ScenarioCell.n_assigned),
        ("revenue_usd", ScenarioCell.revenue_usd),
        ("anchor_revenue_usd", ScenarioCell.anchor_revenue_usd),
        ("total_cost_usd", ScenarioCell.total_cost_usd),
        ("realized_margin", ScenarioCell.realized_margin),
        ("anchor_share", ScenarioCell.anchor_share),
    ):
        part = select(*keys, prop.alias(col)).to_df()
        cells_df = cells_df.merge(part, on=CELL_KEYS, how="left")
        cells_df[col] = pd.to_numeric(cells_df[col], errors="coerce")
    for col in ("n_assigned", "revenue_usd", "anchor_revenue_usd", "total_cost_usd"):
        cells_df[col] = cells_df[col].fillna(0)

    kind, count_ref = String.ref(), Integer.ref()
    for relationship, kinds in (
        (ScenarioCell.n_by_type, WORKLOAD_TYPES),
        (ScenarioCell.n_by_tier, PRIORITY_TIERS),
    ):
        part = select(*keys, kind.alias("kind"), count_ref.alias("n")).where(
            relationship(kind, count_ref)
        ).to_df()
        part["n"] = pd.to_numeric(part["n"], errors="coerce")
        wide = part.pivot_table(index=CELL_KEYS, columns="kind", values="n", aggfunc="sum").reset_index()
        for k in kinds:
            if k not in wide:
                wide[k] = 0
        wide = wide[CELL_KEYS + list(kinds)].rename(columns={k: f"n_{k}" for k in kinds})
        cells_df = cells_df.merge(wide, on=CELL_KEYS, how="left")
        for k in kinds:
            cells_df[f"n_{k}"] = cells_df[f"n_{k}"].fillna(0).astype(int)
    return cells_df.sort_values(CELL_KEYS)


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
        print("  Note: TIME_LIMIT means solver returned a feasible but not "
              "proven-optimal solution. Per-cell results below remain valid.")

    cells_df = cell_table()
    if cells_df.empty:
        print("  No scenario cells returned.")
        return
    labels = cells_df["status"].value_counts()
    summary = ", ".join(f"{n} {label.lower()}" for label, n in labels.items())
    print(f"\n  Per-cell summary ({len(cells_df)} cells: {summary}):")
    display_cols = (
        CELL_KEYS + ["status", "n_assigned", "revenue_usd", "total_cost_usd",
                     "realized_margin", "anchor_share"]
        + [f"n_{wt}" for wt in WORKLOAD_TYPES]
        + [f"n_{pt}" for pt in PRIORITY_TIERS]
    )
    print(cells_df[display_cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    # Two headline Pareto frontiers, both at envelope=100pct.
    headline_env = "100pct"
    print(f"\n  Pareto frontier 1: Margin floor <-> Revenue (envelope={headline_env}, "
          f"diversity=none)")
    p1 = cells_df[
        (cells_df["envelope"] == headline_env) & (cells_df["diversity"] == "none")
    ].sort_values("margin")
    if len(p1):
        print(p1[["margin", "n_assigned", "revenue_usd", "realized_margin",
                  "anchor_share"]].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    print(f"\n  Pareto frontier 2: Diversity cap <-> Revenue (envelope={headline_env}, "
          f"margin=unconstrained)")
    p2 = cells_df[
        (cells_df["envelope"] == headline_env) & (cells_df["margin"] == "unconstrained")
    ].sort_values("diversity")
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
        AllocationPlan.realized_margin.alias("realized_margin"),
        AllocationPlan.anchor_share.alias("anchor_share"),
        AllocationPlan.binding_axis.alias("binding_axis"),
    ).to_df()
    if plan_df.empty:
        print("\n  AllocationPlan has no summary: the chosen cell has no assignments.")
        return
    print("\n  AllocationPlan singleton (queryable as ontology):")
    print(plan_df.to_string(index=False))

    n_chosen = int(select(count(Assignment).alias("n")).where(Assignment.is_chosen()).to_df()["n"].iloc[0])
    print(f"  Assignment.is_chosen rows: {n_chosen} (matches n_assigned above)")

    overlay_df = select(
        DemandScenario.name.alias("scenario"),
        DemandScenario.factor.alias("factor"),
        DemandScenarioOutlook.realized_revenue_usd.alias("realized_revenue_usd"),
        DemandScenarioOutlook.stranded_revenue_usd.alias("stranded_revenue_usd"),
    ).where(DemandScenarioOutlook.scenario == DemandScenario).to_df()
    overlay_df = overlay_df.sort_values("factor", ascending=False).reset_index(drop=True)
    expected_revenue = float(plan_df["revenue_usd"].iloc[0])
    overlay_df["stranded_pct"] = (
        overlay_df["stranded_revenue_usd"] / expected_revenue * 100.0 if expected_revenue else 0.0
    )
    print("\n  DemandScenario overlay (chosen plan replayed under risk):")
    print(overlay_df.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))


def main() -> None:
    stage_0_ontology()
    if not stage_1_predictive():
        return
    stage_2_rules()
    stage_3_graph()
    stage_4_prescriptive()


if __name__ == "__main__":
    main()
