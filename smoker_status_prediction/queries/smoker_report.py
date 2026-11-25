"""Smoker report: per-person predictions and test-set metrics from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.smoker_report

Prints the data and split summary, a sample of the test-cohort predictions, and
the test-set ROC-AUC, accuracy, and class distributions.
"""

from model import (
    ClassShare,
    DataSummary,
    SmokerPrediction,
    TestAccuracy,
    TestAuc,
    TestCohort,
    TestTable,
)
from relationalai.semantics import Float, Integer, select


def main() -> None:
    people, related, train, validation, test = (Integer.ref() for _ in range(5))
    counts = (
        select(
            people.alias("people"),
            related.alias("related"),
            train.alias("train"),
            validation.alias("val"),
            test.alias("test"),
        )
        .where(DataSummary(people, related, train, validation, test))
        .to_df()
        .iloc[0]
    )
    print(f"People: {counts['people']:,}  Related: {counts['related']:,}")
    print(f"Splits: train={counts['train']:,}  val={counts['val']:,}  test={counts['test']:,}")

    # Pull per-person predictions joined to the held-out actual labels, so the sample shows the
    # GNN's test-cohort scores next to the truth.
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

    # Test-set metrics, as the model publishes them. ROC-AUC is rank-based (ties share the
    # average rank), so the script stays sklearn-free. It is undefined when the scored cohort
    # has one class only.
    n_test_ref, n_correct_ref, accuracy_ref, auc_ref = (
        Integer.ref(),
        Integer.ref(),
        Float.ref(),
        Float.ref(),
    )
    n_test = int(
        select(n_test_ref).where(TestCohort(n_test_ref, n_correct_ref)).to_df().iloc[0, 0]
    )
    accuracy = float(select(accuracy_ref).where(TestAccuracy(accuracy_ref)).to_df().iloc[0, 0])
    auc_values = select(auc_ref).where(TestAuc(auc_ref)).to_df().iloc[:, 0].tolist()
    test_auc = float(auc_values[0]) if auc_values else float("nan")
    shares = (
        select(
            ClassShare.label.alias("label"),
            ClassShare.actual_share.alias("actual"),
            ClassShare.predicted_share.alias("predicted"),
        )
        .to_df()
        .set_index("label")
    )
    actual_dist = shares["actual"].to_dict()
    predicted_dist = shares["predicted"].to_dict()

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
