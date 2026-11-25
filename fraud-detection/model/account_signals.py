"""Account signals for the fraud classifier: PageRank on the funds-flow graph and each account's
count of sent transfers."""

from relationalai.semantics import Float, Integer, count
from relationalai.semantics.reasoners.graph import Graph

from .schema import Account, Transaction, model

# Account->Account funds-flow graph: one edge per transaction from sender
# to receiver. `node_concept=Account` means `acct_graph.Node IS Account`,
# so graph-algorithm results attach directly to Account without a
# DataFrame round-trip. `aggregator="sum"` collapses multi-edges that
# arise when the same pair of accounts trades more than once.
acct_graph = Graph(
    model, directed=True, weighted=False,
    node_concept=Account, aggregator="sum",
    name="funds_flow_graph",
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
# feeds the GNN as an integer feature (see `fraud_classifier.py`).

Account.activity_count = model.Property(
    f"{Account} has {Integer:activity_count}")
model.define(Account.activity_count(
    count(Transaction).per(Account)
)).where(Transaction.name_orig == Account.account_id)
