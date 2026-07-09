# Runbook: Fraud Detection — Multi-Reasoner Walkthrough

A fraud team has to decide which flagged transactions to send to human investigators when investigator time is the scarce resource. This chain turns raw accounts and transactions into a prioritized, budget-feasible audit queue: score account centrality, flag sender activity, learn a per-transaction fraud probability with a graph neural network (GNN), blend that into an alert score, then solve a knapsack optimization that captures the most expected loss within a fixed investigator-hours budget. Four reasoner families, one ontology — no single one produces the audit schedule.

## The chain

```
~32,700 accounts and ~16,400 transactions (PaySim mobile-money). The chain scores
account centrality, flags sender activity, learns per-transaction fraud probability
(GNN), blends it into an alert score, then picks the audit queue that captures the most
expected loss within a 2,000 investigator-hour budget — OPTIMAL, ~$1.70B captured,
about +40% over a naive sort-by-score.

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
                             Maximize captured expected loss within 2,000
                             investigator-hours. OPTIMAL, ~$1.70B captured;
                             +$489M (~40%) over a naive top-by-score sort.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts. This template reads from Snowflake source tables and trains a GNN on a GPU engine (a gurobi/HiGHS-enabled prescriptive engine and a GPU predictive engine are prerequisites).

### 1. Build ontology

**Prompt**

```
/rai-ontology Build an ontology from the PaySim mobile-money Snowflake schema: accounts (each with an id and an account-type prefix), transactions (each with a type, an amount, sender and receiver balance changes, the sender and receiver accounts, an existing fraud flag, and an audit cost), and the train / validation / test split tables that label transactions as fraud or not. Link each transaction to its sender and receiver accounts.
```

**Response**

Loads `Account` (~32,661: customer and merchant prefixes), `Transaction` (~16,426, with `trans_type`, `amount`, balance deltas, `is_flagged_fraud`, and an `audit_cost` of 1 hour for amounts up to $1M and 5 hours above), and the `TRAIN` / `VAL` / `TEST` label tables (~11,498 / 2,463 / 2,465). The TEST set is the unlabeled decision set.

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

`Account` (~32,661), `Transaction` (~16,426, linked to sender and receiver accounts), and the train/val/test split tables. The training set carries the fraud label (about 38% fraud after class-balance inflation of the rare native rate).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We need to pick which flagged transactions to investigate within a limited number of investigator-hours, using network structure and a learned fraud probability. How should we break this down?
```

**Response**

Routes to graph centrality and an activity flag (account features), a GNN fraud classifier (per-transaction probability), an alert-score blend, and a knapsack optimization over the investigator-hours budget.

### 4. Score account centrality

**Prompt**

```
/rai-graph-analysis On the account-to-account funds-flow graph (an edge from each transaction's sender to its receiver), score each account's centrality with PageRank, and persist it as Account.pagerank so the fraud model can use it as a feature.
```

**Response**

PageRank runs over the account funds-flow graph; `Account.pagerank` is written back as a continuous feature.

### 5. Flag account activity

**Prompt**

```
/rai-pyrel For each account, count how many transactions it sends, and persist it as Account.activity_count for use as a model feature.
```

**Response**

`Account.activity_count` is derived as the per-account count of outbound transactions and written back — the second account-level feature.

### 6. Train the fraud classifier

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Train a graph neural network to predict whether each transaction is fraudulent (binary classification, evaluated by ROC-AUC) over the transaction-to-account graph, using the transaction fields plus the account features (pagerank, activity count). Train on the labeled training split, validate, and score the test transactions, writing the fraud probabilities back to the ontology.
```

**Response**

A GNN binary classifier trains on the transaction-account graph (features include `amount`, balance deltas, `pagerank`, `activity_count`) and scores the 2,465 test transactions; the probabilities are written back as `Transaction.predictions` (`.probs`). Training plus prediction takes roughly 10 minutes on the GPU engine.

### 7. Blend into an alert score

**Prompt**

```
/rai-pyrel Combine the existing fraud flag and the model's probability into a single alert score — 30% the flag, 70% the predicted probability — and persist it as Transaction.alert_score.
```

**Response**

`Transaction.alert_score = 0.3 x is_flagged_fraud + 0.7 x predicted probability` is written back, giving each transaction a single prioritization score.

### 8. Allocate the investigator budget

**Prompt**

```
/rai-prescriptive-problem Choose which test transactions to audit to maximize captured expected loss — alert score times amount — within a 2,000 investigator-hour budget (each audit costs its transaction's audit_cost in hours), with at most one audit per receiving account. Persist the audit decision as Transaction.x_audit.
```

**Response**

OPTIMAL (HiGHS knapsack MILP), capturing about **$1.70B** of expected loss within the 2,000-hour budget. The budget binds — feasible audit demand (~5,300 hours) far exceeds it — and `Transaction.x_audit` is written back.

### 9. Compare to the naive queue

**Prompt**

```
/rai-prescriptive-results How much more expected loss does the optimized audit queue capture than a naive queue that just sorts by alert score until the budget runs out?
```

**Response**

The cost-aware MILP captures about **$489M more** than the naive sort-by-score queue (~$1.70B vs ~$1.21B) — roughly a **40% uplift** — by trading each audit's hour-cost against its catch value and respecting the one-audit-per-receiver cap, rather than spending the budget on the highest-scored (but expensive or redundant) transactions first. (The exact dollar figures depend on the trained model's probabilities; the sizable uplift over the naive queue is the stable result.)

## Data

Source: the PaySim mobile-money Snowflake schema (accounts, transactions, train/val/test splits). The audit budget (2,000 hours), audit-cost tiers, and alert-score blend are constants in the script. Full chain in `fraud_detection.py`.
