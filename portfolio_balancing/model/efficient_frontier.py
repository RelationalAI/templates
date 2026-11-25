"""Efficient frontier: the bi-objective portfolio problems of every scenario (the two anchors, the
minimum-variance solve at the maximum return, and the grid, adaptive, and dichotomic drivers), and the
frontier points each solve publishes with the stock amounts and weights they allocate."""

import warnings

from relationalai.semantics import Float, Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import clip, maximum, minimum

# Declares Stock.is_non_representative and Stock.regime_covar, which the constraints and the objective read.
from . import correlation_clusters, regime_covariance  # noqa: F401
from .compliance_flags import SECTOR_LIMIT
from .schema import FrontierPoint, Scenario, Stock, model

# The frontier below creates rules in Python loops (one chained solve per return target),
# which trips PyRel's "rules created in a loop" perf heuristic. The pattern is deliberate and
# harmless at this size, so a single module filter is simpler than a filter around every loop.
warnings.filterwarnings("ignore", message=r"\[Rules created in a loop\]")

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

REP_POSITION_LIMIT = 0.30  # max fraction per representative in Stage 3 optimization
# (reps carry combined cluster exposure, so cap is higher;
# feasibility needs REP_POSITION_LIMIT * num_reps >= 1.0 --
# floor is 1/5 = 0.20, so 0.30 leaves headroom)

# --------------------------------------------------
# Stage 3: Prescriptive -- bi-objective QP with epsilon constraint
# --------------------------------------------------
# Scenarios encode budget x regime, so one solve prices every combination. Each solve
# minimizes portfolio variance under a per-scenario return floor (or, for the second
# anchor, maximizes return). The solves are the two anchors, the minimum-variance solve at
# the maximum return, and then the epsilon-constraint targets of three drivers that all
# steer by a reference scenario's frontier:
#   grid       evenly spaced return targets (the control, blind to the frontier's shape)
#   adaptive   each step sized by the previous point's shadow price, so points land evenly
#              in variance space
#   dichotomic repeatedly splits the interval with the largest chord-vs-tangent gap
# Every driver gets the same budget of N_SOLVES points: the two shared anchors plus
# N_SOLVES - 2 interior solves. By the envelope theorem a return floor's shadow price is
# the exact local slope of the frontier, d(min variance) / d(return target).
#
# Every solve is a configured Problem, and each later solve's return floor is a rule over
# earlier solves' published results (values and shadow prices), so one refresh solves the
# anchors, then the targets they determine. Return rates are regime- and budget-independent,
# so a target chosen on the reference scenario applies to every scenario in the same solve.

N_SOLVES = 6
N_INTERIOR = N_SOLVES - 2
REFERENCE_SCENARIO = "base_1000"  # mid-budget, base regime

GRID_SOLVES = [f"grid_{k}" for k in range(1, N_INTERIOR + 1)]
ADAPTIVE_SOLVES = [f"adaptive_{k}" for k in range(1, N_INTERIOR + 1)]
DICHOTOMIC_SOLVES = [f"dichotomic_{k}" for k in range(1, N_INTERIOR + 1)]

x_qty = Float.ref()
x_qty_paired = Float.ref()
regime_cov_val = Float.ref()
PairedStock = Stock.ref()

# Sector constraint ref -- defined at module level.
sector_ref = String.ref()

# The status of every solve, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"{String:solve} solve status is {String:status}")


def _add_compliance_constraints(problem):
    """Add position, sector, and representative-only constraints to a Problem."""
    # Position limit: each representative allocation <= REP_POSITION_LIMIT * budget.
    # This is higher than Stage 1's POSITION_LIMIT because a representative
    # carries its whole cluster's exposure (the cluster's other members are
    # forced to zero below).
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(x_qty <= REP_POSITION_LIMIT * Scenario.budget)
    )

    # Sector limit: total allocation to stocks in same sector <= SECTOR_LIMIT * budget.
    sector_alloc = (
        sum(Stock, x_qty)
        .where(
            Stock.x_quantity(Scenario, x_qty),
            Stock.sector == sector_ref,
        )
        .per(Scenario, sector_ref)
    )
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
            Stock.sector(sector_ref),
        ).require(sector_alloc <= SECTOR_LIMIT * Scenario.budget)
    )

    # Representative-only: non-representative stocks are forced to zero.
    # The cluster's representative (highest Sharpe, picked in Stage 2) is
    # the sole carrier of its exposure in the portfolio. This collapses
    # redundant bets rather than capping within a redundant set.
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
            Stock.is_non_representative(),
        ).require(x_qty == 0)
    )


