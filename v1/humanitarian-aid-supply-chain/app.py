"""Streamlit app for Humanitarian Aid Supply Chain Network analysis.

This interactive app visualizes the PageRank and Degree Centrality analysis
from the humanitarian aid supply chain network using RelationalAI and Streamlit.

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
    page_title="Humanitarian Aid Supply Chain Network",
    page_icon="🚁",
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
def get_results(_model, _graph, _DistributionPoint, _SupplyRoute):
    """Query and return analysis results."""
    # Calculate graph metrics
    pagerank = _graph.pagerank(damping_factor=0.85, tolerance=1e-6, max_iter=100)
    degree_centrality = _graph.degree_centrality()
    indegree = _graph.indegree()
    outdegree = _graph.outdegree()

    # Create variable references
    point = _graph.Node.ref("point")
    pr_score = Float.ref("pr_score")
    dc_score = Float.ref("dc_score")
    in_routes = Integer.ref("in_routes")
    out_routes = Integer.ref("out_routes")

    # Query results
    results = where(
        pagerank(point, pr_score),
        degree_centrality(point, dc_score),
        indegree(point, in_routes),
        outdegree(point, out_routes)
    ).select(
        point.id,
        point.name,
        point.type,
        point.region,
        point.capacity,
        point.population_served,
        pr_score.alias("pagerank"),
        dc_score.alias("degree_centrality"),
        in_routes.alias("incoming_routes"),
        out_routes.alias("outgoing_routes")
    ).to_df()

    # Convert to standard types
    results['incoming_routes'] = results['incoming_routes'].astype(int)
    results['outgoing_routes'] = results['outgoing_routes'].astype(int)
    results['capacity'] = results['capacity'].astype(int)
    results['population_served'] = results['population_served'].astype(int)
    results['total_routes'] = results['incoming_routes'] + results['outgoing_routes']

    return results


def create_network_graph(results, routes_df):
    """Create an interactive network visualization using Plotly."""
    # Create a simple circular layout
    n_points = len(results)
    angles = np.linspace(0, 2 * np.pi, n_points, endpoint=False)

    # Position nodes in a circle with some variation based on PageRank
    node_positions = {}
    for i, (_, point) in enumerate(results.iterrows()):
        # Use PageRank to adjust radius slightly (more important = further out)
        radius_offset = point['pagerank'] * 2
        radius = 5 + radius_offset
        x = radius * np.cos(angles[i])
        y = radius * np.sin(angles[i])
        node_positions[point['id']] = (x, y)

    # Create edges
    edge_x = []
    edge_y = []
    for _, route in routes_df.iterrows():
        if route['from_point_id'] in node_positions and route['to_point_id'] in node_positions:
            x0, y0 = node_positions[route['from_point_id']]
            x1, y1 = node_positions[route['to_point_id']]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines',
        showlegend=False
    )

    # Create node traces (separate by strategic category for color coding)
    pr_threshold = results['pagerank'].quantile(0.70)
    dc_threshold = results['degree_centrality'].quantile(0.70)

    node_traces = []

    # Critical Coordination Hubs
    critical = results[
        (results['pagerank'] >= pr_threshold) &
        (results['degree_centrality'] >= dc_threshold)
    ]
    if len(critical) > 0:
        node_traces.append(create_node_trace(critical, node_positions, 'red', 'Critical Coordination Hubs'))

    # Influential Endpoints
    influential = results[
        (results['pagerank'] >= pr_threshold) &
        (results['degree_centrality'] < dc_threshold)
    ]
    if len(influential) > 0:
        node_traces.append(create_node_trace(influential, node_positions, 'orange', 'Influential Endpoints'))

    # Network Connectors
    connectors = results[
        (results['pagerank'] < pr_threshold) &
        (results['degree_centrality'] >= dc_threshold)
    ]
    if len(connectors) > 0:
        node_traces.append(create_node_trace(connectors, node_positions, 'yellow', 'Network Connectors'))

    # Regular nodes
    regular = results[
        (results['pagerank'] < pr_threshold) &
        (results['degree_centrality'] < dc_threshold)
    ]
    if len(regular) > 0:
        node_traces.append(create_node_trace(regular, node_positions, 'lightblue', 'Regular Distribution Points'))

    # Create figure
    fig = go.Figure(data=[edge_trace] + node_traces,
                    layout=go.Layout(
                        title='Humanitarian Aid Supply Chain Network',
                        title_font_size=16,
                        showlegend=True,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=700
                    ))

    return fig


def create_node_trace(df, node_positions, color, name):
    """Create a Plotly scatter trace for a set of nodes."""
    node_x = []
    node_y = []
    node_text = []
    node_size = []

    for _, point in df.iterrows():
        if point['id'] in node_positions:
            x, y = node_positions[point['id']]
            node_x.append(x)
            node_y.append(y)

            # Create hover text
            text = (f"<b>{point['name']}</b><br>"
                   f"Type: {point['type']}<br>"
                   f"Region: {point['region']}<br>"
                   f"PageRank: {point['pagerank']:.4f}<br>"
                   f"Degree Centrality: {point['degree_centrality']:.4f}<br>"
                   f"Capacity: {point['capacity']:,}<br>"
                   f"Serves: {point['population_served']:,} people<br>"
                   f"Routes: {point['total_routes']}")
            node_text.append(text)

            # Size based on total routes
            node_size.append(10 + point['total_routes'] * 3)

    return go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[],  # No labels on the graph itself
        hovertext=node_text,
        marker=dict(
            showscale=False,
            color=color,
            size=node_size,
            line_width=2,
            line_color='white'
        ),
        name=name,
        showlegend=True
    )


# --------------------------------------------------
# Main app
# --------------------------------------------------

def main():
    st.title("🚁 Humanitarian Aid Supply Chain Network")
    st.markdown("**PageRank & Degree Centrality Analysis**")

    # Load data
    with st.spinner("Loading RelationalAI model and analyzing network..."):
        model, graph, DistributionPoint, SupplyRoute = load_model()
        results = get_results(model, graph, DistributionPoint, SupplyRoute)
        routes_df = pd.read_csv(DATA_DIR / "supply_routes.csv")

    # Sidebar with summary stats
    st.sidebar.header("📊 Network Summary")
    st.sidebar.metric("Total Distribution Points", len(results))
    st.sidebar.metric("Total Supply Routes", len(routes_df))
    st.sidebar.metric("Total Population Served", f"{results['population_served'].sum():,}")
    st.sidebar.metric("Total Network Capacity", f"{results['capacity'].sum():,} units")
    st.sidebar.divider()

    most_influential = results.loc[results['pagerank'].idxmax()]
    st.sidebar.markdown("**Most Influential (PageRank)**")
    st.sidebar.write(f"{most_influential['name']}")
    st.sidebar.metric("PageRank Score", f"{most_influential['pagerank']:.4f}")

    most_connected = results.loc[results['degree_centrality'].idxmax()]
    st.sidebar.markdown("**Most Connected (Degree Centrality)**")
    st.sidebar.write(f"{most_connected['name']}")
    st.sidebar.metric("Degree Centrality Score", f"{most_connected['degree_centrality']:.4f}")

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "🗺️ Network Visualization", "📋 Detailed Rankings", "🎯 Strategic Analysis"])

    with tab1:
        st.header("Overview")
        st.markdown("""
        This analysis uses **two complementary graph algorithms** to identify strategic priorities in humanitarian aid distribution:

        - **PageRank**: Measures influence in the supply network (where aid naturally flows)
        - **Degree Centrality**: Measures connectivity and hub importance (which points serve as coordination hubs)

        By combining both metrics, we can identify different strategic categories of distribution points.
        """)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔝 Top 5 by PageRank (Influence)")
            top_pr = results.nlargest(5, 'pagerank')[['name', 'type', 'region', 'pagerank']]
            top_pr['pagerank'] = top_pr['pagerank'].round(4)
            st.dataframe(top_pr, hide_index=True, width='stretch')

        with col2:
            st.subheader("🔗 Top 5 by Degree Centrality (Connectivity)")
            top_dc = results.nlargest(5, 'degree_centrality')[['name', 'type', 'region', 'degree_centrality']]
            top_dc['degree_centrality'] = top_dc['degree_centrality'].round(4)
            st.dataframe(top_dc, hide_index=True, width='stretch')

    with tab2:
        st.header("Network Visualization")
        st.markdown("Interactive graph showing distribution points colored by strategic category. Node size indicates number of connections.")

        fig = create_network_graph(results, routes_df)
        st.plotly_chart(fig, width='stretch')

        st.markdown("""
        **Legend:**
        - 🔴 **Red**: Critical Coordination Hubs (High PageRank + High Degree) - Maximize capacity & redundancy
        - 🟠 **Orange**: Influential Endpoints (High PageRank + Lower Degree) - Optimize throughput
        - 🟡 **Yellow**: Network Connectors (Lower PageRank + High Degree) - Strengthen infrastructure
        - 🔵 **Blue**: Regular Distribution Points
        """)

    with tab3:
        st.header("Detailed Rankings")

        # Add filters
        col1, col2 = st.columns(2)
        with col1:
            region_filter = st.multiselect("Filter by Region", options=sorted(results['region'].unique()), default=sorted(results['region'].unique()))
        with col2:
            type_filter = st.multiselect("Filter by Type", options=sorted(results['type'].unique()), default=sorted(results['type'].unique()))

        # Apply filters
        filtered_results = results[
            results['region'].isin(region_filter) &
            results['type'].isin(type_filter)
        ].copy()

        # Sort options
        sort_by = st.selectbox("Sort by", options=['PageRank', 'Degree Centrality', 'Total Routes', 'Capacity', 'Population Served'])
        sort_map = {
            'PageRank': 'pagerank',
            'Degree Centrality': 'degree_centrality',
            'Total Routes': 'total_routes',
            'Capacity': 'capacity',
            'Population Served': 'population_served'
        }

        filtered_results = filtered_results.sort_values(sort_map[sort_by], ascending=False)
        filtered_results.insert(0, 'rank', range(1, len(filtered_results) + 1))

        # Format display
        display_df = filtered_results[['rank', 'name', 'type', 'region', 'capacity', 'population_served',
                                       'pagerank', 'degree_centrality', 'total_routes']].copy()
        display_df['pagerank'] = display_df['pagerank'].round(4)
        display_df['degree_centrality'] = display_df['degree_centrality'].round(4)

        st.dataframe(display_df, hide_index=True, width='stretch', height=500)

        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="humanitarian_aid_supply_chain_analysis.csv",
            mime="text/csv"
        )

    with tab4:
        st.header("Strategic Analysis")

        pr_threshold = results['pagerank'].quantile(0.70)
        dc_threshold = results['degree_centrality'].quantile(0.70)

        # Category 1: Critical Coordination Hubs
        critical_hubs = results[
            (results['pagerank'] >= pr_threshold) &
            (results['degree_centrality'] >= dc_threshold)
        ].sort_values('pagerank', ascending=False)

        st.subheader("🔴 Critical Coordination Hubs")
        st.markdown(f"**{len(critical_hubs)} points** with high influence AND high connectivity")
        st.warning("⚠️ **PRIORITY**: Maximize capacity, deploy redundancy, ensure resilience")

        if len(critical_hubs) > 0:
            for _, hub in critical_hubs.iterrows():
                with st.expander(f"📍 {hub['name']} ({hub['type']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("PageRank", f"{hub['pagerank']:.4f}")
                    col2.metric("Degree Centrality", f"{hub['degree_centrality']:.4f}")
                    col3.metric("Total Routes", hub['total_routes'])

                    st.write(f"**Region**: {hub['region']}")
                    st.write(f"**Capacity**: {hub['capacity']:,} units")
                    st.write(f"**Population Served**: {hub['population_served']:,} people")
                    st.write(f"**Incoming Routes**: {hub['incoming_routes']} | **Outgoing Routes**: {hub['outgoing_routes']}")

        st.divider()

        # Category 2: Influential Endpoints
        influential_endpoints = results[
            (results['pagerank'] >= pr_threshold) &
            (results['degree_centrality'] < dc_threshold)
        ].sort_values('pagerank', ascending=False)

        st.subheader("🟠 Influential Endpoints")
        st.markdown(f"**{len(influential_endpoints)} points** with high influence but lower connectivity")
        st.info("✅ **PRIORITY**: Optimize throughput, increase capacity, monitor closely")

        if len(influential_endpoints) > 0:
            for _, hub in influential_endpoints.iterrows():
                with st.expander(f"📍 {hub['name']} ({hub['type']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("PageRank", f"{hub['pagerank']:.4f}")
                    col2.metric("Degree Centrality", f"{hub['degree_centrality']:.4f}")
                    col3.metric("Total Routes", hub['total_routes'])

                    st.write(f"**Region**: {hub['region']}")
                    st.write(f"**Capacity**: {hub['capacity']:,} units")
                    st.write(f"**Population Served**: {hub['population_served']:,} people")

        st.divider()

        # Category 3: Network Connectors
        connectors = results[
            (results['pagerank'] < pr_threshold) &
            (results['degree_centrality'] >= dc_threshold)
        ].sort_values('degree_centrality', ascending=False)

        st.subheader("🟡 Network Connectors")
        st.markdown(f"**{len(connectors)} points** with lower influence but high connectivity")
        st.warning("⚠️ **PRIORITY**: Strengthen infrastructure, maintain reliability, prevent failures")

        if len(connectors) > 0:
            for _, hub in connectors.iterrows():
                with st.expander(f"📍 {hub['name']} ({hub['type']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("PageRank", f"{hub['pagerank']:.4f}")
                    col2.metric("Degree Centrality", f"{hub['degree_centrality']:.4f}")
                    col3.metric("Total Routes", hub['total_routes'])

                    st.write(f"**Region**: {hub['region']}")
                    st.write(f"**Capacity**: {hub['capacity']:,} units")
                    st.write(f"**Population Served**: {hub['population_served']:,} people")

        st.divider()

        # Regional Analysis
        st.subheader("🌍 Regional Distribution Analysis")
        regional_stats = results.groupby('region').agg({
            'name': 'count',
            'capacity': 'sum',
            'population_served': 'sum',
            'pagerank': 'mean',
            'degree_centrality': 'mean'
        }).round(4)
        regional_stats.columns = ['Points', 'Total Capacity', 'Population Served', 'Avg PageRank', 'Avg Degree Centrality']
        st.dataframe(regional_stats, width='stretch')


if __name__ == "__main__":
    main()
