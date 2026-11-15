"""Churn report: highest-predicted-risk subscribers per segment from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.churn_report

Prints the data and split summary, the top-N highest-predicted-risk test
subscribers per segment, and the test-set RMSE.
"""

from model import Call, Subscriber, TestTable, TrainTable, ValTable, model
from relationalai.semantics import Float, count, select

TOP_N_PER_SEGMENT = 5


def main() -> None:
    counts = (
        select(
            count(Subscriber).alias("subscribers"),
            count(Call).alias("calls"),
            count(TrainTable).alias("train"),
            count(ValTable).alias("val"),
            count(TestTable).alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    risk = select(Subscriber.sub_id, Subscriber.churn_risk_score).to_df()["churn_risk_score"]
    print(f"Subscribers: {counts['subscribers']}  Calls: {counts['calls']}")
    print(
        f"Splits: train={counts['train']}  val={counts['val']}  test={counts['test']}"
        "  (stratified by SEGMENT)"
    )
    print(
        f"CHURN_RISK_SCORE: min={risk.min():.2f}  mean={risk.mean():.2f}  max={risk.max():.2f}"
    )

    print("\n" + "=" * 60)
    print(f"Top {TOP_N_PER_SEGMENT} highest-predicted-risk subscribers per segment")
    print("=" * 60)

    risk_ref = Float.ref()
    results_df = (
        model.where(Subscriber.predictions.predicted_value(risk_ref))
        .select(
            Subscriber.sub_id.alias("sub_id"),
            Subscriber.segment.alias("segment"),
            Subscriber.subscriber_type.alias("type"),
            Subscriber.lifetime_value_usd.alias("lifetime_value"),
            Subscriber.churn_risk_score.alias("actual_risk"),
            risk_ref.alias("predicted_risk"),
        )
        .to_df()
    )

    if results_df.empty:
        print("(no predictions returned)")
    else:
        results_df["predicted_risk"] = results_df["predicted_risk"].astype(float)
        results_df["actual_risk"] = results_df["actual_risk"].astype(float)
        for seg, group in results_df.groupby("segment"):
            top = group.sort_values("predicted_risk", ascending=False).head(
                TOP_N_PER_SEGMENT
            )
            print(f"\n[{seg}]  ({len(group)} test subscribers)")
            print(top.to_string(index=False))

        rmse = float(
            ((results_df["predicted_risk"] - results_df["actual_risk"]) ** 2).mean() ** 0.5
        )
        print(f"\nTest-set RMSE: {rmse:.4f}")


if __name__ == "__main__":
    main()
