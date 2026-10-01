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

**Full guide:** [Explore the Portfolio Re-balancing model, run the example, and follow the code](https://docs.relational.ai/build/templates/portfolio_balancing/).

## What this template is for

Investment managers need to keep portfolios within concentration and
compliance limits while weighing expected return against risk. This template
flags concentration problems, groups correlated stocks, calculates constrained
allocations, and compares them under normal and stressed markets. Adapt the
investment universe, limits, objectives, and stress assumptions for your
workflow.

## Quickstart

Before you start, install Python 3.10 or later and get access to a Snowflake
account with the RAI Native App. Graph and Prescriptive reasoning are in Public
Preview; ask your RelationalAI support representative to enable Prescriptive
reasoning. Preview features are for evaluation and testing, not production
applications. The template pins `relationalai==1.9.0` in `pyproject.toml`.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/portfolio_balancing.zip), unzip it, and enter the template directory:

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

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python portfolio_balancing.py
   ```

   ```text
   STAGE 1: COMPLIANCE ANALYSIS (rules)
   STAGE 2: GRAPH -- Covariance Clustering (Louvain)
     Louvain communities: 5 cluster(s)
   STAGE 3: BI-OBJECTIVE OPTIMIZATION
   Status: OPTIMAL
   SENSITIVITY-GUIDED FRONTIER  (reference 'base_1000', 6-solve budget per method)
     dichotomic         6          202.2972  <- tightest
   STAGE 4: CRISIS REGIME STRESS TEST
   KNEE PORTFOLIO ALLOCATIONS BY SCENARIO
     base_1000 (budget=1000, regime=base, point=p3)
     expected return=80.46, volatility=83.33
     Each knee is a candidate portfolio, not a recommendation. The amounts apply to
     the sample scenario, not to a specific account.
   ```

   The run flags four holdings and two sectors, groups eight stocks into five
   correlation clusters, and selects `p3` as the candidate frontier point in
   each of six budget-and-market scenarios. Estimated crisis volatility is
   22% to 30% above the base regime.

   These candidates are starting points for review, not recommendations or
   trades for a specific account. See `runbook.md` for the full workflow and
   result interpretation.
