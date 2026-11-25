"""Grid topology: connected components, Louvain communities, and centrality of the transmission grid, the
structurally critical substations, and the grid's connectivity and regions."""

from relationalai.semantics import Float, Integer, String, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import Substation, TransmissionLine, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

CRITICAL_THRESHOLD = 3  # top-N substations by combined centrality rank are "structurally critical"

# --------------------------------------------------
# Stage 2: Graph -- Grid Topology & Structural Vulnerability
# --------------------------------------------------

grid_graph = Graph(
    model,
    name="grid_graph",
    directed=False,
    weighted=False,
    node_concept=Substation,
    aggregator="sum",
)

# Edges: active transmission lines between substations.
line_ref = TransmissionLine.ref()
model.define(grid_graph.Edge.new(src=line_ref.from_substation, dst=line_ref.to_substation)).where(
    line_ref.is_active == True
)

# a) Weakly Connected Components
wcc = grid_graph.weakly_connected_component()
Substation.component = model.Property(f"{Substation} in component {String:component}")
wcc_node, wcc_comp = Substation.ref(), Substation.ref()
model.define(wcc_node.component(wcc_comp.id)).where(wcc(wcc_node, wcc_comp))

# b) Community Detection (Louvain)
community = grid_graph.louvain()
comm_label = Integer.ref("comm")

# c) Centrality Analysis (betweenness, degree, eigenvector)
betweenness = grid_graph.betweenness_centrality()
btwn_score = Float.ref("btwn")

degree = grid_graph.degree_centrality()
deg_score = Float.ref("deg")

eigenvector = grid_graph.eigenvector_centrality()
eig_score = Float.ref("eig")

# Store graph results directly on Substation.
Substation.grid_community = model.Property(
    f"{Substation} in grid community {Integer:grid_community}"
)
Substation.betweenness = model.Property(f"{Substation} has {Float:betweenness}")
Substation.degree_centrality = model.Property(f"{Substation} has {Float:degree_centrality}")
Substation.eigenvector_centrality = model.Property(
    f"{Substation} has {Float:eigenvector_centrality}"
)

sub_ref = Substation.ref()
model.define(sub_ref.grid_community(comm_label)).where(community(sub_ref, comm_label))
model.define(sub_ref.betweenness(btwn_score)).where(betweenness(sub_ref, btwn_score))
model.define(sub_ref.degree_centrality(deg_score)).where(degree(sub_ref, deg_score))
model.define(sub_ref.eigenvector_centrality(eig_score)).where(eigenvector(sub_ref, eig_score))

# Composite critical rank from all three centrality metrics.
Substation.betweenness_rank = model.Property(f"{Substation} has {Integer:betweenness_rank}")
Substation.degree_rank = model.Property(f"{Substation} has {Integer:degree_rank}")
Substation.eigenvector_rank = model.Property(f"{Substation} has {Integer:eigenvector_rank}")
Substation.combined_rank = model.Property(f"{Substation} has {Integer:combined_rank}")
Substation.critical_rank = model.Property(f"{Substation} has {Integer:critical_rank}")

model.define(
    Substation.betweenness_rank(aggs.rank(aggs.desc(Substation.betweenness, Substation.id)))
)
model.define(
    Substation.degree_rank(aggs.rank(aggs.desc(Substation.degree_centrality, Substation.id)))
)
model.define(
    Substation.eigenvector_rank(
        aggs.rank(aggs.desc(Substation.eigenvector_centrality, Substation.id))
    )
)
model.define(
    Substation.combined_rank(
        Substation.betweenness_rank + Substation.degree_rank + Substation.eigenvector_rank
    )
)
model.define(Substation.critical_rank(aggs.rank(Substation.combined_rank, Substation.id)))

Substation.is_structurally_critical = model.Relationship(f"{Substation} is structurally critical")
model.where(Substation.critical_rank <= CRITICAL_THRESHOLD).define(
    Substation.is_structurally_critical()
)

# The grid's size, number of connected components, number of Louvain communities, and whether it is
# CONNECTED (one component) or FRAGMENTED.
GridTopology = model.Concept("GridTopology", identify_by={"id": Integer})
GridTopology.n_substations = model.Property(f"{GridTopology} has {Integer:n_substations} substations")
GridTopology.n_components = model.Property(f"{GridTopology} has {Integer:n_components} components")
GridTopology.n_communities = model.Property(f"{GridTopology} has {Integer:n_communities} communities")
GridTopology.connectivity = model.Property(f"{GridTopology} is {String:connectivity}")
model.define(GridTopology.new(id=1))
model.define(
    GridTopology.n_substations(aggs.count(Substation).per(GridTopology)),
    GridTopology.n_components(aggs.count(distinct(Substation.component)).per(GridTopology)),
    GridTopology.n_communities(aggs.count(distinct(Substation.grid_community)).per(GridTopology)),
)
model.where(GridTopology.n_components == 1).define(GridTopology.connectivity("CONNECTED"))
model.where(GridTopology.n_components != 1).define(GridTopology.connectivity("FRAGMENTED"))

# Each Louvain community with its member substations' names, in id order.
GridRegion = model.Concept("GridRegion", identify_by={"community": Integer})
GridRegion.members = model.Property(f"{GridRegion} has members {String:members}")
model.define(GridRegion.new(community=Substation.grid_community))
model.define(
    GridRegion.members(
        aggs.string_join(Substation.name, sep=", ", index=Substation.id)
        .per(GridRegion)
        .where(Substation.grid_community == GridRegion.community)
    )
)
