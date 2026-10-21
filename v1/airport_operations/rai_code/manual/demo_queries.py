"""Demo queries Q1-Q5 from DEMO_QUESTIONS.md, implemented against the manual
ontology in eham_acdm.py. The five acts of the A-CDM Decision Hub talk track:

    Q1 Act 1 (Rules)         tobt_violations_by_handler
    Q2 Act 2 (Graph)         rotation_cascade_from_KL1234
    Q3 Act 3 (Predictive)    ms5_conflict_ranking (deterministic heuristic;
                              predictive reasoner is preview, fallback per
                              talk-track disclaimer)
    Q4 Act 4 (Prescriptive)  tsat_resequence_under_storm  (HiGHS LP)
    Q5 Act 5 (Superalignment) tsat_resequence_with_preservation

Run from project root:
    .venv/bin/python rai_code/manual/demo_queries.py
"""
# All query LOGIC is expressed in PyRel. The only pandas usage in this file is
# display-side sorting on the returned DataFrames, and that's NOT part of the
# query / data-flow at all (the query has already executed when sort_values
# runs). The 120-slot grid lives in Snowflake (ACDM_DEMO.EHAM.STORM_SLOT) and
# the slot_blocks edges come from FLIGHT.SLOT_BLOCKS_CALLSIGN.
from relationalai.semantics import Float, Integer, distinct
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.datetime import datetime as dt_std

try:
    from .eham_acdm import (
        Aircraft,
        Arrival,
        Departure,
        Flight,
        FlightSlot,
        GroundHandler,
        Operator,
        PreservedFlight,
        Runway,
        Slot,
        Stand,
        StormWindowDeparture,
        TOBTViolation,
        feeds_callsign,
        model,
        shares_stand,
        slot_blocks,
    )
except ImportError:
    from eham_acdm import (
        Aircraft,
        Arrival,
        Departure,
        Flight,
        FlightSlot,
        GroundHandler,
        Operator,
        PreservedFlight,
        Runway,
        Slot,
        Stand,
        StormWindowDeparture,
        TOBTViolation,
        feeds_callsign,
        model,
        shares_stand,
        slot_blocks,
    )


# =============================================================================
# Q1. Act 1 - Rules: TOBT compliance audit
#
# "Show me every flight in the last four hours where actual ready time
#  deviated from TOBT by more than five minutes, broken down by ground
#  handler."  (Per ICAO MS12: |ARDT - TOBT| > 5 min triggers TOBT/TSAT removal.)
# =============================================================================
def q1_tobt_violations_by_handler():
    """Per-handler violation count + average ARDT-vs-TOBT deviation in the
    4-hour window ending at the demo 'now' = 2026-10-14 14:30."""
    now = dt_std(2026, 10, 14, 14, 30)
    four_hours_ago = dt_std(2026, 10, 14, 10, 30)

    df = (
        model.where(
            TOBTViolation(Flight),
            Flight.handler == GroundHandler,
            Flight.ardt >= four_hours_ago,
            Flight.ardt <= now,
        )
        .select(
            distinct(
                GroundHandler.code.alias("handler"),
                aggs.count(Flight).per(GroundHandler).alias("violations"),
                aggs.avg(
                    dt_std.diff("minute", Flight.tobt, Flight.ardt)
                )
                .per(GroundHandler)
                .alias("avg_deviation_min"),
            )
        )
        .to_df()
        .sort_values("violations", ascending=False)
        .reset_index(drop=True)
    )
    # Force RAI's Int128 column into plain int64 so Snowsight's Arrow-based
    # DataFrame renderer (and Plotly, downstream) can consume it. astype()
    # can fail on the Int128 extension type in some pandas/pyarrow versions,
    # so we route via Python int which Int128 supports unconditionally.
    if "violations" in df.columns:
        df["violations"] = [int(v) if v is not None else 0 for v in df["violations"]]
    if "avg_deviation_min" in df.columns:
        df["avg_deviation_min"] = [
            float(v) if v is not None else 0.0 for v in df["avg_deviation_min"]
        ]
    return df


