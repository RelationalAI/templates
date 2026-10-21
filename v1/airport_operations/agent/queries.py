"""Pre-canned demo queries exposed to the Cortex agent via QueryCatalog.

Each function is module-level, takes zero arguments, and returns a single
pandas DataFrame OR a dict with ``records`` + ``chart_hint`` (the agent's
generic-tool path accepts either, and dict results pass through unchanged).

Two flavours per question:
- ``<name>`` returns the full ranked table (good for "show me everything").
- ``<name>_chart`` returns a tighter 2-3 column DataFrame plus a chart_hint
  dict, shaped for Snowsight's auto-visualizer. The hint tells the agent
  what kind of chart to suggest in its text reply.
"""
import pandas as pd

from rai_code.manual.demo_queries import (
    q1_tobt_violations_by_handler,
    q2_rotation_cascade_from,
    q3_ms5_conflict_ranking,
    q4_tsat_resequence_under_storm,
    q5_tsat_resequence_with_preservation,
)


def _wrap_chart(df, *, chart_type, x, y, title, color=None):
    """Wrap a DataFrame with a chart hint the agent can mention in its text
    reply. The agent's LLM will see ``chart_hint`` in the tool output and
    propose the visualisation; the user clicks Snowsight's chart icon to
    render it from the same records."""
    hint = {"type": chart_type, "x": x, "y": y, "title": title}
    if color:
        hint["color"] = color
    return {
        "records": df.to_dict(orient="records"),
        "chart_hint": hint,
    }


# =============================================================================
# Q1 - TOBT compliance
# =============================================================================
def tobt_violations_by_handler():
    """Act 1. Per-handler count of TOBT violations in the four-hour window
    before the demo "now" (2026-10-14 14:30). A TOBT violation is any
    DEPARTURE whose actual ready time (ARDT) deviates from the target
    off-block time (TOBT) by more than 5 minutes, per ICAO MS12. Columns:
    handler, violations, avg_deviation_min."""
    return q1_tobt_violations_by_handler()


def tobt_violations_by_handler_chart():
    """Act 1 - chart-friendly variant. Returns ``handler`` and
    ``violations`` only, plus a bar-chart hint. When called, the agent will
    propose 'show this as a bar chart by handler' in its text reply, and
    Snowsight's chart icon yields a one-click bar."""
    df = q1_tobt_violations_by_handler()[["handler", "violations"]]
    return _wrap_chart(
        df,
        chart_type="bar",
        x="handler",
        y="violations",
        title="TOBT violations by handler (4h before 14:30)",
    )


# =============================================================================
# Q2 - Rotation cascade
# =============================================================================
def rotation_cascade_from_kl1234():
    """Act 2. Graph reachability from arrival KL1234 across the union of
    rotation edges (FEEDS_CALLSIGN), slot-block edges, and stand-contention
    edges. Returns the callsigns of downstream flights at risk. The seed
    flight also appears in the reachability result. Columns: from, to."""
    return q2_rotation_cascade_from("KL1234")


# =============================================================================
# Q3 - MS5 gate-conflict ranking
# =============================================================================
def ms5_conflict_ranking():
    """Act 3. Ranks inbound arrivals (TLDT in the next 30 minutes from 14:30)
    by a deterministic MS5 conflict-priority score, not a trained or
    calibrated probability. The score weights time pressure, connecting
    passenger volume, pier proximity, and WTC fit.
    Columns: inbound, current_stand, pier, predicted_landing, pax_conn, wtc,
    p_conflict."""
    return q3_ms5_conflict_ranking()


def ms5_conflict_ranking_chart():
    """Act 3 - chart-friendly variant. Returns ``inbound`` and
    ``p_conflict`` only, plus a horizontal-bar hint. Land the visual on the
    top-N risk ranking."""
    df = q3_ms5_conflict_ranking()[["inbound", "p_conflict"]]
    return _wrap_chart(
        df,
        chart_type="bar_h",
        x="p_conflict",
        y="inbound",
        title="MS5 gate-conflict score (top arrivals)",
    )


