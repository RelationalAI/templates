# Runbook: Fraud Detection — Multi-Reasoner Walkthrough

A fraud team has to decide which flagged transactions to send to human investigators when investigator time is the scarce resource. This chain turns raw accounts and transactions into a prioritized, budget-feasible audit queue: score account centrality, flag sender activity, learn a per-transaction fraud probability with a graph neural network (GNN), blend that into an alert score, then solve a knapsack optimization that captures the most expected loss within a fixed investigator-hours budget. Four reasoner families, one shared model — no single one produces the audit schedule.

## The chain

```
~32,700 accounts and ~16,400 transactions (bundled PaySim sample). The chain
scores account centrality, flags sender activity, learns per-transaction fraud
probability (GNN), blends it into an alert score, then picks the audit queue
that captures the most expected loss within an 80 investigator-hour budget.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Account.pagerank
                             Centrality on the account funds-flow graph.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Account.activity_count
                             Per-account count of outbound transactions.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Predictive   ──►  Transaction.predictions (.probs)
                  (GNN)      Binary fraud classifier (ROC-AUC) over the
                             transaction-account graph; pagerank + activity
                             count are features. Scores the 2,465 test txns.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Rules/bridge ──►  Transaction.alert_score
                             0.3 x is_flagged_fraud + 0.7 x predicted prob.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  Transaction.x_audit  (knapsack MILP)
                             Maximize captured expected loss within 80
                             investigator-hours, then compare the result with
                             a naive top-by-score queue.
  ─────────────────────────────────────────────────────────────────
```

## Code map

- `model/schema.py` declares the stable `Account` and `Transaction` concepts,
  sender and receiver relationships, and train/validation/test task surfaces.
- `model/source.py` provides explicit `load_local_data()` and
  `load_snowflake_data()` functions. Importing `model` does not select or load
  a data source.
- `fraud_detection_local.py` is the primary runner. It loads the bundled CSVs,
  trains on CPU, solves the 80-hour audit problem, and prints the audit queue.
- `fraud_detection.py` is the Snowflake adaptation. It loads equivalent tables,
  trains on GPU, and uses a 2,000-hour budget by default.
- `fraud_detection_rules.ipynb` remains a complementary rule-based
  identity-graph introduction.

## Workflow

> **How to use this walkthrough.** Run `python fraud_detection_local.py` for
> the complete bundled example. The prompts below describe the same stages for
> an analyst using the named `/rai-*` skills. Run them **in order, in one
> session** because each step adds data or properties to the shared model.
> The local path uses CSV data and CPU training; it still requires a configured
> RelationalAI connection and a writable experiment schema.

### 1. Build ontology

**Prompt**

```text
/rai-ontology Load the bundled PaySim CSVs with load_local_data(): accounts
(each with an id and account-type prefix), transactions (each with a type,
amount, sender and receiver balances, sender and receiver accounts, fraud flag,
and derived audit cost), and the train/validation/test task files. Use the
Account and Transaction declarations from model/schema.py and connect each
transaction to its sender and receiver accounts.
```

**Response**

`load_local_data()` loads `Account` (~32,661 customer and merchant accounts),
`Transaction` (~16,426 rows with `trans_type`, `amount`, balance fields,
`is_flagged_fraud`, and a derived audit cost), and the train/validation/test
task files (~11,498 / 2,463 / 2,465 rows). The test set is the unlabeled
decision set.

### 2. Examine ontology

**Prompt**

