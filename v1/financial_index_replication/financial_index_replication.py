"""Financial index replication (prescriptive optimization) template.

This script demonstrates sparse index replication in RelationalAI:

- Load sample monthly returns for an S&P 500-like benchmark and 50 stocks.
- Choose exactly 20 names and their portfolio weights.
- Minimize full-history tracking residuals versus the benchmark.
- Enforce long-only weights, max position size, liquidity eligibility,
  sector neutrality, and per-name ADV participation limits.
- Report full-history tracking error and compare against a simple correlation
  baseline.

The optimization is modeled as a mixed-integer linear problem that minimizes
absolute tracking residuals.

Run:
    python financial_index_replication.py
"""

from math import sqrt
from pathlib import Path

import pandas as pd
from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure replication policy
# --------------------------------------------------

N_REPLICATION_NAMES = 20
MAX_WEIGHT = 0.10
SECTOR_ACTIVE_BAND = 0.04
MIN_AVG_DOLLAR_VOLUME = 100_000_000
PORTFOLIO_VALUE = 10_000_000
MAX_ADV_PARTICIPATION = 0.05
MONTHS_PER_YEAR = 12

DATA_DIR = Path(__file__).parent / "data"

stocks_csv = pd.read_csv(DATA_DIR / "stocks.csv")
index_returns_csv = pd.read_csv(DATA_DIR / "index_returns.csv")
stock_returns_csv = pd.read_csv(DATA_DIR / "stock_returns.csv")

model = Model("financial_index_replication")

# --------------------------------------------------
# Define semantic model and load data
# --------------------------------------------------

Stock = model.Concept("Stock", identify_by={"ticker": String})
Stock.name = model.Property(f"{Stock} has name {String:name}")
Stock.sector = model.Property(f"{Stock} has sector {String:sector}")
Stock.benchmark_weight = model.Property(
    f"{Stock} has benchmark weight {Float:benchmark_weight}"
)
Stock.avg_dollar_volume = model.Property(
    f"{Stock} has average dollar volume {Float:avg_dollar_volume}"
)
Stock.previous_weight = model.Property(
    f"{Stock} has previous portfolio weight {Float:previous_weight}"
)
model.define(Stock.new(model.data(stocks_csv).to_schema()))

Sector = model.Concept("Sector", identify_by={"sector_name": String})
model.define(Sector.new(sector_name=Stock.sector))
Stock.sector_ref = model.Property(f"{Stock} belongs to {Sector}")
model.define(Stock.sector_ref(Sector)).where(Stock.sector == Sector.sector_name)

Sector.benchmark_weight = model.Property(
    f"{Sector} has benchmark weight {Float:sector_benchmark_weight}"
)
model.define(
    Sector.benchmark_weight(
        sum(Stock.benchmark_weight).where(Stock.sector_ref(Sector)).per(Sector)
    )
)

ReturnDate = model.Concept("ReturnDate", identify_by={"date": String})
ReturnDate.index_return = model.Property(
    f"{ReturnDate} has index return {Float:index_return}"
)
model.define(ReturnDate.new(model.data(index_returns_csv).to_schema()))

Stock.return_on = model.Property(
    f"{Stock} on {ReturnDate} has return {Float:stock_return}"
)
stock_return_data = model.data(stock_returns_csv)
model.define(Stock.return_on(ReturnDate, stock_return_data["return"])).where(
    Stock.ticker(stock_return_data.ticker),
    ReturnDate.date(stock_return_data.date),
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

Stock.x_selected = model.Property(f"{Stock} selected if {Float:selected}")
Stock.x_weight = model.Property(f"{Stock} has replication weight {Float:weight}")
ReturnDate.x_pos_error = model.Property(
    f"{ReturnDate} has positive tracking residual {Float:pos_error}"
)
ReturnDate.x_neg_error = model.Property(
    f"{ReturnDate} has negative tracking residual {Float:neg_error}"
)

selected = Float.ref("selected")
weight = Float.ref("weight")
pos_error = Float.ref("pos_error")
neg_error = Float.ref("neg_error")
index_return = Float.ref("index_return")
stock_return = Float.ref("stock_return")

problem = Problem(model, Float)

problem.solve_for(
    Stock.x_selected(selected),
    type="bin",
    name=["selected", Stock.ticker],
)
problem.solve_for(
    Stock.x_weight(weight),
    type="cont",
    lower=0,
    upper=MAX_WEIGHT,
    name=["weight", Stock.ticker],
)
problem.solve_for(
    ReturnDate.x_pos_error(pos_error),
    type="cont",
    lower=0,
    name=["pos_error", ReturnDate.date],
)
problem.solve_for(
    ReturnDate.x_neg_error(neg_error),
    type="cont",
    lower=0,
    name=["neg_error", ReturnDate.date],
)

# Select exactly N names and invest all capital.
problem.satisfy(
    model.where(Stock.x_selected(selected)).require(
        sum(selected) == N_REPLICATION_NAMES
    )
)
# Full-investment constraint: portfolio weights must sum to 100%.
problem.satisfy(model.where(Stock.x_weight(weight)).require(sum(weight) == 1.0))

# A stock can carry weight only when selected.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.x_selected(selected),
    ).require(weight <= MAX_WEIGHT * selected)
)