def _per_scenario(kind, label, props):
    """A concept keyed by Scenario holding one solve's inputs or outputs.

    Each solve has its own concept: a relation that one solve reads must not be written by
    that solve or a later one, so a shared store (Scenario itself) would close a cycle.
    """
    C = model.Concept(f"{kind}_{label}", identify_by={"scenario": Scenario})
    for prop in props:
        setattr(
            C,
            prop,
            model.Property(f"{C} has {prop} {Float:{label}_{kind.lower()}_{prop}}"),
        )
    return C


def frontier_problem(label, *, maximize_return=False, floor=None):
    """Declare one configured solve over every Scenario and publish its results.

    ``floor`` is a per-Scenario Property holding this solve's return floor; a Scenario with no
    floor value becomes a constraint no point meets, so a missing upstream result makes this
    solve infeasible rather than unconstrained. With a floor the solve also requests the
    floor's shadow price, which equals the frontier's slope at the solution.

    The solve's per-Scenario results are returned as a concept with ``ret`` (expected return),
    ``risk`` (variance), and, with a floor, ``sp`` (the shadow price, clamped at 0 as the
    minimize-variance, return >= floor formulation guarantees lambda >= 0).
    """
    problem = Problem(model, Float, name=f"portfolio_balancing_{label}")

    quantity_var = problem.solve_for(
        Stock.x_quantity(Scenario, x_qty),
        name=["qty", Scenario.name, Stock.index],
        populate=False,
    )

    # Non-negative
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(x_qty >= 0)
    )

    # Budget per scenario
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(Stock, x_qty).per(Scenario) <= Scenario.budget)
    )

    # Fully invested per scenario
    problem.satisfy(
        model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(sum(Stock, x_qty).per(Scenario) >= Scenario.budget)
    )

    # Compliance constraints (position + sector limits; non-reps forced to 0)
    _add_compliance_constraints(problem)

    # EPSILON CONSTRAINT: per-scenario return floor. keyed_by Scenario attaches an entity
    # back-pointer so the shadow price joins back to its scenario by KEY, never by parsing
    # the constraint name.
    return_floor = None
    if floor is not None:
        return_floor = problem.satisfy(
            model.where(
                Stock.x_quantity(Scenario, x_qty),
                floor.scenario == Scenario,
            ).require(sum(Stock, Stock.returns * x_qty).per(Scenario) >= floor.value),
            name=["return_floor", Scenario.name],
            keyed_by={"scenario": Scenario},
        )

    if maximize_return:
        problem.maximize(
            sum(Stock, Scenario, Stock.returns * x_qty).where(
                Stock.x_quantity(Scenario, x_qty)
            )
        )
    else:
        # Primary objective: minimize risk (quadratic via regime-conditioned covariance).
        # Each Scenario picks its matching regime covariance, so base and crisis
        # scenarios solve against different covariances in the same call.
        problem.minimize(
            sum(
                Stock, PairedStock, Scenario, regime_cov_val * x_qty * x_qty_paired
            ).where(
                Stock.regime_covar(PairedStock, Scenario.regime, regime_cov_val),
                Stock.x_quantity(Scenario, x_qty),
                PairedStock.x_quantity(Scenario, x_qty_paired),
            )
        )

    # Each refresh of the deployed model runs this solve. HiGHS solves the convex QP (the
    # covariance is PSD-preserving) and returns sensitivity duals, requested only when there
    # is a return floor to price.
    problem.configure("highs", time_limit_sec=60, sensitivity=floor is not None)

    status = String.ref()
    model.where(problem.termination_status()(status)).define(SolveStatus(label, status))

    # Per-scenario return and variance of the solution (allocations above 1e-6), and the
    # floor's shadow price.
    Result = _per_scenario("Result", label, ("ret", "risk", "sp"))
    qa, qb, va, vb, cov = (
        quantity_var.ref(),
        quantity_var.ref(),
        Float.ref(),
        Float.ref(),
        Float.ref(),
    )
    model.define(
        r := Result.new(scenario=Scenario),
        r.ret(
            sum(qa, qa.stock.returns * va)
            .where(
                qa.values(0, va),
                va > 1e-6,
                qa.scenario == Scenario,
            )
            .per(Scenario),
        ),
    )
    model.define(
        r := Result.new(scenario=Scenario),
        r.risk(
            sum(qa, qb, cov * va * vb)
            .where(
                qa.values(0, va),
                qb.values(0, vb),
                va > 1e-6,
                vb > 1e-6,
                qa.scenario == Scenario,
                qb.scenario == Scenario,
                qa.stock.regime_covar(qb.stock, Scenario.regime, cov),
            )
            .per(Scenario),
        ),
    )
    if return_floor is not None:
        # A solve without sensitivity duals (e.g. at its time limit) steers the drivers with
        # a 0 slope, so the later targets stay defined.
        model.where(return_floor.scenario == Scenario).define(
            r := Result.new(scenario=Scenario),
            r.sp(maximum(0.0, return_floor.shadow_price) | 0.0),
        )

    # The solve's results as FrontierPoints, which the deployed model publishes for the
    # queries: one per Scenario, with its return, risk, shadow price, and allocations. Only
    # a solve with an accepted status publishes them, so a failed solve's incumbent never
    # enters the frontier ("LOCALLY_SOLVED" covers non-HiGHS back ends).
    for accepted in ("OPTIMAL", "LOCALLY_SOLVED"):
        solved = (problem.termination_status()(status), status == accepted)
        model.where(Result.scenario == Scenario, *solved).define(
            fp := FrontierPoint.new(scenario_label=Scenario.name, solve=label),
            fp.scenario(Scenario),
            fp.return_value(Result.ret),
            fp.risk(Result.risk),
        )
        if return_floor is not None:
            # The published marginal is the solver's dual alone, so a missing one stays
            # visible.
            model.where(
                Result.scenario == Scenario, return_floor.scenario == Scenario, *solved
            ).define(
                fp := FrontierPoint.new(scenario_label=Scenario.name, solve=label),
                fp.marginal_risk_per_return(maximum(0.0, return_floor.shadow_price)),
            )
    amount = Float.ref()
    model.where(
        FrontierPoint.solve == label,
        FrontierPoint.scenario_label == quantity_var.scenario.name,
        quantity_var.values(0, amount),
        amount > 1e-6,
    ).define(FrontierPoint.allocates(quantity_var.stock, amount))

    return Result


