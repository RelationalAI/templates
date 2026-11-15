"""Fraud-detection reasoning: account graph signals, the fraud GNN, alert scores, and the investigation-queue MILP."""

from relationalai.semantics import Float, Integer, String, count, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Account, Test, Train, Transaction, Val, model

SEED = 42

# Alert-score mixing weights: final score = ALPHA * is_flagged_fraud + (1-ALPHA) * GNN prob
ALPHA_FLAG = 0.3

# Prescriptive phase: investigator-hours budget + per-audit cost model.
# Each audit consumes hours proportional to transaction size (big transfers
# take deeper forensic work), which `Transaction.audit_cost` carries. This
# makes the MILP a real knapsack problem: a ranker sorting by alert_score
# alone ignores the cost side and over-spends.
AUDIT_BUDGET_HOURS = 80.0  # total investigator hours available
PER_ACCOUNT_CAP = 1  # at most 1 audit per receiver account (avoid flooding)

# Directed Transaction->Account bipartite graph: used by the GNN for
# sender/receiver message-passing.
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.sender(Account)
)
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.receiver(Account)
)

# Account->Account funds-flow graph: one edge per transaction from sender
# to receiver. `node_concept=Account` means `acct_graph.Node IS Account`,
# so graph-algorithm results attach directly to Account without a
# DataFrame round-trip. `aggregator="sum"` collapses multi-edges that
# arise when the same pair of accounts trades more than once.
acct_graph = Graph(
    model, directed=True, weighted=False,
    node_concept=Account, aggregator="sum",
)
_sender = Account.ref()
_receiver = Account.ref()
_txn_ref = Transaction.ref()
model.define(acct_graph.Edge.new(src=_sender, dst=_receiver)).where(
    _txn_ref.sender(_sender),
    _txn_ref.receiver(_receiver),
)

# --------------------------------------------------
# Stage 1: Graph -- account centrality via PageRank
# --------------------------------------------------
# PageRank returns a binary Relationship (account, score). Bind it to an
# explicit Account.pagerank Property so the GNN table materialiser sees a
# named column.
pagerank_rel = acct_graph.pagerank()
Account.pagerank = model.Property(f"{Account} has {Float:pagerank}")
_a_pr = Account.ref()
_score_pr = Float.ref()
model.define(_a_pr.pagerank(_score_pr)).where(pagerank_rel(_a_pr, _score_pr))

# --------------------------------------------------
# Stage 2: Rules -- account activity (derivation rule)
# --------------------------------------------------
# Canonical PyRel rule pattern: a derivation Property whose value is computed
# by aggregation. Sender-side count is a reasonable proxy for activity in a
# mule-style pattern; a symmetric sender-or-receiver count would need an
# OR-join the PyRel aggregation surface doesn't expose directly. The output
# feeds the GNN as an integer feature via the PropertyTransformer below.

Account.activity_count = model.Property(
    f"{Account} has {Integer:activity_count}")
model.define(Account.activity_count(
    count(Transaction).per(Account)
)).where(Transaction.name_orig == Account.account_id)

# PropertyTransformer -- drop PK/FK string IDs, keep typed behavioural
# fields plus the Stage-1 graph output and Stage-2 rule flags.
pt = PropertyTransformer(
    drop=[
        Account.account_id,
        Transaction.transaction_id, Transaction.name_orig, Transaction.name_dest,
        Transaction.sender, Transaction.receiver,
        Transaction.audit_cost,  # operational parameter for the MILP, not a GNN feature
    ],
    category=[Account.account_type_prefix, Transaction.trans_type],
    continuous=[
        Transaction.amount,
        Transaction.old_balance_orig, Transaction.new_balance_orig,
        Transaction.old_balance_dest, Transaction.new_balance_dest,
        Account.pagerank,  # graph-reasoner feature (Stage 1)
    ],
    integer=[
        Transaction.step,
        Transaction.is_flagged_fraud,
        Account.activity_count,  # rule-derived feature (Stage 2)
    ],
    datetime=[Transaction.step_ts],
    time_col=[Transaction.step_ts],
)

