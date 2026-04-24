---
title: "Fraud Detection"
description: "Rule-based identity-graph discovery plus a GNN predict-then-optimize pipeline: train a binary classifier on a bundled PaySim subset, blend its score with rule flags, then allocate a finite investigator-audit budget via MILP."
featured: true
experience_level: advanced
industry: "Financial Services"
reasoning_types:
  - Graph
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

Fraud and risk teams face three interconnected problems: discovering suspicious identity patterns in the first place, scoring transactions as they come in, and deciding which alerts to actually investigate given finite human capacity. Traditionally these live in separate tools. This template shows all three working together on one semantic model in RelationalAI.

**Start with `fraud_detection_local.py`** -- it trains a real GNN binary classifier on a bundled PaySim subset (CPU, no external data), blends its probability with PaySim's built-in heuristic flag, and runs a small investigator-budget MILP. A few minutes end-to-end. It's the quickest way to see the full predict-then-optimize loop.

**Then adapt the pattern to your own Snowflake data** using `fraud_detection.py` as a reference. It trains the same GNN against the full PaySim dataset (or your own customer/transaction data) in Snowflake and allocates a larger investigator budget.

**For the original rule-based identity-graph approach** (no ML), see `fraud_detection_rules.ipynb` -- a standalone Jupyter notebook that uses Weakly Connected Components on shared-identifier edges to flag suspicious users. It's a useful intro to graph-based fraud signals without any predictive modeling.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** used in this template is in
> early access. The API surface (`GNN`, `PropertyTransformer`, task
> relationships) may still change between releases; check the
> `rai-predictive-modeling` and `rai-predictive-training` skills for the
> current guidance before adapting to production data.

## Who this is for

- Data scientists building end-to-end ML-to-optimization pipelines on transaction graphs
- Fraud analysts combining heuristic flags with learned signals to prioritize audits
- ML engineers exploring GNN-based prediction on relational/graph data
- Operations researchers interested in predict-then-optimize patterns

Assumes familiarity with Python, basic ML concepts (binary classification, ROC AUC), and mixed-integer programming.

## What you'll build

- A GNN binary classifier on the Account-Transaction graph, predicting `isFraud` per transaction
- A bridge layer combining GNN probabilities with a rule-based flag into a per-transaction alert score
- A knapsack-style investigator-budget MILP that maximizes expected loss averted (`alert_score × transaction_amount`) subject to a fixed-hours audit budget (audit cost scales with transaction size) plus a per-receiver cap
- The same pipeline running against either a bundled CSV subset (local demo) or a full Snowflake dataset (reference path)

## What's included

- **Runners**:
  - `fraud_detection_local.py` -- **primary, runnable out of the box.** Trains a real GNN on bundled PaySim CSVs and solves the investigator MILP.
  - `fraud_detection.py` -- **reference pattern** for adapting the pipeline to your own Snowflake data. Same structure, GPU-trained.
  - `fraud_detection_rules.ipynb` -- original rule-based identity-graph notebook, kept as a complementary intro.
- **Model**: `Account`, `Transaction`, `Edge` (Transaction-to-Account in both sender and receiver roles), plus rule and alert-score derived properties
- **Sample data**:
  - `data/paysim_mini/` -- ~16K transactions from PaySim (class-balanced ~50% fraud for CPU training), plus train/val/test splits. Redistributed under CC BY-SA 4.0 (see `LICENSE.txt` in that directory).
- **Outputs**: class-balance profile, GNN ROC-AUC, top-K alert queue, optimal audit schedule

## Prerequisites

### Access

**To run the local demo (`fraud_detection_local.py`)** you need any Snowflake
account with the RAI Native App. No PaySim Snowflake data, no GPU. The bundled
`data/paysim_mini/` CSVs ship with the template; the GNN trains on CPU in a
few minutes.

**To adapt to your own Snowflake pipeline (`fraud_detection.py` as reference)**
you'll additionally need:

