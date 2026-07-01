# Financial Index Replication — Analyst Runbook

A portfolio manager wants to track a broad benchmark without holding all of its constituents — a sparse basket is cheaper to run, easier to custody, and more tax-flexible. From a 50-stock S&P 500-like universe, the goal is to pick exactly 20 names and size their weights so the portfolio follows the benchmark's historical returns as closely as possible, while staying long-only, diversified, sector-neutral, and within realistic trading-capacity limits. The dataset is 50 stocks, 42 months of returns, and the benchmark's monthly index returns. The analysis selects names and weights jointly in one mixed-integer linear program.

```text
50-stock universe (benchmark weight, sector, ADV) · 42 months of returns · benchmark index returns
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: pick 20 names (binary) + weights (continuous) + monthly tracking residuals
   • constraints: exactly 20 names; weights sum to 1; ≤ 10% per name; sectors within ±4% of benchmark;
     trading-capacity (ADV) limit; residual = benchmark − basket return each month
   • objective: minimize total absolute monthly tracking error (L1)
   • HiGHS mixed-integer program (240s cap)      -> feasible basket, ~0.4% annualized tracking error
      │
      ▼
/rai-prescriptive-results-interpretation
   • the 20-name basket tracks the benchmark to well under 1% annualized error
   • several times tighter than an equal-weight top-20 baseline (~2.6%); solve is time-limited
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Stock`/`ReturnDate`/`Sector` concepts the build step created, and the interpret step reads the `Stock.x_selected` and `Stock.x_weight` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/stocks.csv` (each stock has a benchmark weight, a sector, an average dollar volume, and a previous weight), `data/index_returns.csv` (the benchmark's monthly return per date), and `data/stock_returns.csv` (each stock's monthly return per date). Derive sectors from the stocks, and model the stock return as a relationship from a stock to a date carrying that month's return.

**Response:** Loads `Stock` (50, with `benchmark_weight`, `sector`, `avg_dollar_volume`, `previous_weight`), `ReturnDate` (42 monthly dates with the benchmark `index_return`), a derived `Sector` (7, carrying each sector's aggregated benchmark weight), and a `Stock.return_on(ReturnDate)` relationship (2,100 stock-month returns).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Concepts — 50 `Stock`, 42 `ReturnDate` (with `index_return`), and a derived `Sector` (7: Technology, Healthcare, Consumer Discretionary, Financials, Industrials, Consumer Staples, Energy) — linked by `return_on` with 2,100 stock-month return rows (50 stocks x 42 months).

## 3. Build the replication basket

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Which 20 stocks, and at what weights, best replicate the benchmark's monthly returns? Select exactly 20 names (binary) and assign continuous weights that sum to 1, with at most 10% in any one name and a weight only if the name is selected; keep each sector within ±4% of its benchmark weight; respect a trading-capacity limit (the change from the previous weight, scaled by a $10 million portfolio value, can't exceed 5% of a stock's average dollar volume); and define each month's tracking residual as benchmark return minus basket return. Minimize the total absolute monthly tracking error, and persist the selection and weights to the ontology.

**Response:** Returns a 20-name basket. The decision is `Stock.x_selected` (exactly 20 names) plus `Stock.x_weight` (summing to 1) and per-month residual variables. This is a cardinality-constrained tracking MILP: depending on the solver it either solves to OPTIMAL or returns a strong feasible incumbent at the time limit — either way the exact names and weights can vary, so treat the tracking quality below, not a specific basket, as the result.

## 4. Assess tracking quality

**Prompt:** /rai-prescriptive-results-interpretation How closely does the basket track the benchmark (annualized tracking error), and how does it compare to a naive equal-weight basket of the 20 stocks most correlated with the benchmark?

**Response:** The optimized 20-name basket tracks the benchmark to a **low annualized tracking error — on the order of ~0.4%** (the exact figure varies with the solver and solve settings) — **materially tighter than the naive equal-weight top-20-by-correlation baseline (~2.6%)**. It holds sector neutrality within the ±4% band (Energy and Consumer Staples sit closest to the edge). The reproducible headline is that the optimized basket tracks well under the naive one, not any single name list.

## Data

Bundled CSVs in `data/`: 50 stocks, 42 monthly index returns, 2,100 stock-month returns. The policy parameters (20 names, 10% max weight, ±4% sector band, ADV limit) are constants in the script; the run writes a `replica_returns.csv` of monthly basket vs benchmark returns. Full model in `financial_index_replication.py`.
