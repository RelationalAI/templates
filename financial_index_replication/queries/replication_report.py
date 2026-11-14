"""Replication report: reads the deployed index-replication model.

Run after `rai models deploy --path model`:
    python -m queries.replication_report

Prints the selected 20-stock basket, sector exposures, tracking quality metrics,
and a top-correlation baseline comparison. Every input comes from the deployed
model. Writes data/replica_returns.csv with date, index_return, and replica_return
columns for downstream plotting.
"""

from math import sqrt

import pandas as pd
from model import (
    DATA_DIR,
    MAX_ADV_PARTICIPATION,
    MAX_WEIGHT,
    MONTHS_PER_YEAR,
    N_REPLICATION_NAMES,
    PORTFOLIO_VALUE,
    SECTOR_ACTIVE_BAND,
    ReturnMonth,
    Sector,
    SolveStatus,
    Stock,
    TotalResidual,
    model,
    selected,
    stock_return,
    weight,
)

if __name__ == "__main__":
    print("=" * 70)
    print("FINANCIAL INDEX REPLICATION")
    print("=" * 70)
    n_stocks = len(model.select(Stock.ticker).to_df())
    print(f"Universe: {n_stocks} stocks")
    print(f"Selected names: exactly {N_REPLICATION_NAMES}")
    print(f"Max position: {MAX_WEIGHT:.0%}")
    print(f"Sector active band: +/- {SECTOR_ACTIVE_BAND:.0%}")
    print(f"Portfolio value: ${PORTFOLIO_VALUE:,.0f}")
    print(f"Max ADV participation per name: {MAX_ADV_PARTICIPATION:.0%}")

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    residual = model.select(TotalResidual).to_df().iloc[:, 0].tolist()
    if status not in (["OPTIMAL"], ["TIME_LIMIT"]):
        raise SystemExit(f"Solver did not find an optimal solution: {status}")

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
            weight > 0.0001,
        )
        .to_df()
        .sort_values("weight", ascending=False)
    )

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
    index_series = (
        model.select(
            ReturnMonth.date.alias("date"),
            ReturnMonth.index_return.alias("index_return"),
        )
        .to_df()
        .set_index("date")
        .sort_index()
    )
    weights = solution_df.set_index("ticker")["weight"]
    portfolio_returns = returns_wide[weights.index].mul(weights, axis=1).sum(axis=1)
    tracking_diff = portfolio_returns - index_series["index_return"]

    def annualized_tracking_error():
        monthly_rms = sqrt((tracking_diff ** 2).mean())
        return monthly_rms * sqrt(MONTHS_PER_YEAR)

    def mean_abs_tracking():
        return tracking_diff.abs().mean()

    print("\n=== Selected Replication Basket ===")
    print(
        solution_df[
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

    sector_report = (
        solution_df.groupby("sector", as_index=False)["weight"].sum()
        .merge(
            model.select(
                Sector.sector_name.alias("sector"),
                Sector.benchmark_weight.alias("benchmark_weight"),
            ).to_df(),
            on="sector",
        )
    )
    sector_report["active_weight"] = (
        sector_report["weight"] - sector_report["benchmark_weight"]
    )

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

    previous_df = model.select(
        Stock.ticker.alias("ticker"),
        Stock.previous_weight.alias("previous_weight"),
    ).to_df()
    turnover = (
        solution_df.set_index("ticker")["weight"]
        .reindex(previous_df["ticker"], fill_value=0.0)
        .sub(previous_df.set_index("ticker")["previous_weight"])
        .abs()
        .sum()
    )

    print("\n=== Tracking Quality ===")
    print(f"Annualized tracking error: {annualized_tracking_error():.2%}")
    print(f"Mean abs monthly residual: {mean_abs_tracking():.4%}")
    print(f"Implied turnover: {turnover:.2%}")

    # Simple benchmark: equal-weight the 20 most correlated stocks.
    top_corr_ids = (
        returns_wide
        .corrwith(index_series["index_return"])
        .abs()
        .sort_values(ascending=False)
        .head(20)
        .index
    )
    baseline_returns = returns_wide[top_corr_ids].mean(axis=1)
    baseline_diff = baseline_returns - index_series["index_return"]

    baseline_tracking_error = sqrt((baseline_diff ** 2).mean()) * sqrt(
        MONTHS_PER_YEAR
    )

    replica_returns_csv = DATA_DIR / "replica_returns.csv"
    pd.DataFrame({
        "date": index_series.index,
        "index_return": index_series["index_return"].values,
        "replica_return": portfolio_returns.reindex(index_series.index).values,
    }).to_csv(replica_returns_csv, index=False)

    print("\n=== Baseline Comparison ===")
    print("Baseline: equal-weight top-20 stocks by full-history correlation")
    print(f"Baseline annualized tracking error: {baseline_tracking_error:.2%}")
    print(f"\nWrote benchmark-vs-replica returns to: {replica_returns_csv}")
