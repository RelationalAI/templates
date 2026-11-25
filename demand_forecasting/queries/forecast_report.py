"""Forecast report: weekly per-(city, item family) forecast from the deployed model.

Run after `rai models deploy --path model`, `python train.py` and a refresh:
    python -m queries.forecast_report

Prints the data and split summary, a weekly forecast table per (store city,
item family) over the test window, and the test-set RMSE.
"""

import pandas as pd
from model import (
    SaleForecast,
    SaleRmse,
    SalesCounts,
    TestStart,
    UnitSales,
    ValStart,
    WeeklyForecast,
    WeeklyRmse,
    model,
)
from relationalai.semantics import Float, Integer


def published(relationship) -> float:
    """The one figure a nullary relationship of the model publishes, NaN when it derives none."""
    values = model.select(relationship).to_df().iloc[:, 0]
    return float(values.iloc[0]) if len(values) else float("nan")


def main() -> None:
    stores, items, sales, train, val, test = (Integer.ref() for _ in range(6))
    counts = (
        model.where(SalesCounts(stores, items, sales, train, val, test))
        .select(
            stores.alias("stores"),
            items.alias("items"),
            sales.alias("sales"),
            train.alias("train"),
            val.alias("val"),
            test.alias("test"),
        )
        .to_df()
        .iloc[0]
    )
    lowest, highest, mean = Integer.ref(), Integer.ref(), Float.ref()
    unit_sales = (
        model.where(UnitSales(lowest, highest, mean))
        .select(lowest.alias("min"), highest.alias("max"), mean.alias("mean"))
        .to_df()
    )
    print(f"Stores: {counts['stores']}  Items: {counts['items']}  Sales: {counts['sales']:,}")
    print(
        f"Splits (temporal): train={counts['train']:,}  val={counts['val']:,}  test={counts['test']:,}"
    )
    # The cutoffs that the model splits the sales on.
    val_start = pd.Timestamp(model.select(ValStart).to_df().iloc[0, 0])
    test_start = pd.Timestamp(model.select(TestStart).to_df().iloc[0, 0])
    print(f"Train: < {val_start.date()}; Val: {val_start.date()} -- {test_start.date()}; "
          f"Test: >= {test_start.date()}")
    print(f"unit_sales: min={unit_sales['min'].iloc[0]} mean={unit_sales['mean'].iloc[0]:.2f} "
          f"max={unit_sales['max'].iloc[0]}")

    print("\n" + "=" * 60)
    print("Forecast (test window) -- weekly aggregate per (city, item family)")
    print("=" * 60)

    # A prediction whose store or item is missing has no city or family: it counts toward
    # the per-Sale RMSE but is left out of the weekly table.
    n_predictions = len(model.select(SaleForecast.sale_id).to_df())
    if n_predictions == 0:
        print("(no predictions returned)")
    else:
        labeled = model.select(
            SaleForecast.sale_id.alias("sale_id"),
            SaleForecast.city.alias("city"),
            SaleForecast.family.alias("family"),
        ).to_df()
        unlabeled = n_predictions - len(labeled)
        if unlabeled:
            print(f"{unlabeled} predictions have no store city or item family: they count toward "
                  "the per-Sale RMSE but not the weekly table.")

        weekly = (
            model.select(
                WeeklyForecast.city.alias("city"),
                WeeklyForecast.family.alias("family"),
                WeeklyForecast.week_start.alias("week_start"),
                WeeklyForecast.actual.alias("actual"),
                WeeklyForecast.predicted.alias("predicted"),
                WeeklyForecast.abs_err.alias("abs_err"),
            )
            .to_df()
            .sort_values(["city", "family", "week_start"])
        )
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        print(weekly.head(20).to_string(index=False))

        print(f"\nTest-set RMSE (per-Sale):           {published(SaleRmse):.4f}")
        print(f"Test-set RMSE (per (city, family, week)): {published(WeeklyRmse):.4f}")


if __name__ == "__main__":
    main()
