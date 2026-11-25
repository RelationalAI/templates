"""Strategic categories: each point's category from its PageRank and degree centrality, the points in each
category, and each point's influence rank within its category."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declare DistributionPoint.pagerank and degree_centrality, and the influence_rank read below.
from . import point_rankings, supply_network  # noqa: F401
from .schema import DistributionPoint, model

# Strategic category: whether a point's PageRank and degree centrality reach the network's
# 70th percentile (inclusive, interpolated linearly between ranks).
other = DistributionPoint.ref()
pagerank_cut = aggs.percentile(70, other, other.pagerank)
degree_cut = aggs.percentile(70, other, other.degree_centrality)
high_pagerank = DistributionPoint.pagerank >= pagerank_cut
low_pagerank = DistributionPoint.pagerank < pagerank_cut
high_degree = DistributionPoint.degree_centrality >= degree_cut
low_degree = DistributionPoint.degree_centrality < degree_cut
DistributionPoint.category = model.Property(f"{DistributionPoint} is a {String:category}")
model.where(high_pagerank, high_degree).define(DistributionPoint.category("Critical Coordination Hub"))
model.where(high_pagerank, low_degree).define(DistributionPoint.category("Influential Endpoint"))
model.where(low_pagerank, high_degree).define(DistributionPoint.category("Network Connector"))
model.where(low_pagerank, low_degree).define(DistributionPoint.category("Regular Distribution Point"))

# The categories that have points, and how many points each holds.
PointCategory = model.Concept("PointCategory", identify_by={"label": String})
PointCategory.n_points = model.Property(f"{PointCategory} has {Integer:n_points} points")
model.define(PointCategory.new(label=DistributionPoint.category))
_in_category = DistributionPoint.category == PointCategory.label
model.define(PointCategory.n_points(aggs.count(DistributionPoint).per(PointCategory).where(_in_category)))

# Each point's place within its category, most influential first.
DistributionPoint.category_rank = model.Property(
    f"{DistributionPoint} has rank {Integer:category_rank} in its category"
)
model.define(
    DistributionPoint.category_rank(
        aggs.rank(DistributionPoint.influence_rank).per(PointCategory).where(_in_category)
    )
)
