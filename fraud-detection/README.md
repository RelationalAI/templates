---
title: "Fraud Detection"
description: "Find transfers that may be fraudulent by looking at payment details and the flow of money between accounts. Then prioritize cases for investigators by both the chance of fraud and the amount at stake."
featured: true
experience_level: advanced
industry: "Financial Services"
reasoning_types:
  - Graph
  - Rules-based
  - Predictive
  - Prescriptive
tags:
  - GNN
  - Fraud
  - Predict-then-Optimize
  - Classification
  - MILP
  - Multi-Reasoner
sidebar:
  order: 2
---

**Full guide:** [Explore the Fraud Detection model, run the example, and follow the code](https://docs.relational.ai/build/templates/fraud-detection/).

## What this template is for

Payments teams often receive more fraud alerts than investigators can review,
and transaction attributes alone can miss suspicious account-network behavior.
This template combines network signals with a fraud classifier, then selects
the investigations that maximize expected loss averted within a fixed
investigator-hours budget. Adapt its transaction data, fraud signals,
predictive model, and review constraints for your workflow.

## Prerequisites

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner**. It creates the model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

## Quickstart

Before you start, install Python 3.10 or later and complete the model
deployment setup listed under Prerequisites. Graph, Predictive, and
Prescriptive reasoning are in Public Preview; ask your RelationalAI support
representative to enable Prescriptive reasoning. Preview features are for
evaluation and testing, not production applications. The bundled example uses
local CSVs and runs on CPU without an external dataset or GPU. The template
pins `relationalai[gnn]==2.1.1` in `pyproject.toml`.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The classifier keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.FRAUD_DETECTION;
CREATE SCHEMA IF NOT EXISTS <DB>.FRAUD_DETECTION_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.FRAUD_DETECTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.FRAUD_DETECTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.FRAUD_DETECTION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.FRAUD_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model, train the classifier, and print the audit queue:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/fraud-detection.zip), unzip it, and enter the template directory:

   ```bash
   unzip fraud-detection.zip
   cd fraud-detection
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

   Set the connection `role` to the model role, then add the predictive and prescriptive reasoners, the registered version the classifier predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: fraud_gnn                  # created on first use if it doesn't exist
       gnns:
         fraud_classifier:              # the GNN's name in model/reasoning.py
           registry: <DB>.FRAUD_DETECTION
           model: FRAUD_CLASSIFIER
           version: V1                  # train.py registers this version
     prescriptive:
       name: fraud_audit_solver         # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.FRAUD_DETECTION          # published views and tables
     identity:
       internal_schema: <DB>.FRAUD_DETECTION_META # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>           # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the reasoners and the public schema named in `raiconfig.yaml` if they don't exist and waits for the model's first refresh, which loads the sample data, ranks the accounts, and counts their activity. No version of the classifier is registered yet, so this refresh scores no transfers and selects no audits.

6. **Train the classifier**

   Train the classifier over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it scores the test transfers with this version and solves the audit selection over those scores: `CALL DB.FRAUD_DETECTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `DB`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the alert queue and the audit schedule from the deployed model:

   ```bash
   python -m queries.fraud_report
   ```

   ```text
   === Fraud class balance (train split) ===
     n=11498  fraud=4339  fraud_rate=37.7%
     Baseline ROC_AUC = 0.5
   === Top-20 alert-scored transactions ===
    transaction_id trans_type      amount    receiver  alert_score
        6205440   TRANSFER   353874.22 C1770418982     0.998784
        6266414   TRANSFER  2542664.27  C661958277     0.998668
        6351226   TRANSFER  3171085.59 C1308068787     0.998606
   ...
   ============================================================
   Stage 5: Prescriptive -- investigator-budget allocation
   ============================================================
   MILP Status: OPTIMAL
   Captured expected loss (optimal within budget): $111,827,688
     MILP (cost-aware + per-receiver cap) -> $111,827,688 captured across the audit queue
     Naive top-by-alert-score (budget only, same hours) -> $72,288,588 captured across 17 audits
     MILP uplift over naive sort: $+39,539,099
   === Selected audit queue ===
     16 audits scheduled; 80.0/80 investigator hours used
    transaction_id trans_type     amount    receiver  alert_score  audit_cost
        6205437   CASH_OUT 10000000.0  C427067936     0.698927         5.0
        6281460   CASH_OUT 10000000.0 C1823815645     0.698923         5.0
        6362508   CASH_OUT 10000000.0  C635621973     0.698923         5.0
   ...
   ============================================================
   Report complete
   ============================================================
   ```

   The report prints the class balance, the top-20 alert queue, the audit solve against a naive sort-by-score queue, and the selected audits; the lines above are trimmed. The classifier is stochastic, so the scores, the naive baseline, and the selected audits shift from one training run to the next; the structural outcome reproduces: status OPTIMAL, all 80 investigator hours used, and a captured loss well above the naive queue. The full printout and a step-by-step walkthrough are in `runbook.md`. The bundled PaySim sample
   overrepresents fraud for CPU training, so its scores don't estimate
   real-world detection accuracy. The sample comes from Edgar Lopez-Rojas's
   PaySim synthetic mobile-money dataset under CC BY-SA 4.0. See
   `data/paysim_mini/LICENSE.txt` for attribution and citation details.

   To score and select again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.FRAUD_DETECTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

8. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas, with the classifier's experiments and registered versions in the public schema.

To run the same pipeline over your own Snowflake tables, call `load_snowflake_data()` in `model/__init__.py` in place of `load_local_data()`. It reads `ACCOUNTS`, `TRANSACTIONS`, `TRAIN`, `VAL`, and `TEST` from the database and schema you pass, which need change tracking and a derived `audit_cost` column on the transactions table. Size the predictive reasoner for your data with `reasoners.predictive.size` in `raiconfig.yaml`, and raise `AUDIT_BUDGET_HOURS` and the training settings in `model/reasoning.py` to match its scale.
