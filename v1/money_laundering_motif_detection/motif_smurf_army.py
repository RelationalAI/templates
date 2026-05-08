"""Smurf-army motif with pairwise distinct beneficial owners.

CSP technique demonstrated: pairwise constraints over a decision-selected
vertex subset, plus all-different on a vertex property. The solver picks
N source accounts whose deposits to a single target destination must:
  - have pairwise-distinct beneficial owners (no two chosen smurfs share
    a `bo_id`)
  - sum to a known launder target within tolerance
  - all transact within a tight time window of each other
  - each stay below the FinCEN $10K currency-transaction-report threshold

The pairwise constraints are over the *chosen* subset of accounts, which
is the part rules / paths / graph reasoning can't enforce: pre-filtered
pair tables can't bind to "the K-subset the solver itself picks." The
sum-equals-target arithmetic adds a second CSP-required dimension --
no single edge or walk has the information the constraint needs.

Topology: AMLworld fan-in pattern (Altman et al., NeurIPS 2023) +
FATF / FinCEN structuring typology (31 CFR § 1010.311). The launderer
recruits N separate identities with distinct beneficial owners to break
a known total ($SMURF_TARGET_DOLLARS) into under-threshold deposits all
arriving at the target merchant within a short coordinated burst.

Run:  python motif_smurf_army.py
"""

from model_setup import AMOUNT_THRESHOLD_DOLLARS, create_model
from relationalai.semantics import Integer, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# The target merchant the smurfs deposit into. In production this could be a
# known launder destination from a watchlist; for the demo it's the bundled
# data's planted target ("Pacific Receivables Inc", id 41).
SMURF_TARGET_DESTINATION_ID = 41
# Total launder amount (the smurfs collectively deposit this much).
SMURF_TARGET_DOLLARS = 27_000
# Sum-equals-target tolerance: real launderers absorb tiny rounding fees.
SMURF_TARGET_TOLERANCE_DOLLARS = 100
# Time-window size: the structuring burst must complete within this many
# minutes (max ts - min ts <= window). 60 minutes is tight enough to read as
# coordinated activity rather than independent deposits.
SMURF_WINDOW_MINUTES = 60
# Smurf cohort size: exactly N source accounts contribute to the burst.
N_SMURFS = 5
# Solver solution-limit: enumerate up to this many distinct smurf cohorts.
MAX_SMURF_MOTIFS = 5

model, Account, Transaction = create_model()

# Decision-valued properties for the smurf-army motif.
Account.is_smurf = model.Property(f"{Account} is smurf if {Integer:is_smurf}")
Transaction.is_smurf_tx = model.Property(f"{Transaction} is smurf tx if {Integer:is_smurf_tx}")

problem = Problem(model, Integer)

# Full-Account scope for is_smurf and full-Transaction scope for is_smurf_tx
# -- not narrowed via `where=[...]` on the `solve_for(...)` call. Tight scoping
# leaves the variable undefined for accounts/transactions outside that scope,
# and constraints referencing it get silently dropped from the per-account
# flow ICs. Full-scope decisions are forced to 0 by the constraints below
# for ineligible accounts and non-target transactions.
is_smurf_var = problem.solve_for(
    Account.is_smurf,
    type="bin",
    name=["is_smurf", Account.id],
    populate=False,
)
is_smurf_tx_var = problem.solve_for(
    Transaction.is_smurf_tx,
    type="bin",
    name=["is_smurf_tx", Transaction.tx_id],
    populate=False,
)

# Force is_smurf_tx = 0 on every transaction NOT going to the target merchant.
# Without this, the sum-equals-target constraint below would pick up amounts
# from unrelated transactions to other destinations.
not_target_tx_ic = model.where(Transaction.dst.id != SMURF_TARGET_DESTINATION_ID).require(
    Transaction.is_smurf_tx == 0
)
problem.satisfy(not_target_tx_ic)

# Exactly N smurfs in the cohort.
n_smurfs_ic = model.require(sum(Account.is_smurf) == N_SMURFS)
problem.satisfy(n_smurfs_ic)

# Per-account flow link: a chosen smurf has exactly one smurf-tx to the
# target; a non-smurf has none. The where matches any (transaction,
# account) pair where the account is the source -- we deliberately do NOT
# scope this to dst==target. Tighter scoping would leave the constraint
# un-instantiated for accounts whose outgoing edges don't reach the
# target, letting the solver freely set their is_smurf bit. The broader
# scope plus `not_target_tx_ic` (which forces is_smurf_tx=0 on non-target
# tx) gives the right semantics: sum of an account's is_smurf_tx equals
# its is_smurf, where the only tx that can contribute are those going to
# the target.
out_smurf_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_smurf_tx).per(Transaction.src) == Account.is_smurf
)
problem.satisfy(out_smurf_ic)

# Flow consistency: total smurf-tx count equals total smurf-account count.
# Catches accounts with NO outgoing transactions (the per-account flow IC
# isn't instantiated for them so is_smurf is otherwise free). The sum-
# equals-target constraint below would also detect this in most realistic
# data, but the explicit consistency constraint is cleaner and works even
# when target tolerance is wide.
flow_consistency_ic = model.require(sum(Transaction.is_smurf_tx) == sum(Account.is_smurf))
problem.satisfy(flow_consistency_ic)

