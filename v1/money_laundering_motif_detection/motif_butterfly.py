"""Butterfly / scatter-gather motif with per-hub flow conservation.

CSP technique demonstrated: per-vertex equality of two aggregates over a
decision-selected edge subset. For every account the solver picks as a
hub, sum-of-incoming-motif-amounts equals sum-of-outgoing-motif-amounts
within tolerance. This binds the equality to "the K-subset of edges the
solver picks, where the K accounts the solver assigns as hubs each
individually conserve flow" -- the joint-decision-arithmetic shape that
a graph-pattern matcher or paths library cannot enforce.

Topology: AMLworld scatter-gather pattern (Altman et al., NeurIPS 2023).
A source account fans out to K intermediary "hub" accounts that all
share a beneficial owner, each forwarding their share onward to a
single destination. Every per-leg amount stays under the FinCEN $10K
currency-transaction-report threshold so no leg triggers a CTR filing.

Run:  python motif_butterfly.py
"""

import pandas as pd
from model_setup import AMOUNT_THRESHOLD_DOLLARS, DATA_DIR, create_model
from relationalai.semantics import Integer, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# Runner-level parameters.
# K = 3 is the smallest hub count that's clearly a fan-out-then-fan-in pattern
# rather than a direct payment chain.
K = 3
# Per-hub conservation tolerance: a hub absorbs a small per-hop fee ("dirty")
# but must forward most of the funds. $100 admits realistic small residuals.
CONSERVATION_TOLERANCE_DOLLARS = 100
# Solver solution-limit: cap how many distinct motifs to enumerate per run.
# The bundled data plants exactly two butterflies; raise this when running on
# your own ledger.
MAX_BUTTERFLY_MOTIFS = 10

model, Account, Transaction = create_model()

# Tightest big-M coefficient for the per-hub conservation IC below. The big-M
# form makes that IC active when `is_hub == 1` and vacuous when `is_hub == 0`;
# M needs to bound |sum_in - sum_out| over decision-selected motif edges,
# which is at most the per-account total of incoming or outgoing amounts.
# Compute that from the data and add a small buffer. (We re-read the CSV here
# rather than wire it through `create_model()`'s return -- only butterfly
# needs the post-load aggregation, and the bundled file is small.)
_tx_csv = pd.read_csv(DATA_DIR / "transactions.csv")
CONSERVATION_BIG_M = (
    int(
        max(
            _tx_csv.groupby("dst_id")["amount_dollars"].sum().max(),
            _tx_csv.groupby("src_id")["amount_dollars"].sum().max(),
        )
    )
    + AMOUNT_THRESHOLD_DOLLARS
)

# Decision-valued properties for the butterfly motif.
Transaction.is_motif = model.Property(f"{Transaction} is in motif if {Integer:is_motif}")
Account.is_source = model.Property(f"{Account} is source if {Integer:is_source}")
Account.is_hub = model.Property(f"{Account} is hub if {Integer:is_hub}")
Account.is_dest = model.Property(f"{Account} is dest if {Integer:is_dest}")

problem = Problem(model, Integer)

# Each role decision spans the full Account scope -- not narrowed via
# `where=[...]` on the `solve_for(...)` call. Tighter scoping leaves the
# variable undefined for accounts outside that scope, and constraints that
# reference both an undefined role variable and a defined one are silently
# dropped from the per-account flow ICs -- letting the solver place motif
# edges into accounts that aren't actually hubs or destinations. Full-scope
# decisions are forced to 0 by the role-count and per-account flow ICs below.
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
    populate=False,
)
is_hub_var = problem.solve_for(
    Account.is_hub,
    type="bin",
    name=["is_hub", Account.id],
    populate=False,
)
is_dest_var = problem.solve_for(
    Account.is_dest,
    type="bin",
    name=["is_dest", Account.id],
    populate=False,
)

# An account plays at most one motif role.
role_exclusive_ic = model.require(Account.is_source + Account.is_hub + Account.is_dest <= 1)
problem.satisfy(role_exclusive_ic)

# Exactly one source, K hubs, one destination.
one_source_ic = model.require(sum(Account.is_source) == 1)
problem.satisfy(one_source_ic)
k_hubs_ic = model.require(sum(Account.is_hub) == K)
problem.satisfy(k_hubs_ic)
one_dest_ic = model.require(sum(Account.is_dest) == 1)
problem.satisfy(one_dest_ic)

# Per-account out-flow over motif edges = K * is_source + is_hub.
# Source has K outgoing motif edges; each hub has 1 outgoing motif edge.
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == K * Account.is_source + Account.is_hub
)
problem.satisfy(out_flow_ic)

