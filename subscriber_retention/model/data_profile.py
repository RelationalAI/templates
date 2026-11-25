"""Data profile: how many subscribers, calls, and split subscribers the model holds, and the range of
the churn-risk scores."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs

# Loads the subscribers, calls, and split tables, declaring Subscriber.churn_risk_score.
from . import source  # noqa: F401
from .schema import Call, Subscriber, TestTable, TrainTable, ValTable, model

# The size of each loaded table and of the three split tables.
DataCounts = model.Relationship(
    f"the data has {Integer:subscribers} subscribers, {Integer:calls} calls, and splits of "
    f"{Integer:train} training, {Integer:val} validation, and {Integer:test} test subscribers"
)
model.define(
    DataCounts(
        aggs.count(Subscriber),
        aggs.count(Call),
        aggs.count(TrainTable),
        aggs.count(ValTable),
        aggs.count(TestTable),
    )
)

# The churn-risk score range over the subscribers that have a score.
ChurnRiskRange = model.Relationship(
    f"churn risk scores have minimum {Float:minimum}, mean {Float:mean}, and maximum {Float:maximum}"
)
model.define(
    ChurnRiskRange(
        aggs.min(Subscriber.churn_risk_score),
        aggs.avg(Subscriber, Subscriber.churn_risk_score),
        aggs.max(Subscriber.churn_risk_score),
    )
)