def floor_from_rate(label, rate_rel):
    """A per-Scenario return floor ``rate * budget`` from a scalar rate relation."""
    floor = _per_scenario("Floor", label, ("value",))
    model.define(
        floor.new(scenario=Scenario)
    )  # every scenario has a floor row; its value may be missing
    r, f = Float.ref(), floor.ref()
    model.where(rate_rel(r), f.scenario == Scenario).define(
        f.value(r * Scenario.budget)
    )
    return floor


def scalar(name, type_=Float):
    """A one-value relationship, for the targets and bookkeeping the drivers pass between solves."""
    return model.Relationship(f"{name} is {type_:{name}}")


def reference_point(name, result, sp=None):
    """The (return, variance, shadow price) scalars of a solve's result at the reference scenario."""
    point = {k: scalar(f"{name}_{k}") for k in ("ret", "var", "sp")}
    r = result.ref()
    model.where(r.scenario.name == REFERENCE_SCENARIO).define(point["ret"](r.ret))
    model.where(r.scenario.name == REFERENCE_SCENARIO).define(point["var"](r.risk))
    if sp is None:
        model.where(r.scenario.name == REFERENCE_SCENARIO).define(point["sp"](r.sp))
    else:
        model.define(point["sp"](sp))
    return point



# The reference scenario's budget, which turns a return target into a return rate.
REF_BUDGET = scalar("ref_budget")
model.where(Scenario.name == REFERENCE_SCENARIO).define(REF_BUDGET(Scenario.budget))
_ref_budget = Float.ref()

# --------------------------------------------------
# Anchors
# --------------------------------------------------

# Anchor 1: minimize risk with no return floor (so its shadow price is 0 by definition).
min_risk = frontier_problem("min_risk")
# Anchor 2: maximize return. One solve covers all scenarios -- maximize aggregate return,
# then read per-scenario.
max_return = frontier_problem("max_return", maximize_return=True)

LO = reference_point("lo", min_risk, sp=0.0)
RETURN_HI = scalar("return_hi")
_r = max_return.ref()
model.where(_r.scenario.name == REFERENCE_SCENARIO).define(RETURN_HI(_r.ret))

