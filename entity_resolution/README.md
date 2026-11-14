---
title: "Entity Resolution"
description: "Match policy records for the same person or household across insurance systems. Add up their coverage to spot totals above a risk limit, then choose which excess risk to transfer to another insurer within a budget."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - Entity Resolution
  - Record Linkage
  - Deduplication
  - Weakly Connected Components
  - Accumulation Control
  - Reinsurance Optimization
  - Insurance
---

**Full guide:** [Explore the Entity Resolution model, run the example, and follow the code](https://docs.relational.ai/build/templates/entity_resolution/).

## What this template is for

Insurers often store the same person or household as separate policyholder
records, hiding combined coverage and accumulation risk. This template scores
record matches, clusters high-confidence matches into resolved parties, and
holds uncertain pairs for review. It then totals coverage, flags parties above
a configurable limit, and selects reinsurance cessions within a premium
budget. Adapt the matching fields, thresholds, exposure rules, and decision
constraints for your workflow.

## Quickstart

Before you start, install Python 3.10 or later and get access to a Snowflake
account with the RAI Native App. An account administrator must first do the
one-time model deployment setup on that account: follow
[Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup)
through **Governed setup**, **PAT authentication**, and steps 1-2 of
**Additional setup for the prescriptive reasoner** (Quickstart step 4 below
covers this template's own schema). It gives you a model role, a programmatic
access token (PAT) stored as a secret, an external access integration, a PAT
user, and a warehouse; your Snowflake user must hold the model role. Graph and
Prescriptive reasoning are in Public Preview; ask your RelationalAI support representative to enable Prescriptive
reasoning. Preview features are for evaluation and testing, not production
applications. The template pins `relationalai==2.1.1` in `pyproject.toml` and
uses HiGHS without a separate solver license.

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/entity_resolution.zip), unzip it, and enter the template directory:

   ```bash
   unzip entity_resolution.zip
   cd entity_resolution
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

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection. Set the connection `role` to the model role, then add a `deployment` section. Give each template its own schema pair so two deployed templates never share one.

   ```yaml
   reasoners:
     prescriptive:
       name: entity_resolution_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.ENTITY_RESOLUTION               # published views and tables
     identity:
       internal_schema: <DB>.ENTITY_RESOLUTION_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

   Without the `deployment` section, `python entity_resolution.py` stops with an error naming the missing setting.

   Before the first run, create the internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

   ```sql
   -- as the model role
   CREATE SCHEMA IF NOT EXISTS <DB>.ENTITY_RESOLUTION_META;
   
   -- as an administrator
   GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER USAGE ON SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.ENTITY_RESOLUTION_META TO APPLICATION <RAI_APP_NAME>;
   ```

   The deploy creates the public schema `<DB>.ENTITY_RESOLUTION` if it doesn't exist.

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python entity_resolution.py
   ```

   The script deploys the model, waits for the first refresh, which runs the solve, and prints the report from the deployed model. Each refresh of the deployed model runs the solve again; `rai models deploy` deploys without printing the report. To remove the deployment, run `rai models teardown --force` from this directory; it keeps the two schemas.

   ```text
   Auto-resolved 51 records into 31 insured parties.
   Households over the limit after RESOLUTION:       4
     -> ceded $927,000 of excess exposure for $111,240 premium (of $120,000)
   ```

   No single policy breaches the $1M limit, but resolution surfaces four
   over-limit households and the optimizer cedes the most excess it can afford
   within budget. See `runbook.md` for the full workflow.
