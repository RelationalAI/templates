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

## Quickstart

Before you start, install Python 3.10 or later and get access to a Snowflake
account with the RAI Native App. Graph, Predictive, and Prescriptive reasoning
are in Public Preview; ask your RelationalAI support representative to enable
Prescriptive reasoning. Preview features are for evaluation and testing, not
production applications. The local demo uses bundled CSVs and runs on CPU
without an external dataset or GPU. The template pins
`relationalai[gnn]==1.27.1` in `pyproject.toml`.

Ask an administrator to run this SQL before you start. It creates the writable
experiment schema used by `fraud_detection_local.py` and grants the RAI Native
App access:

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

   The run reports the classifier's ROC-AUC score, ranked alerts, and the audit
   schedule that fits the investigator budget. The bundled PaySim sample
   overrepresents fraud for CPU training, so its scores don't estimate
   real-world detection accuracy. The sample comes from Edgar Lopez-Rojas's
   PaySim synthetic mobile-money dataset under CC BY-SA 4.0. See
   `data/paysim_mini/LICENSE.txt` for attribution and citation details.
