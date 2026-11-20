"""The call graph and its PageRank, the call-volume features, and the churn-risk GNN."""

from relationalai.semantics import Float, Integer, count
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

from .schema import Call, Subscriber, Test, Train, Val, model
from .source import SEED

STREAM_LOGS = False

# --------------------------------------------------
# Graph: PageRank on the call graph
# --------------------------------------------------
# Build a directed Subscriber -> Subscriber graph with one edge per call.
# PageRank scores act as a "social influence" continuous feature.

call_graph = Graph(
    model,
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

# --------------------------------------------------
# PropertyTransformer -- declare feature types
# --------------------------------------------------

pt = PropertyTransformer(
    drop=[
        Subscriber.sub_id,  # PK -- graph carries identity
        Subscriber.postal_code,  # high-cardinality int ID; noise as a feature
        Subscriber.churn_risk_score,  # target -- never a feature
    ],
    category=[
        Subscriber.subscriber_type,
        Subscriber.segment,
        Subscriber.status,
        Subscriber.plan_type,
        Subscriber.auto_renew,
    ],
    continuous=[
        Subscriber.lifetime_value_usd,
        Subscriber.monthly_rate_usd,
        Subscriber.early_termination_fee_usd,
        Subscriber.pagerank,  # graph-reasoner feature
    ],
    integer=[
        Subscriber.nps_score,
        Subscriber.data_limit_gb,
        Subscriber.term_months,
        Subscriber.outgoing_calls,  # rule-derived feature
        Subscriber.incoming_calls,  # rule-derived feature
    ],
    datetime=[Subscriber.signup_date],
)

# --------------------------------------------------
# Predictive: GNN regression on CHURN_RISK_SCORE
# --------------------------------------------------
# `name` ties this GNN to the registered model and version that
# `reasoners.predictive.gnns.churn_risk` names in raiconfig.yaml: train.py
# registers the trained run there, and every refresh scores the test
# subscribers with it.

gnn = GNN(
    name="churn_risk",
    graph=call_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    stream_logs=STREAM_LOGS,
    seed=SEED,
    n_epochs=20,
    lr=0.005,
)
Subscriber.predictions = gnn.predictions(domain=Test)