- A dataset in Snowflake with a schema analogous to PaySim -- an accounts
  table plus a transactions table that references accounts as sender and
  receiver, and pre-built train/val/test split tables. The as-shipped
  `fraud_detection.py` targets PaySim loaded at
  `FRAUD_DB.PAYSIM.{ACCOUNTS, TRANSACTIONS, TRAIN, VAL, TEST}`; the full
  dataset is available at [Kaggle: ealaxi/paysim1](https://www.kaggle.com/datasets/ealaxi/paysim1).
- A GPU-enabled RAI engine for GNN training at scale (~6M row full PaySim).

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14
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

5. Run the local demo on the bundled PaySim subset (CPU, a few minutes):
   ```bash
   python fraud_detection_local.py
   ```

### Adapting to your own Snowflake data

`fraud_detection.py` is the reference for wiring this pattern against a real
Snowflake dataset (accounts + transactions + train/val/test task tables):

1. Point the table references at your data:
   ```python
   DATABASE = "YOUR_DB"
   SCHEMA = "YOUR_SCHEMA"   # schema with ACCOUNTS, TRANSACTIONS, TRAIN, VAL, TEST
   ```
2. Adjust the `PropertyTransformer` to match your columns -- drop your PKs/FKs
   explicitly, annotate categoricals and continuous fields, set `time_col` on
   your timestamp column.
3. If your task tables use different column names, update the `Relationship`
   templates (and any `TrainTable.<column>` accesses) to match.
4. Run against a GPU-enabled RAI engine:
   ```bash
   python fraud_detection.py
   ```

If you're using PaySim as-is, build the train/val/test tables from the main
transaction table by `step` cutoff:

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
=== Fraud class balance (train split) ===
  n=11498  fraud=4339  fraud_rate=37.7%
  Baseline ROC_AUC = 0.5

============================================================
PREDICTIVE: Fraud binary-classification GNN (CPU, PaySim mini)
============================================================
=== Start GNN Training ===
  ✓ Step 1 completed (~30s)   # prepare dataset + GNN tables
  ✓ Step 2 completed (~2s)    # trainer config
  ✓ Step 3 completed (~5s)    # submit training job
=== Start GNN Prediction ===
  ✓ GNN Prediction Complete (~110s)

=== Top-20 alert-scored transactions ===
  transaction_id  trans_type     amount    receiver     alert_score
  6205440         TRANSFER       353874    C1770418982  0.999406
  6266414         TRANSFER       2542664   C661958277   0.999319
  ...

MILP Status: OPTIMAL
Captured expected loss (optimal within budget): $111,901,446
  MILP (cost-aware + per-receiver cap) -> $111,901,446 captured across the audit queue
  Naive top-by-alert-score (budget only, same hours) -> $40,682,083 captured across 17 audits
  MILP uplift over naive sort: $+71,219,363

=== Selected audit queue ===
  16 audits scheduled; 80.0/80 investigator hours used
  By trans_type:
    CASH_OUT    12
    TRANSFER     4
```

The MILP picks 16 large ($10M) transactions at 0.699 alert over the 0.999-alert
smaller transfers because expected loss per audit-hour is higher. Natural
diversity falls out without any per-type cap: 12 CASH_OUT + 4 TRANSFER. A
naive sort by alert-score alone would spend the same 80 hours for only 40% of
the captured value.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── fraud_detection_local.py        # primary: real GNN on bundled PaySim CSVs + MILP
├── fraud_detection.py              # reference pattern: same pipeline in Snowflake (GPU)
├── fraud_detection_rules.ipynb     # rule-based identity-graph intro (no ML)
└── data/
    └── paysim_mini/
        ├── transactions.csv        # ~16K sampled transactions (class-balanced)
        ├── accounts.csv            # derived unique accounts from nameOrig ∪ nameDest
        ├── train.csv               # 70% temporal split with is_fraud label
        ├── val.csv                 # 15%
        ├── test.csv                # 15%, no label
        ├── sample.py               # one-time sampler from a local PaySim dump
        └── LICENSE.txt             # CC BY-SA 4.0 + PaySim attribution
```

**Start here**: `fraud_detection_local.py` (CPU, no external setup). Use
`fraud_detection.py` (requires GPU) as the adaptation reference when you wire
this pattern into your own Snowflake data. Explore
`fraud_detection_rules.ipynb` for a rule-based-only take on identity graphs.

## Sample data

The bundled mini dataset is sampled from the [PaySim synthetic mobile-money
transactions dataset](https://www.kaggle.com/datasets/ealaxi/paysim1) by
Edgar Lopez-Rojas, released under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

- **16K transactions** sampled with class balance inflated from PaySim's native
  0.13% fraud up to 50% so the GNN has enough positive signal to learn from on
  CPU. Real-world fraud-detection runs should preserve native imbalance and
  use class weighting.
- **Fraud is confined to `CASH_OUT` and `TRANSFER` transaction types** -- this
  is a documented PaySim quirk. The GNN's job is to distinguish *fraudulent*
  CASH_OUT/TRANSFER from *normal* CASH_OUT/TRANSFER via graph context, not to
  rediscover the type filter.
- See `data/paysim_mini/LICENSE.txt` for full attribution and citation.

## Model overview

### Key entities

- **Account** (`account_id`): a PaySim participant, either customer (ID prefix `C`) or merchant (prefix `M`). Appears as either sender (`name_orig`) or receiver (`name_dest`) on transactions.
- **Transaction**: one mobile-money transfer with amount, sender balance delta, receiver balance delta, transaction type (`PAYMENT` / `CASH_IN` / `CASH_OUT` / `TRANSFER` / `DEBIT`), and PaySim's own `is_flagged_fraud` heuristic.

### Pipeline stages

```text
Accounts + Transactions (Snowflake tables or bundled CSVs)
  → GNN binary classification (Transaction.predictions.probs)
  → Alert-score bridge (blend with is_flagged_fraud)
  → Knapsack MILP allocation (hours budget + per-receiver cap)
```

## How it works

### 1. Build the graph

`Account` and `Transaction` concepts are populated from CSVs (local) or Snowflake
(full). A directed `Graph` links each `Transaction` to its sender and receiver
accounts:

```python
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_orig == Account.account_id)
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_dest == Account.account_id)
```

### 2. Train a GNN binary classifier

Task relationships encode the `isFraud` label on train/val and omit it on test:

```python
Train = Relationship(f"{Transaction} at {Any:step_ts} has {Any:label}")
model.define(Train(Transaction, TrainTable.step_ts, TrainTable.is_fraud))
    .where(Transaction.transaction_id == TrainTable.transaction_id)

gnn = GNN(
    exp_database=..., exp_schema=...,
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=False, seed=42,
    device="cpu", n_epochs=10, lr=0.005, temporal_strategy="last",
)
gnn.fit()
Transaction.predictions = gnn.predictions(domain=Test)
```

### 3. Blend GNN probability with heuristic flag

PaySim ships an `isFlaggedFraud` heuristic (large TRANSFER > 200K). Combine it
with the GNN probability:

```python
model.define(Transaction.alert_score(
    ALPHA_FLAG * Transaction.is_flagged_fraud
    + (1 - ALPHA_FLAG) * Transaction.predictions.probs
)).where(Transaction.predictions)
```

### 4. Allocate investigator audit budget (knapsack MILP)

An auditor's time is the scarce resource: the total investigation budget is
fixed in hours, and the time to audit a transaction grows with its size.
Maximize expected loss averted (score × amount) subject to that budget, plus
a per-receiver cap to prevent flooding one account.

```python
problem.satisfy(...).require(
    sum(Txn_ref, Txn_ref.audit_cost * select_ref) <= AUDIT_BUDGET_HOURS
)
# per-receiver cap: at most 1 audit per destination account
problem.maximize(sum(Txn_obj.alert_score * Txn_obj.amount * sel_obj))
```

Because cost and value both scale with transaction size, ranking by
`alert_score` alone is provably suboptimal -- a high-score $5M transfer
consumes 5 hours but may yield less value per hour than three medium-score
$500K transfers at 1 hour each. The MILP trades them off correctly; the
output prints both the MILP objective and a naive sort-and-take baseline so
the tradeoff is visible.

## Customize this template

**Use your own data:**

- Replace the PaySim CSVs (or Snowflake tables) with your own accounts /
  transactions. Keep `customer_id`-style string PKs and a stable transaction
  PK.
- The PropertyTransformer is the main place to localize: drop your PKs/FKs,
  list your categorical vs continuous fields.

**Tune knobs:**

- `ALPHA_FLAG` (0..1) -- weight on the rule-based flag vs the GNN prob.
- `TOTAL_AUDIT_SLOTS` / `PER_ACCOUNT_CAP` -- investigator budget.
- `AUDIT_BUDGET_HOURS` -- total investigator hours available. Raise to audit
  more transactions; lower to stress-test prioritization.
- `LARGE_AMOUNT_THRESHOLD` / `SMALL_AUDIT_COST_HOURS` / `LARGE_AUDIT_COST_HOURS`
  -- the audit-cost curve. Make the jump steeper to reward the MILP's
  knapsack-style tradeoffs more aggressively.
- GNN hyperparameters (`n_epochs`, `lr`, `train_batch_size`, ...) -- see the
  `rai-predictive-training` skill for tuning guidance.

**Extend the model:**

- Add a rule-based Phase-1 filter (e.g. account-level community detection) and
  blend its output into `alert_score`.
- Add additional graph-analysis features (account degree, centrality) via
  derived properties and include them in the `PropertyTransformer` as
  `integer` or `continuous`.

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
<summary><code>has_time_column=True</code> fails validation</summary>

Known limitation in the rai-predictive-training skill: when the concept carrying `time_col` (here, `Transaction`) is used only as an edge intermediary, validation can fail with "no time column defined in data tables." Workaround: set `has_time_column=False` and remove the `"at"` clause from your Relationship templates until resolved.
</details>

<details>
<summary>Spinner floods the log when running in CI / non-TTY</summary>

Set `STREAM_LOGS = False` at the top of the script (the default). The GNN continues training server-side; only the client-side log stream is suppressed.
</details>