```text
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

`Account` (~32,661), `Transaction` (~16,426, linked to sender and receiver
accounts), and the train/validation/test task surfaces. The training set
carries the fraud label after the sample inflates the rare native fraud rate
for CPU training.

### 3. Discover reasoner questions

**Prompt**

```text
/rai-discovery We need to pick which flagged transactions to investigate within a limited number of investigator-hours, using network structure and a learned fraud probability. How should we break this down?
```

**Response**

Routes to graph centrality and an activity flag (account features), a GNN fraud classifier (per-transaction probability), an alert-score blend, and a knapsack optimization over the investigator-hours budget.

### 4. Score account centrality

**Prompt**

```text
/rai-graph-analysis On the account-to-account funds-flow graph (an edge from each transaction's sender to its receiver), score each account's centrality with PageRank, and persist it as Account.pagerank so the fraud model can use it as a feature.
```

**Response**

PageRank runs over the account funds-flow graph; `Account.pagerank` is written back as a continuous feature.

### 5. Flag account activity

**Prompt**

```text
/rai-pyrel For each account, count how many transactions it sends, and persist it as Account.activity_count for use as a model feature.
```

**Response**

`Account.activity_count` is derived as the per-account count of outbound transactions and written back — the second account-level feature.

### 6. Train the fraud classifier

**Prompt**

```text
/rai-predictive-modeling + /rai-predictive-training Train a graph neural network to predict whether each transaction is fraudulent (binary classification, evaluated by ROC-AUC) over the transaction-to-account graph, using the transaction fields plus the account features (pagerank, activity count). Train on the labeled training split, validate, and score the test transactions, writing the fraud probabilities back to the ontology.
```

**Response**

A GNN binary classifier trains on the transaction-account graph (features
include `amount`, balance deltas, `pagerank`, and `activity_count`) and scores
the 2,465 test transactions. The probabilities are written back as
`Transaction.predictions` (`.probs`). The bundled runner trains on CPU; runtime
depends on the connected engine and environment.

### 7. Blend into an alert score

**Prompt**

```text
/rai-pyrel Combine the existing fraud flag and the model's probability into a single alert score — 30% the flag, 70% the predicted probability — and persist it as Transaction.alert_score.
```

**Response**

`Transaction.alert_score = 0.3 x is_flagged_fraud + 0.7 x predicted probability` is written back, giving each transaction a single prioritization score.

### 8. Allocate the investigator budget

**Prompt**

```text
/rai-prescriptive-problem Choose which test transactions to audit to maximize
captured expected loss — alert score times amount — within an 80
investigator-hour budget (each audit costs its transaction's audit_cost in
hours), with at most one audit per receiving account. Persist the audit
decision as Transaction.x_audit.
```

**Response**

The verified bundled run reaches an `OPTIMAL` HiGHS solution and captures
about **$111.9M** of expected loss within the 80-hour budget.
`Transaction.x_audit` stores the selected transactions. Exact values may shift
slightly with GNN numerical variation.

### 9. Compare to the naive queue

**Prompt**

```text
/rai-prescriptive-results How much more expected loss does the optimized audit queue capture than a naive queue that just sorts by alert score until the budget runs out?
```

**Response**

The verified bundled run captures about **$43.9M more** than the naive
sort-by-score queue (~$111.9M vs ~$67.9M). The MILP trades each audit's
hour-cost against its catch value and respects the one-audit-per-receiver cap,
rather than spending the budget on the highest-scored but expensive or
redundant transactions first. Exact values depend on the trained model's
probabilities.

## Adapt the flow to Snowflake

Use `fraud_detection.py` when your accounts, transactions, and task splits
already live in Snowflake:

1. Set `DATABASE` and `SCHEMA` to the location of `ACCOUNTS`,
   `TRANSACTIONS`, `TRAIN`, `VAL`, and `TEST`.
2. Provide `audit_cost` on `TRANSACTIONS`; the loader maps the column without
   recomputing it.
3. Update the feature mapping and task-column accesses in the runner for your
   schema.
4. Run `python fraud_detection.py` on a GPU-enabled RAI engine.

The Snowflake runner calls `load_snowflake_data()` explicitly and retains the
same schema, reasoning stages, output comparison, and `Transaction.x_audit`
result as the local runner. Its default investigator budget is 2,000 hours to
match the larger dataset.
