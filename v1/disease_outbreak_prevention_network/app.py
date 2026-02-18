"""Streamlit app for Disease Outbreak Prevention Network analysis.

This interactive app visualizes the weighted degree centrality analysis from the
disease outbreak prevention network using RelationalAI and Streamlit, incorporating
transfer volume and contact intensity risk metrics.

Run:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from relationalai.semantics import where, Integer, Float

from model_setup import create_model, DATA_DIR

# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Disease Outbreak Prevention Network",
    page_icon="🏥",
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
def get_results(_model, _graph, _Facility):
    """Query and return analysis results."""
    # Calculate graph metrics
    degree_centrality = _graph.degree_centrality()
    incoming_edges = _graph.indegree()
    outgoing_edges = _graph.outdegree()

    # Create variable references
    facility = _graph.Node.ref("facility")
    centr_score = Float.ref("d_score")
    in_edges = Integer.ref("in_edges")
    out_edges = Integer.ref("out_edges")

    # Query results
    results = where(
        degree_centrality(facility, centr_score),
        incoming_edges(facility, in_edges),
        outgoing_edges(facility, out_edges)
    ).select(
        facility.id,
        facility.name,
        facility.type,
        facility.region,
        centr_score.alias("degree_centrality"),
        in_edges.alias("incoming_connections"),
        out_edges.alias("outgoing_connections")
    ).to_df()

    # Convert to standard types
    results['incoming_connections'] = results['incoming_connections'].astype(int)
    results['outgoing_connections'] = results['outgoing_connections'].astype(int)

    # Sort by degree centrality
    results = results.sort_values("degree_centrality", ascending=False)
    results.insert(0, "rank", range(1, len(results) + 1))

    # Calculate total connections
    results['total_connections'] = results['incoming_connections'] + results['outgoing_connections']

    return results

def create_network_graph(results, connections_df):
    """Create an interactive network visualization using Plotly."""
    import numpy as np

    # Create node positions based on region
    regions = {
        'Downtown': (0, 0),
        'North': (0, 2),
        'South': (0, -2),
        'East': (2, 0),
        'West': (-2, 0)
    }

    node_positions = {}
    region_counts = {}

    for _, row in results.iterrows():
        region = row['region']
        if region not in region_counts:
            region_counts[region] = 0

        # Arrange facilities in each region in a circle
        base_x, base_y = regions.get(region, (0, 0))
        count = region_counts[region]
        offset_x = 0.5 * np.cos(2 * np.pi * count / 4)
        offset_y = 0.5 * np.sin(2 * np.pi * count / 4)

        node_positions[row['name']] = (base_x + offset_x, base_y + offset_y)
        region_counts[region] += 1

    # Create edges
    facility_id_to_name = dict(zip(results['id'], results['name']))

    edge_x = []
    edge_y = []
    edge_annotations = []

    for _, edge in connections_df.iterrows():
        from_name = facility_id_to_name.get(edge['from_facility_id'])
        to_name = facility_id_to_name.get(edge['to_facility_id'])

        if from_name and to_name and from_name in node_positions and to_name in node_positions:
            x0, y0 = node_positions[from_name]
            x1, y1 = node_positions[to_name]

            # Add edge line
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

            # Add arrow annotation
            edge_annotations.append(
                dict(
                    x=x1,
                    y=y1,
                    ax=x0,
                    ay=y0,
                    xref='x',
                    yref='y',
                    axref='x',
                    ayref='y',
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor='#888',
                    opacity=0.5
                )
            )

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines',
        showlegend=False
    )

    # Create nodes
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []

    # Normalize node sizes for visualization (scale to 20-60 range)
    min_centrality = results['degree_centrality'].min()
    max_centrality = results['degree_centrality'].max()
    centrality_range = max_centrality - min_centrality if max_centrality > min_centrality else 1

    for _, row in results.iterrows():
        if row['name'] in node_positions:
            x, y = node_positions[row['name']]
            node_x.append(x)
            node_y.append(y)
            node_text.append(
                f"<b>{row['name']}</b><br>"
                f"Type: {row['type']}<br>"
                f"Region: {row['region']}<br>"
                f"Rank: #{row['rank']}<br>"
                f"Weighted Degree Centrality: {row['degree_centrality']:.2f}<br>"
                f"Total Connections: {row['total_connections']}<br>"
                f"Incoming: {row['incoming_connections']} | Outgoing: {row['outgoing_connections']}"
            )
            node_color.append(row['degree_centrality'])
            # Scale node size proportionally between 20 and 60 based on centrality
            normalized_size = (row['degree_centrality'] - min_centrality) / centrality_range
            node_size.append(20 + normalized_size * 40)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[row['name'] for _, row in results.iterrows() if row['name'] in node_positions],
        textposition="top center",
        textfont=dict(size=9),
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='Reds',
            color=node_color,
            size=node_size,
            colorbar=dict(
                thickness=15,
                title=dict(text='Risk Weight', side='right')
            ),
            line=dict(width=2, color='white')
        ),
        showlegend=False
    )

    # Create figure
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title=dict(text='Disease Outbreak Prevention Network - Weighted Degree Centrality', font=dict(size=20)),
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        annotations=edge_annotations,
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor='white',
                        height=700
                    ))

    return fig

# --------------------------------------------------
# Main app
# --------------------------------------------------

def main():
    st.title("🏥 Disease Outbreak Prevention Network Analysis")
    st.markdown("### Weighted Degree Centrality for Risk-Based Resource Prioritization")

    st.markdown("""
    This app analyzes healthcare facility connections and transmission risk metrics to identify the most strategically important
    locations for resource deployment during disease outbreaks. Risk weights are calculated from patient transfer volume and contact intensity.
    """)

    # Load data
    with st.spinner("Loading model and analyzing network..."):
        model, graph, Facility = load_model()
        results = get_results(model, graph, Facility)
        connections_df = pd.read_csv(DATA_DIR / "connections.csv")

    # Sidebar with summary statistics
    st.sidebar.header("📊 Network Summary")
    st.sidebar.metric("Total Facilities", len(results))
    st.sidebar.metric("Total Connections", results['total_connections'].sum() // 2)
    st.sidebar.metric("Avg Connections per Facility", f"{results['total_connections'].mean():.1f}")
    st.sidebar.metric("Avg Degree Centrality", f"{results['degree_centrality'].mean():.4f}")

    most_connected = results.iloc[0]
    st.sidebar.markdown(f"**Most Connected:**  \n{most_connected['name']}  \n({int(most_connected['total_connections'])} connections)")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Network Visualization", "📋 Facility Rankings", "🎯 Priority Facilities"])

    with tab1:
        st.subheader("Interactive Network Graph")
        st.markdown("Hover over nodes to see details. Node size and color represent weighted degree centrality (risk weight). Arrows show connection direction.")

        fig = create_network_graph(results, connections_df)
        st.plotly_chart(fig, use_container_width=True)

        st.info("💡 **Tip:** Facilities grouped by region. Highly connected facilities (darker/larger) should receive priority resources.")

    with tab2:
        st.subheader("Facility Rankings by Weighted Degree Centrality")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            selected_types = st.multiselect(
                "Filter by Type",
                options=sorted(results['type'].unique()),
                default=sorted(results['type'].unique())
            )
        with col2:
            selected_regions = st.multiselect(
                "Filter by Region",
                options=sorted(results['region'].unique()),
                default=sorted(results['region'].unique())
            )

        # Filter data
        filtered_results = results[
            (results['type'].isin(selected_types)) &
            (results['region'].isin(selected_regions))
        ]

        # Display data
        display_df = filtered_results[['rank', 'name', 'type', 'region', 'degree_centrality',
                                       'incoming_connections', 'outgoing_connections', 'total_connections']].copy()
        display_df['degree_centrality'] = display_df['degree_centrality'].round(2)

        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )

        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Rankings as CSV",
            data=csv,
            file_name="outbreak_prevention_rankings.csv",
            mime="text/csv"
        )

        st.markdown("""
        **Weighted Degree Centrality** measures the cumulative transmission risk for each facility:
        - **Formula**: Sum of (transfer_volume × contact_intensity) for all connections
        - **Higher scores** = Greater risk = More critical for outbreak response
        - **Transfer Volume** = Patient transfers, samples, or resource exchanges (1-10)
        - **Contact Intensity** = Frequency/intensity of staff and data interactions (1-10)
        - **Incoming connections** = Facilities that depend on or report to this one
        - **Outgoing connections** = Facilities this one coordinates with or refers to
        """)

    with tab3:
        st.subheader("🎯 Top Priority Facilities for Resource Deployment")

        # Top N selector
        top_n = st.slider("Number of top facilities to display", 3, 10, 5)

        top_facilities = results.head(top_n)

        st.markdown("""
        These facilities should receive **immediate priority** for:
        - 💉 Vaccine and medical supply deployment
        - 🧪 Testing station setup
        - 🚑 Emergency response team positioning
        """)

        st.markdown("---")

        for _, row in top_facilities.iterrows():
            with st.expander(f"**#{int(row['rank'])} - {row['name']}**", expanded=(row['rank'] <= 3)):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Type", row['type'])
                    st.metric("Region", row['region'])

                with col2:
                    st.metric("Weighted Degree Centrality", f"{row['degree_centrality']:.2f}")
                    st.metric("Total Connections", int(row['total_connections']))

                with col3:
                    st.metric("Incoming", int(row['incoming_connections']))
                    st.metric("Outgoing", int(row['outgoing_connections']))

                # Show connection analysis
                if row['outgoing_connections'] > row['incoming_connections']:
                    st.info(f"📤 **Coordinator Role:** This facility connects to many others, making it ideal for distributing resources and information.")
                elif row['incoming_connections'] > row['outgoing_connections']:
                    st.info(f"📥 **Hub Role:** Many facilities connect to this one, making it a critical dependency for the network.")
                else:
                    st.info(f"🔄 **Balanced Role:** Equal incoming and outgoing connections indicate a well-balanced coordination role.")

    st.markdown("---")
    st.markdown("*Built with RelationalAI, Streamlit, and Plotly*")

if __name__ == "__main__":
    main()