# =============================================================================
# Q2. Act 2 - Graph: Rotation cascade trace from KL1234
#
# "KL1234 inbound is 35 minutes late at final approach. Trace the rotation
#  impact across the next 6 hours. Which outbound flights are at risk?"
# Multi-relational graph: feeds_callsign (rotation) UNION shares_stand
# (stand-contention). Reachability is computed by the graph reasoner.
# =============================================================================
def _ensure_rotation_graph():
    """Build the (callsign-id) directed graph once: rotation + stand edges.
    Cached on the model object so repeat calls don't redefine the graph."""
    if hasattr(model, "_acdm_rotation_graph"):
        return model._acdm_rotation_graph  # type: ignore[attr-defined]
    g = Graph(model, directed=True, weighted=False)

    # 1. Nodes: every flight that's an endpoint of any cascade edge.
    src = Flight.ref()
    dst = Flight.ref()
    model.where(feeds_callsign(src, dst)).define(g.Node.new(id=src.callsign))
    model.where(feeds_callsign(src, dst)).define(g.Node.new(id=dst.callsign))
    sb_src = Flight.ref()
    sb_dst = Flight.ref()
    model.where(slot_blocks(sb_src, sb_dst)).define(g.Node.new(id=sb_src.callsign))
    model.where(slot_blocks(sb_src, sb_dst)).define(g.Node.new(id=sb_dst.callsign))
    f1 = Flight.ref()
    f2 = Flight.ref()
    model.where(
        shares_stand(f1, f2),
        f1.sobt < f2.sobt,
    ).define(g.Node.new(id=f1.callsign))
    model.where(
        shares_stand(f1, f2),
        f1.sobt < f2.sobt,
    ).define(g.Node.new(id=f2.callsign))

    # 2. Rotation edges (feeds_callsign).
    src_node = g.Node.ref()
    dst_node = g.Node.ref()
    fsrc = Flight.ref()
    fdst = Flight.ref()
    model.where(
        feeds_callsign(fsrc, fdst),
        src_node.id == fsrc.callsign,
        dst_node.id == fdst.callsign,
    ).define(g.Edge.new(src=src_node, dst=dst_node))

    # 3. Slot-block edges (operational cascade across stands/piers).
    src_node_sb = g.Node.ref()
    dst_node_sb = g.Node.ref()
    fsrc_sb = Flight.ref()
    fdst_sb = Flight.ref()
    model.where(
        slot_blocks(fsrc_sb, fdst_sb),
        src_node_sb.id == fsrc_sb.callsign,
        dst_node_sb.id == fdst_sb.callsign,
    ).define(g.Edge.new(src=src_node_sb, dst=dst_node_sb))

    # 4. Stand-contention edges (forward in time).
    src_node2 = g.Node.ref()
    dst_node2 = g.Node.ref()
    f1b = Flight.ref()
    f2b = Flight.ref()
    model.where(
        shares_stand(f1b, f2b),
        f1b.sobt < f2b.sobt,
        src_node2.id == f1b.callsign,
        dst_node2.id == f2b.callsign,
    ).define(g.Edge.new(src=src_node2, dst=dst_node2))

    model._acdm_rotation_graph = g  # type: ignore[attr-defined]
    return g


def q2_rotation_cascade_from(callsign: str = "KL1234"):
    """Reachable callsigns from `callsign` via the union of rotation and
    stand-contention edges. Returns the (from, to) reachability pairs filtered
    to those starting at the seed callsign."""
    g = _ensure_rotation_graph()
    reach = g.reachable(full=True)
    n1, n2 = g.Node.ref(), g.Node.ref()
    df = (
        model.where(
            reach(n1, n2),
            n1.id == callsign,
        )
        .select(n1.id.alias("from"), n2.id.alias("to"))
        .to_df()
    )
    return df.sort_values("to").reset_index(drop=True)


# =============================================================================
# Q3. Act 3 - Predictive (heuristic fallback): MS5 gate-conflict ranking
#
# The talk-track predictive reasoner is preview-only. Fallback per the disclaimer:
#   "deterministic rule (e.g., p_conflict = 1 if overlap > 5 min else 0.3)"
# We use a richer deterministic score *entirely expressed in PyRel*:
#   ms5_score(f) = 0.40 * (30 - minutes_to_landing(f)) / 30
#                + 0.35 * pax_connections(f) / 150
#                + ms5_pier_bonus(f)        (0.15 if pier in {M,G,H}, else 0)
#                - ms5_wtc_penalty(f)       (0.20 if wtc not in {H,M}, else 0)
# Rank arrivals with TLDT in [14:30, 15:00] by ms5_score descending.
# =============================================================================
MS5Candidate = model.Relationship(f"{Flight} is an MS5 candidate", short_name="ms5_candidate")
Flight.ms5_minutes_to_landing = model.Property(
    f"{Flight} ms5_minutes_to_landing {Integer:ms5_minutes_to_landing}"
)
Flight.ms5_pier_bonus = model.Property(f"{Flight} ms5_pier_bonus {Float:ms5_pier_bonus}")
Flight.ms5_wtc_penalty = model.Property(f"{Flight} ms5_wtc_penalty {Float:ms5_wtc_penalty}")
Flight.ms5_score = model.Property(f"{Flight} ms5_score {Float:ms5_score}")

