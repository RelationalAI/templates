---
title: "Fraud Detection"
description: "Transaction-fraud pipeline where account PageRank and account-activity signals feed a graph neural network (GNN) binary classifier whose per-transaction scores drive a knapsack investigator-budget mixed-integer linear program (MILP)."
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

## What this template is for

A payments company receives more potentially fraudulent transactions than its
investigators can review. Ranking transfers by transaction attributes alone can
miss suspicious account-network behavior, while investigating every alert
exceeds the team's capacity.

This template combines account graph features with a transaction classifier,
then chooses which high-risk transactions to investigate within a fixed hours
budget. Use it as a starting point for your own transaction data, fraud signals,
predictive model, and operational constraints.

## Who this is for

- Data scientists building end-to-end ML-to-optimization pipelines on transaction graphs
- Fraud analysts combining heuristic flags with learned signals to prioritize audits
- ML engineers exploring GNN-based prediction on relational/graph data
- Operations researchers interested in predict-then-optimize patterns

Assumes familiarity with Python, basic ML concepts (binary classification, ROC AUC), and mixed-integer programming.

## What you'll build

You'll chain RelationalAI's Graph Reasoning, Rules-Based Reasoning, Predictive
Reasoning, and Prescriptive Reasoning into one predict-then-optimize pipeline.
Account PageRank and activity signals feed a graph neural network (GNN)
classifier; its probabilities combine with a heuristic flag in a
per-transaction alert score; and that score drives a mixed-integer linear
programming (MILP) audit allocation.

- **Graph**: PageRank on an Account-Account funds-flow graph, exposing account centrality as a GNN feature
- **Rules**: derived `activity_count` property per account, fed to the GNN as an integer feature alongside the raw transaction fields
- **Predictive**: a GNN binary classifier on the Account-Transaction graph, predicting `isFraud` per transaction
- **Bridge**: a layer combining GNN probabilities with a rule-based heuristic flag into a per-transaction `alert_score`
- **Prescriptive**: a knapsack-style investigator-budget MILP that maximizes expected loss averted (`alert_score × transaction_amount`) subject to a fixed-hours audit budget (audit cost scales with transaction size) plus a per-receiver cap
- The same five-stage pipeline running against either a bundled CSV subset (local demo) or a full Snowflake dataset (reference path)

## What's included

- **Runners**:
  - `fraud_detection_local.py` -- **primary runnable path.** Runs all five stages (Graph / Rules / Predictive / Bridge / Prescriptive) end-to-end on the bundled demo CSVs.
  - `fraud_detection.py` -- **reference pattern** for adapting the pipeline to your own Snowflake data. Same five stages, GPU-trained.
  - `fraud_detection_rules.ipynb` -- original rule-based identity-graph notebook, kept as a complementary intro.
- **Shared model**:
  - `model/schema.py` -- stable `Account` and `Transaction` concepts, sender and receiver relationships, and train/validation/test task surfaces.
  - `model/source.py` -- explicit `load_local_data()` and `load_snowflake_data()` functions that map either source into the shared schema.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Model**: `Account`, `Transaction`, plus two graphs (Account-Account for PageRank; Transaction-to-Account for the GNN), derived account properties, and the alert-score bridge
