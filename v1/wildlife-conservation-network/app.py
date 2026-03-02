"""Streamlit app for Wildlife Conservation Network analysis.

This interactive app visualizes the community detection analysis from the
wildlife conservation network using RelationalAI and Streamlit.

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
    page_title="Wildlife Conservation Network",
    page_icon="🦁",
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
def get_results(_model, _graph, _Organization):
    """Query and return analysis results."""
    # Calculate graph metrics
    louvain_communities = _graph.louvain()
    degree_centrality = _graph.degree_centrality()
    degree = _graph.degree()

    # Create variable references
    org = _graph.Node.ref("org")
    community_id = Integer.ref("community_id")
    centr_score = Float.ref("centr_score")
    partner_count = Integer.ref("partner_count")

    # Query results
    results = where(
        louvain_communities(org, community_id),
        degree_centrality(org, centr_score),
        degree(org, partner_count)
    ).select(
        org.id,
        org.name,
        org.type,
        org.region,
        org.focus_species,
        community_id.alias("community"),
        centr_score.alias("degree_centrality"),
        partner_count.alias("partnerships")
    ).to_df()

    # Convert to standard types
    results['community'] = results['community'].astype(int)
    results['partnerships'] = results['partnerships'].astype(int)

    # Sort by community, then by centrality within each community
    results = results.sort_values(["community", "degree_centrality"], ascending=[True, False])

    return results


def create_network_graph(results, partnerships_df):
    """Create an interactive network visualization using Plotly."""
    # Create node positions based on community and centrality
    num_communities = results['community'].nunique()
    colors_per_community = {}

    # Assign colors to communities
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    for i, comm in enumerate(sorted(results['community'].unique())):
        colors_per_community[comm] = colors[i % len(colors)]

    # Position nodes
    node_positions = {}
    community_counts = {}

    for _, row in results.iterrows():
        comm = row['community']
        if comm not in community_counts:
            community_counts[comm] = 0

        # Position communities in a circle around the origin
        num_comms = num_communities
        angle = 2 * np.pi * comm / num_comms
        base_x = 10 * np.cos(angle)
        base_y = 10 * np.sin(angle)

        # Position organizations within their community circle
        count = community_counts[comm]
        local_angle = 2 * np.pi * count / max(5, len(results[results['community'] == comm]))
        offset_x = 3 * np.cos(local_angle)
        offset_y = 3 * np.sin(local_angle)

        node_positions[row['id']] = (base_x + offset_x, base_y + offset_y)
        community_counts[comm] += 1

    # Create edges
    org_id_to_name = dict(zip(results['id'], results['name']))
    edge_x = []
    edge_y = []

    for _, edge in partnerships_df.iterrows():
        from_id = edge['from_org_id']
        to_id = edge['to_org_id']

        if from_id in node_positions and to_id in node_positions:
            x0, y0 = node_positions[from_id]
            x1, y1 = node_positions[to_id]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines',
        showlegend=False
    )

    # Create node traces per community
    node_traces = []

    for comm in sorted(results['community'].unique()):
        comm_orgs = results[results['community'] == comm]
        color = colors_per_community[comm]

        node_x = []
        node_y = []
        node_text = []
        node_size = []

        for _, row in comm_orgs.iterrows():
            if row['id'] in node_positions:
                x, y = node_positions[row['id']]
                node_x.append(x)
                node_y.append(y)

                # Create hover text
                text = (f"<b>{row['name']}</b><br>"
                       f"Type: {row['type']}<br>"
                       f"Region: {row['region']}<br>"
                       f"Species Focus: {row['focus_species']}<br>"
                       f"Degree Centrality: {row['degree_centrality']:.4f}<br>"
                       f"Partnerships: {row['partnerships']}")
                node_text.append(text)

                # Size based on partnerships
                node_size.append(10 + row['partnerships'] * 3)

        trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[row['name'] for _, row in comm_orgs.iterrows() if row['id'] in node_positions],
            textposition="top center",
            textfont=dict(size=8),
            hovertext=node_text,
            marker=dict(
                color=color,
                size=node_size,
                line_width=2,
                line_color='white'
            ),
            name=f'Community {comm} ({len(comm_orgs)} orgs)',
            showlegend=True
        )
        node_traces.append(trace)

    # Create figure
    fig = go.Figure(data=[edge_trace] + node_traces,
                    layout=go.Layout(
                        title='Wildlife Conservation Network - Community Detection',
                        title_font_size=16,
                        showlegend=True,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=700
                    ))

    return fig


# --------------------------------------------------
# Main app
# --------------------------------------------------

def main():
    st.title("🦁 Wildlife Conservation Network")
    st.markdown("**Community Detection & Collaboration Analysis**")

    st.markdown("""
    This analysis uses the **Louvain algorithm** to detect communities (clusters) of conservation organizations
    that work closely together. Understanding these collaboration patterns helps optimize resource sharing,
    identify partnership opportunities, and strengthen cross-community coordination.
    """)

    # Load data
    with st.spinner("Loading RelationalAI model and analyzing network..."):
        model, graph, Organization = load_model()
        results = get_results(model, graph, Organization)
        partnerships_df = pd.read_csv(DATA_DIR / "partnerships.csv")

    # Sidebar with summary stats
    st.sidebar.header("📊 Network Summary")
    st.sidebar.metric("Total Organizations", len(results))
    st.sidebar.metric("Detected Communities", results['community'].nunique())
    st.sidebar.metric("Total Partnerships", len(partnerships_df))
    st.sidebar.metric("Avg Partnerships/Org", f"{results['partnerships'].mean():.1f}")
    st.sidebar.divider()

    most_connected = results.loc[results['degree_centrality'].idxmax()]
    st.sidebar.markdown("**Most Connected Organization**")
    st.sidebar.write(f"{most_connected['name']}")
    st.sidebar.metric("Partnerships", int(most_connected['partnerships']))

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "🗺️ Network Visualization", "📋 Community Breakdown", "🎯 Strategic Analysis"])

    with tab1:
        st.header("Overview")
        st.markdown("""
        The **Louvain algorithm** identifies communities by optimizing modularity—grouping nodes that have
        many internal connections but few connections to other groups. In wildlife conservation, this reveals:
        - **Geographic clusters**: Organizations working in the same region
        - **Species-focused groups**: Organizations collaborating on specific species conservation
        - **Cross-community opportunities**: Partnerships that could strengthen network resilience
        """)

        # Top organizations by centrality
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🌟 Top 5 Most Connected Organizations")
            top_orgs = results.nlargest(5, 'degree_centrality')[['name', 'community', 'partnerships', 'degree_centrality']]
            top_orgs['degree_centrality'] = top_orgs['degree_centrality'].round(4)
            st.dataframe(top_orgs, hide_index=True, width='stretch')

        with col2:
            st.subheader("🤝 Communities by Size")
            comm_sizes = results.groupby('community').size().reset_index(name='Size')
            st.dataframe(comm_sizes, hide_index=True, width='stretch')

    with tab2:
        st.header("Network Visualization")
        st.markdown("Interactive graph showing organizations colored by detected community. Node size indicates number of partnerships.")

        fig = create_network_graph(results, partnerships_df)
        st.plotly_chart(fig, width='stretch')

        st.info("💡 **Tip:** Organizations are positioned by community. Larger nodes have more partnerships within their community.")

    with tab3:
        st.header("Community Breakdown")

        for comm_id in sorted(results['community'].unique()):
            community_orgs = results[results['community'] == comm_id]

            with st.expander(f"📍 **Community {comm_id}** ({len(community_orgs)} organizations)", expanded=(comm_id == 0)):
                # Community statistics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Size", len(community_orgs))
                col2.metric("Avg Centrality", f"{community_orgs['degree_centrality'].mean():.4f}")
                col3.metric("Avg Partnerships", f"{community_orgs['partnerships'].mean():.1f}")
                col4.metric("Hub Organization", community_orgs.iloc[0]['name'])

                # Community details
                st.markdown("**Primary Characteristics:**")

                regions = community_orgs['region'].value_counts()
                primary_region = regions.index[0]
                st.write(f"- **Primary Region**: {primary_region}")

                species = community_orgs['focus_species'].value_counts()
                species_summary = ", ".join([f"{sp}" for sp in species.index[:3]])
                st.write(f"- **Species Focus**: {species_summary}")

                types = community_orgs['type'].value_counts()
                types_summary = ", ".join([f"{t} ({c})" for t, c in types.items()])
                st.write(f"- **Organization Types**: {types_summary}")

                # List all members
                st.markdown("**Member Organizations:**")
                for _, org in community_orgs.iterrows():
                    st.write(f"- **{org['name']}** ({org['type']}, {org['region']}) - Focus: {org['focus_species']} - Partnerships: {org['partnerships']}")

    with tab4:
        st.header("Strategic Analysis")

        st.markdown("""
        ### Collaboration Patterns & Opportunities

        Use these insights to strengthen the conservation network:
        """)

        # Identify inter-community connectors
        st.subheader("🌉 Cross-Community Connectors")
        st.info("Organizations with partnerships outside their community can strengthen network coordination")

        connectors = []
        for _, org in results.iterrows():
            # Check if this org has partnerships with orgs in other communities
            org_partnerships = partnerships_df[
                (partnerships_df['from_org_id'] == org['id']) |
                (partnerships_df['to_org_id'] == org['id'])
            ]

            if len(org_partnerships) > 0:
                partner_ids = []
                for _, p in org_partnerships.iterrows():
                    partner_id = p['to_org_id'] if p['from_org_id'] == org['id'] else p['from_org_id']
                    partner_ids.append(partner_id)

                partner_comms = results[results['id'].isin(partner_ids)]['community'].unique()

                if len(partner_comms) > 1:
                    connectors.append({
                        'name': org['name'],
                        'community': org['community'],
                        'partnerships': org['partnerships'],
                        'connections_to_communities': len(partner_comms)
                    })

        if connectors:
            connector_df = pd.DataFrame(connectors).sort_values('partnerships', ascending=False)
            st.dataframe(connector_df, hide_index=True, width='stretch')
        else:
            st.write("No significant cross-community connectors detected")

        st.divider()

        # Geographic analysis
        st.subheader("🌍 Geographic Distribution")
        geo_stats = results.groupby('region').agg({
            'name': 'count',
            'community': 'nunique',
            'partnerships': 'mean',
            'degree_centrality': 'mean'
        }).round(4)
        geo_stats.columns = ['Total Orgs', 'Communities', 'Avg Partnerships', 'Avg Centrality']
        st.dataframe(geo_stats, width='stretch')

        st.divider()

        # Species focus analysis
        st.subheader("🐾 Species Focus Summary")
        species_stats = results['focus_species'].value_counts().reset_index()
        species_stats.columns = ['Species', 'Number of Organizations']
        st.dataframe(species_stats, hide_index=True, width='stretch')


if __name__ == "__main__":
    main()
