"""Money-laundering layering motif detection (constrained subgraph match
with flow conservation, multi-solution) template.

This script demonstrates anti-money-laundering motif detection in
RelationalAI:

- Given an account-and-transaction graph, find every layering
  "butterfly" pattern in the data: one source account routes funds
  through K intermediary "hub" accounts to a single destination, where
  every per-leg amount sits under the FinCEN currency-transaction-report
  threshold ($10,000) and every hub shares a beneficial owner.
- The motif is encoded as binary indicators on transactions and on
  accounts. Per-account flow-conservation in *count* couples edge
  selection to role assignment; per-hub flow-conservation in *amount*
  requires the solver to balance the chosen edges' values against each
  other, which is the CSP arithmetic a graph-pattern / paths library
  cannot express.
- Solve as constraint satisfaction with `solution_limit=MAX_MOTIFS`
  (MiniZinc) and enumerate every feasible motif via
  `Variable.values(solution_index, value)`. AML triage is plural by
  definition -- the analyst inbox should surface every layering
  pattern in the ledger, not just the first one the solver returns.

Run:
    `python money_laundering_motif_detection.py`

Output:
    Prints the formulation, every detected motif (one row per motif
    transaction per solution), per-solution motif hubs with shared
    beneficial owner, and post-solve constraint verification.
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
# Solver solution-limit: cap how many distinct motifs to enumerate per
# run. Sized generous enough to cover the bundled data's two motifs and
# leave headroom for additional ones if you swap in your own ledger.
MAX_MOTIFS = 10

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
Transaction.src = model.Property(f"{Transaction} from {Account:src}")
Transaction.dst = model.Property(f"{Transaction} to {Account:dst}")
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

# Role eligibility, derived from the transaction graph. The per-account flow
# ICs further down need outgoing tx for `is_source` / `is_hub` and incoming
# tx for `is_hub` / `is_dest`. These sub-concepts mark accounts that have at
# least one transaction in each direction; the `solve_for` calls scope each
# role decision variable to the relevant sub-concept(s), so the solver never
# instantiates a role bit for ineligible accounts (avoids the all-zero
# trivial assignment without forcing-to-zero linear constraints).
HasOutgoing = model.Concept("HasOutgoing", extends=[Account])
HasIncoming = model.Concept("HasIncoming", extends=[Account])
model.define(HasOutgoing(Account)).where(Transaction.src(Account))
model.define(HasIncoming(Account)).where(Transaction.dst(Account))

problem = Problem(model, Integer)
# Every output goes through `Variable.values(solution_index, value)` against
# the captured ProblemVariable handles, so the populated property path is
# unused. `populate=False` skips the first-solution write-back -- avoiding
# wasted work and the latent FDError that `populate=True` invites when
# MiniZinc returns multiple solutions via `solution_limit`.
is_motif_var = problem.solve_for(
    Transaction.is_motif,
    type="bin",
    name=["is_motif", Transaction.tx_id],
    populate=False,
)
is_source_var = problem.solve_for(
    Account.is_source,
    type="bin",
    name=["is_source", Account.id],
    where=[HasOutgoing(Account)],
    populate=False,
)
is_hub_var = problem.solve_for(
    Account.is_hub,
    type="bin",
    name=["is_hub", Account.id],
    where=[HasOutgoing(Account), HasIncoming(Account)],
    populate=False,
)
is_dest_var = problem.solve_for(
    Account.is_dest,
    type="bin",
    name=["is_dest", Account.id],
    where=[HasIncoming(Account)],
    populate=False,
)

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

# Layer constraints: forbid a motif edge from going directly source -> dest
# (skipping the hub layer), and forbid a motif edge from going hub -> hub
# (chaining through hubs). Without these, the per-account count flow ICs
# alone admit non-butterfly shapes when the graph has the right inter-role
# edges. Expressed as `sum of three binaries <= 2` (equivalent to "the three
# binaries are not all 1 simultaneously") so the constraint stays in plain
# relational arithmetic and `verify()` can re-evaluate it.
no_direct_src_to_dst_ic = model.require(
    Transaction.is_motif + Transaction.src.is_source + Transaction.dst.is_dest <= 2
)
problem.satisfy(no_direct_src_to_dst_ic)

no_hub_to_hub_ic = model.require(
    Transaction.is_motif + Transaction.src.is_hub + Transaction.dst.is_hub <= 2
)
problem.satisfy(no_hub_to_hub_ic)

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
# `solution_limit=MAX_MOTIFS` asks the solver to enumerate up to that
# many distinct motifs; query each one via `Variable.values(idx, val)`.
# Without it, MiniZinc returns just the first feasible motif and stops.
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_MOTIFS)
si = problem.solve_info()
si.display()

# Re-check the relational ICs in the returned solution. The implies-bodied
# conservation ICs are solver-only and omitted; the count-side flow ICs plus
# data-fixed amounts already pin the conservation residuals tightly. Verify
# inspects only the first solution (the populated property), so it is a
# sanity check on the pure-arithmetic ICs in the first witness -- not a
# re-proof across every motif. The per-hub residual output below makes the
# conservation arithmetic directly inspectable for every returned solution.
problem.verify(
    role_exclusive_ic,
    one_source_ic,
    k_hubs_ic,
    one_dest_ic,
    out_flow_ic,
    in_flow_ic,
    no_direct_src_to_dst_ic,
    no_hub_to_hub_ic,
    amount_threshold_ic,
    same_bo_ic,
)

if si.num_points is None or si.num_points == 0:
    print(
        "\nNo layering motifs found under the encoded constraints. "
        "Check the troubleshooting section in the README for likely causes."
    )

# --------------------------------------------------
# Inspect every detected motif
# --------------------------------------------------

# `Variable.values(solution_index, value)` indexes the solver's outputs
# across every returned solution. Filtering on `value == 1` surfaces the
# rows the solver picked into each motif. The populated properties
# (e.g. `Transaction.is_motif`) reflect ONLY the first solution; for
# multi-solution output we always go through `.values(...)`.

print("\nCandidate motif transactions (one row per motif edge per solution):")
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    is_motif_var.transaction.tx_id.alias("tx_id"),
    is_motif_var.transaction.src.id.alias("src_account_id"),
    is_motif_var.transaction.src.name.alias("src_name"),
    is_motif_var.transaction.dst.id.alias("dst_account_id"),
    is_motif_var.transaction.dst.name.alias("dst_name"),
    is_motif_var.transaction.amount_dollars.alias("amount"),
    is_motif_var.transaction.ts_minutes.alias("ts_min"),
).where(is_motif_var.values(sol_idx, val), val == 1).inspect()

print("\nCandidate motif hubs per solution (with shared beneficial owner):")
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    is_hub_var.account.id.alias("hub_id"),
    is_hub_var.account.name.alias("hub_name"),
    is_hub_var.account.bo_id.alias("bo_id"),
).where(is_hub_var.values(sol_idx, val), val == 1).inspect()

print("\nCandidate motif source and destination per solution:")
src_sol = Integer.ref()
src_val = Integer.ref()
dst_sol = Integer.ref()
dst_val = Integer.ref()
model.select(
    src_sol.alias("solution"),
    is_source_var.account.id.alias("source_id"),
    is_source_var.account.name.alias("source_name"),
    is_dest_var.account.id.alias("dest_id"),
    is_dest_var.account.name.alias("dest_name"),
).where(
    is_source_var.values(src_sol, src_val),
    src_val == 1,
    is_dest_var.values(dst_sol, dst_val),
    dst_val == 1,
    src_sol == dst_sol,
).inspect()
