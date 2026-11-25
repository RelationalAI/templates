"""Network criticality: the site shipping graph, its connected components, and each site's
eigenvector centrality, rank, and the most critical site."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import Operation, Site, model

# --------------------------------------------------
# Stage 1: Graph -- network criticality
# --------------------------------------------------

# Build undirected unweighted graph: Sites as nodes, SHIP operations as edges.
graph = Graph(
    model, directed=False, weighted=False, node_concept=Site, aggregator="sum", name="shipping_network"
)

s1, s2, op_ref = Site.ref(), Site.ref(), Operation.ref()
model.define(
    graph.Edge.new(src=s1, dst=s2)
).where(
    op_ref.source_site(s1),
    op_ref.output_site(s2),
    op_ref.op_type == "SHIP",
)

# The site graph's size, which the deployed model publishes for the queries.
node_count, edge_count = Integer.ref(), Integer.ref()
num_nodes = model.Relationship(f"the site graph has {Integer:num_nodes} nodes")
num_edges = model.Relationship(f"the site graph has {Integer:num_edges} edges")
model.where(graph.num_nodes()(node_count)).define(num_nodes(node_count))
model.where(graph.num_edges()(edge_count)).define(num_edges(edge_count))

# Weakly connected components.
wcc = graph.weakly_connected_component()

# Eigenvector centrality: identify most critical sites.
eigenvector = graph.eigenvector_centrality()

# Attach both results to Site, so the deployed model publishes them for the queries.
Site.component = wcc
Site.eigenvector_centrality = eigenvector

# Store centrality on Site for use in optimization objective: the eigenvector score
# of each site other than stores and offices, divided by the largest such score. When
# the largest score is 0, every score is 0 and is kept as is.
Site.centrality = model.Property(f"{Site} has centrality {Float:centrality}")
MaxCentrality = model.Relationship(f"max eigenvector centrality is {Float:max_score}")
site_max, score_max = Site.ref(), Float.ref()
model.define(MaxCentrality(aggs.max(score_max))).where(
    eigenvector(site_max, score_max),
    site_max.site_type != "STORE",
    site_max.site_type != "OFFICE",
)
site_eig, score_eig, max_score = Site.ref(), Float.ref(), Float.ref()
model.where(
    eigenvector(site_eig, score_eig),
    site_eig.site_type != "STORE",
    site_eig.site_type != "OFFICE",
    MaxCentrality(max_score),
    max_score > 0,
).define(site_eig.centrality(score_eig / max_score))
model.where(
    eigenvector(site_eig, score_eig),
    site_eig.site_type != "STORE",
    site_eig.site_type != "OFFICE",
    MaxCentrality(0.0),
).define(site_eig.centrality(score_eig))

# The site with the highest centrality, the lowest ID among ties; the site-offline
# scenario takes this one site offline.
MostCriticalSiteId = model.Relationship(f"the most critical site has id {String:site_id}")
site_top, score_top = Site.ref(), Float.ref()
model.define(MostCriticalSiteId(aggs.min(site_top.id))).where(
    eigenvector(site_top, score_top),
    site_top.site_type != "STORE",
    site_top.site_type != "OFFICE",
    MaxCentrality(score_top),
)
Site.is_most_critical = model.Relationship(f"{Site} is the most critical site")
model.where(MostCriticalSiteId(Site.id)).define(Site.is_most_critical())

# Each scored site's rank by centrality, highest first, ties broken by site id. The score is
# negated so both keys sort ascending, a form every backend ranks.
Site.centrality_rank = model.Property(f"{Site} has centrality rank {Integer:centrality_rank}")
model.define(Site.centrality_rank(aggs.rank(-Site.centrality, Site.id)))

# Each weakly connected component, keyed by the id of its representative site, with its site
# count and the sorted distinct regions its sites span.
SiteCluster = model.Concept("SiteCluster", identify_by={"id": String})
SiteCluster.n_sites = model.Property(f"{SiteCluster} has {Integer:n_sites} sites")
SiteCluster.regions = model.Property(f"{SiteCluster} spans regions {String:regions}")
cluster_site, cluster_root = Site.ref(), Site.ref()
model.define(SiteCluster.new(id=cluster_root.id)).where(wcc(cluster_site, cluster_root))
_in_cluster = (wcc(cluster_site, cluster_root), cluster_root.id == SiteCluster.id)
model.define(
    SiteCluster.n_sites(aggs.count(cluster_site).per(SiteCluster).where(*_in_cluster)),
    SiteCluster.regions(
        aggs.string_join(cluster_site.region, sep=", ").per(SiteCluster).where(*_in_cluster)
    ),
)

# The number of components (zero for an empty graph).
num_components = model.Relationship(f"the site graph has {Integer:num_components} connected components")
model.define(num_components(aggs.count(cluster_root).where(wcc(cluster_site, cluster_root)) | 0))
