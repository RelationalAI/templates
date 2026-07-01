---
title: "Financial Index Replication"
description: "Select a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
    - Prescriptive
    - Rules-based
tags:
  - Mixed-Integer Programming
  - Portfolio Optimization
  - Index Replication
  - Tracking Error
  - Sparse Portfolio
  - Cardinality Constraint
  - Sector Neutrality
  - ADV Participation Constraint
  - HiGHS
---

## What this template is for

Index funds and separately managed accounts often need to track a broad benchmark without holding every constituent. Full replication is operationally expensive, especially for smaller accounts, tax-aware portfolios, or products with custody and trading constraints. A sparse replicating basket captures most of the benchmark exposure while cutting the number of positions to trade and maintain.

The hard part is that name selection and weight sizing interact. The best 20 names are not simply the largest constituents or the highest-correlated stocks; they have to work together as a portfolio while respecting sector and per-name trading-capacity rules. This template builds that basket from a 50-stock, S&P 500-like universe: it selects exactly 20 names and their weights so the portfolio follows the benchmark's historical returns as closely as possible.

**It uses Prescriptive reasoning to co-optimize selection and sizing in a single mixed-integer program that minimizes tracking residuals subject to long-only weights, a maximum position size, sector neutrality, and per-name average-daily-volume (ADV) participation limits.**

## Who this is for

- Quantitative analysts building index replication workflows
- Portfolio managers exploring sparse benchmark tracking
- Data scientists learning mixed-integer optimization with financial constraints
- Engineers modeling linked selection and allocation decisions

## What you'll build

- A semantic model for stocks, sectors, benchmark returns, and stock returns
- A mixed-integer optimization model with 20-name cardinality
- Long-only portfolio weights with max position constraints
- Sector-neutrality and ADV participation constraints
- A tracking residual objective over historical returns
- Full-history tracking error reports and a simple baseline comparison

## What's included

- `financial_index_replication.py` -- Main script with the semantic model, optimization model, solve, and reporting
- `data/stocks.csv` -- 50-stock universe with ticker, sector, benchmark weight, liquidity, and previous weight
- `data/index_returns.csv` -- Monthly S&P 500-like benchmark returns
- `data/stock_returns.csv` -- Monthly historical returns by stock
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/financial_index_replication.zip
   unzip financial_index_replication.zip
   cd financial_index_replication
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python financial_index_replication.py
   ```

6. Expected output (a few lines confirm a successful run; exact figures depend on the data):

   ```text
   ======================================================================
   FINANCIAL INDEX REPLICATION
   ======================================================================
   Universe: 50 stocks
   Selected names: exactly 20
   Max position: 10%
   Sector active band: +/- 4%

   Status: OPTIMAL
   Objective: total absolute residual = ...

   === Selected Replication Basket ===
   ticker  sector  weight  benchmark_weight  previous_weight  avg_dollar_volume
   ...

   Wrote benchmark-vs-replica returns to: data/replica_returns.csv
   ```

   The solve selects exactly 20 names, reports the basket, sector exposures, tracking quality, and a baseline comparison, and writes `data/replica_returns.csv` for plotting. The full printout is in `runbook.md`.

## Template structure

```text
.
├─ README.md                            # this file
├─ pyproject.toml                       # dependencies
├─ financial_index_replication.py      # main entrypoint: model, solve, report
└─ data/
   ├─ stocks.csv                        # 50-stock universe
   ├─ index_returns.csv                 # benchmark monthly returns
   ├─ stock_returns.csv                 # per-stock monthly returns
   └─ replica_returns.csv               # written by the script after solving
