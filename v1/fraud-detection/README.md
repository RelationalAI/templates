---
title: "Fraud Detection"
description: "Multi-reasoner transaction-fraud pipeline: account PageRank (Graph) + high-volume account flags (Rules) feed a GNN binary classifier (Predictive) whose per-transaction scores drive a knapsack investigator-budget MILP (Prescriptive)."
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

Fraud and risk teams face four interconnected problems: discovering suspicious structure in the identity / transaction graph, classifying accounts by behavior rules, scoring transactions as they come in, and deciding which alerts to investigate given finite human capacity. Traditionally these live in separate tools. This template shows all four working together on one semantic model in RelationalAI, wiring the **Graph → Rules → Predictive → Prescriptive** reasoners into a single pipeline.

**Start with `fraud_detection_local.py`** -- it runs the full five-stage pipeline on a small bundled demo dataset (CPU, no external data): compute account PageRank, derive high-volume account flags, train a GNN binary classifier on the Account-Transaction graph, blend its probability with a rule-based heuristic flag, and solve a knapsack investigator-budget MILP. A few minutes end-to-end.

**Adapt the pattern to your own Snowflake data** using `fraud_detection.py` as a reference -- same five stages, loaded from Snowflake and trained on GPU.

**For the older rule-based-only take** (no ML), see `fraud_detection_rules.ipynb` -- a standalone notebook using Weakly Connected Components on shared-identifier edges to flag suspicious users.

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

- **Graph**: PageRank on an Account-Account funds-flow graph, exposing account centrality as a GNN feature
- **Rules**: derived `activity_count` property per account, fed to the GNN as an integer feature alongside the raw transaction fields
- **Predictive**: a GNN binary classifier on the Account-Transaction graph, predicting `isFraud` per transaction
- **Bridge**: a layer combining GNN probabilities with a rule-based heuristic flag into a per-transaction `alert_score`
- **Prescriptive**: a knapsack-style investigator-budget MILP that maximizes expected loss averted (`alert_score × transaction_amount`) subject to a fixed-hours audit budget (audit cost scales with transaction size) plus a per-receiver cap
- The same five-stage pipeline running against either a bundled CSV subset (local demo) or a full Snowflake dataset (reference path)

## What's included

- **Runners**:
  - `fraud_detection_local.py` -- **primary, runnable out of the box.** Runs all five stages (Graph / Rules / Predictive / Bridge / Prescriptive) end-to-end on the bundled demo CSVs.
  - `fraud_detection.py` -- **reference pattern** for adapting the pipeline to your own Snowflake data. Same five stages, GPU-trained.
  - `fraud_detection_rules.ipynb` -- original rule-based identity-graph notebook, kept as a complementary intro.
