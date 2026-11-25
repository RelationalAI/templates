"""Customer impact: subscriber PageRank, each subscriber's customer value and its rank, and each critical
tower's impact on customers."""

from relationalai.semantics import Float, Integer, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

# Declares CellTower.is_critical_restore, the towers whose impact matters.
from . import critical_towers  # noqa: F401
from .schema import CallDetailRecord, CellTower, Subscriber, SubscriberStatus, model

# --------------------------------------------------
# Stage 3: Graph -- Customer impact analysis
# (PageRank as graph-reasoner signal; per-tower weighted_impact from
# customer_value (revenue x churn). PageRank-weighted impact retained
# as a secondary network-effect signal alongside the headline measure.)
# --------------------------------------------------

call_graph = Graph(
    model,
    name="call_graph",
    directed=True,
    weighted=False,
    node_concept=Subscriber,
    edge_concept=CallDetailRecord,
    edge_src_relationship=CallDetailRecord.caller,
    edge_dst_relationship=CallDetailRecord.callee,
    aggregator="sum",
)
call_graph.Node.influence_score = call_graph.pagerank()

# Per-subscriber customer_value = lifetime value weighted by churn risk:
# at-risk subscribers (high churn_risk_score) get up to ~1.9x the weight
# of stable ones. Possible refinements: SLA-tier and emergency-service
# multipliers; NPS-deterioration weighting; log-scaling to compress the
# enterprise-vs-consumer LTV gap (~130x in the bundled corpus).
model.define(Subscriber.customer_value(Subscriber.lifetime_value * (1.0 + Subscriber.churn_risk_score)))

CellTower.impact_count = model.Property(f"{CellTower} has {Float:impact_count}")
# weighted_impact is the headline per-tower customer-impact score: the
# sum of customer_value (revenue x churn) over the distinct ACTIVE
# subscribers whose calls route through the tower. The Stage 5 MIP
# objective consumes this directly to prioritize towers by
# revenue-at-risk weighted by churn urgency.
#
# The sum is keyed by subscriber, so a subscriber's value counts once per
# tower however many of their calls it carries: revenue at risk does not
# grow with call volume.
CellTower.weighted_impact = model.Property(f"{CellTower} has {Float:weighted_impact}")
# Secondary signal: PageRank-weighted impact retained so the graph
# reasoner's network-effect view is still queryable alongside the
# revenue-based headline. Not consumed by the Stage 5 objective.
CellTower.weighted_pagerank = model.Property(f"{CellTower} has {Float:weighted_pagerank}")

model.define(
    CellTower.impact_count(
        aggs.count(distinct(Subscriber))
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == SubscriberStatus.ACTIVE,
        )
        .per(CellTower)
    )
)
model.define(
    CellTower.weighted_impact(
        aggs.sum(Subscriber.customer_value)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == SubscriberStatus.ACTIVE,
        )
        .per(CellTower)
    )
)
model.define(
    CellTower.weighted_pagerank(
        aggs.sum(Subscriber.influence_score)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
            Subscriber.status == SubscriberStatus.ACTIVE,
        )
        .per(CellTower)
    )
)

# A critical tower is high-value when its weighted_impact reaches the 75th
# percentile of the critical towers' (interpolated linearly between ranks).
peer = CellTower.ref()
CellTower.is_high_value = model.Relationship(f"{CellTower} is a high-value critical tower")
model.where(
    CellTower.is_critical_restore(),
    CellTower.weighted_impact
    >= aggs.percentile(75, peer, peer.weighted_impact).where(peer.is_critical_restore()),
).define(CellTower.is_high_value())

# Subscribers ranked by customer value, highest first, ties broken by subscriber id. The
# value is negated so both keys sort ascending.
Subscriber.customer_rank = model.Property(f"{Subscriber} has {Integer:customer_rank}")
model.define(Subscriber.customer_rank(aggs.rank(-Subscriber.customer_value, Subscriber.id)))
