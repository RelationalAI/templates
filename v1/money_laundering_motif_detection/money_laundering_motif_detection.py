"""Money-laundering smurfing motif detection (constrained subgraph match)
template.

This script demonstrates anti-money-laundering motif detection in
RelationalAI:

- Given an account-and-transaction graph (data), find a "smurfing fan-in"
  subgraph: K intermediary "smurf" accounts each sending one transaction
  under the FinCEN reporting threshold to a single destination account,
  all within a tight time window, where every smurf shares a beneficial
  owner.
- The motif is encoded as binary indicators on transactions and on
  accounts; flow-conservation constraints over the directed graph couple
  edge-selection to role-assignment, so the solver is forced to pick a
  structurally valid pattern.
- Solve as constraint satisfaction (MiniZinc / Chuffed) and inspect the
  detected motif.

Modeling approach:
- Three binary decision streams: ``Transaction.is_motif`` (which edges
  are part of the motif), ``Account.is_smurf`` and ``Account.is_dest``
  (which accounts play which role).
- Per-account flow conservation over the directed transaction graph
  drives structure: each smurf has exactly one outgoing motif edge,
  the destination has exactly K incoming motif edges. These linear
  ICs are re-evaluated by ``problem.verify()``.
- Filter-style amount and time-window predicates are written as
  data-side ``where`` filters that exclude offending rows or pairs,
  then enforce a sum-bound on the affected decisions. Amounts never
  need to be aggregated across decisions, so the template stays
  CSP-pure (no LP/MIP arithmetic on decisions).
- The "same beneficial owner" cluster filter is a pairwise constraint
  blocking any two smurfs from coming from different owners.

Run:
    `python money_laundering_motif_detection.py`

Output:
    Prints the formulation, the detected motif transactions, the role
    assignment (which account is the destination, which are smurfs),
    and post-solve constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# A FinCEN currency-transaction-report (CTR) is filed for cash transactions
# >= $10,000; smurfs split deposits into amounts that stay under the
# threshold. K = 3 is the smallest count that's clearly a fan-in pattern
# rather than a direct payment.
K = 3
AMOUNT_THRESHOLD_DOLLARS = 10_000
TIME_WINDOW_MINUTES = 30

model = Model("money_laundering_motif_detection")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: bank account
Account = model.Concept("Account", identify_by={"id": Integer})
Account.name = model.Property(f"{Account} has {String:name}")
Account.bo_id = model.Property(f"{Account} owned by {Integer:bo_id}")
accounts_csv = read_csv(data_dir / "accounts.csv")
model.define(Account.new(model.data(accounts_csv).to_schema()))

# Concept: transaction (a directed edge in the graph)
Transaction = model.Concept("Transaction", identify_by={"tx_id": Integer})
Transaction.src = model.Relationship(f"{Transaction} from {Account:src}")
Transaction.dst = model.Relationship(f"{Transaction} to {Account:dst}")
Transaction.amount_dollars = model.Property(f"{Transaction} has {Integer:amount_dollars}")
Transaction.ts_minutes = model.Property(f"{Transaction} occurs at {Integer:ts_minutes}")
tx_csv = read_csv(data_dir / "transactions.csv")
tx_data = model.data(tx_csv)
model.define(
    Transaction.new(tx_id=tx_data.tx_id),
)
model.define(Transaction.amount_dollars(tx_data.amount_dollars)).where(
    Transaction.tx_id(tx_data.tx_id)
)
model.define(Transaction.ts_minutes(tx_data.ts_minutes)).where(Transaction.tx_id(tx_data.tx_id))
model.define(Transaction.src(Account)).where(
    Transaction.tx_id(tx_data.tx_id),
    Account.id(tx_data.src_id),
)
model.define(Transaction.dst(Account)).where(
    Transaction.tx_id(tx_data.tx_id),
    Account.id(tx_data.dst_id),
)

# --------------------------------------------------
# Decision-valued properties
# --------------------------------------------------

Transaction.is_motif = model.Property(f"{Transaction} is in motif if {Integer:is_motif}")
Account.is_smurf = model.Property(f"{Account} is smurf if {Integer:is_smurf}")
Account.is_dest = model.Property(f"{Account} is dest if {Integer:is_dest}")

problem = Problem(model, Integer)
problem.solve_for(Transaction.is_motif, type="bin", name=["is_motif", Transaction.tx_id])
problem.solve_for(Account.is_smurf, type="bin", name=["is_smurf", Account.id])
problem.solve_for(Account.is_dest, type="bin", name=["is_dest", Account.id])

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# An account plays at most one motif role.
role_exclusive_ic = model.require(Account.is_smurf + Account.is_dest <= 1)
problem.satisfy(role_exclusive_ic)

# Exactly one destination.
one_dest_ic = model.require(sum(Account.is_dest) == 1)
problem.satisfy(one_dest_ic)

# Exactly K smurfs.
k_smurfs_ic = model.require(sum(Account.is_smurf) == K)
problem.satisfy(k_smurfs_ic)

# Per-account out-flow over motif edges = is_smurf (smurfs send 1 motif tx,
# others send 0). Sums Transaction.is_motif grouped by Transaction.src,
# joined to the matching Account so the comparison can name Account.is_smurf.
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == Account.is_smurf
)
problem.satisfy(out_flow_ic)

# Per-account in-flow over motif edges = K * is_dest (the destination
# receives K motif tx, all others receive 0).
in_flow_ic = model.where(Transaction.dst == Account).require(
    sum(Transaction.is_motif).per(Transaction.dst) == K * Account.is_dest
)
problem.satisfy(in_flow_ic)

# Amount filter: any over-threshold transaction is excluded from the motif.
# Filter framing (per plan): the threshold is a per-tx predicate, never
# an aggregate over decisions. The where clause filters at relational time
# to over-threshold rows; the constraint forces is_motif = 0 on those.
amount_threshold_ic = model.where(Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS).require(
    Transaction.is_motif == 0
)
problem.satisfy(amount_threshold_ic)

# Time window: motif transactions must fall inside one TIME_WINDOW_MINUTES
# span. Iterate over all transaction pairs whose timestamps differ by more
# than the window; for any such pair, at most one can be in the motif.
T1 = Transaction.ref()
T2 = Transaction.ref()
time_window_ic = model.where(
    T1.ts_minutes + TIME_WINDOW_MINUTES < T2.ts_minutes,
).require(T1.is_motif + T2.is_motif <= 1)
problem.satisfy(time_window_ic)

# Same beneficial owner across smurfs: any two accounts with different
# beneficial owners cannot both be smurfs, so the cluster reads as a
# single laundering ring rather than scattered low-amount transactors.
S1 = Account.ref()
S2 = Account.ref()
same_bo_ic = model.where(
    S1.id < S2.id,
    S1.bo_id != S2.bo_id,
).require(S1.is_smurf + S2.is_smurf <= 1)
problem.satisfy(same_bo_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Re-check every constraint in the returned solution -- all ICs are pure
# relational arithmetic (where-filtered linear sums on integer decisions),
# so the engine can re-evaluate them.
problem.verify(
    role_exclusive_ic,
    one_dest_ic,
    k_smurfs_ic,
    out_flow_ic,
    in_flow_ic,
    amount_threshold_ic,
    time_window_ic,
    same_bo_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect the detected motif
# --------------------------------------------------

print("\nDetected smurfing motif (one row per motif transaction):")
model.select(
    Transaction.tx_id.alias("tx_id"),
    Transaction.src.id.alias("src_account_id"),
    Transaction.src.name.alias("src_name"),
    Transaction.dst.id.alias("dst_account_id"),
    Transaction.dst.name.alias("dst_name"),
    Transaction.amount_dollars.alias("amount"),
    Transaction.ts_minutes.alias("ts_min"),
).where(Transaction.is_motif == 1).inspect()

print("\nMotif accounts (roles and beneficial owner):")
model.select(
    Account.id.alias("account_id"),
    Account.name.alias("name"),
    Account.bo_id.alias("bo_id"),
    Account.is_dest.alias("is_dest"),
    Account.is_smurf.alias("is_smurf"),
).where(Account.is_smurf + Account.is_dest >= 1).inspect()
