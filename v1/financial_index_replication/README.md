---
title: "Financial Index Replication"
description: "This template selects 20 of 50 sample stocks and sets how much to invest in each. The goal is to keep their combined returns close to a broad market index while limiting holding size, sector mix, and trading volume."
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

Explore the [model](https://docs.relational.ai/build/templates/financial_index_replication/#explore-the-model) and [guided walkthrough](https://docs.relational.ai/build/templates/financial_index_replication/#see-how-it-works) in the documentation.

## What this template is for

An asset manager wants to follow a broad market index, called a benchmark, without buying every stock it contains. A smaller basket means fewer holdings to manage, but its returns can drift from the benchmark or become too concentrated in a few stocks or sectors.

Using synthetic monthly returns, this template selects 20 of 50 stocks and assigns weights to keep the basket close to the benchmark within position, sector, and trading-volume limits. It reports tracking error, a measure of how far the basket's returns differ from the benchmark, and compares the result with a simple alternative. Adapt the data and portfolio limits for another index strategy, but treat this example as a starting point rather than a production portfolio.

## Quickstart

Before you start, install Python 3.10 or later. You need a Snowflake account
with the RAI Native App, user access to the app, and an engine enabled for
Prescriptive reasoning. Prescriptive reasoning is in Public Preview and
available by request. Preview features are for evaluation and testing, not
production applications. The template installs the SDK version pinned in
`pyproject.toml`: `relationalai==1.0.14`.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/financial_index_replication.zip). Unzip it and enter the template directory:

   ```bash
   unzip financial_index_replication.zip
   cd financial_index_replication
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the template and its dependencies in the active environment:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory. Follow that guide to save the file and verify your connection.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python financial_index_replication.py
   ```

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

   The solve selects exactly 20 names, though some selected names may have zero weight. It reports the basket, sector exposures, tracking quality, and a baseline comparison, and writes `data/replica_returns.csv` for plotting. The full printout is in `runbook.md`.
