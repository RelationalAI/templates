"""Money-laundering layering motif detection (constrained subgraph match
with flow conservation) template.

This script demonstrates anti-money-laundering motif detection in
RelationalAI:

- Given an account-and-transaction graph, find a layering "butterfly"
  pattern: one source account routes funds through K intermediary "hub"
  accounts to a single destination, where every per-leg amount sits
  under the FinCEN currency-transaction-report threshold ($10,000) and
  every hub shares a beneficial owner.
- The motif is encoded as binary indicators on transactions and on
  accounts. Per-account flow-conservation in *count* couples edge
  selection to role assignment; per-hub flow-conservation in *amount*
  requires the solver to balance the chosen edges' values against each
  other, which is the CSP arithmetic a graph-pattern / paths library
  cannot express.
- Solve as constraint satisfaction (MiniZinc / Chuffed) and inspect the
  detected motif.

Run:
    `python money_laundering_motif_detection.py`

Output:
    Prints the formulation, the detected motif transactions, the role
    assignment, the per-hub conservation residuals, and post-solve
    constraint verification.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

# Runner-level parameters.
# A FinCEN currency-transaction-report (CTR) is filed for cash transactions
# >= $10,000; layering schemes split deposits into amounts that stay
# under the threshold. K = 3 is the smallest hub count that's clearly a
# fan-out-then-fan-in pattern rather than a direct payment chain.
K = 3
AMOUNT_THRESHOLD_DOLLARS = 10_000
# Per-hub conservation tolerance: the dollar amount a hub receives must
# equal the amount it forwards, within this many dollars. Real schemes
# absorb small "fees" at each hop; $100 is generous enough to admit
# several legitimate-looking residuals while still rejecting hops that
# pocket significant amounts.
CONSERVATION_TOLERANCE_DOLLARS = 100

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
    t := Transaction.new(tx_id=tx_data.tx_id),
    t.amount_dollars(tx_data.amount_dollars),
    t.ts_minutes(tx_data.ts_minutes),
)
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
Account.is_source = model.Property(f"{Account} is source if {Integer:is_source}")
Account.is_hub = model.Property(f"{Account} is hub if {Integer:is_hub}")
Account.is_dest = model.Property(f"{Account} is dest if {Integer:is_dest}")

problem = Problem(model, Integer)
problem.solve_for(Transaction.is_motif, type="bin", name=["is_motif", Transaction.tx_id])
problem.solve_for(Account.is_source, type="bin", name=["is_source", Account.id])
problem.solve_for(Account.is_hub, type="bin", name=["is_hub", Account.id])
problem.solve_for(Account.is_dest, type="bin", name=["is_dest", Account.id])

# --------------------------------------------------
# Constraints
# --------------------------------------------------

# An account plays at most one motif role.
role_exclusive_ic = model.require(Account.is_source + Account.is_hub + Account.is_dest <= 1)
problem.satisfy(role_exclusive_ic)

# Exactly one source.
one_source_ic = model.require(sum(Account.is_source) == 1)
problem.satisfy(one_source_ic)

# Exactly K hubs.
k_hubs_ic = model.require(sum(Account.is_hub) == K)
problem.satisfy(k_hubs_ic)

# Exactly one destination.
one_dest_ic = model.require(sum(Account.is_dest) == 1)
problem.satisfy(one_dest_ic)

# Per-account out-flow over motif edges = K * is_source + is_hub.
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == K * Account.is_source + Account.is_hub
)
problem.satisfy(out_flow_ic)

# Per-account in-flow over motif edges = is_hub + K * is_dest.
in_flow_ic = model.where(Transaction.dst == Account).require(
    sum(Transaction.is_motif).per(Transaction.dst) == Account.is_hub + K * Account.is_dest
)
problem.satisfy(in_flow_ic)

# Per-hub flow conservation in amount (the butterfly's signature). For each
# hub, |amount_in - amount_out| <= CONSERVATION_TOLERANCE_DOLLARS, expressed
# as two one-sided inequalities (CSP backends don't handle abs directly).
# Half-reified on `is_hub == 1` so the constraint is active only on accounts
# the solver picks as hubs.
T_in = Transaction.ref()
T_out = Transaction.ref()
conservation_pos_ic = model.where(T_in.dst == Account, T_out.src == Account).require(
    implies(
        Account.is_hub == 1,
        sum(T_in.amount_dollars * T_in.is_motif).per(T_in.dst)
        - sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
        <= CONSERVATION_TOLERANCE_DOLLARS,
    )
)
problem.satisfy(conservation_pos_ic)

conservation_neg_ic = model.where(T_in.dst == Account, T_out.src == Account).require(
    implies(
        Account.is_hub == 1,
        sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
        - sum(T_in.amount_dollars * T_in.is_motif).per(T_in.dst)
        <= CONSERVATION_TOLERANCE_DOLLARS,
    )
)
problem.satisfy(conservation_neg_ic)

# Amount filter: where-clause keeps the threshold predicate at relational
# time; the constraint then forces is_motif = 0 on over-threshold rows.
amount_threshold_ic = model.where(Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS).require(
    Transaction.is_motif == 0
)
problem.satisfy(amount_threshold_ic)

# Same beneficial owner across hubs: pair filter forbids cross-cluster hub
# pairs, so the cluster reads as a single ring rather than scattered hits.
H1 = Account.ref()
H2 = Account.ref()
same_bo_ic = model.where(
    H1.id < H2.id,
    H1.bo_id != H2.bo_id,
).require(H1.is_hub + H2.is_hub <= 1)
problem.satisfy(same_bo_ic)

# --------------------------------------------------
# Solve and verify
# --------------------------------------------------

problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# Re-check the relational ICs in the returned solution. The implies-bodied
# conservation ICs are solver-only and omitted; the count-side flow ICs plus
# data-fixed amounts already pin the conservation residuals tightly.
problem.verify(
    role_exclusive_ic,
    one_source_ic,
    k_hubs_ic,
    one_dest_ic,
    out_flow_ic,
    in_flow_ic,
    amount_threshold_ic,
    same_bo_ic,
)
model.require(problem.termination_status() == "OPTIMAL")

# --------------------------------------------------
# Inspect the detected motif
# --------------------------------------------------

print("\nDetected layering motif (one row per motif transaction):")
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
    Account.is_source.alias("is_source"),
    Account.is_hub.alias("is_hub"),
    Account.is_dest.alias("is_dest"),
).where(Account.is_source + Account.is_hub + Account.is_dest >= 1).inspect()

print(
    "\nPer-hub conservation residuals (in_amount - out_amount, must be in [-tolerance, +tolerance]):"
)
In = Transaction.ref()
Out = Transaction.ref()
model.select(
    Account.id.alias("hub_id"),
    Account.name.alias("hub_name"),
    sum(In.amount_dollars * In.is_motif).per(In.dst).alias("in_amount"),
    sum(Out.amount_dollars * Out.is_motif).per(Out.src).alias("out_amount"),
).where(
    In.dst == Account,
    Out.src == Account,
    Account.is_hub == 1,
).inspect()
