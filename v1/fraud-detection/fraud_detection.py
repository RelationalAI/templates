"""Fraud Detection -- full-pipeline runner for the predict-then-optimize template.

Reference implementation of the same 3-phase pipeline as fraud_detection_local.py,
but loading from a full PaySim dataset in Snowflake and training on GPU. Use this
as an adaptation reference when wiring the pattern into your own Snowflake data
(customer / transaction / counterparty tables + train/val/test split tables).

Phases (identical to the local runner):
  1. GNN binary classification of fraudulent transactions
     (Account-Transaction graph -> isFraud probability).
  2. Alert-score bridge combining the GNN probability with a rule-based flag.
  3. Prescriptive investigator-budget allocation (knapsack MILP):
     maximize expected loss averted (alert_score x transaction_amount)
     subject to a fixed-hours audit budget (cost proportional to size)
     plus a per-receiver cap. Ranking by score alone is suboptimal.

Prerequisites:
  - PaySim loaded in Snowflake as FRAUD_DB.PAYSIM.{TRANSACTIONS, ACCOUNTS, TRAIN, VAL, TEST}
    (a SQL snippet for building the train/val/test splits by `step` cutoff is in the README)
  - RAI native app granted USAGE on FRAUD_DB + ALL on the experiment schema:
      GRANT USAGE ON DATABASE FRAUD_DB TO APPLICATION RELATIONALAI;
      GRANT ALL ON SCHEMA FRAUD_DB.EXPERIMENTS TO APPLICATION RELATIONALAI;
  - GPU-enabled RAI engine (otherwise training is prohibitively slow on 6M rows)

Run:
    python fraud_detection.py

Output:
    Class-balance profile, GNN ROC-AUC, knapsack MILP objective ($ expected
    loss averted), and a naive-sort baseline for comparison.
"""

from pathlib import Path

import numpy as np
from relationalai.semantics import Any, Float, Integer, Model, String, select, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configuration
# --------------------------------------------------
# Snowflake location for PaySim data. Adjust to match your environment.
DATABASE = "FRAUD_DB"
SCHEMA = "PAYSIM"       # schema with TRANSACTIONS + ACCOUNTS + train/val/test tables

# Snowflake location for GNN experiment artifacts. The RAI native app
# must have USAGE on the database and ALL on this schema.
GNN_EXP_DATABASE = "FRAUD_DB"
GNN_EXP_SCHEMA = "EXPERIMENTS"

SEED = 42
STREAM_LOGS = False
VERBOSE_DATASET = False

ALPHA_FLAG = 0.3

# Prescriptive phase: investigator-hours budget + per-audit cost model.
AUDIT_BUDGET_HOURS = 2000.0       # scale up from the local subset's 80h
LARGE_AMOUNT_THRESHOLD = 1_000_000.0
SMALL_AUDIT_COST_HOURS = 1.0
LARGE_AUDIT_COST_HOURS = 5.0
PER_ACCOUNT_CAP = 1

DATA_DIR = Path(__file__).parent / "data"


def _report(gnn, label):
    if not VERBOSE_DATASET:
        return
    print(f"\n--- {label}: engine-side data config ---")
    try:
        gnn.dataset.print_data_config()
    except Exception as e:
        print(f"  print_data_config unavailable: {e}")
    try:
        viz = gnn.visualize_dataset(show_dtypes=True)
        viz.write_png(f"{label}_schema.png")
    except Exception as e:
        print(f"  visualize_dataset unavailable (install pydot?): {e}")


model = Model("fraud_detection")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# --------------------------------------------------
# Phase 1: Core entity concepts + graph (loaded from Snowflake)
# --------------------------------------------------
Account = Concept("Account", identify_by={"account_id": String})
Transaction = Concept("Transaction", identify_by={"transaction_id": Integer})

model.define(Account.new(Table(f"{DATABASE}.{SCHEMA}.ACCOUNTS").to_schema()))
model.define(Transaction.new(Table(f"{DATABASE}.{SCHEMA}.TRANSACTIONS").to_schema()))

# Derive audit_cost (hours) from transaction size in Snowflake as part of the
# TRANSACTIONS table (add a view with a CASE expression) rather than at Python
# load time. Example SQL:
#     SELECT *, CASE WHEN amount > 1000000 THEN 5.0 ELSE 1.0 END AS audit_cost
#     FROM RAW_TRANSACTIONS;
# The PropertyTransformer drops audit_cost below so it's not a GNN feature.

gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_orig == Account.account_id)
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_dest == Account.account_id)

pt = PropertyTransformer(
    drop=[
        Account.account_id,
        Transaction.transaction_id, Transaction.name_orig, Transaction.name_dest,
        Transaction.audit_cost,
    ],
    category=[Account.account_type_prefix, Transaction.trans_type],
    continuous=[
        Transaction.amount,
        Transaction.old_balance_orig, Transaction.new_balance_orig,
        Transaction.old_balance_dest, Transaction.new_balance_dest,
    ],
    integer=[Transaction.is_flagged_fraud],
    datetime=[Transaction.step_ts],
    time_col=[Transaction.step_ts],
)

# --------------------------------------------------
# Phase 2: Binary-classification task setup + GNN training
# --------------------------------------------------
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

model.define(TrainTable.new(Table(f"{DATABASE}.{SCHEMA}.TRAIN").to_schema()))
model.define(ValTable.new(Table(f"{DATABASE}.{SCHEMA}.VAL").to_schema()))
model.define(TestTable.new(Table(f"{DATABASE}.{SCHEMA}.TEST").to_schema()))

