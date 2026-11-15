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
    SolveObjective,
    SolveStatus,
    Train,
    Transaction,
    model,
)
from relationalai.semantics import DateTime, Float, Integer, select


def main() -> None:
    # Class-balance profile of the training labels (baseline ROC_AUC = 0.5)
    train_txn = Transaction.ref()
    train_ts = DateTime.ref()
    train_label = Integer.ref()
    _label_df = select(
        train_txn.transaction_id.alias("transaction_id"),
        train_label.alias("label"),
    ).where(Train(train_txn, train_ts, train_label)).to_df()
    if len(_label_df):
        # Cast out of pyarrow's Int128 to Python int for aggregation
        _l = _label_df["label"].astype("int64")
        print("\n=== Fraud class balance (train split) ===")
        print(f"  n={len(_l)}  fraud={int(_l.sum())}  "
              f"fraud_rate={_l.mean():.1%}")
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

    print("\n=== Top-20 alert-scored transactions ===")
    print(_alert_df.sort_values("alert_score", ascending=False).head(20).to_string(index=False))

    print("\n" + "=" * 60)
    print("Stage 5: Prescriptive -- investigator-budget allocation")
    print("=" * 60)

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    objective = model.select(SolveObjective).to_df().iloc[:, 0].tolist()
    print(f"\nMILP Status: {', '.join(status)}")
    if objective:
        objective_value = float(objective[0])
        # Compare against a naive sort-and-take baseline: pick top transactions by
        # alert_score, ignoring audit-cost and per-receiver caps, consuming hours
        # until the budget is spent. The audit cost is the model's own per-
        # transaction cost, the one the MILP constraint reads.
        amount_ref = Float.ref()
        cost_ref = Float.ref()
        _full_df = (
            model.select(
                Txn_ref.transaction_id.alias("transaction_id"),
                Txn_ref.trans_type.alias("trans_type"),
                amount_ref.alias("amount"),
                cost_ref.alias("audit_cost"),
                score_ref.alias("alert_score"),
            )
            .where(
                Cand_ref.alert_score(score_ref),
                Txn_ref.transaction_id == Cand_ref.transaction_id,
                Txn_ref.amount == amount_ref,
                Txn_ref.audit_cost == cost_ref,
            )
            .to_df()
        )
        _full_df["amount"] = _full_df["amount"].astype("float64")
        _full_df["alert_score"] = _full_df["alert_score"].astype("float64")
        _full_df["audit_cost"] = _full_df["audit_cost"].astype("float64")
        _full_df["expected_loss"] = _full_df["alert_score"] * _full_df["amount"]
        _naive = _full_df.sort_values("alert_score", ascending=False).copy()
        _naive["cumulative_hours"] = _naive["audit_cost"].cumsum()
        _naive_fit = _naive[_naive["cumulative_hours"] <= AUDIT_BUDGET_HOURS]
        _naive_obj = float(_naive_fit["expected_loss"].sum())
        _naive_types = {k: int(v) for k, v in _naive_fit["trans_type"].value_counts().items()}
        print(f"Captured expected loss (optimal within budget): ${objective_value:,.0f}")
        print(f"  MILP (cost-aware + per-receiver cap) -> ${objective_value:,.0f} "
              f"captured across the audit queue")
        print(f"  Naive top-by-alert-score (budget only, same hours) -> "
              f"${_naive_obj:,.0f} captured across {len(_naive_fit)} audits "
              f"(by type: {_naive_types})")
        uplift = objective_value - _naive_obj
        print(f"  MILP uplift over naive sort: ${uplift:+,.0f}")

    # Report the selected audit queue
    print("\n=== Selected audit queue ===")
    sel_ref = Float.ref()
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
            Cand_ref.x_audit(sel_ref),
            sel_ref > 0.5,
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
        hours_used = float(audit_df["audit_cost"].sum())
        print(f"  {len(audit_df)} audits scheduled; "
              f"{hours_used:.1f}/{AUDIT_BUDGET_HOURS:.0f} investigator hours used")
        print(audit_df.to_string(index=False))
        print("\n  By trans_type:")
        print(audit_df["trans_type"].value_counts().to_string())

    print("\n" + "=" * 60)
    print("Report complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
