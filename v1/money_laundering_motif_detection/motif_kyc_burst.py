"""KYC-burst motif with cardinality constraint over a chosen subset.

CSP technique demonstrated: cardinality constraint over a decision-selected
vertex subset. The solver picks N source accounts whose deposits to a single
target destination must:
  - have at least RETAIL_FLOOR retail-tier accounts among the chosen
  - all transact within a tight time window of each other
  - each stay below the FinCEN $10K currency-transaction-report threshold

The cardinality constraint is over the *chosen* subset of accounts.
Rules can label each account's KYC tier; only CSP enforces the count
*over the selected subset*. A graph or paths library has no way to
express "≥ 4 of the K accounts I'm picking are retail-tier."

Topology: AMLworld fan-in pattern (Altman et al., NeurIPS 2023) with the
KYC-tier-diversity profile that AML practitioner literature flags as a
smurf-army signature -- launderers recruit a tier-diverse cohort of
mules to defeat single-tier-pattern alerts ([Tookitaki AML guidance](
https://www.tookitaki.com/compliance-hub/smurfing-structuring-aml-detection-reporting)).

Run:  python motif_kyc_burst.py
"""

from model_setup import AMOUNT_THRESHOLD_DOLLARS, create_model
from relationalai.semantics import Integer, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# Target destination receiving the coordinated burst. Bundled data plants
# Continental Settlements LLC (id 51).
BURST_TARGET_DESTINATION_ID = 51
# Time-window size: the burst must complete within this many minutes.
BURST_WINDOW_MINUTES = 60
# Cohort size: exactly N accounts in the burst.
N_BURST = 5
# KYC-mix distribution: a launder-grade burst recruits at least RETAIL_FLOOR
# retail-tier accounts within the cohort. The cardinality is over the
# *selected* subset, so rules alone can't enforce it -- they can label each
# account's tier but not bind a count constraint to the K-subset the solver
# picks.
RETAIL_FLOOR = 4
# Solver solution-limit: enumerate up to this many distinct burst cohorts.
MAX_BURST_MOTIFS = 5

model, Account, Transaction = create_model()

# Decision-valued properties for the KYC-burst motif.
Account.is_burst = model.Property(f"{Account} is burst if {Integer:is_burst}")
Transaction.is_burst_tx = model.Property(f"{Transaction} is burst tx if {Integer:is_burst_tx}")

problem = Problem(model, Integer)

# Full-Account scope for is_burst and full-Transaction scope for is_burst_tx
# -- not narrowed via `where=[...]` on the `solve_for(...)` call. Tight scoping
# leaves the variable undefined for outside accounts and the per-account flow
# constraints get silently dropped, letting the solver place burst-tx into
# accounts that aren't actually in the burst cohort.
is_burst_var = problem.solve_for(
    Account.is_burst,
    type="bin",
    name=["is_burst", Account.id],
    populate=False,
)
is_burst_tx_var = problem.solve_for(
    Transaction.is_burst_tx,
    type="bin",
    name=["is_burst_tx", Transaction.tx_id],
    populate=False,
)

# Force is_burst_tx = 0 on every transaction NOT going to the burst target.
not_target_tx_ic = model.where(Transaction.dst.id != BURST_TARGET_DESTINATION_ID).require(
    Transaction.is_burst_tx == 0
)
problem.satisfy(not_target_tx_ic)

# Exactly N accounts in the burst cohort.
n_burst_ic = model.require(sum(Account.is_burst) == N_BURST)
problem.satisfy(n_burst_ic)

# Per-account flow link: a chosen burst account contributes exactly one
# burst-tx; a non-chosen account contributes none. The where matches any
# (transaction, account) pair where the account is the source -- we
# deliberately do NOT scope this to dst==target. Tighter scoping would
# leave the constraint un-instantiated for accounts whose outgoing edges
# don't reach the target, letting the solver freely set their is_burst
# bit and pick a fake cohort that has no actual transactions to the
# target. The broader scope plus `not_target_tx_ic` (which forces
# is_burst_tx=0 on non-target tx) gives the right semantics: sum of an
# account's is_burst_tx equals its is_burst, where the only tx that can
# contribute are those going to the target.
out_burst_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_burst_tx).per(Transaction.src) == Account.is_burst
)
problem.satisfy(out_burst_ic)

# Flow consistency: total burst-tx count equals total burst-account count.
# This catches the edge case where an account with NO outgoing transactions
# at all (the burst target itself, or any pure-sink account) gets picked
# into the cohort -- the per-account flow IC isn't instantiated for those
# accounts so is_burst is otherwise free for them. Forcing the global sums
# to match means each chosen account must contribute exactly one burst-tx.
flow_consistency_ic = model.require(sum(Transaction.is_burst_tx) == sum(Account.is_burst))
problem.satisfy(flow_consistency_ic)

