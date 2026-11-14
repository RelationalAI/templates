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

Deploy:
    Part of the model in `model/`, deployed with `rai models deploy --path model`;
    each refresh of the deployment runs this solve. `python -m queries.butterfly_motifs`
    prints its report from the deployed model.
"""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .ontology import AMOUNT_THRESHOLD_DOLLARS, Account, Transaction, model, tx_csv

# Motif parameters.
# K = 3 is the smallest hub count that's clearly a fan-out-then-fan-in pattern
# rather than a direct payment chain.
K = 3
# Per-hub conservation tolerance: a hub absorbs a small per-hop skim (the
# launderer's overhead) but must forward most of the funds. $100 admits
# realistic small residuals.
CONSERVATION_TOLERANCE_DOLLARS = 100
# Solver solution-limit: cap how many distinct motifs to enumerate per run.
# The bundled data plants exactly two butterflies; raise this when running on
# your own ledger.
MAX_BUTTERFLY_MOTIFS = 10

# Tightest big-M coefficient for the per-hub conservation IC below. The big-M
# form makes that IC active when `is_hub == 1` and vacuous when `is_hub == 0`;
# M needs to bound |sum_in - sum_out| over decision-selected motif edges,
# which is at most the per-account total of incoming or outgoing amounts.
CONSERVATION_BIG_M = (
    int(
        max(
            tx_csv.groupby("dst_id")["amount_dollars"].sum().max(),
            tx_csv.groupby("src_id")["amount_dollars"].sum().max(),
        )
    )
    + AMOUNT_THRESHOLD_DOLLARS
)

# Decision-valued properties for the butterfly motif.
Transaction.is_motif = model.Property(f"{Transaction} is in motif if {Integer:is_motif}")
Account.is_source = model.Property(f"{Account} is source if {Integer:is_source}")
Account.is_hub = model.Property(f"{Account} is hub if {Integer:is_hub}")
Account.is_dest = model.Property(f"{Account} is dest if {Integer:is_dest}")

# The model configures three Problems, one per motif, so each has a unique name.
problem = Problem(model, Integer, name="butterfly")

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
role_exclusive_ic = model.where(Account).require(Account.is_source + Account.is_hub + Account.is_dest <= 1)
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

# Global motif-edge count = K source->hub edges + K hub->dest edges = 2K.
# Closes a gap in the per-account flow ICs above: those use `model.where(...)`
# to scope per-account, so the IC isn't instantiated for accounts with no
# outgoing (resp. no incoming) transactions. On a customer ledger with
# sink-only or source-only accounts, the per-account ICs alone would let the
# solver pick such an account as a hub (or one-sided role) with no actual
# motif edge attached. The global count forces 2K motif edges total, which
# combined with the per-account ICs that DO fire on connected accounts
# rules out phantom role assignments.
total_motif_edges_ic = model.require(sum(Transaction.is_motif) == 2 * K)
problem.satisfy(total_motif_edges_ic)

# Layer constraints: forbid a motif edge from going directly source -> dest
# (skipping the hub layer) or hub -> hub (chaining through hubs). The count
# flow ICs above plus the global motif-edge count constrain the *number* of
# motif edges per role, but cannot rule out the topological shape
# `S->D, S->H1, S->H2, H1->H3, H2->D, H3->D` (still 2K edges, still 1 per
# hub in / 1 per hub out, K per dest in, K per source out) where one hub
# chains through another and one leg skips the hub layer. The bundled
# data has no under-threshold direct source-dest or hub-hub edges, so these
# ICs are vacuous on the demo; they are load-bearing on customer ledgers
# that have such edges. Expressed as `sum of three binaries <= 2` so the
# constraint stays in plain relational arithmetic.
no_direct_src_to_dst_ic = model.where(Transaction).require(
    Transaction.is_motif + Transaction.src.is_source + Transaction.dst.is_dest <= 2
)
problem.satisfy(no_direct_src_to_dst_ic)

no_hub_to_hub_ic = model.where(Transaction).require(
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
# Big-M is preferred over a half-reified `implies(is_hub == 1, ...)`:
# half-reification introduces a free Boolean auxiliary per non-hub account
# that MiniZinc treats as part of the search space, returning thousands of
# trivially-distinct solutions for the same role/motif assignment. The big-M
# form has no auxiliary -- enumeration stays clean and the solver exhausts
# after the data's actual motifs.
T_out = Transaction.ref()
conservation_pos_ic = model.where(Transaction.dst == Account, T_out.src == Account).require(
    sum(Transaction.amount_dollars * Transaction.is_motif).per(Transaction.dst)
    - sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
    + CONSERVATION_BIG_M * Account.is_hub
    <= CONSERVATION_TOLERANCE_DOLLARS + CONSERVATION_BIG_M
)
problem.satisfy(conservation_pos_ic)

conservation_neg_ic = model.where(Transaction.dst == Account, T_out.src == Account).require(
    sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
    - sum(Transaction.amount_dollars * Transaction.is_motif).per(Transaction.dst)
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
H2 = Account.ref()
same_bo_ic = model.where(
    Account.id < H2.id,
    Account.bo_id != H2.bo_id,
).require(Account.is_hub + H2.is_hub <= 1)
problem.satisfy(same_bo_ic)

# Each refresh of the deployed model runs this solve.
problem.configure("minizinc", time_limit_sec=60, solution_limit=MAX_BUTTERFLY_MOTIFS)

# Deploy the rules behind problem.display() with the model.
problem.install_display_strings()

# The solve's status, published through the model's own relationship.
SolveStatus = model.Relationship(f"butterfly solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))