- **Model**: `Account`, `Transaction`, plus two graphs (Account-Account for PageRank; Transaction-to-Account for the GNN), derived account properties, and the alert-score bridge
- **Sample data**: a small class-balanced transactions subset sampled from a public mobile-money dataset (CC BY-SA 4.0) -- see [Sample data](#sample-data) below for details and attribution
- **Outputs**: class-balance profile, GNN ROC-AUC, top-K alert queue, optimal audit schedule, MILP-vs-naive uplift

## Prerequisites

### Access

**To run the local demo (`fraud_detection_local.py`)** you need any Snowflake
account with the RAI Native App. No external data, no GPU. The bundled CSVs
under `data/paysim_mini/` ship with the template; the GNN trains on CPU in a
few minutes.

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
- RelationalAI Python SDK (`relationalai`) `==1.0.14`
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

5. Run the local demo on the bundled subset (CPU, a few minutes):
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
   explicitly, annotate categoricals and continuous fields, and -- if your
   data is small enough that the GNN's datetime pipeline doesn't choke on it
   -- set `time_col` on your timestamp column. (See the "has_time_column"
   troubleshooting note below for the workaround at scale.)
3. If your task tables use different column names, update the `Relationship`
   templates (and any `TrainTable.<column>` accesses) to match.
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
=== Fraud class balance (train split) ===
  n=11498  fraud=4339  fraud_rate=37.7%
  Baseline ROC_AUC = 0.5

============================================================
Stage 3: Predictive -- fraud binary-classification GNN (CPU)
============================================================
=== Start GNN Training ===
  ✓ Step 1 completed (~20s)   # prepare dataset + GNN tables
  ✓ Step 2 completed (~2s)    # trainer config
  ✓ Step 3 completed (~5s)    # submit training job
=== Start GNN Prediction ===
  ✓ GNN Prediction Complete (~85s)

============================================================
Stage 5: Prescriptive -- investigator-budget allocation
============================================================
MILP Status: OPTIMAL
Captured expected loss (optimal within budget): $111,854,667
  MILP (cost-aware + per-receiver cap) -> $111,854,667 captured across the audit queue
  Naive top-by-alert-score (budget only, same hours) -> $67,947,657 captured across 16 audits
  MILP uplift over naive sort: $+43,907,010

=== Selected audit queue ===
  16 audits scheduled; 80.0/80 investigator hours used
  By trans_type:
    TRANSFER    11
    CASH_OUT     5
```

The MILP captures ~65% more expected loss than a naive sort-by-alert-score
under the same 80-hour budget, because it trades off per-audit cost (audit
hours scale with transaction size) against catch value and respects the
per-receiver cap. Natural type diversity falls out of the solve without any
per-type constraint.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── fraud_detection_local.py        # primary: 5-stage pipeline on bundled CSVs (CPU)
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

- **Account** (`account_id`): one participant in the transaction network -- customer (ID prefix `C`) or merchant (prefix `M`) in the demo dataset. Appears as either sender (`name_orig`) or receiver (`name_dest`) on transactions. Enriched at pipeline time with `pagerank` (from Stage 1) and `activity_count` (from Stage 2).
- **Transaction**: one transfer with amount, sender balance delta, receiver balance delta, transaction type, and a pre-existing rule-based flag `is_flagged_fraud` used as the heuristic comparator.

### Pipeline stages

```text
Accounts + Transactions (Snowflake tables or bundled CSVs)
  → Stage 1 -- Graph:       PageRank on Account-Account funds-flow graph
  → Stage 2 -- Rules:       Account.activity_count (per-sender derivation)
  → Stage 3 -- Predictive:  GNN binary classification (Transaction.predictions.probs)
  → Stage 4 -- Bridge:      alert_score blends GNN prob with is_flagged_fraud
  → Stage 5 -- Prescriptive: knapsack MILP (hours budget + per-receiver cap)
```

## How it works

### 1. Build the graphs

`Account` and `Transaction` concepts are populated from CSVs (local) or
Snowflake (full). The template constructs two graphs serving different
reasoners. A directed Transaction-to-Account bipartite graph used by the GNN:

```python
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_orig == Account.account_id)
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_dest == Account.account_id)
```

And a directed Account-Account funds-flow graph used by the graph reasoner
(`node_concept=Account` means `acct_graph.Node` binds directly to `Account`):

```python
acct_graph = Graph(
    model, directed=True, weighted=False,
    node_concept=Account, aggregator="sum",
)
_sender, _receiver = Account.ref(), Account.ref()
_txn = Transaction.ref()
model.define(acct_graph.Edge.new(src=_sender, dst=_receiver)).where(
    _txn.name_orig == _sender.account_id,
    _txn.name_dest == _receiver.account_id,
)
```

### 2. Stage 1 -- Graph reasoner: account PageRank

Run PageRank on the funds-flow graph and bind the score to an explicit
`Account.pagerank` property so it surfaces as a GNN feature column:

```python
pagerank_rel = acct_graph.pagerank()
Account.pagerank = model.Property(f"{Account} has {Float:pagerank}")
a, score = Account.ref(), Float.ref()
model.define(a.pagerank(score)).where(pagerank_rel(a, score))
```

### 3. Stage 2 -- Rules reasoner: account activity

Canonical PyRel derivation rule -- a `Property` whose value comes from an
aggregation over related instances:

```python
# Aggregate transaction count per sending account
Account.activity_count = model.Property(
    f"{Account} has {Integer:activity_count}")