# The minimum-variance solve at the maximum return, shared by all three drivers.
hi_rate = scalar("hi_rate")
_ret_hi = Float.ref()
model.where(RETURN_HI(_ret_hi), REF_BUDGET(_ref_budget)).define(hi_rate(_ret_hi / _ref_budget))
hi = frontier_problem("hi", floor=floor_from_rate("hi", hi_rate))
HI = reference_point("hi", hi)

# --------------------------------------------------
# Grid driver: evenly spaced returns between the anchors
# --------------------------------------------------

grid_step = scalar("grid_step")
_ret_lo, _span = Float.ref(), Float.ref()
model.where(LO["ret"](_ret_lo), RETURN_HI(_ret_hi)).define(
    grid_step((_ret_hi - _ret_lo) / (N_SOLVES - 1))
)
for k, label in enumerate(GRID_SOLVES, start=1):
    rate = scalar(f"{label}_rate")
    model.where(LO["ret"](_ret_lo), grid_step(_span), REF_BUDGET(_ref_budget)).define(
        rate((_ret_lo + k * _span) / _ref_budget)
    )
    frontier_problem(label, floor=floor_from_rate(label, rate))

# --------------------------------------------------
# Dichotomic driver: repeatedly split the interval with the largest chord-vs-tangent gap
# --------------------------------------------------
# The value function lies below the chord between two points and above each point's supporting
# tangent (slope = its shadow price). At the tangent crossover eps* the gap is chord - tangent
# >= 0 (either tangent gives the same value there), and eps* is also the best place to sample
# next. This is the epsilon-constraint, dual-guided analogue of NISE: classical NISE
# (Aneja-Nair 1979, non-inferior-set estimation) is a WEIGHTED-SUM scheme that splits by
# picking the next weight as the chord normal; here the next epsilon is the shadow-price
# crossover. Same supported set on a convex bi-objective frontier.
#
# Each step has its own Interval concept (the live intervals before that step's solve); the
# step's solve splits the interval with the largest gap, the earliest-created on a tie.


def interval_concept(k):
    """The intervals live before dichotomic step ``k``, with each one's crossover and gap."""
    interval = model.Concept(f"Interval{k}", identify_by={"ctr": Integer})
    for end in ("a", "b"):
        for f in ("ret", "var", "sp"):
            setattr(
                interval,
                f"{end}_{f}",
                model.Property(f"{interval} has {end} {f} {Float:i{k}_{end}_{f}}"),
            )
    interval.estar = model.Property(f"{interval} has crossover {Float:i{k}_estar}")
    interval.gap = model.Property(f"{interval} has gap {Float:i{k}_gap}")
    # Chord-vs-tangent gap between the endpoints and the tangent crossover eps* where it peaks;
    # locally linear (tangents ~parallel) or degenerate endpoints sample at the midpoint.
    de, dl = interval.b_ret - interval.a_ret, interval.b_sp - interval.a_sp
    mid = 0.5 * (interval.a_ret + interval.b_ret)
    model.where(de <= 1e-9).define(interval.estar(mid), interval.gap(0.0))
    model.where(de > 1e-9, dl <= 1e-9).define(interval.estar(mid))
    model.where(de > 1e-9, dl > 1e-9).define(
        interval.estar(
            clip(
                (
                    interval.a_var
                    - interval.a_sp * interval.a_ret
                    - interval.b_var
                    + interval.b_sp * interval.b_ret
                )
                / dl,
                interval.a_ret,
                interval.b_ret,
            )
        )
    )
    chord = interval.a_var + (interval.b_var - interval.a_var) / de * (
        interval.estar - interval.a_ret
    )
    tangent = interval.a_var + interval.a_sp * (interval.estar - interval.a_ret)
    model.where(de > 1e-9).define(interval.gap(maximum(chord - tangent, 0.0)))
    return interval


def set_interval(interval, ctr, a, b, *where):
    """Define interval ``ctr`` of ``interval`` with endpoints a, b (dicts of scalar relations)."""
    ar, av, asp, br, bv, bsp = (Float.ref() for _ in range(6))
    model.where(
        a["ret"](ar),
        a["var"](av),
        a["sp"](asp),
        b["ret"](br),
        b["var"](bv),
        b["sp"](bsp),
        *where,
    ).define(
        i := interval.new(ctr=ctr),
        i.a_ret(ar),
        i.a_var(av),
        i.a_sp(asp),
        i.b_ret(br),
        i.b_var(bv),
        i.b_sp(bsp),
    )


