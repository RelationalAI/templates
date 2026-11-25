"""Network analysis: the distribution network graph, each site's eigenvector centrality, the weakly
connected components with their sizes and regions, and the cross-region bridge routes."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .schema import Property, Route, Site, model

# --------------------------------------------------
# Stage 1: Graph Analysis -- identify critical network hubs
# --------------------------------------------------

graph = Graph(
    model, directed=False, weighted=True, node_concept=Site, aggregator="sum", name="warehouse_network"
)

# Build edges from routes (undirected, weighted by capacity)
route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
model.where(route_ref.source(src), route_ref.dest(dst)).define(
    graph.Edge.new(src=src, dst=dst, weight=route_ref.capacity),
)

# Eigenvector centrality: stored directly on Site (via node_concept)
Site.centrality = graph.eigenvector_centrality()

# --------------------------------------------------
# Stage 1b: Weakly Connected Components -- surface fragmentation
# --------------------------------------------------

# Each site's component, named by one of its sites, which the deployed model publishes for the queries.
wcc = graph.weakly_connected_component()
SiteComponent = model.Relationship(f"{Site} is in the component of {Site:component}")
site_member, site_component = Site.ref(), Site.ref()
model.where(wcc(site_member, site_component)).define(SiteComponent(site_member, site_component))

# Each component's number of sites and its regions in alphabetical order. A component is
# identified by the id of the site that names it.
NetworkComponent = model.Concept("NetworkComponent", identify_by={"component_id": Integer})
NetworkComponent.n_sites = model.Property(f"{NetworkComponent} has {Integer:n_sites} sites")
NetworkComponent.regions = model.Property(f"{NetworkComponent} spans regions {String:regions}")
model.where(SiteComponent(site_member, site_component)).define(
    NetworkComponent.new(component_id=site_component.id)
)
_in_component = (
    SiteComponent(site_member, site_component),
    site_component.id == NetworkComponent.component_id,
)
model.define(
    NetworkComponent.n_sites(aggs.count(site_member).per(NetworkComponent).where(*_in_component)),
    NetworkComponent.regions(
        aggs.string_join(site_member.region, sep=", ").per(NetworkComponent).where(*_in_component)
    ),
)

# The number of components, and whether the network is one component (UNIFIED) or several
# (FRAGMENTED).
num_components = model.Relationship(f"the network has {Integer:num_components} components")
model.define(num_components(aggs.count(NetworkComponent)))
NetworkState = model.Relationship(f"the network is {String:state}")
_n_components = Integer.ref()
model.where(num_components(_n_components), _n_components == 1).define(NetworkState("UNIFIED"))
model.where(num_components(_n_components), _n_components != 1).define(NetworkState("FRAGMENTED"))

# --------------------------------------------------
# Stage 1c: Bridge Routes -- cross-region connectors
# --------------------------------------------------
# Routes whose endpoints lie in different regions: the links that carry
# inter-region flow. This compares region labels only; it does not test
# whether removing a route disconnects the graph.

route_ref = Route.ref()
src, dst = Site.ref(), Site.ref()
Route.is_cross_region = Property(f"{Route} is cross-region {Float:is_cross_region}")
model.where(
    route_ref.source(src),
    route_ref.dest(dst),
    src.region != dst.region,
).define(Route.is_cross_region(route_ref, 1.0))