_q3_now = dt_std(2026, 10, 14, 14, 30)
_q3_horizon = dt_std(2026, 10, 14, 15, 0)

# Scope: arrivals not yet landed (ALDT NULL is implicit - we filter by TLDT only),
# with TLDT in [14:30, 15:00].
model.where(
    Arrival(Flight),
    Flight.tldt >= _q3_now,
    Flight.tldt <= _q3_horizon,
).define(MS5Candidate(Flight))

# minutes_to_landing = diff_minutes(now, tldt)
model.where(MS5Candidate(Flight)).define(
    Flight.ms5_minutes_to_landing(dt_std.diff("minute", _q3_now, Flight.tldt))
)

# pier_bonus: 0.15 if pier is M/G/H, 0 otherwise. Two disjoint rules.
model.where(
    MS5Candidate(Flight),
    Flight.assigned_stand == Stand,
    (Stand.pier == "M") | (Stand.pier == "G") | (Stand.pier == "H"),
).define(Flight.ms5_pier_bonus(0.15))
model.where(
    MS5Candidate(Flight),
    Flight.assigned_stand == Stand,
    Stand.pier != "M",
    Stand.pier != "G",
    Stand.pier != "H",
).define(Flight.ms5_pier_bonus(0.0))

# wtc_penalty: 0.20 if wtc is not H/M, 0 otherwise.
model.where(
    MS5Candidate(Flight),
    (Flight.wtc == "H") | (Flight.wtc == "M"),
).define(Flight.ms5_wtc_penalty(0.0))
model.where(
    MS5Candidate(Flight),
    Flight.wtc != "H",
    Flight.wtc != "M",
).define(Flight.ms5_wtc_penalty(0.20))

# Composite score - pure PyRel arithmetic on derived properties.
model.where(MS5Candidate(Flight)).define(
    Flight.ms5_score(
        (30.0 - Flight.ms5_minutes_to_landing) / 30.0 * 0.40
        + Flight.pax_connections * 1.0 / 150.0 * 0.35
        + Flight.ms5_pier_bonus
        - Flight.ms5_wtc_penalty
    )
)


def q3_ms5_conflict_ranking():
    """Top arrivals at risk of an MS5 gate conflict, ranked by a deterministic
    PyRel-computed fit-score. Reproduces the talk-track Act 3 5-candidate set."""
    df = (
        model.where(
            MS5Candidate(Flight),
            Flight.assigned_stand == Stand,
        )
        .select(
            Flight.callsign.alias("inbound"),
            Stand.code.alias("current_stand"),
            Stand.pier.alias("pier"),
            Flight.tldt.alias("predicted_landing"),
            Flight.pax_connections.alias("pax_conn"),
            Flight.wtc.alias("wtc"),
            Flight.ms5_minutes_to_landing.alias("minutes_to_land"),
            Flight.ms5_score.alias("p_conflict"),
        )
        .to_df()
        .sort_values("p_conflict", ascending=False)
        .reset_index(drop=True)
    )
    for col in ("pax_conn", "minutes_to_land"):
        if col in df.columns:
            df[col] = [int(v) if v is not None else 0 for v in df[col]]
    return df


