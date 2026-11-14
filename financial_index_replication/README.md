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

## Prerequisites

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above. Prescriptive reasoning is in Public Preview; ask your RelationalAI support representative to enable it. Preview features are for evaluation and testing, not production applications. The template pins `relationalai==2.1.1` in `pyproject.toml`.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.FINANCIAL_INDEX_REPLICATION_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.FINANCIAL_INDEX_REPLICATION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

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

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: financial_index_replication_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.FINANCIAL_INDEX_REPLICATION               # published views and tables
     identity:
       internal_schema: <DB>.FINANCIAL_INDEX_REPLICATION_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys it.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.replication_report
   ```

   ```text
   Selected names: exactly 20
   Status: TIME_LIMIT
   Wrote benchmark-vs-replica returns to: data/replica_returns.csv
   ```

   The solve selects exactly 20 names, though a selected stock may have zero weight. The solve ends as `OPTIMAL` or at its 240 second time limit (`TIME_LIMIT`) with the best basket found so far. The report accepts both, stops on any other termination status, and writes `data/replica_returns.csv` for plotting. See `runbook.md` for the basket, sector exposures, tracking quality, and baseline comparison.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.FINANCIAL_INDEX_REPLICATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

