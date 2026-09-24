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

Explore the [model](https://docs.relational.ai/build/templates/fraud-detection/#explore-the-model) and [guided walkthrough](https://docs.relational.ai/build/templates/fraud-detection/#see-how-it-works) in the documentation.

## What this template is for

Payments teams often receive more potentially fraudulent transactions than
investigators can review. Ranking transfers by transaction attributes alone can
miss suspicious behavior that appears only in the account network, while
reviewing every alert is not operationally feasible.

This template combines account-network signals with a fraud classifier, then
selects the transactions that maximize expected loss averted within a fixed
investigator-hours budget. Use it as a starting point for adapting your
transaction data, fraud signals, predictive model, and review constraints.

## Quickstart

Before you start, install Python 3.10 or later. You need a Snowflake account
with the RAI Native App and user access to it. Graph, Predictive, and
Prescriptive reasoning are in Public Preview. Ask your RelationalAI support
representative to enable Prescriptive reasoning before you run the full
pipeline. Preview features are for evaluation and testing, not production
applications. The local demo uses bundled CSVs and runs on CPU, without an
external dataset or GPU. The template installs the SDK version pinned in
`pyproject.toml`: `relationalai[gnn]==1.27.1`.

Before running the demo, ask an administrator with permission to run this SQL to create a writable experiment schema and grant the RAI Native App access. The runner uses `FRAUD_DETECTION.EXPERIMENTS` unless you change `exp_database` and `exp_schema` in `fraud_detection_local.py`:

```sql
CREATE DATABASE IF NOT EXISTS FRAUD_DETECTION;
CREATE SCHEMA IF NOT EXISTS FRAUD_DETECTION.EXPERIMENTS;

GRANT USAGE ON DATABASE FRAUD_DETECTION TO APPLICATION RELATIONALAI;
GRANT USAGE ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

Use this sequence to run the bundled example:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/fraud-detection.zip). Unzip it and enter the template directory:

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

   Install the template and its dependencies in the active environment:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Start building with PyRel](https://docs.relational.ai/get-started/start-building-with-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory. Follow that guide to save the file and verify your connection.

   Add this setting to `raiconfig.yaml` before running the template:

   ```yaml
   data:
       ensure_change_tracking: true
   ```

5. **Run the template**

   Run the bundled script from the template directory:

   ```bash
   python fraud_detection_local.py
   ```

   The run reports the classifier's ROC-AUC score, the top alerts, and the
   audit schedule that fits the investigator budget. The bundled PaySim sample
   overrepresents fraud for CPU training, so its scores don't estimate
   real-world detection accuracy. It comes from Edgar Lopez-Rojas's PaySim
   synthetic mobile-money dataset under CC BY-SA 4.0. See
   `data/paysim_mini/LICENSE.txt` for the full attribution, source, and citation.
