"""Alert scores: each scored test transaction's alert score, its place in the alert queue, and the
expected loss an audit of it averts."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs

# Declares Transaction.predictions, the GNN scores the alert score reads.
from . import fraud_classifier  # noqa: F401
from .schema import Transaction, model

# Alert-score mixing weights: final score = ALPHA * is_flagged_fraud + (1-ALPHA) * GNN prob
ALPHA_FLAG = 0.3

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

# The alert queue order: highest alert score first, ties broken by the lower
# transaction id.
AuditCandidate.alert_rank = model.Property(f"{AuditCandidate} has {Integer:alert_rank}")
model.define(AuditCandidate.alert_rank(
    aggs.rank(aggs.desc(AuditCandidate.alert_score), aggs.asc(AuditCandidate.transaction_id))
))

# Expected loss an audit averts: the alert score times the amount at stake.
AuditCandidate.expected_loss = model.Property(f"{AuditCandidate} has {Float:expected_loss}")
model.define(AuditCandidate.expected_loss(
    AuditCandidate.alert_score * Transaction.amount
)).where(Transaction.transaction_id == AuditCandidate.transaction_id)