model.define(Account.activity_count(
    count(Transaction).per(Account)
)).where(Transaction.name_orig == Account.account_id)
```

Both `Account.pagerank` (continuous) and `Account.activity_count` (integer)
get included in the `PropertyTransformer` so the GNN sees them as features
alongside the raw transaction fields.

### 4. Stage 3 -- Predictive: GNN binary classifier

Task relationships encode the `isFraud` label on train/val and omit it on
test. Both the local and Snowflake reference scripts use temporal
Relationships (`at {Any:step_ts}`) and `has_time_column=True`. At
multi-million-row scale the GNN's datetime pipeline can hit a server-side
`ValidationError` -- if you encounter that adapting to your own data, see
the troubleshooting block below for the workaround (drop temporal handling).

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

### 5. Stage 4 -- Bridge: blend GNN probability with heuristic flag

The bundled dataset carries an `is_flagged_fraud` heuristic from the source
dataset. Combine it with the GNN probability via a convex mix:

```python
model.define(Transaction.alert_score(
    ALPHA_FLAG * Transaction.is_flagged_fraud
    + (1 - ALPHA_FLAG) * Transaction.predictions.probs
)).where(Transaction.predictions)
```

### 6. Stage 5 -- Prescriptive: knapsack MILP investigator-budget allocation

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

- Replace the bundled CSVs (or Snowflake tables) with your own accounts /
  transactions. Keep `customer_id`-style string PKs and a stable transaction
  PK.
- The PropertyTransformer is the main place to localize: drop your PKs/FKs,
  list your categorical vs continuous fields.

**Tune knobs:**

- `ALPHA_FLAG` (0..1) -- weight on the rule-based flag vs the GNN prob.
- `AUDIT_BUDGET_HOURS` / `PER_ACCOUNT_CAP` -- investigator budget knobs.
  Raise the budget to audit more transactions; tighten the cap to spread
  audits across more receivers.
- `LARGE_AMOUNT_THRESHOLD` / `SMALL_AUDIT_COST_HOURS` / `LARGE_AUDIT_COST_HOURS`
  -- the audit-cost curve. Make the jump steeper to reward the MILP's
  knapsack-style tradeoffs more aggressively.
- GNN hyperparameters (`n_epochs`, `lr`, `train_batch_size`, ...) -- see the
  `rai-predictive-training` skill for tuning guidance.

**Extend the model:**

- Swap PageRank for other centrality measures (betweenness, eigenvector) or
  add community labels (Louvain / Infomap) as a categorical GNN feature.
- Author additional rules (e.g. balance-change anomalies, velocity spikes)
  and feed them into both the GNN features and the `alert_score` blend.
- Fold a rule-based flag directly into the MILP as a hard constraint (e.g.
  never skip an already-`is_flagged_fraud=True` transaction) rather than as
  an alert-score contributor.

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
<summary><code>has_time_column=True</code> fails validation (two known triggers)</summary>

Known limitation in the predictive reasoner — the GNN's datetime feature pipeline can fail in two distinct cases:

1. **Edge-intermediary case** (small-data trigger, documented in `rai-predictive-training`): when the concept carrying `time_col` is used only as an edge intermediary (not a node), validation fails with *"no time column defined in data tables"*.
2. **Large-data trigger** (encountered while scaling this template's full Snowflake path): with a Snowflake `VARCHAR` ISO-8601 timestamp column loaded via `Table().to_schema()`, training fails server-side with *"ValidationError: Error processing datetime column 'step_ts'"* — even when the column is a node property, format is correct, and there are no NULLs. The bundled local CSV path (which uses `model.data(df).to_schema()` after `parse_dates=...`) does not hit this.

**Workaround for both:** set `has_time_column=False` in the `GNN(...)` constructor, drop `temporal_strategy=...`, strip the `at {Any:step_ts}` clauses from your Train/Val/Test relationship templates, and comment out `datetime=` and `time_col=` from your `PropertyTransformer`. Build the train/val/test split tables by `step` cutoff in SQL (the temporal split is preserved in the data even if the GNN can't use the timestamp as a feature).
</details>

<details>
<summary>Spinner floods the log when running in CI / non-TTY</summary>

Set `STREAM_LOGS = False` at the top of the script (the default). The GNN continues training server-side; only the client-side log stream is suppressed.
</details>
