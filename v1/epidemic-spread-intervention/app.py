"""Streamlit app for Epidemic Spread Intervention analysis.

This interactive app visualizes the multi-layer exposure graph and the results of
Eigenvector Centrality, Betweenness Centrality, and Louvain Community Detection
using RelationalAI and Streamlit.

Run:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

from relationalai.semantics import where, Integer, Float

from model_setup import create_model, DATA_DIR

# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Epidemic Spread Intervention",
    page_icon="🦠",
    layout="wide"
)

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

@st.cache_resource
def load_model():
    """Load and cache the RelationalAI model."""
    return create_model()


@st.cache_data
def get_results(_model, _exposure_graph):
    """Query and return analysis results for all three metrics."""
    # Run graph algorithms
    eigenvector_centrality = _exposure_graph.eigenvector_centrality()
    betweenness_centrality = _exposure_graph.betweenness_centrality()
    louvain_communities = _exposure_graph.louvain()

    # Variable references
    person = _exposure_graph.Node.ref("person")
    eig_score = Float.ref("eig_score")
    btw_score = Float.ref("btw_score")
    community_id = Integer.ref("community_id")

    # Query eigenvector centrality
    eig_df = where(
        eigenvector_centrality(person, eig_score)
    ).select(
        person.person_id,
        eig_score.alias("eigenvector_score")
    ).to_df().sort_values("eigenvector_score", ascending=False).reset_index(drop=True)
    eig_df.insert(0, "rank", range(1, len(eig_df) + 1))

    # Query betweenness centrality
    btw_df = where(
        betweenness_centrality(person, btw_score)
    ).select(
        person.person_id,
        btw_score.alias("betweenness_score")
    ).to_df().sort_values("betweenness_score", ascending=False).reset_index(drop=True)
    btw_df.insert(0, "rank", range(1, len(btw_df) + 1))

    # Query community assignments
    com_df = where(
        louvain_communities(person, community_id)
    ).select(
        person.person_id,
        community_id.alias("community")
    ).to_df().sort_values("community")

    return eig_df, btw_df, com_df


def create_network_graph(eig_df, btw_df, com_df, contacts_df, visits_df, people_df):
    """Create an interactive exposure network visualization using Plotly."""
    # Merge all metrics onto a single DataFrame keyed by person_id
    merged = eig_df[["person_id", "eigenvector_score"]].merge(
        btw_df[["person_id", "betweenness_score"]], on="person_id", how="outer"
    ).merge(
        com_df[["person_id", "community"]], on="person_id", how="outer"
    )
    merged["community"] = merged["community"].fillna(-1).astype(int)

    # Circular layout — spread communities around the ring
    n = len(merged)
    # Sort by community so community members cluster together
    merged = merged.sort_values("community").reset_index(drop=True)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)

    node_positions = {}
    for i, row in merged.iterrows():
        radius = 5 + row["eigenvector_score"] * 3
        node_positions[row["person_id"]] = (
            radius * np.cos(angles[i]),
            radius * np.sin(angles[i])
        )

    # Build edge set from direct contacts and co-location (visits)
    # Use direct_contacts as the primary edge source for visualization
    edge_x, edge_y = [], []
    seen_edges = set()
    for _, row in contacts_df.iterrows():
        a, b = row["person_a"], row["person_b"]
        key = tuple(sorted([a, b]))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        if a in node_positions and b in node_positions:
            x0, y0 = node_positions[a]
            x1, y1 = node_positions[b]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.7, color="#aaa"),
        hoverinfo="none",
        mode="lines",
        showlegend=False
    )

    # Assign a color per community
    community_ids = sorted(merged["community"].unique())
    palette = [
        "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990"
    ]
    community_color = {cid: palette[i % len(palette)] for i, cid in enumerate(community_ids)}

    # Normalize eigenvector scores for node size
    eig_min = merged["eigenvector_score"].min()
    eig_max = merged["eigenvector_score"].max()
    eig_range = eig_max - eig_min if eig_max > eig_min else 1

    # One trace per community for legend
    node_traces = []
    for cid in community_ids:
        group = merged[merged["community"] == cid]
        node_x, node_y, node_text, node_size = [], [], [], []
        for _, row in group.iterrows():
            pid = row["person_id"]
            if pid not in node_positions:
                continue
            x, y = node_positions[pid]
            node_x.append(x)
            node_y.append(y)
            eig = row["eigenvector_score"]
            btw = row["betweenness_score"]
            node_text.append(
                f"<b>{pid}</b><br>"
                f"Community: {cid}<br>"
                f"Eigenvector Score: {eig:.4f}<br>"
                f"Betweenness Score: {btw:.4f}"
            )
            normalized = (eig - eig_min) / eig_range
            node_size.append(12 + normalized * 30)

        node_traces.append(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            hoverinfo="text",
            hovertext=node_text,
            text=[row["person_id"] for _, row in group.iterrows() if row["person_id"] in node_positions],
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                color=community_color[cid],
                size=node_size,
                line=dict(width=1.5, color="white")
            ),
            name=f"Community {cid}",
            showlegend=True
        ))

    fig = go.Figure(
        data=[edge_trace] + node_traces,
        layout=go.Layout(
            title="Exposure Network — nodes colored by Louvain community, sized by Eigenvector Centrality",
            title_font_size=14,
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=50),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            height=650
        )
    )
    return fig


# --------------------------------------------------
# Main app
# --------------------------------------------------

def main():
    st.title("🦠 Epidemic Spread Intervention")
    st.markdown("**Multi-Layer Graph Analysis: Eigenvector Centrality · Betweenness Centrality · Louvain Communities**")

    # Load model and data
    with st.spinner("Loading RelationalAI model and analyzing exposure network..."):
        model, Person, Location, DirectContact, Visit, ColocationContact, ExposureEdge, exposure_graph = load_model()
        eig_df, btw_df, com_df = get_results(model, exposure_graph)
        contacts_df = pd.read_csv(DATA_DIR / "direct_contacts.csv")
        visits_df = pd.read_csv(DATA_DIR / "visits.csv")
        people_df = pd.read_csv(DATA_DIR / "people.csv")
        locations_df = pd.read_csv(DATA_DIR / "locations.csv")

    # Sidebar summary
    st.sidebar.header("📊 Network Summary")
    st.sidebar.metric("People in Network", len(people_df))
    st.sidebar.metric("Locations", len(locations_df))
    st.sidebar.metric("Direct Contacts", len(contacts_df))
    st.sidebar.metric("Louvain Communities", com_df["community"].nunique())
    st.sidebar.divider()

    top_spreader = eig_df.iloc[0]
    st.sidebar.markdown("**Top Super-Spreader (Eigenvector)**")
    st.sidebar.write(top_spreader["person_id"])
    st.sidebar.metric("Eigenvector Score", f"{top_spreader['eigenvector_score']:.4f}")

    top_bridge = btw_df.iloc[0]
    st.sidebar.markdown("**Top Bridge Individual (Betweenness)**")
    st.sidebar.write(top_bridge["person_id"])
    st.sidebar.metric("Betweenness Score", f"{top_bridge['betweenness_score']:.4f}")

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Overview",
        "🗺️ Network Visualization",
        "📋 Rankings",
        "🎯 Intervention Priorities"
    ])

    with tab1:
        st.header("Overview")
        st.markdown("""
        This analysis uses a **multi-layer exposure graph** to model how disease can spread through a population.

        Two types of connections are fused into a single weighted network:
        - **Direct contacts**: Face-to-face interactions with known frequency and duration
        - **Co-location contacts**: Indirect exposure from visiting the same locations

        Edge weights incorporate each person's **base susceptibility** (derived from vaccination level and comorbidity score),
        so the graph reflects actual transmission potential rather than just social proximity.

        Three graph algorithms identify different intervention priorities:
        - **Eigenvector Centrality** — Super-spreaders whose influence is amplified across multiple layers
        - **Betweenness Centrality** — Bridge individuals whose removal fractures the spread network
        - **Louvain Community Detection** — Tight-knit transmission clusters for localized containment
        """)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔝 Top 5 Super-Spreaders (Eigenvector Centrality)")
            top_eig = eig_df.head(5)[["rank", "person_id", "eigenvector_score"]].copy()
            top_eig["eigenvector_score"] = top_eig["eigenvector_score"].round(4)
            st.dataframe(top_eig, hide_index=True, use_container_width=True)

        with col2:
            st.subheader("🌉 Top 5 Bridge Individuals (Betweenness Centrality)")
            top_btw = btw_df.head(5)[["rank", "person_id", "betweenness_score"]].copy()
            top_btw["betweenness_score"] = top_btw["betweenness_score"].round(4)
            st.dataframe(top_btw, hide_index=True, use_container_width=True)

    with tab2:
        st.header("Network Visualization")
        st.markdown(
            "Each node is a person in the exposure network. "
            "**Color** = Louvain community. **Size** = Eigenvector Centrality score. "
            "**Edges** = direct contacts. Hover for details."
        )
        fig = create_network_graph(eig_df, btw_df, com_df, contacts_df, visits_df, people_df)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Detailed Rankings")

        metric = st.selectbox(
            "Select metric to rank by",
            ["Eigenvector Centrality (Super-Spreaders)", "Betweenness Centrality (Bridge Individuals)", "Community (Transmission Clusters)"]
        )

        if metric == "Eigenvector Centrality (Super-Spreaders)":
            st.markdown("**Eigenvector Centrality** measures influence amplified across the network. High-scoring individuals have connections that are themselves highly connected.")
            display_df = eig_df.copy()
            display_df["eigenvector_score"] = display_df["eigenvector_score"].round(4)
            st.dataframe(display_df, hide_index=True, use_container_width=True, height=450)

            csv = display_df.to_csv(index=False)
            st.download_button("📥 Download as CSV", data=csv, file_name="eigenvector_centrality.csv", mime="text/csv")

        elif metric == "Betweenness Centrality (Bridge Individuals)":
            st.markdown("**Betweenness Centrality** measures how often a person lies on the shortest path between two others. High scores indicate bridge individuals whose removal fragments the spread network.")
            display_df = btw_df.copy()
            display_df["betweenness_score"] = display_df["betweenness_score"].round(4)
            st.dataframe(display_df, hide_index=True, use_container_width=True, height=450)

            csv = display_df.to_csv(index=False)
            st.download_button("📥 Download as CSV", data=csv, file_name="betweenness_centrality.csv", mime="text/csv")

        else:
            st.markdown("**Louvain Community Detection** groups people into tightly-connected clusters. Clusters with many high-susceptibility members are the highest-risk transmission pools.")
            display_df = com_df.merge(
                eig_df[["person_id", "eigenvector_score"]], on="person_id", how="left"
            ).merge(
                btw_df[["person_id", "betweenness_score"]], on="person_id", how="left"
            ).sort_values(["community", "eigenvector_score"], ascending=[True, False])
            display_df["eigenvector_score"] = display_df["eigenvector_score"].round(4)
            display_df["betweenness_score"] = display_df["betweenness_score"].round(4)
            st.dataframe(display_df, hide_index=True, use_container_width=True, height=450)

            csv = display_df.to_csv(index=False)
            st.download_button("📥 Download as CSV", data=csv, file_name="community_assignments.csv", mime="text/csv")

    with tab4:
        st.header("Intervention Priorities")

        st.markdown("""
        Use all three metrics together to identify the most critical intervention targets.
        Individuals who rank highly across multiple metrics are the highest-priority candidates.
        """)

        # Cross-reference: find people in top quartile for both centrality metrics
        eig_threshold = eig_df["eigenvector_score"].quantile(0.75)
        btw_threshold = btw_df["betweenness_score"].quantile(0.75)

        cross_ref = eig_df[["person_id", "eigenvector_score"]].merge(
            btw_df[["person_id", "betweenness_score"]], on="person_id", how="outer"
        ).merge(
            com_df[["person_id", "community"]], on="person_id", how="left"
        )

        high_eig = cross_ref["eigenvector_score"] >= eig_threshold
        high_btw = cross_ref["betweenness_score"] >= btw_threshold

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("💉 Vaccination Priority")
            st.markdown("High Eigenvector Centrality — most influential spreaders")
            vax_targets = cross_ref[high_eig].sort_values("eigenvector_score", ascending=False)
            for _, row in vax_targets.iterrows():
                with st.expander(f"**{row['person_id']}** (Community {int(row['community']) if pd.notna(row['community']) else '?'})"):
                    st.metric("Eigenvector Score", f"{row['eigenvector_score']:.4f}")
                    btw_val = row["betweenness_score"]
                    st.metric("Betweenness Score", f"{btw_val:.4f}" if pd.notna(btw_val) else "N/A")
                    if pd.notna(btw_val) and btw_val >= btw_threshold:
                        st.warning("Also a bridge individual — highest priority target")

        with col2:
            st.subheader("🚧 Isolation Priority")
            st.markdown("High Betweenness Centrality — removing these fractures spread routes")
            iso_targets = cross_ref[high_btw].sort_values("betweenness_score", ascending=False)
            for _, row in iso_targets.iterrows():
                with st.expander(f"**{row['person_id']}** (Community {int(row['community']) if pd.notna(row['community']) else '?'})"):
                    eig_val = row["eigenvector_score"]
                    st.metric("Eigenvector Score", f"{eig_val:.4f}" if pd.notna(eig_val) else "N/A")
                    st.metric("Betweenness Score", f"{row['betweenness_score']:.4f}")
                    if pd.notna(eig_val) and eig_val >= eig_threshold:
                        st.warning("Also a super-spreader — highest priority target")

        with col3:
            st.subheader("🏘️ Cluster Interventions")
            st.markdown("Community sizes — target largest clusters for localized containment")
            cluster_sizes = com_df.groupby("community").size().reset_index(name="members").sort_values("members", ascending=False)
            for _, row in cluster_sizes.iterrows():
                cid = int(row["community"])
                size = int(row["members"])
                members = com_df[com_df["community"] == cid]["person_id"].tolist()
                with st.expander(f"**Community {cid}** — {size} members"):
                    st.write(", ".join(members))
                    # Highlight if any high-priority individuals are in this cluster
                    priority_in_cluster = cross_ref[
                        (cross_ref["community"] == cid) & (high_eig | high_btw)
                    ]["person_id"].tolist()
                    if priority_in_cluster:
                        st.info(f"Contains priority targets: {', '.join(priority_in_cluster)}")

    st.markdown("---")
    st.markdown("*Built with RelationalAI, Streamlit, and Plotly*")


if __name__ == "__main__":
    main()
