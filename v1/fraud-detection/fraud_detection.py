"""Fraud Detection -- full-pipeline runner for the predict-then-optimize template.

Reference implementation of the same 3-phase pipeline as fraud_detection_local.py,
but loading from a full PaySim dataset in Snowflake and training on GPU. Use this
as an adaptation reference when wiring the pattern into your own Snowflake data
(customer / transaction / counterparty tables + train/val/test split tables).

Phases (identical to the local runner):
  1. GNN binary classification of fraudulent transactions
     (Account-Transaction graph -> isFraud probability).
  2. Alert-score bridge combining the GNN probability with a rule-based flag.
  3. Prescriptive investigator-budget allocation (MILP).

Prerequisites:
  - PaySim loaded in Snowflake as FRAUD_DB.PAYSIM.{TRANSACTIONS, ACCOUNTS, TRAIN, VAL, TEST}
    (a SQL snippet for building the train/val/test splits by `step` cutoff is in the README)
  - RAI native app granted USAGE on FRAUD_DB + ALL on the experiment schema:
      GRANT USAGE ON DATABASE FRAUD_DB TO APPLICATION RELATIONALAI;
      GRANT ALL ON SCHEMA FRAUD_DB.EXPERIMENTS TO APPLICATION RELATIONALAI;
  - GPU-enabled RAI engine (otherwise training is prohibitively slow on 6M rows)

Run:
    python fraud_detection.py
"""

from pathlib import Path

from pandas import read_csv
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
TOTAL_AUDIT_SLOTS = 500
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
# Phase 4: Prescriptive investigator-budget allocation (MILP)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE: Investigator-budget allocation")
print("=" * 60)

TypeCap = Concept("TypeCap", identify_by={"trans_type": String})
TypeCap.type_cap = model.Property(f"{TypeCap} has {Integer:type_cap}")
budget_csv = read_csv(DATA_DIR / "investigator_budget.csv")
model.define(TypeCap.new(model.data(budget_csv).to_schema()))

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

problem.satisfy(model.where(
    Txn_ref.x_audit(select_ref),
).require(
    sum(Txn_ref, select_ref) <= TOTAL_AUDIT_SLOTS
))

Type_inner = TypeCap.ref()
Txn_inner = Transaction.ref()
select_inner = Float.ref()
problem.satisfy(model.where(
    Txn_inner.x_audit(select_inner),
    Txn_inner.trans_type == Type_inner.trans_type,
).require(
    sum(Txn_inner, select_inner).per(Type_inner) <= Type_inner.type_cap
))

Acct_ref = Account.ref()
Txn_rc = Transaction.ref()
select_rc = Float.ref()
problem.satisfy(model.where(
    Txn_rc.x_audit(select_rc),
    Txn_rc.name_dest == Acct_ref.account_id,
).require(
    sum(Txn_rc, select_rc).per(Acct_ref) <= PER_ACCOUNT_CAP
))

score_obj = Float.ref()
sel_obj = Float.ref()
Txn_obj = Transaction.ref()
problem.maximize(sum(score_obj * sel_obj).where(
    Txn_obj.x_audit(sel_obj),
    Txn_obj.alert_score(score_obj),
))

problem.solve("highs", time_limit_sec=300)
si = problem.solve_info()
print(f"\nMILP Status: {si.termination_status}")
if si.objective_value is not None:
    score_ref = Float.ref()
    _full_alert_df = (
        model.select(
            Txn_ref.trans_type.alias("trans_type"),
            score_ref.alias("alert_score"),
        )
        .where(Txn_ref.alert_score(score_ref))
        .to_df()
    )
    _greedy = _full_alert_df.nlargest(TOTAL_AUDIT_SLOTS, "alert_score")
    _greedy_obj = float(_greedy["alert_score"].sum())
    _greedy_types = dict(_greedy["trans_type"].value_counts())
    print(f"Captured alert score (top-{TOTAL_AUDIT_SLOTS} audits): {si.objective_value:.4f}")
    print(f"  MILP w/ caps   -> {si.objective_value:.2f} captured; diversified by type + receiver")
    print(f"  Naive top-{TOTAL_AUDIT_SLOTS}   -> {_greedy_obj:.2f} captured; by type: {_greedy_types}")
    print(f"  Tradeoff: MILP gives up {_greedy_obj - si.objective_value:.2f} score "
          f"for a balanced queue that covers both attack vectors")

print("\n" + "=" * 60)
print("Pipeline Complete")
print("=" * 60)