intervals = interval_concept(1)
set_interval(intervals, 0, LO, HI)
for k, label in enumerate(DICHOTOMIC_SOLVES, start=1):
    current = intervals
    other = current.ref()
    max_gap = aggs.max(other.gap)
    popped = scalar(f"{label}_popped_ctr", Integer)
    model.define(popped(aggs.min(current.ctr).where(current.gap == max_gap)))
    # The popped interval's endpoints and the new target's rate.
    popped_end = {
        f"{end}_{f}": scalar(f"{label}_popped_{end}_{f}")
        for end in ("a", "b")
        for f in ("ret", "var", "sp")
    }
    rate = scalar(f"{label}_rate")
    c = Integer.ref()
    model.where(popped(c), current.ctr == c, REF_BUDGET(_ref_budget)).define(
        rate(current.estar / _ref_budget),
        *[popped_end[n](getattr(current, n)) for n in popped_end],
    )
    result = frontier_problem(label, floor=floor_from_rate(label, rate))
    if k < N_INTERIOR:
        point = reference_point(label, result)
        following = interval_concept(k + 1)
        # Live intervals carry over unchanged; the popped one splits at the new point.
        model.where(popped(c), current.ctr != c).define(
            j := following.new(ctr=current.ctr),
            j.a_ret(current.a_ret),
            j.a_var(current.a_var),
            j.a_sp(current.a_sp),
            j.b_ret(current.b_ret),
            j.b_var(current.b_var),
            j.b_sp(current.b_sp),
        )
        end_a = {f: popped_end[f"a_{f}"] for f in ("ret", "var", "sp")}
        end_b = {f: popped_end[f"b_{f}"] for f in ("ret", "var", "sp")}
        set_interval(following, 2 * k - 1, end_a, point)
        set_interval(following, 2 * k, point, end_b)
        intervals = following

# --------------------------------------------------
# Adaptive driver: step from the previous point's shadow price
# --------------------------------------------------
# Each step sizes the next return target by the current slope so points land evenly in
# variance space: d(return) = target_dvar / lambda, clipped to [min_step, max_step]. The
# first step bootstraps with the chord slope between the anchors.

target_dvar, min_step, max_step, lam0 = (
    scalar(n) for n in ("target_dvar", "min_step", "max_step", "adaptive_lam0")
)
_ret_lo, _var_lo, _ret_at_hi, _var_at_hi = (Float.ref() for _ in range(4))
model.where(
    LO["ret"](_ret_lo),
    LO["var"](_var_lo),
    HI["ret"](_ret_at_hi),
    HI["var"](_var_at_hi),
    RETURN_HI(_ret_hi),
).define(
    target_dvar((_var_at_hi - _var_lo) / (N_SOLVES - 1)),
    min_step((_ret_hi - _ret_lo) / (4 * (N_SOLVES - 1))),
    max_step((_ret_hi - _ret_lo) / (N_SOLVES - 2)),
    # A single-point frontier (equal anchor returns) has no chord; the floor on the span
    # keeps the bootstrap defined, and the zero step sizes keep every target at the anchor.
    lam0((_var_at_hi - _var_lo) / maximum(_ret_at_hi - _ret_lo, 1e-9)),
)
previous_target, previous_lam = LO["ret"], lam0
for k, label in enumerate(ADAPTIVE_SOLVES, start=1):
    target, rate = scalar(f"{label}_target"), scalar(f"{label}_rate")
    pe, pl, t, mn, mx, h = (Float.ref() for _ in range(6))
    model.where(
        previous_target(pe),
        previous_lam(pl),
        target_dvar(t),
        min_step(mn),
        max_step(mx),
        RETURN_HI(h),
    ).define(target(minimum(pe + clip(t / maximum(pl, 1e-9), mn, mx), h)))
    model.where(target(pe), REF_BUDGET(_ref_budget)).define(rate(pe / _ref_budget))
    result = frontier_problem(label, floor=floor_from_rate(label, rate))
    if k < N_INTERIOR:
        previous_target, previous_lam = target, reference_point(label, result)["sp"]

# --------------------------------------------------
# Allocation weights
# --------------------------------------------------

# Each allocated stock's share of its scenario's budget.
FrontierPoint.weight = model.Relationship(
    f"{FrontierPoint} holds {Stock} at weight {Float:fp_weight}"
)
_allocated = Float.ref()
model.where(FrontierPoint.allocates(Stock, _allocated)).define(
    FrontierPoint.weight(Stock, _allocated / FrontierPoint.scenario.budget)
)
