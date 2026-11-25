"""Churn report: highest-predicted-risk subscribers per segment from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.churn_report

Prints the data and split summary, the top-N highest-predicted-risk test
subscribers per segment, and the test-set RMSE.
"""

from model import (
    ChurnRiskPrediction,
    ChurnRiskRange,
    DataCounts,
    ScoredPerSegment,
    TestRmse,
    model,
)
from relationalai.semantics import Float, Integer, String

TOP_N_PER_SEGMENT = 5


def main() -> None:
    subscribers, calls, train, val, test = (Integer.ref() for _ in range(5))
    counts = (
        model.where(DataCounts(subscribers, calls, train, val, test))
        .select(
            subscribers.alias("subscribers"),
            calls.alias("calls"),
            train.alias("train"),
            val.alias("val"),
            test.alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    lowest, mean, highest = (Float.ref() for _ in range(3))
    risk = (
        model.where(ChurnRiskRange(lowest, mean, highest))
        .select(lowest.alias("min"), mean.alias("mean"), highest.alias("max"))
        .to_df()
        .iloc[0]
    )
    print(f"Subscribers: {int(counts['subscribers'])}  Calls: {int(counts['calls'])}")
    print(
        f"Splits: train={int(counts['train'])}  val={int(counts['val'])}  test={int(counts['test'])}"
        "  (stratified by SEGMENT)"
    )
    print(
        f"CHURN_RISK_SCORE: min={float(risk['min']):.2f}  mean={float(risk['mean']):.2f}"
        f"  max={float(risk['max']):.2f}"
    )

    print("\n" + "=" * 60)
    print(f"Top {TOP_N_PER_SEGMENT} highest-predicted-risk subscribers per segment")
    print("=" * 60)

    results_df = (
        model.where(ChurnRiskPrediction.segment_rank <= TOP_N_PER_SEGMENT)
        .select(
            ChurnRiskPrediction.sub_id.alias("sub_id"),
            ChurnRiskPrediction.subscriber.segment.alias("segment"),
            ChurnRiskPrediction.subscriber.subscriber_type.alias("type"),
            ChurnRiskPrediction.subscriber.lifetime_value_usd.alias("lifetime_value"),
            ChurnRiskPrediction.subscriber.churn_risk_score.alias("actual_risk"),
            ChurnRiskPrediction.predicted_risk.alias("predicted_risk"),
            ChurnRiskPrediction.segment_rank.alias("segment_rank"),
        )
        .to_df()
    )

    if results_df.empty:
        print("(no predictions returned)")
    else:
        results_df["predicted_risk"] = results_df["predicted_risk"].astype(float)
        results_df["actual_risk"] = results_df["actual_risk"].astype(float)
        segment, n_scored = String.ref(), Integer.ref()
        scored = (
            model.where(ScoredPerSegment(segment, n_scored))
            .select(segment.alias("segment"), n_scored.alias("n_scored"))
            .to_df()
            .sort_values("segment")
        )
        for seg, n in zip(scored["segment"], scored["n_scored"]):
            top = (
                results_df[results_df["segment"] == seg]
                .sort_values("segment_rank")
                .drop(columns="segment_rank")
            )
            print(f"\n[{seg}]  ({int(n)} test subscribers)")
            print(top.to_string(index=False))

        rmse = float(model.select(TestRmse).to_df().iloc[0, 0])
        print(f"\nTest-set RMSE: {rmse:.4f}")


if __name__ == "__main__":
    main()