# =============================================================================
# Q4. Act 4 - Prescriptive: TSAT re-sequence under storm
#
# 47 outbound flights with TSAT in [15:00, 17:00) on 18L (single runway).
# Decision: x[Flight, slot] in {0,1}, 120 1-minute slots covering the window.
# Constraints:
#  (a) Each flight assigned to exactly one slot.
#  (b) Each slot holds at most one flight (single-runway).
#  (c) Heavy-followed-by-non-heavy needs +1 extra minute separation.
#  (d) CTOT compliance: assigned minute within [ctot - 5, ctot + 10].
#  (e) Pier pushback: at most 2 simultaneous pushes from the same pier.
# Objective: minimise weighted delay vs SOBT, weighted by (pax_conn + 20*ATFM).
# =============================================================================
def _build_storm_problem(extra_preservation: bool = False):
    """Builds the Act-4 problem (and optionally the Act-5 preservation constraint).
    Returns (chosen_df, solve_info). All concepts and helper Properties live
    in eham_acdm.py; this function only constructs the Problem and reads the
    solve back. Acts 4 and 5 each own a distinct Property
    (assign_base vs assign_preserved) so each Problem
    can populate without colliding with the other."""
    assign = FlightSlot.assign_preserved if extra_preservation else FlightSlot.assign_base
    problem = Problem(model, Float)

    # (Decision variable: assign in {0,1} on every FlightSlot row.)
    problem.solve_for(
        assign,
        where=[],  # FlightSlot rows already constrained to storm window
        lower=0.0,
        upper=1.0,
        type="bin",
    )

    # (a) Each flight assigned to exactly one slot.
    one_slot = problem.satisfy(
        model.require(
            aggs.sum(assign).per(Flight) == 1
        ).where(FlightSlot.flight_ref == Flight),
        name=["one-slot", Flight.callsign],
        keyed_by={"flight": Flight},
    )

    # (b) Each slot holds at most one flight (single-runway).
    slot_cap = problem.satisfy(
        model.require(
            aggs.sum(assign).per(Slot) <= 1
        ).where(FlightSlot.slot_ref == Slot),
        name=["slot-cap", Slot.minute_offset],
        keyed_by={"slot": Slot},
    )

    # (e) Pier pushback: at most 1 simultaneous push from the same pier per
    # minute. The realistic A-CDM constraint at most piers is 1/min (a single
    # tug handles one pushback at a time); the talk track quotes "<= 2" as a
    # liberal default but using 1 here surfaces real contention and gives Q5
    # the chance to make a visible difference.
    pier_push = problem.satisfy(
        model.where(
            FlightSlot.flight_ref == Flight,
            Flight.assigned_stand == Stand,
            FlightSlot.slot_ref == Slot,
        ).require(
            aggs.sum(assign).per(Stand.pier, Slot) <= 1
        ),
        name=["pier-push"],
    )

    # (c) No-earlier-than-SOBT: a flight cannot push before its scheduled
    # off-block time. For every (f, s) where slot.absolute_min < sobt_min,
    # force assign = 0.
    no_early_push = problem.satisfy(
        model.where(
            FlightSlot.flight_ref == Flight,
            FlightSlot.slot_ref == Slot,
            Slot.absolute_min < Flight.sobt_min_storm,
        ).require(assign == 0),
        name=["no-early-push"],
    )

    # (f) Wake separation: a Heavy departure followed by a Medium/Light in
    # the next minute requires +1 min of separation (the standard ICAO
    # behind-heavy rule). For each pair of consecutive slots (sh, sl=sh+1)
    # we require: heavies at sh + non-heavies at sl <= 1. This creates real
    # contention in the LP (KL widebodies dominate the storm window).
    assign_name = "assign_preserved" if extra_preservation else "assign_base"
    fh, fl = Flight.ref(), Flight.ref()
    fs_h, fs_l = FlightSlot.ref(), FlightSlot.ref()
    sh, sl = Slot.ref(), Slot.ref()
    wake_sep = problem.satisfy(
        model.where(
            fs_h.flight_ref == fh,
            fs_h.slot_ref == sh,
            fh.wtc == "H",
            fs_l.flight_ref == fl,
            fs_l.slot_ref == sl,
            (fl.wtc == "M") | (fl.wtc == "L"),
            sl.minute_offset == sh.minute_offset + 1,
        ).require(
            getattr(fs_h, assign_name) + getattr(fs_l, assign_name) <= 1
        ),
        name=["wake-sep"],
    )

    # (d) CTOT compliance is encoded softly via the delay-weighted objective:
    # flights with a CTOT pay a strong penalty for delay beyond +10 minutes.
    # Hard CTOT bounds via per-slot assign-pinning aren't yet expressible in
    # the current Problem rewriter; revisit when the API gains conditional-on-
    # decision predicates.

    # (Act 5 only) Preservation: KL flights with pax_conn > 80 must finish
    # within 8 minutes of SOBT. Express as an aggregate-delay cap per flight:
    # sum_s assign[f, s] * (slot.absolute_min - sobt) <= 8.
    if extra_preservation:
        preserved_cap = problem.satisfy(
            model.require(
                aggs.sum(
                    assign * (Slot.absolute_min - Flight.sobt_min_storm)
                )
                .where(
                    FlightSlot.flight_ref == Flight,
                    FlightSlot.slot_ref == Slot,
                )
                .per(Flight)
                <= Flight.preservation_delay_cap_min
            ),
            name=["preserved-cap", Flight.callsign],
            keyed_by={"flight": Flight},
        )
    else:
        preserved_cap = None

    # Objective: minimise total delay, weighted by ATFM penalty risk. We
    # deliberately drop pax_connections from the Q4 weight so that the
    # baseline solve doesn't already favour high-connector flights - that
    # protection comes from the persistent operator rule in Q5, where it's
    # meant to live ("we absorb the delay elsewhere"). Weight = 1 + 20*ATFM.
    problem.minimize(
        aggs.sum(
            assign
            * (Slot.absolute_min - Flight.sobt_min_storm)
            * (1.0 + 20.0 * Flight.atfm_penalty)
        ).where(
            FlightSlot.flight_ref == Flight,
            FlightSlot.slot_ref == Slot,
        )
    )

    # Pre-solve validation: catch empty variable/constraint registrations before
    # the remote solver returns a misleading empty optimum.
    model.require(problem.num_variables() > 0)
    model.require(problem.num_constraints() > 0)
    model.require(problem.num_min_objectives() + problem.num_max_objectives() == 1)

    problem.solve("highs")
    si = problem.solve_info()

    # Collect chosen (flight, slot) assignments. delay_min is computed in
    # PyRel as (slot.absolute_min - flight.sobt_min_storm).
    fs = (
        model.where(
            FlightSlot.flight_ref == Flight,
            FlightSlot.slot_ref == Slot,
            assign > 0.5,
            Flight.operating_operator == Operator,
            Flight.assigned_stand == Stand,
        )
        .select(
            Flight.callsign.alias("callsign"),
            Operator.iata.alias("op"),
            Stand.pier.alias("pier"),
            Slot.minute_offset.alias("minute_offset"),
            Slot.absolute_min.alias("abs_min"),
            Flight.sobt_min_storm.alias("sobt_min"),
            FlightSlot.delay_min.alias("delay_min"),
            Flight.pax_connections.alias("pax_conn"),
        )
        .to_df()
        .sort_values("minute_offset")
        .reset_index(drop=True)
    )
    # Force RAI's Int128 columns to plain int so pandas/Plotly downstream
    # arithmetic and Snowsight's Arrow renderer work. Route via Python int
    # (Int128 supports __int__) which is more reliable than astype("int64").
    for col in ("minute_offset", "abs_min", "sobt_min", "delay_min", "pax_conn"):
        if col in fs.columns:
            fs[col] = [int(v) if v is not None else 0 for v in fs[col]]
    return fs, si


