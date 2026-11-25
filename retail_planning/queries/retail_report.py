"""Retail planning report: reads the deployed retail planning model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.retail_report

Prints the sales target profile of the train split, the adjusted demand per
planning article that the sales GNN's predictions aggregate to, then the
status and objective of the markdown MILP with the selected discount for each
article and week, and the status and total cost of the demand/inventory
planning LP with its production plan, inventory levels, and unmet demand for
each planning article and week. It stops before the plans if a planning
article has no demand.
"""

from model import (
    ArticleDemand,
    DemandPlanCost,
    DemandPlanStatus,
    Discount,
    MarkdownRevenue,
    MarkdownStatus,
    OptArticle,
    PlanningGap,
    ProdCapacity,
    TrainTargetProfile,
    Week,
    model,
)
from relationalai.semantics import Float, Integer, select


def banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def stage_1_predictive() -> bool:
    """Print the target profile and the demand; return whether every planning article has demand."""
    banner("PREDICTIVE: sales regression GNN (HM_MINI)")
    n_ref, min_ref, max_ref, mean_ref, stddev_ref = (
        Integer.ref(), Float.ref(), Float.ref(), Float.ref(), Float.ref()
    )
    profile = (
        select(
            n_ref.alias("n"),
            min_ref.alias("min"),
            max_ref.alias("max"),
            mean_ref.alias("mean"),
            stddev_ref.alias("stddev"),
        )
        .where(TrainTargetProfile(n_ref, min_ref, max_ref, mean_ref, stddev_ref))
        .to_df()
    )
    if len(profile):
        target = profile.iloc[0]
        print("\n=== Sales target profile (train split) ===")
        print(f"  n={int(target['n'])}  min={target['min']:.4g}  max={target['max']:.4g}  "
              f"mean={target['mean']:.4g}  stddev={target['stddev']:.4g}")
        print(f"  Baseline RMSE (predict-the-mean) ~= stddev = {target['stddev']:.4g}")

    demand = select(
        OptArticle.opt_article_id.alias("article_id"),
        OptArticle.name.alias("name"),
        ArticleDemand.adjusted_demand.alias("adjusted_demand"),
    ).where(ArticleDemand.article_id == OptArticle.opt_article_id).to_df().sort_values("article_id")
    print("\n=== Adjusted Demand per Article (from sales GNN, aggregated) ===")
    if demand.empty:
        print("  (no predictions) Run `python train.py`, then refresh the deployed model.")
    else:
        print(demand.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # Both plans are meaningless for an article without demand.
    gap = sorted(select(PlanningGap).to_df().iloc[:, 0])
    if gap:
        print(f"\n  Articles {gap} lack predicted demand or sit outside the planning set.")
    return not gap


def _print_solve(label: str, status_relation, objective_relation, objective_label: str) -> list[str]:
    status = model.select(status_relation).to_df().iloc[:, 0].tolist()
    objective = model.select(objective_relation).to_df().iloc[:, 0].tolist()
    print(f"\n{label} Status: {', '.join(status) if status else '(no solve yet)'}")
    if objective:
        print(f"{objective_label}: ${float(objective[0]):,.2f}")
    return status


def stage_2_markdown() -> None:
    banner("PRESCRIPTIVE A: Markdown Optimization")
    status = _print_solve("Markdown", MarkdownStatus, MarkdownRevenue, "Total revenue (sales + salvage)")
    if status != ["OPTIMAL"]:
        raise SystemExit(f"termination status {status}")
    week, discount = Week.ref(), Discount.ref()
    picks = select(
        OptArticle.name.alias("article"),
        week.num.alias("week"),
        discount.discount_pct.alias("discount_pct"),
    ).where(OptArticle.markdown(week, discount)).to_df()
    print("\n=== Markdown: Selected Discounts by Article-Week ===")
    if picks.empty:
        print("  (no markdown plan)")
        return
    print(picks.sort_values(["article", "week"]).to_string(index=False))


def stage_3_demand_planning() -> None:
    banner("PRESCRIPTIVE B: Demand / Inventory Planning")
    status = _print_solve("Demand Planning", DemandPlanStatus, DemandPlanCost,
                          "Total cost (production + holding + unmet penalty)")
    week, end_week, value = Week.ref(), Integer.ref(), Float.ref()
    # Every solution has an inventory row for each article at week 0, so no inventory rows
    # means the solve returned no solution, not an empty plan.
    inv_rows = select(
        ProdCapacity.pc_article_id.alias("article_id"),
        end_week.alias("week"),
        value.alias("inventory"),
    ).where(ProdCapacity.planned_inventory(end_week, value)).to_df()
    if inv_rows.empty:
        print("  (no plan: the solve returned no solution)")
        return
    if status != ["OPTIMAL"]:
        print(f"  The plan below is the best solution of a {', '.join(status)} solve, not a proven optimum.")

    print("\n=== Demand Planning: Production Plan (non-zero) ===")
    prod_rows = select(
        ProdCapacity.pc_article_id.alias("article_id"),
        week.num.alias("week"),
        value.alias("production"),
    ).where(ProdCapacity.planned_production(week, value), value > 0.01).to_df()
    if not prod_rows.empty:
        print(prod_rows.sort_values(["article_id", "week"]).to_string(index=False))
    else:
        print("  No production needed (none above 0.01 units).")

    print("\n=== Demand Planning: Inventory Levels ===")
    print(inv_rows.sort_values(["article_id", "week"]).to_string(index=False))

    print("\n=== Demand Planning: Unmet Demand ===")
    unmet_rows = select(
        ProdCapacity.pc_article_id.alias("article_id"),
        week.num.alias("week"),
        value.alias("unmet"),
    ).where(ProdCapacity.planned_unmet(week, value), value > 0.01).to_df()
    if unmet_rows.empty:
        print("  All demand fulfilled! (no shortfall above 0.01 units)")
    else:
        print(unmet_rows.sort_values(["article_id", "week"]).to_string(index=False))


def main() -> None:
    if not stage_1_predictive():
        raise SystemExit("no plan: every planning article needs predicted demand")
    stage_2_markdown()
    stage_3_demand_planning()
    banner("PIPELINE COMPLETE: read from the deployed retail planning model")


if __name__ == "__main__":
    main()
