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

## Prerequisites

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports).

## Quickstart

Before you start, install Python 3.10 or later and complete the model deployment setup listed under Prerequisites. Graph and Prescriptive reasoning are in Public Preview; ask your RelationalAI support representative to enable Prescriptive reasoning. Preview features are for evaluation and testing, not production applications. The template pins `relationalai==2.3.0` in `pyproject.toml` and uses HiGHS without a separate solver license.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.PORTFOLIO_BALANCING_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.PORTFOLIO_BALANCING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

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

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: portfolio_balancing_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.PORTFOLIO_BALANCING               # published views and tables
     identity:
       internal_schema: <DB>.PORTFOLIO_BALANCING_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which flags the holdings, groups the stocks, and runs the 15 solves of the frontier: the anchors first, then the return targets that depend on earlier results. The solves run one after another, so the first deploy takes tens of minutes. Each refresh of the deployed model runs them again.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.portfolio_report
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

   The lines above are excerpts of the full report. It flags four holdings and two sectors, groups eight stocks into five correlation clusters, and selects `p3` as the candidate frontier point in each of six budget-and-market scenarios. Estimated crisis volatility is 22% to 30% above the base regime. The deployed model publishes the return, risk, shadow price, and allocations of each solve that reached an accepted status as `FrontierPoint`s; the report labels the points, checks that return and risk rise along each frontier, and derives the knees and the base-versus-crisis volatilities.

   These candidates are starting points for review, not recommendations or trades for a specific account. See `runbook.md` for the full workflow and result interpretation.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.PORTFOLIO_BALANCING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.
