---
title: "Portfolio Re-balancing"
description: "Flag holdings that exceed concentration limits, group stocks that tend to move together, and compare rebalanced portfolios by expected return and risk under normal and stressed markets."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Prescriptive
  - Rules-based
  - Graph
tags:
  - Multi-Reasoner
  - Portfolio Optimization
  - Quadratic Programming
  - Community Detection
  - Sensitivity Analysis
  - Stress Testing
---

Explore the [model](https://docs.relational.ai/build/templates/portfolio_balancing/#explore-the-model) and [guided walkthrough](https://docs.relational.ai/build/templates/portfolio_balancing/#see-how-it-works) in the documentation.

## What this template is for

Investment managers need to keep client portfolios within concentration and compliance limits while weighing expected return against risk. A portfolio can look diversified across many stocks yet still carry hidden risk when holdings share a sector or tend to move together, especially during market stress.

This template combines portfolio holdings, expected returns, and covariance data to flag concentration problems, group correlated stocks, and calculate rebalanced allocations under portfolio constraints. Use it as a starting point for adapting the investment universe, limits, objectives, or stress scenarios to your own portfolio.

## Quickstart

Before you start, install Python 3.10 or later. You need a Snowflake account
with the RAI Native App, user access to the app, and an engine enabled for
Prescriptive reasoning. Graph and Prescriptive reasoning are in Public Preview,
and Prescriptive reasoning is available by request. Preview features are for
evaluation and testing, not production applications. The template installs the
SDK version pinned in `pyproject.toml`: `relationalai==1.9.0`.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/portfolio_balancing.zip). Unzip it and enter the template directory:

   ```bash
   unzip portfolio_balancing.zip
   cd portfolio_balancing
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
   python portfolio_balancing.py
   ```

   ```text
   STAGE 2: GRAPH -- Covariance Clustering (Louvain)
     Louvain communities: 5 cluster(s)
     Cluster representatives (5 of 8 stocks, picked by highest Sharpe): ...

   SENSITIVITY-GUIDED FRONTIER  (reference 'base_1000', 6-solve budget per method)
     method        solves     max chord-gap
     grid               6          557.9250
     adaptive           6          415.1730
     dichotomic         6          202.2972  <- tightest

   STAGE 4: CRISIS REGIME STRESS TEST
     Crisis volatility ~22-30% above base at every frontier point.
   ```

   Crisis volatility sits ~22-30% above base at every frontier point and the gap peaks in the middle of the frontier, not at the concentrated end. That inversion is the payoff of the representative-only universe: at the concentrated end the optimizer picks the highest-Sharpe distinct bet per cluster, which sits in sectors with lower crisis correlations, including Energy and Consumer Staples.

   The final report lists the stock amounts and budget weights for the portfolio associated with the `FrontierPoint` marked as `is_knee` in each of the six scenarios. Treat these as candidate portfolios, not recommendations. To produce trades for an account, link a scenario to that account and compare the target amounts with its current holdings. The full stage-by-stage printout and a step-by-step walkthrough are in `runbook.md`.
