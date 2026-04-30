---
title: "Financial Index Replication"
description: "Prescriptive optimization template for selecting a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
    - Prescriptive
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

The model uses RelationalAI's **prescriptive** reasoner to optimize both selection and sizing in one mixed-integer program. It includes practical portfolio constraints: long-only weights, max position size, liquidity eligibility, sector neutrality, and per-name ADV participation limits.

## Why this problem matters

Holding every index constituent can be operationally expensive, especially for smaller accounts, tax-aware portfolios, or products with custody and trading constraints. A sparse replicating basket gives most of the benchmark exposure while reducing the number of positions to trade and maintain.

The hard part is that name selection and weight optimization interact. The best 20 names are not simply the largest constituents or the highest-correlated stocks; they need to work together as a portfolio while respecting sector and liquidity rules.

### Key design patterns demonstrated

- **Cardinality-constrained selection** -- binary variables choose exactly 20 stocks.
- **Linked binary and continuous decisions** -- a stock can carry weight only if selected.
- **Tracking objective** -- the solver minimizes absolute tracking residuals while the script reports realized RMS tracking error after solving.
- **Sector neutrality** -- replicated sector exposure must stay within a fixed active band around benchmark sector weights.
- **Liquidity screen** -- illiquid names are excluded from selection.
- **ADV participation control** -- each stock's buy or sell amount is capped as a fraction of average daily dollar volume.
- **Full-history evaluation** -- optimize across the entire return history and report realized tracking quality.
- **Baseline comparison** -- compare against equal-weight top-20 liquid stocks by full-history correlation.

## Who this is for

- Quantitative analysts building index replication workflows
- Portfolio managers exploring sparse benchmark tracking
- Data scientists learning mixed-integer optimization with financial constraints
- Engineers modeling linked selection and allocation decisions

## What you'll build

- A semantic model for stocks, sectors, benchmark returns, and stock returns
- A mixed-integer optimization model with 20-name cardinality
- Long-only portfolio weights with max position constraints
- Liquidity, sector-neutrality, and ADV participation constraints
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
   curl -O https://private.relational.ai/templates/zips/v1/financial_index_replication.zip
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
   Liquidity floor: $100M average dollar volume
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
   Baseline: equal-weight top-20 liquid stocks by full-history correlation
   Baseline annualized tracking error: ...
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

### 4. Add portfolio realism

The template includes constraints practitioners expect:

- exactly 20 selected stocks
- weights sum to 100%
- no shorting
- max 10% per selected stock
- minimum average dollar volume
- sector weights within +/- 4% of benchmark sector weights
- per-name buy and sell amounts no more than 5% of average daily dollar volume

### 5. Evaluate the portfolio

After solving, the script reports:

- selected names and weights
- sector exposures and active sector weights
- annualized tracking error
- mean absolute residual
- implied turnover
- comparison to a simple top-correlation baseline

## Customize

- Change `N_REPLICATION_NAMES` to select more or fewer names.
- Tighten `SECTOR_ACTIVE_BAND` for stricter sector neutrality.
- Raise `MIN_AVG_DOLLAR_VOLUME` to enforce more liquid baskets.
- Lower `MAX_ADV_PARTICIPATION` for stricter per-name trading capacity.
- Replace the synthetic CSVs with real benchmark and constituent returns if your data license allows it.
