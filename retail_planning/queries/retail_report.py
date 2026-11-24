"""Retail planning report: reads the deployed retail planning model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.retail_report

Prints the sales target profile of the train split, the adjusted demand per
planning article that the sales GNN's predictions aggregate to, then the
status and objective of the markdown MILP and the demand/inventory planning LP,
the selected discount for each article and week, and the planned production
quantities for the planning set.
"""

from model import (
    ArticleDemand,
    DemandPlanCost,
    DemandPlanStatus,
    Discount,
    MarkdownRevenue,
    MarkdownStatus,
    OptArticle,
    Train,
    Transaction,
    Week,
    model,
)
from relationalai.semantics import Float, String, select


def banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def stage_1_predictive() -> None:
    banner("PREDICTIVE: sales regression GNN (HM_MINI)")
    timestamp, value = String.ref(), Float.ref()
    target = select(
        Transaction.transaction_id.alias("transaction_id"),
        value.alias("value"),
    ).where(Train(Transaction, timestamp, value)).to_df()["value"]
    print("\n=== Sales target profile (train split) ===")
    print(f"  n={len(target)}  min={target.min():.4g}  max={target.max():.4g}  "
          f"mean={target.mean():.4g}  stddev={target.std():.4g}")
    print(f"  Baseline RMSE (predict-the-mean) ~= stddev = {target.std():.4g}")

    demand = select(
        OptArticle.opt_article_id.alias("article_id"),
        OptArticle.name.alias("name"),
        ArticleDemand.adjusted_demand.alias("adjusted_demand"),
    ).where(ArticleDemand.article_id == OptArticle.opt_article_id).to_df().sort_values("article_id")
    print("\n=== Adjusted Demand per Article (from sales GNN, aggregated) ===")
    if demand.empty:
        print("  (no predictions) Run `python train.py`, then refresh the deployed model.")
        return
    print(demand.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


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
    _print_solve("Demand Planning", DemandPlanStatus, DemandPlanCost,
                 "Total cost (production + holding + unmet penalty)")


def main() -> None:
    stage_1_predictive()
    stage_2_markdown()
    stage_3_demand_planning()
    banner("PIPELINE COMPLETE: read from the deployed retail planning model")


if __name__ == "__main__":
    main()