- **Sample data**: a small class-balanced transactions subset sampled from a public mobile-money dataset (CC BY-SA 4.0) -- see [Sample data](#sample-data) below for details and attribution
- **Outputs**: class-balance profile, GNN ROC-AUC, top-K alert queue, optimal audit schedule, MILP-vs-naive uplift

## Prerequisites

### Access

**To run the local demo (`fraud_detection_local.py`)** you need any Snowflake
account with the RAI Native App. No external data, no GPU. The bundled CSVs
under `data/paysim_mini/` ship with the template; the GNN trains on CPU in a
few minutes.

Graph reasoning and Predictive reasoning are in Public Preview. Prescriptive
reasoning is in Public Preview and available by request. Contact your
RelationalAI support representative to enable Prescriptive reasoning before
running the full pipeline. Preview features are intended for evaluation and
testing, not production applications.

The predictive reasoner needs a writable Snowflake schema where it can create experiments and models. The script defaults to `FRAUD_DETECTION.EXPERIMENTS` (configurable via `exp_database` / `exp_schema` in the script). One-time setup, run as `ACCOUNTADMIN` or any role with privileges to run the commands below:

```sql
-- Use a database you own (FRAUD_DETECTION shown; pick anything writable)
CREATE DATABASE IF NOT EXISTS FRAUD_DETECTION;
CREATE SCHEMA IF NOT EXISTS FRAUD_DETECTION.EXPERIMENTS;

GRANT USAGE ON DATABASE FRAUD_DETECTION TO APPLICATION RELATIONALAI;
GRANT USAGE ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL ON SCHEMA FRAUD_DETECTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

**To adapt to your own Snowflake pipeline (`fraud_detection.py` as reference)**
you'll additionally need:

- A dataset in Snowflake with an accounts table plus a transactions table
  that references accounts as sender and receiver, and pre-built train / val
  / test split tables. The as-shipped `fraud_detection.py` targets a full
  PaySim mobile-money dataset loaded at
  `FRAUD_DB.PAYSIM.{ACCOUNTS, TRANSACTIONS, TRAIN, VAL, TEST}` as a worked
  example; see [Sample data](#sample-data) for the source.
- A GPU-enabled RAI engine for GNN training at dataset scale (PaySim is ~6M rows).

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai[gnn] == 1.27.1`)
- For the rule-based notebook only: `jupyter`

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/fraud-detection.zip
   unzip fraud-detection.zip
   cd fraud-detection
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

   After `rai init` generates the config file, add the following to your `raiconfig.yaml`:

   ```yaml
   data:
       ensure_change_tracking: true
   ```

5. Run the local demo on the bundled subset (CPU, a few minutes):
   ```bash
   python fraud_detection_local.py
   ```

### Adapting to your own Snowflake data

`fraud_detection.py` is the reference for wiring this pattern against a real
Snowflake dataset (accounts + transactions + train/val/test task tables):

1. Point the Snowflake loader at your data:
   ```python
   DATABASE = "YOUR_DB"
   SCHEMA = "YOUR_SCHEMA"   # schema with ACCOUNTS, TRANSACTIONS, TRAIN, VAL, TEST
   ```
   `fraud_detection.py` passes these values to
   `load_snowflake_data(DATABASE, SCHEMA)` in `model/source.py`.
2. Adjust the `PropertyTransformer` in `fraud_detection.py` to match your columns -- drop your PKs/FKs
   explicitly, annotate categoricals and continuous fields, and set `time_col`
   on your timestamp column.
3. If your task tables use different column names, update their mappings in
   `load_snowflake_data()` and any `TrainTable.<column>` accesses in the
   runner.
4. Run against a GPU-enabled RAI engine:
   ```bash
   python fraud_detection.py
   ```

Your TRANSACTIONS table must carry an `audit_cost` column (hours per audit) --
the MILP knapsack constraint reads it directly. Materialize it via a SQL
`CASE` expression so the cost model lives in Snowflake, not Python:

```sql
CREATE OR REPLACE TABLE FRAUD_DB.PAYSIM.TRANSACTIONS AS
  SELECT *, CASE WHEN amount > 1000000 THEN 5.0 ELSE 1.0 END AS audit_cost
  FROM FRAUD_DB.PAYSIM.RAW_TRANSACTIONS;
```

Build the train/val/test tables from the main transaction table by `step`
cutoff:

