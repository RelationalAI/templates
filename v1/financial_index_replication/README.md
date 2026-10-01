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

**Full guide:** [Explore the Financial Index Replication model, run the example, and follow the code](https://docs.relational.ai/build/templates/financial_index_replication/).

## What this template is for

An asset manager may want to follow a broad market index without buying every
stock it contains. Using synthetic monthly returns, this template selects 20 of
50 stocks and assigns weights that track the benchmark within position, sector,
and trading-volume limits. It reports tracking error and compares the result
with a simple alternative. Adapt the data and limits for another index
strategy, but treat the example as a starting point rather than a production
portfolio.

## Quickstart

Before you start, install Python 3.10 or later and get access to a Snowflake
account with the RAI Native App. Prescriptive reasoning is in Public Preview;
ask your RelationalAI support representative to enable it. Preview features are
for evaluation and testing, not production applications. The template pins
`relationalai==1.0.14` in `pyproject.toml`.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/financial_index_replication.zip), unzip it, and enter the template directory:

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

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python financial_index_replication.py
   ```

   ```text
   Selected names: exactly 20
   Status: OPTIMAL
   Wrote benchmark-vs-replica returns to: data/replica_returns.csv
   ```

   The solve selects exactly 20 names, though a selected stock may have zero
   weight. It writes `data/replica_returns.csv` for plotting. See `runbook.md`
   for the basket, sector exposures, tracking quality, and baseline comparison.
