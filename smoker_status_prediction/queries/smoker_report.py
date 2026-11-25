"""Smoker report: per-person predictions and test-set metrics from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.smoker_report

Prints the data and split summary, a sample of the test-cohort predictions, and
the test-set ROC-AUC, accuracy, and class distributions.
"""

from model import People, Related, SmokerPrediction, TestTable, TrainTable, ValidationTable
from relationalai.semantics import count, select


def main() -> None:
    counts = (
        select(
            count(People).alias("people"),
            count(Related).alias("related"),
            count(TrainTable).alias("train"),
            count(ValidationTable).alias("val"),
            count(TestTable).alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    print(f"People: {counts['people']:,}  Related: {counts['related']:,}")
    print(f"Splits: train={counts['train']:,}  val={counts['val']:,}  test={counts['test']:,}")

    # Pull per-person predictions joined to the held-out actual labels in a
    # single query, so we can score the GNN on the test cohort.
    predictions_df = (
        select(
            SmokerPrediction.person_id.alias("Id"),
            SmokerPrediction.predicted_label.alias("predicted_label"),
            SmokerPrediction.probability.alias("prob"),
            TestTable.smoking.alias("actual_smoking"),
        )
        .where(SmokerPrediction.person_id == TestTable.Id)
        .to_df()
        .sort_values("Id")
    )

    if predictions_df.empty:
        print("(no test-set predictions returned)")
        return

    predictions_df["prob"] = predictions_df["prob"].astype(float)

    print("\n=== Smoker predictions (sample) ===")
    print(
        predictions_df[["Id", "predicted_label", "prob", "actual_smoking"]]
        .head(10)
        .to_string(index=False)
    )

    # Test-set metrics. Rank-based ROC-AUC keeps the script sklearn-free:
    # AUC = (sum_of_ranks_of_positives - n_pos*(n_pos+1)/2) / (n_pos * n_neg).
    n_test = len(predictions_df)
    accuracy = float(
        (predictions_df["predicted_label"] == predictions_df["actual_smoking"]).mean()
    )
    ranks = predictions_df["prob"].rank(method="average")
    pos_mask = predictions_df["actual_smoking"] == 1
    n_pos = int(pos_mask.sum())
    n_neg = int((~pos_mask).sum())
    test_auc = (
        float((ranks[pos_mask].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))
        if n_pos > 0 and n_neg > 0
        else float("nan")
    )
    actual_dist = (
        predictions_df["actual_smoking"].value_counts(normalize=True).sort_index().to_dict()
    )
    predicted_dist = (
        predictions_df["predicted_label"].value_counts(normalize=True).sort_index().to_dict()
    )

    print(f"\n=== Test-set metrics (n={n_test}) ===")
    if n_test < counts["test"]:
        print(f"  Partial: {n_test:,} of {counts['test']:,} test rows have a prediction; "
              "the metrics cover those rows only.")
    print(f"  Test-set ROC-AUC:   {test_auc:.4f}")
    print(f"  Test-set accuracy:  {accuracy:.4f}")
    print(
        f"  Actual class dist:    "
        f"{{0: {actual_dist.get(0, 0):.4f}, 1: {actual_dist.get(1, 0):.4f}}}"
    )
    print(
        f"  Predicted class dist: "
        f"{{0: {predicted_dist.get(0, 0):.4f}, 1: {predicted_dist.get(1, 0):.4f}}}"
    )


if __name__ == "__main__":
    main()