```sql
CREATE OR REPLACE TABLE FRAUD_DB.PAYSIM.TRAIN AS
  SELECT transaction_id, step_ts, is_fraud FROM FRAUD_DB.PAYSIM.TRANSACTIONS
  WHERE step <= 520;
CREATE OR REPLACE TABLE FRAUD_DB.PAYSIM.VAL AS
  SELECT transaction_id, step_ts, is_fraud FROM FRAUD_DB.PAYSIM.TRANSACTIONS
  WHERE step BETWEEN 521 AND 631;
CREATE OR REPLACE TABLE FRAUD_DB.PAYSIM.TEST AS
  SELECT transaction_id, step_ts FROM FRAUD_DB.PAYSIM.TRANSACTIONS
  WHERE step > 631;
```

### Expected output (local run, abbreviated)

Real numbers from a verified end-to-end run on the bundled subset (CPU, no
external data, no GPU). Exact scores shift a little with numerical noise
between CPU and GPU runs, but the structure and magnitude are consistent.

```text
Stage 5: Prescriptive -- investigator-budget allocation
  MILP Status: OPTIMAL
  MILP (cost-aware + per-receiver cap) -> $111,854,667 captured
  Naive top-by-alert-score (same 80 hours)  -> $67,947,657 captured
  MILP uplift over naive sort: $+43,907,010
```

The MILP captures materially more expected loss than a naive sort-by-alert-score
under the same 80-hour budget, because it trades off per-audit cost (audit
hours scale with transaction size) against catch value and respects the
per-receiver cap. GNN training on GPU is not bit-for-bit reproducible even with
a fixed seed, so the exact captured and uplift dollars shift from run to run
(a separate run gave $117.3M captured against a $60.2M naive baseline); the
large MILP-over-naive uplift is the stable result. The `runbook.md` walkthrough
covers `fraud_detection.py`, the same chain run against the full PaySim schema
on Snowflake at a much larger scale.

**Start here**: run `python fraud_detection_local.py` for the full five-stage
pipeline end to end (CPU, no external dataset or GPU), or follow `runbook.md`
to reproduce it step by step with the RAI skills. Use `fraud_detection.py`
(requires GPU) as the adaptation reference when you wire this pattern into
your own Snowflake data, and explore `fraud_detection_rules.ipynb` for a
rule-based-only take on identity graphs.

## Sample data