```

**Start here**: run `python financial_index_replication.py` for the full solve and reporting end to end.

## Sample data

The bundled data is synthetic but shaped like an S&P 500 replication problem, so the template runs without licensed market data.

- **`data/stocks.csv`** (50 rows) -- the investable universe: `ticker`, `name`, `sector`, `benchmark_weight`, `avg_dollar_volume`, and `previous_weight` (the prior-period holding).
- **`data/index_returns.csv`** -- monthly benchmark returns keyed by `date` (`index_return`).
- **`data/stock_returns.csv`** -- monthly per-stock returns keyed by `date` and `ticker` (`return`).
- **`data/replica_returns.csv`** -- written by the script after solving, with `date`, `index_return`, and `replica_return` for downstream plotting.

The benchmark constituent weights were generated by first assigning broad target sector allocations, then drawing uneven positive stock weights within each sector and scaling each sector back to its target. The benchmark return each month is the weighted sum of all constituent returns, plus a small noise term so the sparse 20-name replication problem is realistic rather than perfectly mechanical.

## Model overview

Four concepts describe the universe, its sector grouping, and the historical return panel; the decision variables attach to `Stock` and `ReturnDate`.

- **Key entities**: `Stock` (a constituent in the investable universe), `Sector` (a grouping used for the neutrality constraint), and `ReturnDate` (a month in the return panel).
- **Primary identifiers**: `Stock` by `ticker`; `Sector` by `sector_name`; `ReturnDate` by `date`.
- **Important invariants**: exactly `N_REPLICATION_NAMES` stocks are selected; weights are non-negative, at most `MAX_WEIGHT` each, and sum to 100%; a stock can carry weight only if selected; each sector's weight stays within `SECTOR_ACTIVE_BAND` of its benchmark weight.

### `Stock`

A constituent in the investable universe. The selection and weight decision variables attach here.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `ticker` | String | Yes | Loaded from `data/stocks.csv` |
| `name` | String | No | Company name |
| `sector` | String | No | GICS-style sector label |
| `benchmark_weight` | Float | No | Weight in the benchmark |
| `avg_dollar_volume` | Float | No | Average daily dollar volume, for the ADV participation cap |
| `previous_weight` | Float | No | Prior-period portfolio weight, for turnover and ADV |
| `sector_ref` | Relationship | — | Link to the stock's `Sector` |
| `x_selected` | Float (binary) | No | Decision variable: 1 if the stock is in the basket |
| `x_weight` | Float | No | Decision variable: portfolio weight (0 to `MAX_WEIGHT`) |

### `Sector`

A GICS-style grouping derived from `Stock.sector`, carrying an aggregated benchmark weight for the neutrality constraint.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `sector_name` | String | Yes | Distinct values of `Stock.sector` |
| `benchmark_weight` | Float | No | Sum of member stocks' benchmark weights |

### `ReturnDate`

A month in the historical return panel, carrying the benchmark's index return and the per-month tracking-residual variables.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `date` | String | Yes | Loaded from `data/index_returns.csv` |
| `index_return` | Float | No | Benchmark return for the month |
| `x_pos_error` | Float | No | Decision variable: positive tracking residual |
| `x_neg_error` | Float | No | Decision variable: negative tracking residual |

### Relationships

| Relationship | Schema | Notes |
|---|---|---|
| `Stock.return_on(ReturnDate, stock_return)` | `Stock`, `ReturnDate`, `Float` | Per-stock monthly return; joins the return panel to the weights in the tracking constraint |
| `Stock.sector_ref(Sector)` | `Stock`, `Sector` | Assigns each stock to its sector |

## How it works

The design patterns worth noting: **cardinality-constrained selection** (binary variables choose exactly 20 stocks), **linked binary and continuous decisions** (a stock carries weight only if selected), an **L1 tracking objective** (minimize absolute residuals to keep the problem linear with binary selection), **sector neutrality** (replicated sector exposure stays within a fixed active band), **ADV participation control** (each name's buy or sell is capped as a fraction of average daily dollar volume), and a **baseline comparison** against an equal-weight top-correlation basket.

### 1. Define selection and weight variables

The model has two main decisions per stock:

```python
Stock.x_selected = model.Property(f"{Stock} selected if {Float:selected}")
Stock.x_weight = model.Property(f"{Stock} has replication weight {Float:weight}")
```

`x_selected` is binary. `x_weight` is continuous. The linking constraint keeps unselected names at zero weight:

```python
weight <= MAX_WEIGHT * selected
```

### 2. Match benchmark returns

For each historical month, the model creates positive and negative residual variables:

```text
index_return[t] - sum_i weight[i] * stock_return[i,t] = pos_error[t] - neg_error[t]
```

The objective minimizes total absolute residual:

```text
minimize sum_t pos_error[t] + neg_error[t]
```

This keeps the solver problem linear and mixed-integer. After solving, the script computes the standard RMS tracking error across the full history.

This template uses an L1 tracking objective because absolute residuals keep the model linear with binary selection variables. A classic L2 objective, minimizing squared residuals, is also a natural tracking-error formulation if the selected solver supports the resulting mixed-integer quadratic problem.

### 3. Add portfolio realism

The template includes constraints practitioners expect:

- exactly 20 selected stocks
- weights sum to 100%
- no shorting
- max 10% per selected stock
- sector weights within +/- 4% of benchmark sector weights
- per-name buy and sell amounts no more than 5% of average daily dollar volume (ADV)

### 4. Evaluate the portfolio

After solving, the script reports:

- selected names and weights
- sector exposures and active sector weights
- annualized tracking error
- mean absolute residual
- implied turnover
- comparison to a simple top-correlation baseline
- `data/replica_returns.csv` with `date`, `index_return`, and `replica_return`

You can use `data/replica_returns.csv` to plot the original benchmark return series against the optimized replica return series.

## Customize this template

### Use your own data

- Replace the synthetic CSVs with real benchmark and constituent returns if your data license allows it. Keep the headers: `ticker`, `sector`, `benchmark_weight`, `avg_dollar_volume`, `previous_weight` for `stocks.csv`; `date`, `index_return` for `index_returns.csv`; `date`, `ticker`, `return` for `stock_returns.csv`.
- Make sure all three files cover the same date range and use the same return convention (simple or log); a mismatch silently drops months from the join or inflates residuals.

### Tune parameters

- `N_REPLICATION_NAMES` sets how many names the basket holds.
- `MAX_WEIGHT` tightens or relaxes the largest allowed position size.
- `SECTOR_ACTIVE_BAND` controls sector neutrality; tighten it for stricter tracking to benchmark sector weights.
- `MAX_ADV_PARTICIPATION` sets per-name trading capacity; lower it for stricter ADV limits.

### Extend the model

- Swap the L1 tracking objective for an L2 (squared-residual) objective if your solver supports the resulting mixed-integer quadratic problem.
- Add constraints practitioners expect, such as a turnover cap against `previous_weight` or a minimum position size for selected names.

### Scale up / productionize

- Point the `pd.read_csv` calls at Snowflake tables via `model.data(...)` to run over a larger universe and longer return history.
- Pin dependencies and fix any random seed in the data-generation step for reproducible baskets across runs.

## Troubleshooting

<details>
    <summary>Why is the solver returning <code>INFEASIBLE</code>?</summary>

    - The combination of `N_REPLICATION_NAMES`, `SECTOR_ACTIVE_BAND`, and `MAX_ADV_PARTICIPATION` may be over-constrained for the universe. Loosen the sector band first (e.g., 0.04 -> 0.06) and re-run.
    - `MAX_ADV_PARTICIPATION` interacts with `PORTFOLIO_VALUE` and `previous_weight`. A large portfolio rebalancing into low-ADV names can be infeasible -- raise the ADV cap, lower portfolio value, or expand the universe.
    - Check that `MAX_WEIGHT * N_REPLICATION_NAMES >= 1.0` so the full-investment constraint is reachable.
</details>

<details>
    <summary>Why does <code>rai init</code> fail or hang?</summary>

    - Confirm the RAI Native App is installed in your Snowflake account and your user has access.
    - Check that your active Snowflake profile points to the right account/role; re-run `rai init` to refresh credentials.
    - Network proxies and corporate firewalls can block the auth handshake -- try from an unrestricted network.
</details>

<details>
    <summary>Why are my tracking-error numbers worse than the baseline?</summary>

    - Verify that all three CSVs cover the same date range. A mismatch causes the script to silently drop months from the join.
    - Confirm `index_returns.csv` and `stock_returns.csv` use the same return convention (simple vs log) -- mixing them inflates residuals.
    - Inspect the selected basket's sector exposure: a tight `SECTOR_ACTIVE_BAND` can push the optimizer away from the highest-correlation names.
</details>

<details>
    <summary>Why did <code>pd.read_csv</code> fail on one of the data files?</summary>

    - Confirm the file exists under `data/` and matches the expected headers (`ticker`, `sector`, `benchmark_weight`, `avg_dollar_volume`, `previous_weight` for stocks; `date,index_return` for index; `date,ticker,return` for stock returns).
    - Re-extract the template ZIP if any file looks truncated.
    - On Windows, ensure files are UTF-8 encoded with no BOM.
</details>

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used to co-optimize selection and weights.
- [Mixed-integer optimization](https://docs.relational.ai/) — binary selection variables linked to continuous weights, and the cardinality constraint.

### Language / modeling reference

- [PyRel v1 language](https://docs.relational.ai/) — concepts, properties, and relationships as used to model stocks, sectors, and the return panel.

### CLI / SDK guides

- [`rai init` and configuration](https://docs.relational.ai/) — connecting the template to your Snowflake-backed RAI account.

## Support

- File issues at the RelationalAI templates repository.
