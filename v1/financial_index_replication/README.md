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

# Financial Index Replication

## What this template is for

Index funds and separately managed accounts often need to track a broad benchmark without holding every constituent. This template builds a sparse replication basket: from 50 S&P 500-like stocks, select exactly 20 names and their weights so the portfolio follows the benchmark's historical returns as closely as possible.

The model uses RelationalAI's **prescriptive** reasoner to optimize both selection and sizing in one mixed-integer program. It includes practical portfolio constraints: long-only weights, max position size, sector neutrality, and per-name ADV participation limits.

## Why this problem matters

Holding every index constituent can be operationally expensive, especially for smaller accounts, tax-aware portfolios, or products with custody and trading constraints. A sparse replicating basket gives most of the benchmark exposure while reducing the number of positions to trade and maintain.

The hard part is that name selection and weight optimization interact. The best 20 names are not simply the largest constituents or the highest-correlated stocks; they need to work together as a portfolio while respecting sector and per-name trading-capacity rules.

### Key design patterns demonstrated

- **Cardinality-constrained selection** -- binary variables choose exactly 20 stocks.
- **Linked binary and continuous decisions** -- a stock can carry weight only if selected.
- **Tracking objective** -- the solver minimizes absolute tracking residuals while the script reports realized RMS tracking error after solving.
- **Sector neutrality** -- replicated sector exposure must stay within a fixed active band around benchmark sector weights.
- **ADV participation control** -- ADV stands for average daily dollar volume; each stock's buy or sell amount is capped as a fraction of ADV.
- **Full-history evaluation** -- optimize across the entire return history and report realized tracking quality.
- **Baseline comparison** -- compare against equal-weight top-20 stocks by full-history correlation.

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

**Start here**: run `python financial_index_replication.py`.

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

6. Expected output:
   ```text
   ======================================================================
   FINANCIAL INDEX REPLICATION
   ======================================================================
   Universe: 50 stocks
   Selected names: exactly 20
   Max position: 10%
   Sector active band: +/- 4%
   Portfolio value: $10,000,000
   Max ADV participation per name: 5%

   Status: OPTIMAL
   Objective: total absolute residual = ...

   === Selected Replication Basket ===
   ticker                  sector weight benchmark_weight previous_weight avg_dollar_volume
     ...                     ...   ...          ...             ...              ...

   === Sector Exposure ===
                    sector weight benchmark_weight active_weight
     Consumer Discretionary  ...        ...             ...
     ...

   === Tracking Quality ===
   Annualized tracking error: ...
   Mean abs monthly residual: ...
   Implied turnover: ...

   === Baseline Comparison ===
   Baseline: equal-weight top-20 stocks by full-history correlation
   Baseline annualized tracking error: ...

   Wrote benchmark-vs-replica returns to: data/replica_returns.csv
   ```

## How It Works

### 1. Load the universe

The template loads a compact synthetic dataset:

- `stocks.csv`: identifiers, sectors, benchmark weights, liquidity, and previous holdings
- `index_returns.csv`: monthly benchmark returns
- `stock_returns.csv`: monthly returns for each stock

The data is synthetic but shaped like an S&P 500 replication problem, so the template is runnable without licensed market data.

The benchmark constituent weights were generated by first assigning broad target
sector allocations, then drawing uneven positive stock weights within each
sector and scaling those names so each sector sums back to its target. This
creates a market-cap-like benchmark shape without using licensed constituent
weights. The benchmark return for each month is then calculated from the stock
return table as the weighted sum of all constituent returns, with a small random
noise term added so the sparse 20-name replication problem is realistic rather
than perfectly mechanical.

### 2. Define selection and weight variables

The model has two main decisions per stock:

```python
Stock.x_selected = model.Property(f"{Stock} selected if {Float:selected}")
Stock.x_weight = model.Property(f"{Stock} has replication weight {Float:weight}")
```

`x_selected` is binary. `x_weight` is continuous. The linking constraint keeps unselected names at zero weight:

```python
weight <= MAX_WEIGHT * selected
```

### 3. Match benchmark returns

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

### 4. Add portfolio realism

The template includes constraints practitioners expect:

- exactly 20 selected stocks
- weights sum to 100%
- no shorting
- max 10% per selected stock
- sector weights within +/- 4% of benchmark sector weights
- per-name buy and sell amounts no more than 5% of average daily dollar volume (ADV)

### 5. Evaluate the portfolio

After solving, the script reports:

- selected names and weights
- sector exposures and active sector weights
- annualized tracking error
- mean absolute residual
- implied turnover
- comparison to a simple top-correlation baseline
- `data/replica_returns.csv` with `date`, `index_return`, and `replica_return`

You can use `data/replica_returns.csv` to plot the original benchmark return series against the optimized replica return series.

## Customize

- Change `N_REPLICATION_NAMES` to select more or fewer names.
- Change `MAX_WEIGHT` to tighten or relax the largest allowed position size.
- Tighten `SECTOR_ACTIVE_BAND` for stricter sector neutrality.
- Lower `MAX_ADV_PARTICIPATION` for stricter per-name trading capacity.
- Replace the synthetic CSVs with real benchmark and constituent returns if your data license allows it.

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
