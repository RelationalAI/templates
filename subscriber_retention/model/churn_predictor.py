"""Churn-risk predictor: the GNN that scores each test subscriber's churn risk, and the predicted
risk it publishes."""

from relationalai.semantics import Float, String
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

# Declares Subscriber.pagerank, outgoing_calls and incoming_calls, the GNN's rule-derived features.
from .call_signals import call_graph
from .schema import Subscriber, Test, Train, Val, model
from .source import SEED

STREAM_LOGS = False

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

# The predicted churn risk of each scored (test) subscriber, which the deployed model
# publishes for the report. It is a concept of its own, not a Subscriber property: the
# GNN reads Subscriber, so a Subscriber property derived from the predictions would feed
# back into them.
ChurnRiskPrediction = model.Concept("ChurnRiskPrediction", identify_by={"sub_id": String})
ChurnRiskPrediction.predicted_risk = model.Property(
    f"{ChurnRiskPrediction} has predicted churn risk {Float:predicted_risk}"
)
ChurnRiskPrediction.subscriber = model.Property(f"{ChurnRiskPrediction} is for {Subscriber}")
predicted_risk = Float.ref()
model.where(Subscriber.predictions.predicted_value(predicted_risk)).define(
    prediction := ChurnRiskPrediction.new(sub_id=Subscriber.sub_id),
    prediction.predicted_risk(predicted_risk),
    prediction.subscriber(Subscriber),
)
