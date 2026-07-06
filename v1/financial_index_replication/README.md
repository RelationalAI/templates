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
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself
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
├─ runbook.md                           # step-by-step analyst walkthrough
├─ pyproject.toml                       # dependencies
├─ financial_index_replication.py      # main entrypoint: model, solve, report
└─ data/
   ├─ stocks.csv                        # 50-stock universe
   ├─ index_returns.csv                 # benchmark monthly returns
   ├─ stock_returns.csv                 # per-stock monthly returns
   └─ replica_returns.csv               # written by the script after solving
```

**Start here**: run `python financial_index_replication.py` for the full solve and reporting end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

For the full concept and property definitions, see `financial_index_replication.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The design patterns worth noting: **cardinality-constrained selection** (binary variables choose exactly 20 stocks), **linked binary and continuous decisions** (a stock carries weight only if selected), an **L1 tracking objective** (minimize absolute residuals to keep the problem linear with binary selection), **sector neutrality** (replicated sector exposure stays within a fixed active band), **ADV participation control** (each name's buy or sell is capped as a fraction of average daily dollar volume), and a **baseline comparison** against an equal-weight top-correlation basket.

```text
stocks + returns → selection + weight variables → tracking residuals → cardinality/sector/ADV constraints → MIP solve → basket + tracking report
```

### 1. Define selection and weight variables

Each stock carries two linked decisions: a binary `x_selected` (in the basket or not) and a continuous `x_weight` (portfolio weight). A linking constraint holds `weight <= MAX_WEIGHT * selected`, so an unselected name is forced to zero weight.

### 2. Match benchmark returns

For each historical month, the model creates positive and negative residual variables that absorb the gap between the benchmark return and the replica's weighted return:

```text
index_return[t] - sum_i weight[i] * stock_return[i,t] = pos_error[t] - neg_error[t]
```

The objective minimizes the total absolute residual:

```text
minimize sum_t pos_error[t] + neg_error[t]
```

This L1 formulation keeps the problem linear and mixed-integer with the binary selection variables; after solving, the script computes the standard RMS tracking error across the full history. A classic L2 objective (squared residuals) is also a natural tracking-error formulation if the selected solver supports the resulting mixed-integer quadratic problem.

### 3. Add portfolio realism

The template layers on the constraints practitioners expect: exactly 20 selected stocks; weights sum to 100%; no shorting; max 10% per selected stock; sector weights within +/- 4% of benchmark sector weights; and per-name buy and sell amounts no more than 5% of average daily dollar volume (ADV).

### 4. Evaluate the portfolio

After solving, the script reports the selected names and weights, sector exposures and active sector weights, annualized tracking error, mean absolute residual, implied turnover, and a comparison to a simple top-correlation baseline. It also writes `data/replica_returns.csv` (`date`, `index_return`, `replica_return`) so you can plot the benchmark series against the optimized replica.

See `financial_index_replication.py` for the implementation and `runbook.md` for the skill-driven reproduction.

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
