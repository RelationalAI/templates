"""Fraud classifier: the GNN that scores test transactions for fraud, and the class balance of its
training labels."""

from relationalai.semantics import DateTime, Float, Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.std import aggregates as aggs

# Declares Account.pagerank and Account.activity_count, the GNN's account features.
from . import account_signals  # noqa: F401
from .schema import Account, Test, Train, Transaction, Val, model

SEED = 42

# Directed Transaction->Account bipartite graph: used by the GNN for
# sender/receiver message-passing.
gnn_graph = Graph(model, directed=True, weighted=False, name="transaction_account_graph")
Edge = gnn_graph.Edge
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.sender(Account)
)
model.define(Edge.new(src=Transaction, dst=Account)).where(
    Transaction.receiver(Account)
)

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

# Class balance of the training labels: how many labeled transactions, how
# many of them are fraud, and the fraud rate.
TrainClassBalance = model.Relationship(
    f"the training split has {Integer:transactions} transactions, {Integer:fraud} of them fraud, "
    f"a fraud rate of {Float:fraud_rate}"
)
_train_label = Integer.ref()
_labeled = Train(Transaction, DateTime.ref(), _train_label)
model.define(TrainClassBalance(
    aggs.count(Transaction).where(_labeled),
    aggs.sum(Transaction, _train_label).where(_labeled),
    aggs.avg(Transaction, _train_label).where(_labeled),
))
