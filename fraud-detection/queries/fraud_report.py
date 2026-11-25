"""Fraud report: reads the deployed fraud-detection model.

Run after deploying the model, `python train.py` and a refresh:
    python -m queries.fraud_report

Prints the train-split class balance, the top-20 alert-scored transactions,
the status and objective of the latest refresh's audit solve against a naive
sort-and-take baseline, and the selected audit queue.
"""

from model import (
    AUDIT_BUDGET_HOURS,
    AuditCandidate,
    AuditQueue,
    AuditUplift,
    SolveObjective,
    SolveStatus,
    TrainClassBalance,
    Transaction,
    model,
)
from pandas import Index
from relationalai.semantics import Float, Integer, String

TOP_ALERTS = 20


def type_counts(strategy: str, first_seen):
    """One audit queue's audits per transaction type from the model, most first; ties keep the
    order in which their types first appear in `first_seen`."""
    queue = AuditQueue.ref()
    n_ref, type_ref = Integer.ref(), String.ref()
    by_type = (
        model.where(queue.strategy == strategy, queue.audits_by_type(n_ref, type_ref))
        .select(type_ref.alias("trans_type"), n_ref.alias("count"))
        .to_df()
        .set_index("trans_type")["count"]
    )
    order = Index(first_seen.drop_duplicates(), name="trans_type")
    return by_type.reindex(order).astype(int).sort_values(ascending=False, kind="stable")


def queue_summary(strategy: str):
    """One audit queue's size, investigator hours, and captured expected loss."""
    queue = AuditQueue.ref()
    return (
        model.where(queue.strategy == strategy)
        .select(
            queue.n_audits.alias("audits"),
            queue.hours_used.alias("hours"),
            queue.captured_loss.alias("captured_loss"),
        )
        .to_df()
        .iloc[0]
    )


def main() -> None:
    # Class-balance profile of the training labels (baseline ROC_AUC = 0.5)
    n_ref, fraud_ref, rate_ref = Integer.ref(), Integer.ref(), Float.ref()
    balance = (
        model.where(TrainClassBalance(n_ref, fraud_ref, rate_ref))
        .select(n_ref.alias("n"), fraud_ref.alias("fraud"), rate_ref.alias("fraud_rate"))
        .to_df()
    )
    if len(balance):
        print("\n=== Fraud class balance (train split) ===")
        print(f"  n={int(balance['n'].iloc[0])}  fraud={int(balance['fraud'].iloc[0])}  "
              f"fraud_rate={float(balance['fraud_rate'].iloc[0]):.1%}")
        print("  Baseline ROC_AUC = 0.5")

    Txn_ref = Transaction.ref()
    Cand_ref = AuditCandidate.ref()
    score_ref = Float.ref()
    _alert_df = (
        model.select(
            Txn_ref.transaction_id.alias("transaction_id"),
            Txn_ref.trans_type.alias("trans_type"),
            Txn_ref.amount.alias("amount"),
            Txn_ref.name_dest.alias("receiver"),
            score_ref.alias("alert_score"),
            Cand_ref.alert_rank.alias("alert_rank"),
        )
        .where(
            Cand_ref.alert_score(score_ref),
            Txn_ref.transaction_id == Cand_ref.transaction_id,
        )
        .to_df()
    )
    if _alert_df.empty:
        print("\n(no predictions returned)")
        return

    print(f"\n=== Top-{TOP_ALERTS} alert-scored transactions ===")
    top_alerts = _alert_df.sort_values("alert_rank").head(TOP_ALERTS).drop(columns="alert_rank")
    print(top_alerts.to_string(index=False))

    print("\n" + "=" * 60)
    print("Stage 5: Prescriptive -- investigator-budget allocation")
    print("=" * 60)

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print(f"\nMILP Status: {', '.join(status)}")
    if objective:
        objective_value = float(objective[0])
        # Compare against the naive sort-and-take queue the model publishes: top
        # transactions by alert_score, ignoring audit-cost and per-receiver caps,
        # consuming hours until the budget is spent.
        naive = queue_summary("naive")
        naive_queue = AuditQueue.ref()
        naive_order = (
            model.where(
                naive_queue.strategy == "naive",
                naive_queue.audits(Cand_ref),
                Txn_ref.transaction_id == Cand_ref.transaction_id,
            )
            .select(
                Cand_ref.alert_rank.alias("alert_rank"),
                Txn_ref.trans_type.alias("trans_type"),
            )
            .to_df()
            .sort_values("alert_rank")["trans_type"]
        )
        _naive_types = {k: int(v) for k, v in type_counts("naive", naive_order).items()}
        uplift = float(model.select(AuditUplift).to_df().iloc[0, 0])
        quality = "optimal" if status == ["OPTIMAL"] else "best found"
        print(f"Captured expected loss ({quality} within budget): ${objective_value:,.0f}")
        print(f"  MILP (cost-aware + per-receiver cap) -> ${objective_value:,.0f} "
              f"captured across the audit queue")
        print(f"  Naive top-by-alert-score (budget only, same {AUDIT_BUDGET_HOURS:g}-hour budget) -> "
              f"${float(naive['captured_loss']):,.0f} captured across {int(naive['audits'])} audits "
              f"(by type: {_naive_types})")
        print(f"  MILP uplift over naive sort: ${uplift:+,.0f}")

    # Report the selected audit queue
    print("\n=== Selected audit queue ===")
    queue_ref = AuditQueue.ref()
    cost_ref = Float.ref()
    audit_df = (
        model.select(
            Txn_ref.transaction_id.alias("transaction_id"),
            Txn_ref.trans_type.alias("trans_type"),
            Txn_ref.amount.alias("amount"),
            Txn_ref.name_dest.alias("receiver"),
            score_ref.alias("alert_score"),
            cost_ref.alias("audit_cost"),
        )
        .where(
            queue_ref.strategy == "optimized",
            queue_ref.audits(Cand_ref),
            Cand_ref.alert_score(score_ref),
            Txn_ref.transaction_id == Cand_ref.transaction_id,
            Txn_ref.audit_cost == cost_ref,
        )
        .to_df()
        .sort_values("alert_score", ascending=False)
    )
    if audit_df.empty:
        print("  No transactions selected (MILP degenerate).")
    else:
        audit_df["amount"] = audit_df["amount"].astype("float64")
        audit_df["audit_cost"] = audit_df["audit_cost"].astype("float64")
        optimized = queue_summary("optimized")
        print(f"  {int(optimized['audits'])} audits scheduled; "
              f"{float(optimized['hours']):.1f}/{AUDIT_BUDGET_HOURS:.0f} investigator hours used")
        print(audit_df.to_string(index=False))
        print("\n  By trans_type:")
        print(type_counts("optimized", audit_df["trans_type"]).to_string())

    print("\n" + "=" * 60)
    print("Report complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