The bundled mini dataset is sampled from the [PaySim synthetic mobile-money
transactions dataset](https://www.kaggle.com/datasets/ealaxi/paysim1) by
Edgar Lopez-Rojas, released under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The local runner reads these sources through `load_local_data()` in
`model/source.py`. The following rows are representative; the complete files
remain under `data/paysim_mini/`.

| Account ID | Type |
| --- | --- |
| `C658247527` | Customer (`C`) |
| `C1812418129` | Customer (`C`) |
| `C1544350298` | Customer (`C`) |

| Transaction ID | Type | Amount | Sender | Receiver | Flagged |
| --- | --- | ---: | --- | --- | ---: |
| `5682295` | `CASH_IN` | 76,550.74 | `C658247527` | `C492670573` | 0 |
| `3256549` | `PAYMENT` | 12,617.11 | `C1812418129` | `M1924423059` | 0 |
| `1059490` | `CASH_OUT` | 8,055.06 | `C1544350298` | `C912405348` | 0 |

- **16K transactions** are sampled with class balance inflated from PaySim's native
  0.13% fraud up to 50% so the GNN has enough positive signal to learn from on
  CPU. Real-world fraud-detection runs should preserve native imbalance and
  use class weighting.
- **Fraud is confined to `CASH_OUT` and `TRANSFER` transaction types** -- this
  is a documented PaySim quirk. The GNN's job is to distinguish *fraudulent*
  CASH_OUT/TRANSFER from *normal* CASH_OUT/TRANSFER via graph context, not to
  rediscover the type filter.
- See `data/paysim_mini/LICENSE.txt` for full attribution and citation.

## Model overview

Two concepts carry the pipeline: `Account` and `Transaction`. Each stage enriches them with new properties the next stage reads, so the model grows accretively across the run.

- **Key entities**: `Account` (a participant in the transaction network) and `Transaction` (one transfer between two accounts).
- **Primary identifiers**: `Account.account_id` (string, e.g. customer prefix `C` or merchant prefix `M`); `Transaction.transaction_id` (integer).
- **Important invariants**: `is_flagged_fraud` and the GNN's `is_fraud` label are 0/1; `alert_score` is a `[0, 1]` blend of the flag and the GNN probability; audit-cost hours and transaction amounts are non-negative; the MILP's audit decision is binary.

The stable concept and relationship declarations live in `model/schema.py`.
`model/source.py` maps the local CSVs or Snowflake tables into that schema
without selecting a source during import. The runners retain the graph,
rules-based, predictive, and prescriptive reasoning stages.

## How it works

The five stages thread through the shared ontology, each stage's output becoming a property the next stage reads.

```text
Accounts + Transactions (Snowflake tables or bundled CSVs)
  → Stage 1 -- Graph:       PageRank on Account-Account funds-flow graph
  → Stage 2 -- Rules:       Account.activity_count (per-sender derivation)
  → Stage 3 -- Predictive:  GNN binary classification (Transaction.predictions.probs)
  → Stage 4 -- Bridge:      alert_score blends GNN prob with is_flagged_fraud
  → Stage 5 -- Prescriptive: knapsack MILP (hours budget + per-receiver cap)
```

**Load one source and build the graphs.** The local runner calls
`load_local_data()`; the Snowflake runner calls `load_snowflake_data()`.
Both loaders populate the same `Account` and `Transaction` concepts and their
sender and receiver relationships. The runner then constructs a directed
Transaction-to-Account bipartite graph for the GNN and a directed
Account-to-Account funds-flow graph for PageRank.

**Stage 1 -- Graph reasoner: account PageRank.** PageRank runs on the funds-flow graph, and each account's score is bound to an explicit `Account.pagerank` property so it surfaces as a GNN feature column.

**Stage 2 -- Rules reasoner: account activity.** A derived property aggregates each sending account's transaction count into `Account.activity_count`. Both `pagerank` (continuous) and `activity_count` (integer) go into the `PropertyTransformer` so the GNN sees them as features alongside the raw transaction fields.

**Stage 3 -- Predictive: GNN binary classifier.** Task relationships encode the `is_fraud` label on the train/validation splits and omit it on test. The GNN trains on the Transaction-to-Account graph with the enriched features and emits a per-transaction fraud probability. Both scripts use temporal task relationships keyed on the transaction timestamp.

**Stage 4 -- Bridge: blend GNN probability with heuristic flag.** The dataset carries an `is_flagged_fraud` heuristic. A convex mix (weighted by `ALPHA_FLAG`) combines it with the GNN probability into a per-transaction `alert_score` in `[0, 1]`.

**Stage 5 -- Prescriptive: knapsack MILP investigator-budget allocation.** An auditor's time is the scarce resource: the total investigation budget is fixed in hours, and the time to audit a transaction grows with its size. The MILP maximizes expected loss averted (`alert_score × amount`) subject to that budget, plus a per-receiver cap to prevent flooding one account. Because cost and value both scale with transaction size, ranking by `alert_score` alone is provably suboptimal -- a high-score $5M transfer consumes 5 hours but may yield less value per hour than three medium-score $500K transfers at 1 hour each. The MILP trades them off correctly; the output prints both the MILP objective and a naive sort-and-take baseline so the tradeoff is visible.

See `fraud_detection_local.py` (and `fraud_detection.py` for the Snowflake path) for the implementation, and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Adapt `load_local_data()` or `load_snowflake_data()` in `model/source.py` to
  map your own account, transaction, and task data. Keep `customer_id`-style
  string primary keys and a stable transaction primary key.
- The `PropertyTransformer` is the main place to localize: drop your primary
  and foreign keys, and list your categorical versus continuous fields.

### Tune parameters

- `ALPHA_FLAG` (0..1) -- weight on the rule-based flag versus the GNN
  probability.
- `AUDIT_BUDGET_HOURS` / `PER_ACCOUNT_CAP` -- investigator budget knobs.
  Raise the budget to audit more transactions; tighten the cap to spread
  audits across more receivers.
- `LARGE_AMOUNT_THRESHOLD` / `SMALL_AUDIT_COST_HOURS` / `LARGE_AUDIT_COST_HOURS`
  -- the audit-cost curve. Make the jump steeper to reward the MILP's
  knapsack-style tradeoffs more aggressively.
- GNN hyperparameters (`n_epochs`, `lr`, `train_batch_size`, ...) -- see the
  `rai-predictive-training` skill for tuning guidance.

### Extend the model

- Swap PageRank for other centrality measures (betweenness, eigenvector) or
  add community labels (Louvain / Infomap) as a categorical GNN feature.
- Author additional rules (e.g. balance-change anomalies, velocity spikes)
  and feed them into both the GNN features and the `alert_score` blend.
- Fold a rule-based flag directly into the MILP as a hard constraint (e.g.
  never skip an already-`is_flagged_fraud=True` transaction) rather than as
  an alert-score contributor.

### Scale up for evaluation

- Use `fraud_detection.py` as the reference for running against a full
  Snowflake dataset on a GPU-enabled RAI engine (see *Adapting to your own
  Snowflake data* under Quickstart).
- Keep `relationalai` pinned in `pyproject.toml` and set a fixed GNN `seed` to
  reduce run-to-run variation while evaluating the pipeline.

## Troubleshooting

<details>
<summary>GNN training fails or is very slow</summary>

- For the full-scale `fraud_detection.py` path, a GPU-enabled engine is required -- PaySim's 6M rows are too large for CPU.
- For the local path, the bundled 16K-row subset fits comfortably on CPU (~2-5 min).
- Check that the task-table columns in your Relationship templates actually exist on the CSVs (`transaction_id`, `step_ts`, `is_fraud`).
</details>

<details>
<summary>Predictions are all near 0 or all near 1</summary>

- Re-check class balance on the train split (printed before training). If it's extremely imbalanced, either raise the positive sample rate or add class weighting.
- Inspect the PropertyTransformer with `VERBOSE_DATASET = True` -- misconfigured feature types dilute signal.
- Try more epochs; classification may need 10-20 epochs even on balanced data.
</details>

<details>
<summary>MILP infeasible or degenerate</summary>

- Infeasible: `AUDIT_BUDGET_HOURS` is tighter than the cheapest feasible audit, or the per-receiver cap is already saturated. Widen the budget or the per-receiver cap.
- Degenerate (selects 0 transactions): no transactions have an alert_score. Confirm `Transaction.predictions` was populated (test split present + GNN fit succeeded).
</details>

<details>
<summary>Spinner floods the log when running in CI / non-TTY</summary>

Set `STREAM_LOGS = False` at the top of the script (the default). The GNN continues training server-side; only the client-side log stream is suppressed.
</details>

## Learn more

- [Declare concepts](https://docs.relational.ai/build/guides/modeling/declare-concepts/) and [declare relationships and properties](https://docs.relational.ai/build/guides/modeling/declare-relationships-and-properties/) for the shared schema.
- [Run a graph algorithm](https://docs.relational.ai/build/guides/reasoning/graph/run-an-algorithm/) and [derive facts with rules](https://docs.relational.ai/build/guides/reasoning/rules-based/) for account features.
- [Solve a classification problem](https://docs.relational.ai/build/guides/reasoning/predictive/solve-a-classification-problem/) for GNN training and predictions.
- [Add constraints](https://docs.relational.ai/build/guides/reasoning/prescriptive/decision-problems/constraints/) and [work with solutions](https://docs.relational.ai/build/guides/reasoning/prescriptive/decision-problems/solutions/) for the investigator-budget problem.

## Support

- File issues at the RelationalAI templates repository.