Train = Relationship(f"{Transaction} at {Any:step_ts} has {Any:label}")
model.define(
    Train(Transaction, TrainTable.step_ts, TrainTable.is_fraud)
).where(Transaction.transaction_id == TrainTable.transaction_id)

Val = Relationship(f"{Transaction} at {Any:step_ts} has {Any:label}")
model.define(
    Val(Transaction, ValTable.step_ts, ValTable.is_fraud)
).where(Transaction.transaction_id == ValTable.transaction_id)

Test = Relationship(f"{Transaction} at {Any:step_ts}")
model.define(
    Test(Transaction, TestTable.step_ts)
).where(Transaction.transaction_id == TestTable.transaction_id)

_label_df = select(TrainTable.is_fraud.alias("label")).to_df()
if len(_label_df):
    _l = _label_df["label"].astype("int64")
    print("\n=== Fraud class balance (train split) ===")
    print(f"  n={len(_l)}  fraud={int(_l.sum())}  "
          f"fraud_rate={_l.mean():.3%}")
    print("  Baseline ROC_AUC = 0.5")

print("\n" + "=" * 60)
print("PREDICTIVE: Fraud binary-classification GNN (GPU, full PaySim)")
print("=" * 60)

gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cuda", n_epochs=20, train_batch_size=512, lr=0.005, head_layers=2,
    temporal_strategy="last",
)
gnn.fit()
_report(gnn, "fraud_gnn")
Transaction.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Phase 3: Alert score (bridge)
# --------------------------------------------------
Transaction.alert_score = model.Property(
    f"{Transaction} has {Float:alert_score}")
model.define(Transaction.alert_score(
    ALPHA_FLAG * Transaction.is_flagged_fraud
    + (1 - ALPHA_FLAG) * Transaction.predictions.probs
)).where(Transaction.predictions)

# --------------------------------------------------
# Phase 4: Prescriptive investigator-budget allocation (knapsack MILP)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE: Investigator-budget allocation")
print("=" * 60)

Txn_ref = Transaction.ref()
select_ref = Float.ref()
alert_bind = Float.ref()
problem = Problem(model, Float)

Transaction.x_audit = model.Property(
    f"{Transaction} audited as {Float:x}")
problem.solve_for(
    Transaction.x_audit(select_ref),
    type="bin",
    name=["audit", Transaction.transaction_id],
    where=[Transaction.alert_score(alert_bind)],
)

# Constraint: total investigator hours <= budget
problem.satisfy(model.where(
    Txn_ref.x_audit(select_ref),
).require(
    sum(Txn_ref, Txn_ref.audit_cost * select_ref) <= AUDIT_BUDGET_HOURS
))

# Constraint: per-receiver cap
Acct_ref = Account.ref()
Txn_rc = Transaction.ref()
select_rc = Float.ref()
problem.satisfy(model.where(
    Txn_rc.x_audit(select_rc),
    Txn_rc.name_dest == Acct_ref.account_id,
).require(
    sum(Txn_rc, select_rc).per(Acct_ref) <= PER_ACCOUNT_CAP
))

# Objective: maximize expected loss averted (alert_score * amount)
sel_obj = Float.ref()
Txn_obj = Transaction.ref()
problem.maximize(sum(
    Txn_obj.alert_score * Txn_obj.amount * sel_obj
).where(Txn_obj.x_audit(sel_obj)))

problem.solve("highs", time_limit_sec=300)
si = problem.solve_info()
print(f"\nMILP Status: {si.termination_status}")
if si.objective_value is not None:
    # Compare against a naive sort-and-take-until-budget-exhausted baseline
    score_ref = Float.ref()
    amount_ref = Float.ref()
    _full_df = (
        model.select(
            Txn_ref.transaction_id.alias("transaction_id"),
            Txn_ref.trans_type.alias("trans_type"),
            amount_ref.alias("amount"),
            score_ref.alias("alert_score"),
        )
        .where(
            Txn_ref.alert_score(score_ref),
            Txn_ref.amount == amount_ref,
        )
        .to_df()
    )
    _full_df["amount"] = _full_df["amount"].astype("float64")
    _full_df["alert_score"] = _full_df["alert_score"].astype("float64")
    _full_df["audit_cost"] = np.where(
        _full_df["amount"] > LARGE_AMOUNT_THRESHOLD,
        LARGE_AUDIT_COST_HOURS, SMALL_AUDIT_COST_HOURS,
    )
    _full_df["expected_loss"] = _full_df["alert_score"] * _full_df["amount"]
    _naive = _full_df.sort_values("alert_score", ascending=False).copy()
    _naive["cumulative_hours"] = _naive["audit_cost"].cumsum()
    _naive_fit = _naive[_naive["cumulative_hours"] <= AUDIT_BUDGET_HOURS]
    _naive_obj = float(_naive_fit["expected_loss"].sum())
    print(f"Captured expected loss (optimal within budget): ${si.objective_value:,.0f}")
    print(f"  MILP (cost-aware + per-receiver cap) -> ${si.objective_value:,.0f}")
    print(f"  Naive top-by-alert-score (budget only) -> ${_naive_obj:,.0f} "
          f"({len(_naive_fit)} audits)")
    print(f"  MILP uplift over naive sort: ${si.objective_value - _naive_obj:+,.0f}")

print("\n" + "=" * 60)
print("Pipeline Complete")
print("=" * 60)