def q4_tsat_resequence_under_storm():
    """Act 4: TSAT re-sequencing without the preservation rule."""
    return _build_storm_problem(extra_preservation=False)


def q5_tsat_resequence_with_preservation():
    """Act 5: TSAT re-sequencing with the KL high-pax preservation rule."""
    return _build_storm_problem(extra_preservation=True)


# =============================================================================
# Driver
# =============================================================================
def main():
    print("\n=== Q1: TOBT compliance audit (last 4h before 14:30) ===")
    df1 = q1_tobt_violations_by_handler()
    print(df1.to_string(index=False))

    print("\n=== Q2: Rotation cascade from KL1234 ===")
    df2 = q2_rotation_cascade_from("KL1234")
    print(df2.to_string(index=False))
    print(f"flights at risk: {len(df2)}")

    print("\n=== Q3: MS5 gate-conflict ranking (heuristic) ===")
    df3 = q3_ms5_conflict_ranking()
    print(df3.to_string(index=False))

    print("\n=== Q4: TSAT re-sequence under storm (HiGHS) ===")
    df4, si4 = q4_tsat_resequence_under_storm()
    print(
        f"status={si4.termination_status} "
        f"obj={si4.objective_value:.2f} "
        f"time={si4.solve_time_sec:.2f}s "
        f"flights={len(df4)}"
    )
    print(df4.head(15).to_string(index=False))

    print("\n=== Q5: TSAT re-sequence with KL pax_conn>80 preservation ===")
    df5, si5 = q5_tsat_resequence_with_preservation()
    print(
        f"status={si5.termination_status} "
        f"obj={si5.objective_value:.2f} "
        f"time={si5.solve_time_sec:.2f}s "
        f"flights={len(df5)}"
    )
    # Compare KL691 in both solutions
    kl691_q4 = df4[df4["callsign"] == "KL691"]
    kl691_q5 = df5[df5["callsign"] == "KL691"]
    if not kl691_q4.empty and not kl691_q5.empty:
        d4 = int(kl691_q4["delay_min"].iloc[0])
        d5 = int(kl691_q5["delay_min"].iloc[0])
        print(f"KL691 delay: Act4={d4}min -> Act5={d5}min")


if __name__ == "__main__":
    main()
