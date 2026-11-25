"""Network summary: the network's point, route, population, and capacity totals, and the same figures with
average scores for each region."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declares DistributionPoint.pagerank, degree_centrality, and total_routes.
from . import supply_network  # noqa: F401
from .schema import DistributionPoint, SupplyRoute, model

NetworkSummary = model.Concept("NetworkSummary", identify_by={"id": Integer})
NetworkSummary.n_points = model.Property(f"{NetworkSummary} has {Integer:n_points} points")
NetworkSummary.n_routes = model.Property(f"{NetworkSummary} has {Integer:n_routes} routes")
NetworkSummary.mean_routes = model.Property(f"{NetworkSummary} has {Float:mean_routes} routes per point")
NetworkSummary.total_population = model.Property(f"{NetworkSummary} serves {Integer:total_population} people")
NetworkSummary.total_capacity = model.Property(f"{NetworkSummary} has capacity {Integer:total_capacity}")
model.define(NetworkSummary.new(id=1))
model.define(
    NetworkSummary.n_points(aggs.count(DistributionPoint).per(NetworkSummary)),
    NetworkSummary.n_routes(aggs.count(SupplyRoute).per(NetworkSummary)),
    NetworkSummary.mean_routes(aggs.avg(DistributionPoint, DistributionPoint.total_routes).per(NetworkSummary)),
    NetworkSummary.total_population(
        aggs.sum(DistributionPoint, DistributionPoint.population_served).per(NetworkSummary)
    ),
    NetworkSummary.total_capacity(aggs.sum(DistributionPoint, DistributionPoint.capacity).per(NetworkSummary)),
)

# One summary per region: its points, their capacity and population served, and their average PageRank and
# degree centrality.
RegionSummary = model.Concept("RegionSummary", identify_by={"region": String})
RegionSummary.n_points = model.Property(f"{RegionSummary} has {Integer:n_points} points")
RegionSummary.total_capacity = model.Property(f"{RegionSummary} has capacity {Integer:total_capacity}")
RegionSummary.total_population = model.Property(f"{RegionSummary} serves {Integer:total_population} people")
RegionSummary.mean_pagerank = model.Property(f"{RegionSummary} has average PageRank {Float:mean_pagerank}")
RegionSummary.mean_degree_centrality = model.Property(
    f"{RegionSummary} has average degree centrality {Float:mean_degree_centrality}"
)
model.define(RegionSummary.new(region=DistributionPoint.region))
_in_region = DistributionPoint.region == RegionSummary.region
model.define(
    RegionSummary.n_points(aggs.count(DistributionPoint).per(RegionSummary).where(_in_region)),
    RegionSummary.total_capacity(
        aggs.sum(DistributionPoint, DistributionPoint.capacity).per(RegionSummary).where(_in_region)
    ),
    RegionSummary.total_population(
        aggs.sum(DistributionPoint, DistributionPoint.population_served).per(RegionSummary).where(_in_region)
    ),
    RegionSummary.mean_pagerank(
        aggs.avg(DistributionPoint, DistributionPoint.pagerank).per(RegionSummary).where(_in_region)
    ),
    RegionSummary.mean_degree_centrality(
        aggs.avg(DistributionPoint, DistributionPoint.degree_centrality).per(RegionSummary).where(_in_region)
    ),
)