# --------------------------------------------------
# Stage 3: Predictive -- GNN binary classification
# --------------------------------------------------
# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.fraud_classifier` names in raiconfig.yaml:
# train.py registers the trained run there, and every refresh scores the
# test split with it.
gnn = GNN(
    name="fraud_classifier",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, stream_logs=False, seed=SEED,
    n_epochs=10, lr=0.005,
    temporal_strategy="last",
)
Transaction.predictions = gnn.predictions(domain=Test)

# --------------------------------------------------
# Stage 4: Bridge -- alert score
# --------------------------------------------------
# Combine PaySim's built-in isFlaggedFraud heuristic with GNN probability. The
# score is a property of its own concept, not of Transaction: the GNN reads the
# Transaction table, so a Transaction property derived from the predictions
# would make the predictions depend on themselves.
AuditCandidate = model.Concept("AuditCandidate", identify_by={"transaction_id": Integer})
AuditCandidate.alert_score = model.Property(
    f"{AuditCandidate} has {Float:alert_score}")
model.define(AuditCandidate.new(transaction_id=Transaction.transaction_id)).where(
    Transaction.predictions
)
model.define(AuditCandidate.alert_score(
    ALPHA_FLAG * Transaction.is_flagged_fraud
    + (1 - ALPHA_FLAG) * Transaction.predictions.probs
)).where(
    Transaction.predictions,
    Transaction.transaction_id == AuditCandidate.transaction_id,
)

# --------------------------------------------------
# Stage 5: Prescriptive -- knapsack MILP investigator-budget allocation
# --------------------------------------------------
Txn_ref = Transaction.ref()
Cand_ref = AuditCandidate.ref()
select_ref = Float.ref()
problem = Problem(model, Float, name="fraud_detection")

# Decision variable: audit this transaction? (binary), one per scored
# transaction (AuditCandidate rows exist for the test-set transactions only).
AuditCandidate.x_audit = model.Property(
    f"{AuditCandidate} audited as {Float:x}")
problem.solve_for(
    AuditCandidate.x_audit(select_ref),
    type="bin",
    name=["audit", AuditCandidate.transaction_id],
)

# Constraint: total investigator hours <= budget
#   sum over audited transactions of audit_cost <= AUDIT_BUDGET_HOURS
problem.satisfy(model.where(
    Cand_ref.x_audit(select_ref),
    Txn_ref.transaction_id == Cand_ref.transaction_id,
).require(
    sum(Cand_ref, Txn_ref.audit_cost * select_ref) <= AUDIT_BUDGET_HOURS
))

# Constraint: per-receiver-account cap (at most PER_ACCOUNT_CAP audits per receiver)
Acct_ref = Account.ref()
Txn_rc = Transaction.ref()
Cand_rc = AuditCandidate.ref()
select_rc = Float.ref()
problem.satisfy(model.where(
    Cand_rc.x_audit(select_rc),
    Txn_rc.transaction_id == Cand_rc.transaction_id,
    Txn_rc.name_dest == Acct_ref.account_id,
).require(
    sum(Cand_rc, select_rc).per(Acct_ref) <= PER_ACCOUNT_CAP
))

# Objective: maximize expected loss averted
#   E[loss averted | audit] = alert_score * transaction_amount
# Ranking by alert_score alone is suboptimal here: a high-score $5M transfer
# consumes 5 hours but yields less $/hour than two medium-score $500K at 1hr.
sel_obj = Float.ref()
Txn_obj = Transaction.ref()
Cand_obj = AuditCandidate.ref()
problem.maximize(sum(
    Cand_obj.alert_score * Txn_obj.amount * sel_obj
).where(
    Cand_obj.x_audit(sel_obj),
    Txn_obj.transaction_id == Cand_obj.transaction_id,
))

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"fraud audit solve status is {String:status}")
SolveObjective = model.Relationship(f"fraud audit objective is {Float:objective}")
model.define(SolveStatus(problem.termination_status()), SolveObjective(problem.objective_value()))
