"""Forecast report: weekly per-(city, item family) forecast from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.forecast_report

Prints the data and split summary, a weekly forecast table per (store city,
item family) over the test window, and the test-set RMSE.
"""

import numpy as np
import pandas as pd
from model import TEST_START, VAL_START, Item, Sale, Store, TestTable, TrainTable, ValTable, model
from relationalai.semantics import Float, count, select


def main() -> None:
    counts = (
        select(
            count(Store).alias("stores"),
            count(Item).alias("items"),
            count(Sale).alias("sales"),
            (count(TrainTable) | 0).alias("train"),
            (count(ValTable) | 0).alias("val"),
            (count(TestTable) | 0).alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    unit_sales = select(Sale.sale_id, Sale.unit_sales).to_df()["unit_sales"]
    print(f"Stores: {counts['stores']}  Items: {counts['items']}  Sales: {counts['sales']:,}")
    print(
        f"Splits (temporal): train={counts['train']:,}  val={counts['val']:,}  test={counts['test']:,}"
    )
    # The cutoffs that model/source.py split the sales on.
    print(f"Train: < {VAL_START.date()}; Val: {VAL_START.date()} -- {TEST_START.date()}; "
          f"Test: >= {TEST_START.date()}")
    print(f"unit_sales: min={unit_sales.min()} mean={unit_sales.mean():.2f} max={unit_sales.max()}")

    print("\n" + "=" * 60)
    print("Forecast (test window) -- weekly aggregate per (city, item family)")
    print("=" * 60)

    # Predictions and store/item metadata are read separately and left-joined, so a
    # prediction whose store or item is missing still counts toward the per-Sale RMSE.
    predicted_value_ref = Float.ref()
    results_df = (
        model.where(Sale.predictions.predicted_value(predicted_value_ref))
        .select(
            Sale.sale_id.alias("sale_id"),
            Sale.date.alias("date"),
            Sale.unit_sales.alias("actual"),
            predicted_value_ref.alias("predicted"),
        )
        .to_df()
    )
    dimensions_df = select(
        Sale.sale_id.alias("sale_id"), Store.city.alias("city"), Item.family.alias("family")
    ).where(Sale.predictions, Sale.store_id == Store.store_id, Sale.item_id == Item.item_id).to_df()
    results_df = results_df.merge(dimensions_df, on="sale_id", how="left")

    if results_df.empty:
        print("(no predictions returned)")
    else:
        results_df["date"] = pd.to_datetime(results_df["date"])
        results_df["predicted"] = results_df["predicted"].astype(float).clip(lower=0)
        results_df["actual"] = results_df["actual"].astype(float)
        results_df["week_start"] = results_df["date"].dt.to_period("W").dt.start_time
        unlabeled = int((results_df["city"].isna() | results_df["family"].isna()).sum())
        if unlabeled:
            print(f"{unlabeled} predictions have no store city or item family: they count toward "
                  "the per-Sale RMSE but not the weekly table.")

        weekly = (
            results_df.groupby(["city", "family", "week_start"])[["actual", "predicted"]]
            .sum()
            .reset_index()
            .sort_values(["city", "family", "week_start"])
        )
        weekly["abs_err"] = (weekly["predicted"] - weekly["actual"]).abs()

        print(weekly.head(20).to_string(index=False))

        test_rmse = float(np.sqrt(((results_df["predicted"] - results_df["actual"]) ** 2).mean()))
        weekly_rmse = float(np.sqrt(((weekly["predicted"] - weekly["actual"]) ** 2).mean()))
        print(f"\nTest-set RMSE (per-Sale):           {test_rmse:.4f}")
        print(f"Test-set RMSE (per (city, family, week)): {weekly_rmse:.4f}")


if __name__ == "__main__":
    main()
