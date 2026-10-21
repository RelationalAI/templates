"""Generate static PNG figures of each act's expected result.

Used to populate the result cards in RUNNING.html.

Run from project root:
    .venv/bin/python build/generate_demo_figures.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from plotly.subplots import make_subplots

# Make the model importable from project root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Disarm PyRel's event-loop guard before any RAI imports.
import relationalai.client as _ra_client  # noqa: E402
import relationalai.services.reasoners.client as _ra_reasoners_client  # noqa: E402

def _noop(*_a, **_k):
    return None

_ra_client.raise_if_running_event_loop = _noop
_ra_reasoners_client.raise_if_running_event_loop = _noop

from rai_code.manual.eham_acdm import (  # noqa: E402
    Flight,
    StormWindowDeparture,
    model,
    feeds_callsign,
    slot_blocks,
    shares_stand,
)
from rai_code.manual.demo_queries import (  # noqa: E402
    q1_tobt_violations_by_handler,
    q2_rotation_cascade_from,
    q3_ms5_conflict_ranking,
    q4_tsat_resequence_under_storm,
    q5_tsat_resequence_with_preservation,
)

OUT = ROOT / "build" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Q4/Q5 share the same Problem; each solve populates its own decision
# property exactly once. Cache results so we only solve each Act once.
_CACHE: dict = {}


def _q4():
    if "q4" not in _CACHE:
        _CACHE["q4"] = q4_tsat_resequence_under_storm()
    return _CACHE["q4"]


def _q5():
    if "q5" not in _CACHE:
        _CACHE["q5"] = q5_tsat_resequence_with_preservation()
    return _CACHE["q5"]


def _write(fig: go.Figure, name: str, *, w: int = 920, h: int = 460):
    path = OUT / name
    fig.write_image(str(path), width=w, height=h, scale=2)
    print(f"  wrote {path.relative_to(ROOT)} ({os.path.getsize(path):,} bytes)")


# =============================================================================
# Act 1 - TOBT violations by handler
# =============================================================================
def fig_act1():
    df = q1_tobt_violations_by_handler()
    fig = px.bar(
        df,
        x="handler",
        y="violations",
        color="avg_deviation_min",
        color_continuous_scale="RdBu_r",
        color_continuous_midpoint=0,
        text="violations",
        title="Act 1 - TOBT violations by handler (4h before 14:30)",
        labels={"avg_deviation_min": "avg deviation (min)"},
    )
    fig.update_traces(textposition="outside", textfont=dict(size=14, color="#222"))
    fig.update_layout(
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Helvetica Neue, Arial, sans-serif", size=13, color="#222"),
        xaxis=dict(title="handler", showgrid=False, linecolor="#cccccc"),
        yaxis=dict(title="violation count", gridcolor="#eeeeee", range=[0, df["violations"].max() * 1.25]),
        margin=dict(l=60, r=40, t=70, b=50),
    )
    _write(fig, "act1_tobt_violations.png")


# =============================================================================
# Act 2 - KL1234 cascade graph (multi-relational, colored by edge kind, sized by pax)
# =============================================================================
def fig_act2():
    # Pull cascade callsigns
    df_cascade = q2_rotation_cascade_from("KL1234")
    cascade_set = set(df_cascade["to"])

    # Edge sets from the model
    src, dst = Flight.ref(), Flight.ref()
    rot = (
        model.where(feeds_callsign(src, dst))
        .select(src.callsign.alias("src"), dst.callsign.alias("dst"))
        .to_df()
    )
    rot["kind"] = "rotation"

    src, dst = Flight.ref(), Flight.ref()
    sb = (
        model.where(slot_blocks(src, dst))
        .select(src.callsign.alias("src"), dst.callsign.alias("dst"))
        .to_df()
    )
    sb["kind"] = "slot_block"

    src, dst = Flight.ref(), Flight.ref()
    ss = (
        model.where(shares_stand(src, dst), src.sobt < dst.sobt)
        .select(src.callsign.alias("src"), dst.callsign.alias("dst"))
        .to_df()
    )
    ss["kind"] = "stand"

    all_edges = pd.concat([rot, sb, ss], ignore_index=True)
    edges = all_edges[
        all_edges["src"].isin(cascade_set) & all_edges["dst"].isin(cascade_set)
    ].drop_duplicates(subset=["src", "dst", "kind"])

    # Node metadata (operator, pax_connections, flight_type, stand)
    df_nodes = (
        model.where(Flight.callsign.in_(list(cascade_set)) if False else (Flight.callsign == Flight.callsign))
        .select(
            Flight.callsign.alias("callsign"),
            Flight.flight_type.alias("flight_type"),
            Flight.pax_connections.alias("pax_conn"),
        )
        .to_df()
    )
    nodes = df_nodes[df_nodes["callsign"].isin(cascade_set)].copy()
    nodes["pax_conn"] = nodes["pax_conn"].fillna(0).astype("int64")
    nodes["operator"] = nodes["callsign"].str.extract(r"^([A-Z]{2,3})")

    # Layout via networkx (using only edge endpoints actually present)
    G = nx.DiGraph()
    for c in cascade_set:
        G.add_node(c)
    for _, e in edges.iterrows():
        G.add_edge(e["src"], e["dst"], kind=e["kind"])
    pos = nx.spring_layout(G, seed=42, k=1.7)

    # Build edge traces, one per kind, colored + styled
    edge_styles = {
        "rotation":   {"color": "#1f77b4", "dash": "solid",     "width": 3.5, "label": "rotation"},
        "slot_block": {"color": "#d62728", "dash": "solid",     "width": 3.5, "label": "slot_block"},
        "stand":      {"color": "#8a4fbe", "dash": "dot",       "width": 2.0, "label": "stand"},
    }
    edge_traces = []
    # Annotations for edge labels and arrowheads
    arrow_annotations = []
    for kind, style in edge_styles.items():
        xs, ys = [], []
        for u, v, data in G.edges(data=True):
            if data.get("kind") != kind:
                continue
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
            # Arrowhead per edge
            arrow_annotations.append(dict(
                ax=x0, ay=y0, x=x1, y=y1,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=1.4,
                arrowcolor=style["color"], standoff=18, startstandoff=18,
                opacity=0.85,
            ))
        if xs:
            edge_traces.append(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(width=style["width"], color=style["color"], dash=style["dash"]),
                hoverinfo="none", name=style["label"], opacity=0.85,
            ))

    # Color nodes by carrier; size by max(pax_conn, 40) so even pax=0 nodes are visible.
    op_palette = {"KL": "#0064c8", "HV": "#1aa055", "AF": "#9c2a2a"}
    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_text = list(G.nodes())
    op = [(nodes.loc[nodes["callsign"] == n, "operator"].iloc[0] if (nodes["callsign"] == n).any() else "?")
          for n in node_text]
    pax = [int(nodes.loc[nodes["callsign"] == n, "pax_conn"].iloc[0]) if (nodes["callsign"] == n).any() else 0
           for n in node_text]
    ftype = [(nodes.loc[nodes["callsign"] == n, "flight_type"].iloc[0] if (nodes["callsign"] == n).any() else "?")
             for n in node_text]
    sizes = [max(38, min(82, 38 + p * 0.30)) for p in pax]
    node_color = [op_palette.get(o, "#999999") for o in op]
    # Seed (KL1234) gets a gold ring; arrivals get a thicker border than departures
    border_color = [
        "#ffb000" if n == "KL1234" else ("#222222" if ft == "DEPARTURE" else "#1a1a1a")
        for n, ft in zip(node_text, ftype)
    ]
    border_width = [4 if n == "KL1234" else (2 if ft == "DEPARTURE" else 3) for n, ft in zip(node_text, ftype)]

    hover = [
        f"<b>{n}</b><br>{ft}<br>operator: {o}<br>pax_conn: {p}"
        for n, ft, o, p in zip(node_text, ftype, op, pax)
    ]
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=sizes, color=node_color, line=dict(width=border_width, color=border_color)),
        text=node_text, textposition="middle center",
        textfont=dict(size=11, color="#ffffff", family="Helvetica Neue, Arial, sans-serif"),
        name="flight", hoverinfo="text", hovertext=hover,
    )

    # Carrier legend (proxy traces)
    carrier_legend = []
    for op_code, color in op_palette.items():
        carrier_legend.append(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=14, color=color, line=dict(width=1, color="#222")),
            name=op_code, showlegend=True,
        ))

    fig = go.Figure(data=edge_traces + [node_trace] + carrier_legend)
    fig.update_layout(
        title=dict(text="Act 2 - KL1234 rotation cascade (node size = pax connections, color = carrier)",
                   font=dict(size=15)),
        annotations=arrow_annotations + [
            dict(x=0.02, y=-0.16, xref="paper", yref="paper", showarrow=False,
                 text=("<b>Edges:</b> "
                       "<span style='color:#1f77b4'>━━ rotation</span> &nbsp; "
                       "<span style='color:#d62728'>━━ slot_block</span> &nbsp; "
                       "<span style='color:#8a4fbe'>┄┄ stand_share</span> &nbsp; | &nbsp; "
                       "<b>Seed:</b> gold ring (KL1234) &nbsp; | &nbsp; "
                       "<b>Border:</b> thick = arrival, thin = departure"),
                 font=dict(size=11, color="#555")),
        ],
        showlegend=True, legend=dict(orientation="h", x=0.5, y=1.10, xanchor="center"),
        height=520, margin=dict(l=10, r=10, t=70, b=70),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#222"),
    )
    _write(fig, "act2_cascade_graph.png", w=960, h=560)


# =============================================================================
# Act 3 - MS5 ranking
# =============================================================================
def fig_act3():
    df = q3_ms5_conflict_ranking()
    # Highlight the talk-track 5 named flights
    named = {"DL0036", "KL0691", "AF1641", "BA0432", "KL1234"}
    df = df.copy()
    df["highlight"] = df["inbound"].apply(lambda x: "talk-track" if x in named else "other")
    fig = px.bar(
        df.head(11),
        x="p_conflict",
        y="inbound",
        orientation="h",
        color="highlight",
        color_discrete_map={"talk-track": "#d97a4a", "other": "#9ec5e8"},
        hover_data=["current_stand", "pax_conn", "wtc", "minutes_to_land"],
        text="p_conflict",
        title="Act 3 - MS5 gate-conflict ranking (talk-track 5 highlighted)",
    )
    fig.update_traces(texttemplate="%{x:.2f}", textposition="outside")
    fig.update_layout(
        height=480,
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis=dict(categoryorder="total ascending", title=None, automargin=True),
        xaxis=dict(title="ms5_score", gridcolor="#eeeeee", range=[0, df["p_conflict"].max() * 1.15]),
        legend=dict(title="", orientation="h", x=0.5, y=1.06, xanchor="center"),
        margin=dict(l=80, r=60, t=80, b=50),
        font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#222"),
    )
    _write(fig, "act3_ms5_ranking.png", w=960, h=520)


# =============================================================================
# Act 4 - TSAT re-sequence Gantt
# =============================================================================
def _storm_original_tsat_offsets() -> pd.DataFrame:
    """Original storm-window TSAT offsets, in minutes after 15:00."""
    df = (
        model.where(StormWindowDeparture(Flight))
        .select(
            Flight.callsign.alias("callsign"),
            Flight.tsat.alias("tsat"),
        )
        .to_df()
    )
    storm_start = pd.Timestamp("2026-10-14 15:00")
    tsat = pd.to_datetime(df["tsat"])
    if getattr(tsat.dt, "tz", None) is not None:
        tsat = tsat.dt.tz_convert(None)
    df["original_offset"] = (
        (tsat - storm_start).dt.total_seconds().round().astype("int64") // 60
    ).clip(0, 119)
    return df[["callsign", "original_offset"]]


def fig_act4():
    df, _si = _q4()
    df = df.copy().merge(_storm_original_tsat_offsets(), on="callsign", how="left")
    df["original_offset"] = df["original_offset"].fillna(df["sobt_min"] - 900).astype("int64")
    df["same_pier_same_minute"] = (
        df.groupby(["pier", "original_offset"])["callsign"]
        .transform("count")
        .astype("int64")
    )
    df["bar_len"] = 1

    order = df.sort_values(["minute_offset", "callsign"])["callsign"].tolist()
    df = df.set_index("callsign").loc[order].reset_index()

    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.035,
        subplot_titles=(
            "Original TSAT requests",
            "Optimized 18L sequence",
        ),
    )
    fig.add_trace(
        go.Bar(
            x=df["bar_len"],
            base=df["original_offset"],
            y=df["callsign"],
            orientation="h",
            marker=dict(
                color=df["same_pier_same_minute"],
                coloraxis="coloraxis",
                line=dict(color="rgba(40,40,40,0.35)", width=0.5),
            ),
            customdata=df[["op", "pier", "pax_conn", "original_offset", "same_pier_same_minute"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "op=%{customdata[0]} pier=%{customdata[1]} pax_conn=%{customdata[2]}<br>"
                "original TSAT offset=%{customdata[3]} min<br>"
                "same-pier same-minute pushes=%{customdata[4]}"
                "<extra></extra>"
            ),
            name="original TSAT",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=df["bar_len"],
            base=df["minute_offset"],
            y=df["callsign"],
            orientation="h",
            marker=dict(
                color=df["delay_min"],
                coloraxis="coloraxis2",
                line=dict(color="rgba(40,40,40,0.35)", width=0.5),
            ),
            customdata=df[["op", "pier", "pax_conn", "minute_offset", "delay_min"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "op=%{customdata[0]} pier=%{customdata[1]} pax_conn=%{customdata[2]}<br>"
                "optimized offset=%{customdata[3]} min<br>"
                "delay vs SOBT=%{customdata[4]} min"
                "<extra></extra>"
            ),
            name="optimized slot",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    tickvals = [0, 30, 60, 90, 120]
    ticktext = ["15:00", "15:30", "16:00", "16:30", "17:00"]
    fig.update_xaxes(
        title="time",
        range=[-2, 122],
        tickvals=tickvals,
        ticktext=ticktext,
        gridcolor="#eeeeee",
        zeroline=False,
        row=1,
        col=1,
    )
    fig.update_xaxes(
        title="time",
        range=[-2, 122],
        tickvals=tickvals,
        ticktext=ticktext,
        gridcolor="#eeeeee",
        zeroline=False,
        row=1,
        col=2,
    )
    fig.update_yaxes(
        title=None,
        categoryorder="array",
        categoryarray=list(reversed(order)),
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title=None,
        categoryorder="array",
        categoryarray=list(reversed(order)),
        row=1,
        col=2,
    )
    fig.update_layout(
        height=900,
        barmode="overlay",
        plot_bgcolor="white",
        paper_bgcolor="white",
        title=dict(
            text="Act 4 - before/after TSAT re-sequencing under storm (15:00 - 17:00)",
            font=dict(size=15),
        ),
        coloraxis=dict(
            colorscale="OrRd",
            cmin=1,
            colorbar=dict(
                title="same pier<br>same min",
                x=0.465,
                y=0.78,
                len=0.32,
                thickness=12,
            ),
        ),
        coloraxis2=dict(
            colorscale="RdYlGn_r",
            cmin=0,
            cmax=max(1, int(df["delay_min"].max())),
            colorbar=dict(
                title="delay<br>min",
                x=1.02,
                y=0.78,
                len=0.32,
                thickness=12,
            ),
        ),
        font=dict(family="Helvetica Neue, Arial, sans-serif", size=11, color="#222"),
        margin=dict(l=80, r=90, t=85, b=55),
        annotations=[
            *fig.layout.annotations,
            dict(
                x=0.25,
                y=-0.08,
                xref="paper",
                yref="paper",
                showarrow=False,
                text="Before: clustered TSAT requests expose same-pier pushback pressure.",
                font=dict(size=11, color="#555"),
            ),
            dict(
                x=0.75,
                y=-0.08,
                xref="paper",
                yref="paper",
                showarrow=False,
                text="After: one departure slot per minute with wake and pier constraints enforced.",
                font=dict(size=11, color="#555"),
            ),
        ],
    )
    _write(fig, "act4_tsat_gantt.png", w=1320, h=920)


# =============================================================================
# Act 5 - Act 4 vs Act 5 delay delta
# =============================================================================
def fig_act5():
    df4, _ = _q4()
    df5, _ = _q5()
    joined = (
        df4[["callsign", "pax_conn", "delay_min"]]
        .rename(columns={"delay_min": "act4"})
        .merge(
            df5[["callsign", "delay_min"]].rename(columns={"delay_min": "act5"}),
            on="callsign", how="outer",
        )
        .fillna(0)
    )
    joined["delta"] = (joined["act5"] - joined["act4"]).astype("int64")
    # Take the rows that actually moved (delta != 0), plus the protected KL691.
    moved = joined[(joined["delta"] != 0) | (joined["callsign"] == "KL691")]
    moved = moved.sort_values("delta")
    long = moved.melt(id_vars=["callsign", "pax_conn"], value_vars=["act4", "act5"],
                      var_name="solve", value_name="delay_min")
    fig = px.bar(
        long,
        x="callsign", y="delay_min", color="solve", barmode="group",
        color_discrete_map={"act4": "#9ec5e8", "act5": "#5cb85c"},
        hover_data=["pax_conn"],
        title="Act 5 - per-flight delay: Act 4 (baseline) vs Act 5 (with preservation rule)",
    )
    # Highlight KL691 with a vertical band
    if "KL691" in moved["callsign"].values:
        fig.add_vrect(x0=-0.5, x1=0.5, fillcolor="#ffe6cc", opacity=0.3, line_width=0,
                      annotation_text="KL691 (137 pax)", annotation_position="top left",
                      row="all", col="all")
    fig.update_layout(
        height=460,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(title="callsign", tickangle=-45, gridcolor="#eeeeee"),
        yaxis=dict(title="delay (min vs SOBT)", gridcolor="#eeeeee"),
        legend=dict(orientation="h", x=0.5, y=1.07, xanchor="center", title=""),
        font=dict(family="Helvetica Neue, Arial, sans-serif", size=12, color="#222"),
        margin=dict(l=60, r=40, t=80, b=80),
    )
    _write(fig, "act5_preservation_delta.png", w=960, h=520)


# =============================================================================
def main():
    print("=== generating demo figures ===")
    print(f"output dir: {OUT}")
    print()
    fig_act1()
    fig_act2()
    fig_act3()
    fig_act4()
    fig_act5()
    print()
    print("done.")


if __name__ == "__main__":
    main()