# Per-account in-flow over motif edges = is_hub + K * is_dest.
# Each hub has 1 incoming motif edge; destination has K incoming motif edges.
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

# Per-hub flow conservation in amount -- the load-bearing CSP IC. For each
# hub, |amount_in - amount_out| <= CONSERVATION_TOLERANCE_DOLLARS, expressed
# as two one-sided inequalities (CSP backends don't handle abs directly)
# in big-M form so the constraint is active when is_hub == 1 and vacuous
# when is_hub == 0:
#   in - out + M * is_hub <= TOL + M
# When is_hub == 1: in - out <= TOL  (active conservation)
# When is_hub == 0: in - out <= TOL + M  (vacuous if M big enough)
# We prefer big-M to a half-reified `implies(is_hub == 1, ...)` because
# half-reification introduces a free Boolean auxiliary per non-hub account
# that MiniZinc treats as part of the search space, returning thousands of
# trivially-distinct solutions for the same role/motif assignment. The big-M
# form has no auxiliary -- enumeration stays clean and the solver exhausts
# after the data's actual motifs.
T_in = Transaction.ref()
T_out = Transaction.ref()
conservation_pos_ic = model.where(T_in.dst == Account, T_out.src == Account).require(
    sum(T_in.amount_dollars * T_in.is_motif).per(T_in.dst)
    - sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
    + CONSERVATION_BIG_M * Account.is_hub
    <= CONSERVATION_TOLERANCE_DOLLARS + CONSERVATION_BIG_M
)
problem.satisfy(conservation_pos_ic)

conservation_neg_ic = model.where(T_in.dst == Account, T_out.src == Account).require(
    sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
    - sum(T_in.amount_dollars * T_in.is_motif).per(T_in.dst)
    + CONSERVATION_BIG_M * Account.is_hub
    <= CONSERVATION_TOLERANCE_DOLLARS + CONSERVATION_BIG_M
)
problem.satisfy(conservation_neg_ic)

# Amount filter: relational where keeps the threshold predicate at relational
# time; the constraint forces is_motif = 0 on over-threshold rows.
amount_threshold_ic = model.where(Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS).require(
    Transaction.is_motif == 0
)
problem.satisfy(amount_threshold_ic)

# Same beneficial owner across hubs: pairwise filter forbids cross-cluster
# hub pairs so a motif's hubs read as a single beneficial-owner ring rather
# than scattered hits across distinct owners.
H1 = Account.ref()
H2 = Account.ref()
same_bo_ic = model.where(
    H1.id < H2.id,
    H1.bo_id != H2.bo_id,
).require(H1.is_hub + H2.is_hub <= 1)
problem.satisfy(same_bo_ic)

# Solve and report.
print("\n" + "=" * 70)
print("BUTTERFLY (scatter-gather with per-hub conservation)")
print("CSP technique: per-vertex aggregate equality over decision-selected edge subset")
print("=" * 70)
problem.display()
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_BUTTERFLY_MOTIFS)
si = problem.solve_info()
si.display()

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

status = si.termination_status
motif_count = si.num_points or 0
if status == "INFEASIBLE":
    print(
        "\nResult: no butterfly motifs exist under the encoded constraints. "
        "The search space was exhausted with zero feasible motifs."
    )
elif status == "OPTIMAL":
    print(
        f"\nResult: {motif_count} butterfly motif(s) found and search exhausted "
        "(no further motifs exist under the encoded constraints)."
    )
elif status == "SOLUTION_LIMIT":
    print(
        f"\nResult: {motif_count} butterfly motif(s) found; "
        f"hit MAX_BUTTERFLY_MOTIFS={MAX_BUTTERFLY_MOTIFS}. "
        "More may exist -- raise the limit to enumerate further."
    )
else:
    print(
        f"\nResult: search returned status={status} with {motif_count} motif(s); "
        "did not finish. Raise time_limit_sec or check the README troubleshooting."
    )

print("\nButterfly: candidate motif transactions (one row per motif edge per solution):")
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

print("\nButterfly: candidate motif hubs per solution (with shared beneficial owner):")
model.select(
    sol_idx.alias("solution"),
    is_hub_var.account.id.alias("hub_id"),
    is_hub_var.account.name.alias("hub_name"),
    is_hub_var.account.bo_id.alias("bo_id"),
).where(is_hub_var.values(sol_idx, val), val == 1).inspect()

print("\nButterfly: candidate motif source and destination per solution:")
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