# CSP-required piece #1: pairwise-distinct beneficial owners across chosen
# smurfs. The constraint forbids any pair of accounts that share a `bo_id`
# from both being chosen as smurfs simultaneously. Pre-filtered pair tables
# can't bind to "the K-subset the solver picks" -- only this pairwise-over-
# decision-variables formulation does.
S1 = Account.ref()
S2 = Account.ref()
distinct_bo_ic = model.where(S1.id < S2.id, S1.bo_id == S2.bo_id).require(
    S1.is_smurf + S2.is_smurf <= 1
)
problem.satisfy(distinct_bo_ic)

# CSP-required piece #2: sum of selected smurf-tx amounts equals the launder
# target within tolerance. Two one-sided inequalities (CSP backends don't
# handle abs directly).
sum_target_pos_ic = model.require(
    sum(Transaction.amount_dollars * Transaction.is_smurf_tx)
    <= SMURF_TARGET_DOLLARS + SMURF_TARGET_TOLERANCE_DOLLARS
)
problem.satisfy(sum_target_pos_ic)
sum_target_neg_ic = model.require(
    sum(Transaction.amount_dollars * Transaction.is_smurf_tx)
    >= SMURF_TARGET_DOLLARS - SMURF_TARGET_TOLERANCE_DOLLARS
)
problem.satisfy(sum_target_neg_ic)

# CSP-required piece #3: time window across the chosen smurf-tx. For any
# pair of transactions to the target whose timestamps differ by more than
# the window, both can't be smurf-tx. This is also a pairwise-over-decision-
# variables formulation; rules / paths can't bind it to the chosen subset.
T1 = Transaction.ref()
T2 = Transaction.ref()
window_ic = model.where(
    T1.dst.id == SMURF_TARGET_DESTINATION_ID,
    T2.dst.id == SMURF_TARGET_DESTINATION_ID,
    T1.tx_id < T2.tx_id,
    T2.ts_minutes - T1.ts_minutes > SMURF_WINDOW_MINUTES,
).require(T1.is_smurf_tx + T2.is_smurf_tx <= 1)
problem.satisfy(window_ic)

# Amount filter: structuring requires sub-threshold deposits. Push the
# amount comparison to the relational where so the constraint is a pure
# arithmetic bound on the decision variable.
threshold_ic = model.where(
    Transaction.dst.id == SMURF_TARGET_DESTINATION_ID,
    Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS,
).require(Transaction.is_smurf_tx == 0)
problem.satisfy(threshold_ic)

# Solve and report.
print("\n" + "=" * 70)
print(f"SMURF ARMY (fan-in to account id {SMURF_TARGET_DESTINATION_ID})")
print("CSP technique: pairwise distinctness + sum-target over chosen subset")
print("=" * 70)
problem.display()
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_SMURF_MOTIFS)
si = problem.solve_info()
si.display()

problem.verify(
    not_target_tx_ic,
    n_smurfs_ic,
    out_smurf_ic,
    flow_consistency_ic,
    distinct_bo_ic,
    sum_target_pos_ic,
    sum_target_neg_ic,
    window_ic,
    threshold_ic,
)

status = si.termination_status
motif_count = si.num_points or 0
if status == "INFEASIBLE":
    print(
        "\nResult: no smurf-army cohort exists under the encoded constraints "
        f"for target id {SMURF_TARGET_DESTINATION_ID}. The search space was "
        "exhausted with zero feasible cohorts."
    )
elif status == "OPTIMAL":
    print(
        f"\nResult: {motif_count} smurf-army cohort(s) found and search exhausted "
        "(no further cohorts exist under the encoded constraints)."
    )
elif status == "SOLUTION_LIMIT":
    print(
        f"\nResult: {motif_count} smurf-army cohort(s) found; "
        f"hit MAX_SMURF_MOTIFS={MAX_SMURF_MOTIFS}. "
        "More may exist -- raise the limit to enumerate further."
    )
else:
    print(
        f"\nResult: search returned status={status} with {motif_count} cohort(s); "
        "did not finish. Raise time_limit_sec or check the README troubleshooting."
    )

print("\nSmurf army: chosen smurf-tx per solution:")
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    is_smurf_tx_var.transaction.tx_id.alias("tx_id"),
    is_smurf_tx_var.transaction.src.id.alias("src_account_id"),
    is_smurf_tx_var.transaction.src.name.alias("src_name"),
    is_smurf_tx_var.transaction.src.bo_id.alias("src_bo_id"),
    is_smurf_tx_var.transaction.dst.name.alias("dst_name"),
    is_smurf_tx_var.transaction.amount_dollars.alias("amount"),
    is_smurf_tx_var.transaction.ts_minutes.alias("ts_min"),
).where(is_smurf_tx_var.values(sol_idx, val), val == 1).inspect()

print("\nSmurf army: chosen smurf accounts per solution (with distinct BOs and jurisdictions):")
model.select(
    sol_idx.alias("solution"),
    is_smurf_var.account.id.alias("smurf_id"),
    is_smurf_var.account.name.alias("smurf_name"),
    is_smurf_var.account.bo_id.alias("bo_id"),
    is_smurf_var.account.kyc_tier.alias("kyc_tier"),
    is_smurf_var.account.jurisdiction.alias("jurisdiction"),
).where(is_smurf_var.values(sol_idx, val), val == 1).inspect()