# CSP-required piece #1: retail-tier floor over the chosen subset. At least
# RETAIL_FLOOR of the N chosen accounts must have kyc_tier == "retail". The
# cardinality is over the *selected* set -- rules can label each account's
# tier but can't bind a count constraint to "the K-subset the solver picks."
retail_floor_ic = model.require(
    sum(Account.is_burst).where(Account.kyc_tier == "retail") >= RETAIL_FLOOR
)
problem.satisfy(retail_floor_ic)

# CSP-required piece #2: time window across the chosen burst-tx. For any
# pair of transactions to the target whose timestamps differ by more than
# the window, both can't be burst-tx. The asymmetric
# `T2.ts_minutes - Transaction.ts_minutes > WINDOW` predicate handles each
# unordered pair exactly once -- the (a, b) and (b, a) iteration sees only
# one side of the timestamp difference satisfy the > WINDOW threshold, so
# no extra tx_id ordering is needed (and adding one would silently miss
# pairs where tx_id order disagrees with ts_minutes order).
T2 = Transaction.ref()
window_ic = model.where(
    Transaction.dst.id == BURST_TARGET_DESTINATION_ID,
    T2.dst.id == BURST_TARGET_DESTINATION_ID,
    T2.ts_minutes - Transaction.ts_minutes > BURST_WINDOW_MINUTES,
).require(Transaction.is_burst_tx + T2.is_burst_tx <= 1)
problem.satisfy(window_ic)

# Amount filter: burst transactions stay sub-threshold to evade CTR filing.
threshold_ic = model.where(
    Transaction.dst.id == BURST_TARGET_DESTINATION_ID,
    Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS,
).require(Transaction.is_burst_tx == 0)
problem.satisfy(threshold_ic)

# Solve and report.
print("\n" + "=" * 70)
print(f"KYC-MIX BURST (fan-in to account id {BURST_TARGET_DESTINATION_ID})")
print("CSP technique: cardinality over chosen subset")
print("=" * 70)
problem.display()
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_BURST_MOTIFS)
si = problem.solve_info()
si.display()

# No `problem.verify(...)` call: `populate=False` on the `solve_for(...)`
# calls above means the decision-variable values are NOT written back to
# the relational `is_burst` / `is_burst_tx` properties. Without those values
# in the relational layer, verify() cannot re-evaluate ICs that reference
# them and prints spurious "Requirements not met" warnings instead of
# doing real verification. The inspect tables below surface the solver's
# choices directly; manual inspection against the IC formulas is the
# verification path here.

status = si.termination_status
motif_count = si.num_points or 0
if status == "INFEASIBLE":
    print(
        "\nResult: no KYC-mix burst cohort exists under the encoded constraints "
        f"for target id {BURST_TARGET_DESTINATION_ID}. The search space was "
        "exhausted with zero feasible cohorts."
    )
elif status == "OPTIMAL":
    print(
        f"\nResult: {motif_count} KYC-mix burst cohort(s) found and search exhausted "
        "(no further cohorts exist under the encoded constraints)."
    )
elif status == "SOLUTION_LIMIT":
    print(
        f"\nResult: {motif_count} KYC-mix burst cohort(s) found; "
        f"hit MAX_BURST_MOTIFS={MAX_BURST_MOTIFS}. "
        "More may exist -- raise the limit to enumerate further."
    )
else:
    print(
        f"\nResult: search returned status={status} with {motif_count} cohort(s); "
        "did not finish. Raise time_limit_sec or check the README troubleshooting."
    )

print("\nKYC-burst: chosen burst-tx per solution:")
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    is_burst_tx_var.transaction.tx_id.alias("tx_id"),
    is_burst_tx_var.transaction.src.id.alias("src_account_id"),
    is_burst_tx_var.transaction.src.name.alias("src_name"),
    is_burst_tx_var.transaction.src.kyc_tier.alias("src_kyc_tier"),
    is_burst_tx_var.transaction.dst.name.alias("dst_name"),
    is_burst_tx_var.transaction.amount_dollars.alias("amount"),
    is_burst_tx_var.transaction.ts_minutes.alias("ts_min"),
).where(is_burst_tx_var.values(sol_idx, val), val == 1).inspect()

print("\nKYC-burst: chosen burst accounts per solution (with KYC tier and jurisdiction):")
model.select(
    sol_idx.alias("solution"),
    is_burst_var.account.id.alias("burst_id"),
    is_burst_var.account.name.alias("burst_name"),
    is_burst_var.account.kyc_tier.alias("kyc_tier"),
    is_burst_var.account.jurisdiction.alias("jurisdiction"),
    is_burst_var.account.bo_id.alias("bo_id"),
).where(is_burst_var.values(sol_idx, val), val == 1).inspect()
