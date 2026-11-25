"""Point rankings: each distribution point's influence rank, and the points with the most routes and the
highest degree centrality."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

# Declares DistributionPoint.pagerank, degree_centrality, and total_routes.
from . import supply_network  # noqa: F401
from .schema import DistributionPoint, model

# Influence rank 1 is the point with the highest PageRank, then the highest degree centrality, then the
# lowest id. The numeric keys are negated so every key sorts ascending, the one direction a rank accepts
# on results of the graph reasoner.
DistributionPoint.influence_rank = model.Property(f"{DistributionPoint} has influence rank {Integer:influence_rank}")
model.define(
    DistributionPoint.influence_rank(
        aggs.rank(-DistributionPoint.pagerank, -DistributionPoint.degree_centrality, DistributionPoint.id)
    )
)

# The point with the most routes, and the point with the highest degree centrality. A tie goes to the more
# influential point.
DistributionPoint.is_most_connected = model.Relationship(f"{DistributionPoint} has the most routes")
model.where(aggs.rank(-DistributionPoint.total_routes, DistributionPoint.influence_rank) == 1).define(
    DistributionPoint.is_most_connected()
)
DistributionPoint.is_most_central = model.Relationship(f"{DistributionPoint} has the highest degree centrality")
model.where(aggs.rank(-DistributionPoint.degree_centrality, DistributionPoint.influence_rank) == 1).define(
    DistributionPoint.is_most_central()
)
