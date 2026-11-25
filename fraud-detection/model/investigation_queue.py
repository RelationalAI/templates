"""Investigation queue: each transaction's audit cost, the investigator-budget MILP that picks the
audits, and the optimized and naive audit queues the report compares."""

from relationalai.semantics import Float, Integer, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .alert_scores import AuditCandidate
from .schema import Account, Transaction, model

# Each audit consumes hours proportional to transaction size: an audit of a
# transaction over the threshold takes deeper forensic work.
LARGE_AMOUNT_THRESHOLD = 1_000_000.0
SMALL_AUDIT_COST_HOURS = 1.0  # audit of a transaction <= $1M
LARGE_AUDIT_COST_HOURS = 5.0  # audit of a transaction > $1M

# Prescriptive phase: investigator-hours budget + per-audit cost model.
# `Transaction.audit_cost` carries the hours each audit takes. This makes the
# MILP a real knapsack problem: a ranker sorting by alert_score alone ignores
# the cost side and over-spends.
AUDIT_BUDGET_HOURS = 80.0  # total investigator hours available
PER_ACCOUNT_CAP = 1  # at most 1 audit per receiver account (avoid flooding)

model.where(Transaction.amount > LARGE_AMOUNT_THRESHOLD).define(
    Transaction.audit_cost(LARGE_AUDIT_COST_HOURS)
)
model.where(Transaction.amount <= LARGE_AMOUNT_THRESHOLD).define(
    Transaction.audit_cost(SMALL_AUDIT_COST_HOURS)
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
# Ranking by alert_score alone is suboptimal here: it ignores both the amount
# at stake and the hours each audit takes.
sel_obj = Float.ref()
Cand_obj = AuditCandidate.ref()
problem.maximize(sum(
    Cand_obj.expected_loss * sel_obj
).where(
    Cand_obj.x_audit(sel_obj),
))

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=120)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"fraud audit solve status is {String:status}")
SolveObjective = model.Relationship(f"fraud audit objective is {Float:objective}")
model.define(SolveStatus(problem.termination_status()), SolveObjective(problem.objective_value()))

# --------------------------------------------------
# Audit queues: the MILP's selection and a naive sort-and-take baseline
# --------------------------------------------------
# The naive queue takes candidates in alert-queue order, ignoring audit costs
# and the per-receiver cap, for as long as their cumulative audit hours fit the
# same budget.
AuditCandidate.naive_cumulative_hours = model.Property(
    f"{AuditCandidate} has {Float:naive_cumulative_hours}")
model.define(AuditCandidate.naive_cumulative_hours(
    aggs.cumsum_asc(AuditCandidate.alert_rank, Transaction.audit_cost)
)).where(Transaction.transaction_id == AuditCandidate.transaction_id)

# One queue per strategy. Values computed from the solution live on AuditQueue,
# not AuditCandidate: such a property on the concept the solve reads leaves the
# solution empty after the first refresh.
AuditQueue = model.Concept("AuditQueue", identify_by={"strategy": String})
AuditQueue.audits = model.Relationship(f"{AuditQueue} audits {AuditCandidate}")
model.define(AuditQueue.new(strategy="optimized"), AuditQueue.new(strategy="naive"))
_queue = AuditQueue.ref()
model.where(_queue.strategy == "optimized", AuditCandidate.x_audit > 0.5).define(
    _queue.audits(AuditCandidate)
)
model.where(
    _queue.strategy == "naive",
    AuditCandidate.naive_cumulative_hours <= AUDIT_BUDGET_HOURS,
).define(_queue.audits(AuditCandidate))

# Each queue's size, investigator hours, and expected loss captured (zero for
# an empty queue), and its audits per transaction type.
AuditQueue.n_audits = model.Property(f"{AuditQueue} holds {Integer:n_audits} audits")
AuditQueue.hours_used = model.Property(f"{AuditQueue} uses {Float:hours_used} hours")
AuditQueue.captured_loss = model.Property(f"{AuditQueue} captures {Float:captured_loss}")
AuditQueue.audits_by_type = model.Relationship(
    f"{AuditQueue} holds {Integer:n_audits} audits of type {String:trans_type}")
_queued = (
    AuditQueue.audits(AuditCandidate),
    Transaction.transaction_id == AuditCandidate.transaction_id,
)
model.define(
    AuditQueue.n_audits(count(AuditCandidate).per(AuditQueue).where(*_queued) | 0),
    AuditQueue.hours_used(
        sum(AuditCandidate, Transaction.audit_cost).per(AuditQueue).where(*_queued) | 0.0
    ),
    AuditQueue.captured_loss(
        sum(AuditCandidate, AuditCandidate.expected_loss).per(AuditQueue).where(*_queued) | 0.0
    ),
)
_trans_type = String.ref()
model.where(*_queued, Transaction.trans_type == _trans_type).define(AuditQueue.audits_by_type(
    count(AuditCandidate).per(AuditQueue, _trans_type), _trans_type
))

# How much more expected loss the MILP captures than the naive queue.
AuditUplift = model.Relationship(f"the MILP captures {Float:uplift} more than the naive queue")
_objective = Float.ref()
_naive = AuditQueue.ref()
model.where(SolveObjective(_objective), _naive.strategy == "naive").define(
    AuditUplift(_objective - _naive.captured_loss)
)