# =============================================================================
# Q4 - TSAT re-sequence under storm
# =============================================================================
def tsat_resequence_under_storm():
    """Act 4. Optimized 18L departure sequence for the 47 flights with TSAT
    in the storm window (15:00 to 17:00 on 2026-10-14). Decision variables
    are binary slot-assignments. Objective: minimize total delay weighted by
    (1 + 20 * ATFM penalty). Constraints include one slot per flight, one
    flight per runway minute, no early push, pier capacity, and wake
    separation. CTOT is not a hard constraint. Solved with HiGHS. Returns
    the chosen (flight, minute_offset, delay_min) sequence."""
    df, _ = q4_tsat_resequence_under_storm()
    return df


def tsat_resequence_under_storm_chart():
    """Act 4 - chart-friendly variant. Returns ``callsign``,
    ``minute_offset``, and ``delay_min`` columns shaped for a Gantt-style
    timeline (use the chart icon -> scatter or bar with x=minute_offset).
    The chart hint tells the agent to propose a sequence view."""
    df, _ = q4_tsat_resequence_under_storm()
    df = df[["callsign", "minute_offset", "delay_min", "pax_conn"]]
    return _wrap_chart(
        df,
        chart_type="scatter",
        x="minute_offset",
        y="delay_min",
        title="Act 4 - optimised 18L sequence (storm window)",
        color="pax_conn",
    )


# =============================================================================
# Q5 - TSAT re-sequence with preservation
# =============================================================================
def tsat_resequence_with_preservation():
    """Act 5. Re-solves Act 4 with the operator-supplied rule "no KL flight
    with pax_connections > 80 may be delayed more than 8 minutes from SOBT".
    Returns the new sequence. The baseline already assigns KL691 zero delay,
    so do not claim this rule improves KL691's slot."""
    df, _ = q5_tsat_resequence_with_preservation()
    return df


def tsat_preservation_impact():
    """Compare the baseline and eight-minute KL preservation solves. Returns
    solver statuses, objectives, the number of baseline flights violating the
    cap, count of changed slots, and KL691 delays. The seed baseline already
    satisfies the cap; equal objectives and changed slots represent alternate
    optimal sequences, not a cap-driven improvement."""
    df4, si4 = q4_tsat_resequence_under_storm()
    df5, si5 = q5_tsat_resequence_with_preservation()
    compared = df4[["callsign", "minute_offset"]].merge(
        df5[["callsign", "minute_offset"]],
        on="callsign",
        suffixes=("_base", "_preserved"),
    )
    baseline_breaches = df4[
        (df4["op"] == "KL") & (df4["pax_conn"] > 80) & (df4["delay_min"] > 8)
    ]
    return pd.DataFrame([{
        "baseline_status": str(si4.termination_status),
        "preserved_status": str(si5.termination_status),
        "baseline_objective": float(si4.objective_value),
        "preserved_objective": float(si5.objective_value),
        "baseline_cap_breaches": len(baseline_breaches),
        "changed_slots": int((
            compared["minute_offset_base"] != compared["minute_offset_preserved"]
        ).sum()),
        "kl691_base_delay_min": int(df4.loc[df4.callsign == "KL691", "delay_min"].iloc[0]),
        "kl691_preserved_delay_min": int(df5.loc[df5.callsign == "KL691", "delay_min"].iloc[0]),
    }])


def tsat_act4_vs_act5_chart():
    """Act 4 vs Act 5 delta - chart-friendly. Returns
    ``callsign``, ``delay_act4``, ``delay_act5``, ``delta``. The seed baseline
    already meets the preservation cap; changed slots are alternate optima,
    not evidence that the rule forced a change."""
    df4, _ = q4_tsat_resequence_under_storm()
    df5, _ = q5_tsat_resequence_with_preservation()
    joined = (
        df4[["callsign", "pax_conn", "delay_min"]]
        .rename(columns={"delay_min": "delay_act4"})
        .merge(
            df5[["callsign", "delay_min"]].rename(columns={"delay_min": "delay_act5"}),
            on="callsign",
            how="outer",
        )
        .fillna(0)
    )
    joined["delta"] = (joined["delay_act5"] - joined["delay_act4"]).astype("int64")
    # Only keep the flights whose delay actually changed (or the protected ones).
    moved = joined[joined["delta"] != 0]
    if moved.empty:
        moved = joined.head(15)
    moved = moved.sort_values("delta", ascending=False).head(15)
    return _wrap_chart(
        moved,
        chart_type="bar",
        x="callsign",
        y="delta",
        title="Act 5 vs Act 4 - per-flight delay change (min)",
    )