# Exclude stocks below the liquidity floor.
problem.satisfy(
    model.where(
        Stock.x_selected(selected),
        Stock.avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME,
    ).require(selected == 0)
)

# Keep sector exposures close to benchmark sector weights.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.sector_ref(Sector),
    ).require(
        sum(weight).per(Sector) <= Sector.benchmark_weight + SECTOR_ACTIVE_BAND
    )
)
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
        Stock.sector_ref(Sector),
    ).require(
        sum(weight).per(Sector) >= Sector.benchmark_weight - SECTOR_ACTIVE_BAND
    )
)

# Limit per-name buy and sell dollars as a fraction of average dollar volume.
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
    ).require(
        PORTFOLIO_VALUE * (weight - Stock.previous_weight)
        <= MAX_ADV_PARTICIPATION * Stock.avg_dollar_volume
    )
)
problem.satisfy(
    model.where(
        Stock.x_weight(weight),
    ).require(
        PORTFOLIO_VALUE * (Stock.previous_weight - weight)
        <= MAX_ADV_PARTICIPATION * Stock.avg_dollar_volume
    )
)

# Monthly benchmark residual:
# index_return[t] - sum_i weight[i] * stock_return[i,t] = pos_error[t] - neg_error[t]
problem.satisfy(
    model.where(
        ReturnDate.index_return(index_return),
        ReturnDate.x_pos_error(pos_error),
        ReturnDate.x_neg_error(neg_error),
        Stock.x_weight(weight),
        Stock.return_on(ReturnDate, stock_return),
    ).require(
        index_return - sum(stock_return * weight).per(ReturnDate)
        == pos_error - neg_error
    )
)

# Minimize total absolute tracking residual.
problem.minimize(
    sum(pos_error + neg_error).where(
        ReturnDate.x_pos_error(pos_error),
        ReturnDate.x_neg_error(neg_error),
    )
)

# --------------------------------------------------
# Solve
# --------------------------------------------------

print("=" * 70)
print("FINANCIAL INDEX REPLICATION")
print("=" * 70)
print(f"Universe: {len(stocks_csv)} stocks")
print(f"Selected names: exactly {N_REPLICATION_NAMES}")
print(f"Max position: {MAX_WEIGHT:.0%}")
print(f"Sector active band: +/- {SECTOR_ACTIVE_BAND:.0%}")
print(f"Liquidity floor: ${MIN_AVG_DOLLAR_VOLUME / 1_000_000:.0f}M average dollar volume")
print(f"Portfolio value: ${PORTFOLIO_VALUE:,.0f}")
print(f"Max ADV participation per name: {MAX_ADV_PARTICIPATION:.0%}")

problem.display()
problem.solve("highs", time_limit_sec=120)
si = problem.solve_info()
si.display()
model.require(problem.termination_status() == "OPTIMAL")

print(f"\nStatus: {si.termination_status}")
print(f"Objective: total absolute residual = {si.objective_value:.6f}")

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

returns_wide = stock_returns_csv.pivot(
    index="date", columns="ticker", values="return"
).sort_index()
index_series = index_returns_csv.set_index("date").sort_index()
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
        stocks_csv.groupby("sector", as_index=False)["benchmark_weight"].sum(),
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

turnover = (
    solution_df.set_index("ticker")["weight"]
    .reindex(stocks_csv["ticker"], fill_value=0.0)
    .sub(stocks_csv.set_index("ticker")["previous_weight"])
    .abs()
    .sum()
)

print("\n=== Tracking Quality ===")
print(f"Annualized tracking error: {annualized_tracking_error():.2%}")
print(f"Mean abs monthly residual: {mean_abs_tracking():.4%}")
print(f"Implied turnover: {turnover:.2%}")

# Simple benchmark: equal-weight the 20 most correlated liquid stocks.
eligible_ids = stocks_csv.loc[
    stocks_csv["avg_dollar_volume"] >= MIN_AVG_DOLLAR_VOLUME, "ticker"
]
top_corr_ids = (
    returns_wide[eligible_ids]
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
print("Baseline: equal-weight top-20 liquid stocks by full-history correlation")
print(f"Baseline annualized tracking error: {baseline_tracking_error:.2%}")
print(f"\nWrote benchmark-vs-replica returns to: {replica_returns_csv}")
