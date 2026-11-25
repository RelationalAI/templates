"""Replication report: reads the deployed index-replication model.

Run after `rai models deploy --path model`:
    python -m queries.replication_report

Prints the status and objective of the latest refresh's solve, the selected 20-stock
basket, sector exposures, tracking quality metrics, and a top-correlation baseline
comparison. Every input comes from the deployed model. Writes data/replica_returns.csv
with date, index_return, and replica_return columns for downstream plotting.
"""

import os

from model import (
    BASELINE_NAMES,
    DATA_DIR,
    MAX_ADV_PARTICIPATION,
    MAX_WEIGHT,
    N_REPLICATION_NAMES,
    PORTFOLIO_VALUE,
    SECTOR_ACTIVE_BAND,
    AnnualizedTrackingError,
    BaselineTrackingError,
    ImpliedTurnover,
    MeanAbsResidual,
    ReturnMonth,
    SectorExposure,
    SolveStatus,
    Stock,
    TotalResidual,
    TrackingMonth,
    model,
    num_stocks,
    selected,
    stock_return,
    weight,
)


def published(relationship):
    """The one figure a nullary relationship of the model publishes."""
    return model.select(relationship).to_df().iloc[0, 0]


if __name__ == "__main__":
    print("=" * 70)
    print("FINANCIAL INDEX REPLICATION")
    print("=" * 70)
    print(f"Universe: {published(num_stocks)} stocks")
    print(f"Selected names: exactly {N_REPLICATION_NAMES}")
    print(f"Max position: {MAX_WEIGHT:.0%}")
    print(f"Sector active band: +/- {SECTOR_ACTIVE_BAND:.0%}")
    print(f"Portfolio value: ${PORTFOLIO_VALUE:,.0f}")
    print(f"Max ADV participation per name: {MAX_ADV_PARTICIPATION:.0%}")

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    residual = model.select(TotalResidual).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status not in (["OPTIMAL"], ["TIME_LIMIT"]):
        raise SystemExit(f"termination status {status}")
    if not residual:
        raise SystemExit("The solve returned no portfolio, so there is nothing to export.")
    print(f"• objective: {round(residual[0], 9)}\n")

    print(f"\nStatus: {status[0]}")
    print(f"Objective: total absolute residual = {residual[0]:.6f}")

    # --------------------------------------------------
    # Evaluate and report
    # --------------------------------------------------

    solution_df = (
        model.select(
            Stock.ticker.alias("ticker"),
            Stock.sector.alias("sector"),
            Stock.benchmark_weight.alias("benchmark_weight"),
            Stock.previous_weight.alias("previous_weight"),
            Stock.avg_dollar_volume.alias("avg_dollar_volume"),
            selected.alias("selected"),
            weight.alias("weight"),
        )
        .where(
            Stock.x_selected(selected),
            Stock.x_weight(weight),
        )
        .to_df()
        .sort_values("weight", ascending=False)
    )
    if solution_df.empty:
        raise SystemExit("The solve returned no portfolio, so there is nothing to export.")
    # Returns, sector exposure and turnover use every solved weight; the printed basket
    # lists only weights above 0.01% of the portfolio.
    basket_df = solution_df[solution_df["weight"] > 0.0001]

    returns_wide = (
        model.select(
            Stock.ticker.alias("ticker"),
            ReturnMonth.date.alias("date"),
            stock_return.alias("return"),
        )
        .where(Stock.monthly_return(ReturnMonth, stock_return))
        .to_df()
        .pivot(index="date", columns="ticker", values="return")
        .sort_index()
    )
    weights = solution_df.set_index("ticker")["weight"]
    # A zero-weight stock needs no return history; a held one needs a return every month.
    weights = weights[weights != 0]
    unpriced = [t for t in weights.index if t not in returns_wide or returns_wide[t].isna().any()]
    if unpriced:
        raise SystemExit(f"Held stocks {unpriced} lack a monthly return in the deployed model.")

    print("\n=== Selected Replication Basket ===")
    print(
        basket_df[
            [
                "ticker",
                "sector",
                "weight",
                "benchmark_weight",
                "previous_weight",
                "avg_dollar_volume",
            ]
        ].to_string(
            index=False,
            formatters={
                "weight": "{:.2%}".format,
                "benchmark_weight": "{:.2%}".format,
                "previous_weight": "{:.2%}".format,
                "avg_dollar_volume": "${:,.0f}".format,
            },
        )
    )

    sector_report = model.select(
        SectorExposure.sector_name.alias("sector"),
        SectorExposure.weight.alias("weight"),
        SectorExposure.benchmark_weight.alias("benchmark_weight"),
        SectorExposure.active_weight.alias("active_weight"),
    ).to_df()

    print("\n=== Sector Exposure ===")
    print(
        sector_report.sort_values("sector").to_string(
            index=False,
            formatters={
                "weight": "{:.2%}".format,
                "benchmark_weight": "{:.2%}".format,
                "active_weight": "{:+.2%}".format,
            },
        )
    )

    print("\n=== Tracking Quality ===")
    print(f"Annualized tracking error: {published(AnnualizedTrackingError):.2%}")
    print(f"Mean abs monthly residual: {published(MeanAbsResidual):.4%}")
    print(f"Implied turnover: {published(ImpliedTurnover):.2%}")

    replica_returns_csv = DATA_DIR / "replica_returns.csv"
    (
        model.where(ReturnMonth.date == TrackingMonth.date)
        .select(
            ReturnMonth.date.alias("date"),
            ReturnMonth.index_return.alias("index_return"),
            TrackingMonth.replica_return.alias("replica_return"),
        )
        .to_df()
        .sort_values("date")
        .to_csv(replica_returns_csv, index=False)
    )

    print("\n=== Baseline Comparison ===")
    print(f"Baseline: equal-weight top-{BASELINE_NAMES} stocks by full-history correlation")
    print(f"Baseline annualized tracking error: {published(BaselineTrackingError):.2%}")
    print(f"\nWrote benchmark-vs-replica returns to: {os.path.relpath(replica_returns_csv)}")
