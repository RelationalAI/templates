"""Correlation clusters: each stock's variance, volatility, and pairwise correlation, the correlation graph
and its Louvain clusters, the representative of each cluster (highest Sharpe ratio), and summaries of the
clustering."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import abs as math_abs
from relationalai.semantics.std.math import sqrt

from .schema import Stock, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

CORR_THRESHOLD = 0.3  # |correlation| >= threshold to create a graph edge (Stage 2)

# --------------------------------------------------
# Stage 2: Graph -- covariance clustering
# --------------------------------------------------

# Derived per-stock variance (covar diagonal, i == j).
PairedStockVar = Stock.ref()
var_ref = Float.ref()
model.where(
    Stock.covar(PairedStockVar, var_ref),
    Stock.index == PairedStockVar.index,
).define(Stock.variance(var_ref))

# Derived per-stock volatility (sqrt of variance). Used downstream to derive
# correlation and the crisis regime covariance -- no numpy, no precompute.
model.define(Stock.volatility(sqrt(Stock.variance)))

# Derived pairwise correlation: corr(i, j) = covar(i, j) / (vol_i * vol_j).
# Stored as a two-argument property on Stock (keyed by the paired Stock).
PairedStockCorr = Stock.ref()
cov_ij_ref = Float.ref()
model.where(
    Stock.covar(PairedStockCorr, cov_ij_ref),
).define(
    Stock.correlation(
        PairedStockCorr,
        cov_ij_ref / (Stock.volatility * PairedStockCorr.volatility),
    )
)

# Build the undirected correlation graph. Nodes are Stocks; edges link stocks
# with |correlation| >= CORR_THRESHOLD. Correlations are filtered in PyRel
# against the derived Stock.correlation property.
corr_graph = Graph(
    model,
    name="corr_graph",
    directed=False,
    weighted=False,
    node_concept=Stock,
    aggregator="sum",
)

stock_i_ref = Stock.ref()
stock_j_ref = Stock.ref()
corr_ref = Float.ref()
model.define(corr_graph.Edge.new(src=stock_i_ref, dst=stock_j_ref)).where(
    stock_i_ref.correlation(stock_j_ref, corr_ref),
    stock_i_ref.index < stock_j_ref.index,
    math_abs(corr_ref) >= CORR_THRESHOLD,
)

# Louvain community detection -- stored as Stock.cluster (integer id).
community = corr_graph.louvain()
cluster_label = Integer.ref("cluster_label")
stock_clust_ref = Stock.ref()
model.define(stock_clust_ref.cluster(cluster_label)).where(
    community(stock_clust_ref, cluster_label)
)

# Representative selection: for each cluster, the single stock with the
# highest Sharpe (return / volatility) is the cluster representative. If
# several stocks co-move strongly they carry near-identical exposure --
# prefer the best risk-adjusted one and drop the rest from the investable
# universe. This collapses redundant bets instead of merely capping them.
model.define(Stock.sharpe(Stock.returns / Stock.volatility))

# Per-cluster maximum Sharpe, written back onto each Stock.
peer_for_max = Stock.ref()
model.define(
    Stock.cluster_max_sharpe(
        aggs.max(peer_for_max.sharpe)
        .where(peer_for_max.cluster == Stock.cluster)
        .per(Stock)
    )
)

# Representative Relationship: stock whose Sharpe equals its cluster's max.
model.where(Stock.sharpe == Stock.cluster_max_sharpe).define(Stock.is_representative())

# Complementary Relationship used positively in solver constraints
# (the prescriptive rewriter doesn't accept `model.not_(...)` in a .where()).
model.where(Stock.sharpe < Stock.cluster_max_sharpe).define(
    Stock.is_non_representative()
)


# --------------------------------------------------
# Summaries of the clustering
# --------------------------------------------------

# The correlation graph's edge count, as the graph counts it.
edge_count = Integer.ref()
num_edges = model.Relationship(f"the correlation graph has {Integer:num_edges} edges")
model.where(corr_graph.num_edges()(edge_count)).define(num_edges(edge_count))

# Each Louvain cluster and the number of stocks in it.
Cluster = model.Concept("Cluster", identify_by={"cluster_id": Integer})
Cluster.size = model.Property(f"{Cluster} has {Integer:size}")
model.define(Cluster.new(cluster_id=Stock.cluster))
model.define(
    Cluster.size(aggs.count(Stock).per(Cluster).where(Stock.cluster == Cluster.cluster_id))
)

num_clusters = model.Relationship(f"the stocks form {Integer:num_clusters} clusters")
num_stocks = model.Relationship(f"there are {Integer:num_stocks} stocks")
num_representatives = model.Relationship(
    f"{Integer:num_representatives} stocks represent their clusters"
)
model.define(num_clusters(aggs.count(Cluster) | 0))
model.define(num_stocks(aggs.count(Stock) | 0))
model.define(num_representatives(aggs.count(Stock).where(Stock.is_representative()) | 0))

# Average correlation over the stock pairs (i < j) that share a cluster and over the pairs in
# different clusters; 0.0 when there is no such pair.
intra_cluster_correlation = model.Relationship(
    f"stocks in the same cluster have average correlation {Float:intra_cluster_correlation}"
)
inter_cluster_correlation = model.Relationship(
    f"stocks in different clusters have average correlation {Float:inter_cluster_correlation}"
)
model.define(
    intra_cluster_correlation(
        aggs.avg(stock_i_ref, stock_j_ref, corr_ref).where(
            stock_i_ref.correlation(stock_j_ref, corr_ref),
            stock_i_ref.index < stock_j_ref.index,
            stock_i_ref.cluster == stock_j_ref.cluster,
        )
        | 0.0
    )
)
model.define(
    inter_cluster_correlation(
        aggs.avg(stock_i_ref, stock_j_ref, corr_ref).where(
            stock_i_ref.correlation(stock_j_ref, corr_ref),
            stock_i_ref.index < stock_j_ref.index,
            stock_i_ref.cluster != stock_j_ref.cluster,
        )
        | 0.0
    )
)
