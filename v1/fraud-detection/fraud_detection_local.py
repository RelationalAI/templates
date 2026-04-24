"""Fraud Detection -- local CPU runner for the predict-then-optimize template.

Runs the full pipeline on a bundled class-balanced subset of the PaySim
synthetic mobile-money dataset (~16K transactions, 50% fraud). Everything
loads from CSVs in `data/paysim_mini/` via `model.data()` -- no Snowflake
data loading, no GPU required.

Phases:
  1. GNN binary classification of fraudulent transactions
     (Customer-Transaction-Merchant graph -> isFraud probability).
  2. Alert-score bridge combining the GNN probability with PaySim's
     built-in `isFlaggedFraud` heuristic.
  3. Prescriptive investigator-budget allocation (MILP): choose which
     transactions to audit, subject to a total slot cap, per-transaction-type
     caps, and a per-receiver-account cap.

For the full pipeline against PaySim-in-Snowflake + GPU, see fraud_detection.py.
The rule-based identity-graph intro remains in fraud_detection_rules.ipynb.

Run:
    python fraud_detection_local.py
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
SEED = 42
STREAM_LOGS = False  # True for TTY; False avoids spinner flood in non-TTY logs
VERBOSE_DATASET = False

# Alert-score mixing weights: final score = ALPHA * is_flagged_fraud + (1-ALPHA) * GNN prob
ALPHA_FLAG = 0.3

# Prescriptive phase: investigator budget knobs
TOTAL_AUDIT_SLOTS = 50        # K audit slots across all flagged transactions
PER_ACCOUNT_CAP = 1           # at most 1 audit per receiver account (avoids flooding)

DATA_DIR = Path(__file__).parent / "data"
PAYSIM_DIR = DATA_DIR / "paysim_mini"


def _report(gnn, label):
    """After gnn.fit(), dump the engine-side data config to help diagnose
    feature-type or edge misconfig. Gated by VERBOSE_DATASET."""
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
        print(f"  wrote {label}_schema.png")
    except Exception as e:
        print(f"  visualize_dataset unavailable (install pydot?): {e}")


model = Model("fraud_detection_local")
Concept, Relationship = model.Concept, model.Relationship

# --------------------------------------------------
# Phase 1: Core entity concepts + graph
# --------------------------------------------------
Account = Concept("Account", identify_by={"account_id": String})
Transaction = Concept("Transaction", identify_by={"transaction_id": Integer})

accounts_df = read_csv(PAYSIM_DIR / "accounts.csv")
transactions_df = read_csv(PAYSIM_DIR / "transactions.csv", parse_dates=["step_ts"])

model.define(Account.new(model.data(accounts_df).to_schema()))
model.define(Transaction.new(model.data(transactions_df).to_schema()))

gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
# Sender edge: transaction -> origin account
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_orig == Account.account_id)
# Receiver edge: transaction -> destination account
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.name_dest == Account.account_id)

# PropertyTransformer -- drop PK/FK string IDs, keep typed behavioural fields.
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

train_df = read_csv(PAYSIM_DIR / "train.csv", parse_dates=["step_ts"])
val_df = read_csv(PAYSIM_DIR / "val.csv", parse_dates=["step_ts"])
test_df = read_csv(PAYSIM_DIR / "test.csv", parse_dates=["step_ts"])

model.define(TrainTable.new(model.data(train_df).to_schema()))
model.define(ValTable.new(model.data(val_df).to_schema()))
model.define(TestTable.new(model.data(test_df).to_schema()))

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

# Class-balance profile before training (baseline ROC_AUC = 0.5)
_label_df = select(TrainTable.is_fraud.alias("label")).to_df()
if len(_label_df):
    # Cast out of pyarrow's Int128 to Python int for aggregation
    _l = _label_df["label"].astype("int64")
    print("\n=== Fraud class balance (train split) ===")
    print(f"  n={len(_l)}  fraud={int(_l.sum())}  "
          f"fraud_rate={_l.mean():.1%}")
    print("  Baseline ROC_AUC = 0.5")

print("\n" + "=" * 60)
print("PREDICTIVE: Fraud binary-classification GNN (CPU, PaySim mini)")
print("=" * 60)

gnn = GNN(
    exp_database="FRAUD_DETECTION", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=STREAM_LOGS, seed=SEED,
    device="cpu", n_epochs=10, lr=0.005,
    temporal_strategy="last",
)
gnn.fit()
_report(gnn, "fraud_gnn")
Transaction.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Phase 3: Alert score (bridge)
# --------------------------------------------------
# Combine PaySim's built-in isFlaggedFraud heuristic with GNN probability.
Transaction.alert_score = model.Property(
    f"{Transaction} has {Float:alert_score}")
model.define(Transaction.alert_score(
    ALPHA_FLAG * Transaction.is_flagged_fraud
    + (1 - ALPHA_FLAG) * Transaction.predictions.probs
)).where(Transaction.predictions)

print("\n=== Top-20 alert-scored transactions ===")
Txn_ref = Transaction.ref()
score_ref = Float.ref()
_alert_df = (
    model.select(
        Txn_ref.transaction_id.alias("transaction_id"),
        Txn_ref.trans_type.alias("trans_type"),
        Txn_ref.amount.alias("amount"),
        Txn_ref.name_dest.alias("receiver"),
        score_ref.alias("alert_score"),
    )
    .where(Txn_ref.alert_score(score_ref))
    .to_df()
    .sort_values("alert_score", ascending=False)
    .head(20)
)
print(_alert_df.to_string(index=False))

# --------------------------------------------------
# Phase 4: Prescriptive investigator-budget allocation (MILP)
# --------------------------------------------------
print("\n" + "=" * 60)
print("PRESCRIPTIVE: Investigator-budget allocation")
print("=" * 60)

# Per-transaction-type caps (forces audit breadth across types, not just the
# top two fraud-native types)
TypeCap = Concept("TypeCap", identify_by={"trans_type": String})
TypeCap.type_cap = model.Property(f"{TypeCap} has {Integer:type_cap}")
budget_csv = read_csv(DATA_DIR / "investigator_budget.csv")
model.define(TypeCap.new(model.data(budget_csv).to_schema()))

Txn_ref = Transaction.ref()
select_ref = Float.ref()
alert_bind = Float.ref()
problem = Problem(model, Float)

# Decision variable: audit this transaction? (binary)
# Use `Transaction` directly in both the solve_for signature and the name=
# tuple so the FD check sees one variable per transaction. The where= filter
# restricts the domain to transactions that have an alert_score (test-set
# only).
Transaction.x_audit = model.Property(
    f"{Transaction} audited as {Float:x}")
problem.solve_for(
    Transaction.x_audit(select_ref),
    type="bin",
    name=["audit", Transaction.transaction_id],
    where=[Transaction.alert_score(alert_bind)],
)

# Constraint: total audit slots
problem.satisfy(model.where(
    Txn_ref.x_audit(select_ref),
).require(
    sum(Txn_ref, select_ref) <= TOTAL_AUDIT_SLOTS
))

# Constraint: per-trans_type cap (diversity across PAYMENT/CASH_OUT/TRANSFER/...)
Type_inner = TypeCap.ref()
Txn_inner = Transaction.ref()
select_inner = Float.ref()
problem.satisfy(model.where(
    Txn_inner.x_audit(select_inner),
    Txn_inner.trans_type == Type_inner.trans_type,
).require(
    sum(Txn_inner, select_inner).per(Type_inner) <= Type_inner.type_cap
))

# Constraint: per-receiver-account cap (at most PER_ACCOUNT_CAP audits per receiver)
Acct_ref = Account.ref()
Txn_rc = Transaction.ref()
select_rc = Float.ref()
problem.satisfy(model.where(
    Txn_rc.x_audit(select_rc),
    Txn_rc.name_dest == Acct_ref.account_id,
).require(
    sum(Txn_rc, select_rc).per(Acct_ref) <= PER_ACCOUNT_CAP
))

# Objective: maximize captured alert score
score_obj = Float.ref()
sel_obj = Float.ref()
Txn_obj = Transaction.ref()
problem.maximize(sum(score_obj * sel_obj).where(
    Txn_obj.x_audit(sel_obj),
    Txn_obj.alert_score(score_obj),
))

problem.solve("highs", time_limit_sec=120)
si = problem.solve_info()
print(f"\nMILP Status: {si.termination_status}")
if si.objective_value is not None:
    # Compare with a naive top-K by alert_score (no per-type or per-receiver caps)
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

# Report the selected audit queue
print("\n=== Selected audit queue ===")
sel_ref = Float.ref()
audit_df = (
    model.select(
        Txn_ref.transaction_id.alias("transaction_id"),
        Txn_ref.trans_type.alias("trans_type"),
        Txn_ref.amount.alias("amount"),
        Txn_ref.name_dest.alias("receiver"),
        score_ref.alias("alert_score"),
    )
    .where(
        Txn_ref.x_audit(sel_ref),
        sel_ref > 0.5,
        Txn_ref.alert_score(score_ref),
    )
    .to_df()
    .sort_values("alert_score", ascending=False)
)
if audit_df.empty:
    print("  No transactions selected (MILP degenerate).")
else:
    print(f"  {len(audit_df)} audits scheduled:")
    print(audit_df.to_string(index=False))
    print("\n  By trans_type:")
    print(audit_df["trans_type"].value_counts().to_string())

print("\n" + "=" * 60)
print("Local run complete. Full pipeline (Snowflake + GPU): fraud_detection.py")
print("=" * 60)
