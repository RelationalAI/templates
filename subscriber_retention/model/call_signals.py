"""Call signals for the churn-risk model: the call graph, each subscriber's PageRank, and each
subscriber's counts of outgoing and incoming calls."""

from relationalai.semantics import Float, Integer, count
from relationalai.semantics.reasoners.graph import Graph

# Loads Call and Subscriber from the CSVs, declaring the call and subscriber columns read here.
from . import source  # noqa: F401
from .schema import Call, Subscriber, model

# --------------------------------------------------
# Graph: PageRank on the call graph
# --------------------------------------------------
# Build a directed Subscriber -> Subscriber graph with one edge per call.
# PageRank scores act as a "social influence" continuous feature.

call_graph = Graph(
    model,
    name="call_graph",
    directed=True,
    weighted=False,
    node_concept=Subscriber,
    aggregator="sum",
)
caller = Subscriber.ref()
callee = Subscriber.ref()
call_ref = Call.ref()
model.define(call_graph.Edge.new(src=caller, dst=callee)).where(
    call_ref.caller_sub_id == caller.sub_id,
    call_ref.callee_sub_id == callee.sub_id,
)

pagerank_rel = call_graph.pagerank()
Subscriber.pagerank = model.Property(f"{Subscriber} has {Float:pagerank}")
sub_pr = Subscriber.ref()
score_pr = Float.ref()
model.define(sub_pr.pagerank(score_pr)).where(pagerank_rel(sub_pr, score_pr))

# --------------------------------------------------
# Call-volume features (count-based rules)
# --------------------------------------------------
# count(Call).per(Subscriber) aggregates derive integer features alongside
# the PageRank score.

Subscriber.outgoing_calls = model.Property(
    f"{Subscriber} has {Integer:outgoing_calls}"
)
model.define(
    Subscriber.outgoing_calls(count(Call).per(Subscriber))
).where(Call.caller_sub_id == Subscriber.sub_id)

Subscriber.incoming_calls = model.Property(
    f"{Subscriber} has {Integer:incoming_calls}"
)
model.define(
    Subscriber.incoming_calls(count(Call).per(Subscriber))
).where(Call.callee_sub_id == Subscriber.sub_id)
