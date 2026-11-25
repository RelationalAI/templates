"""Prediction summary: each scored subscriber's rank by predicted risk within its segment, the scored
subscribers per segment, and the root mean squared error of the predictions."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

from .churn_predictor import ChurnRiskPrediction
from .schema import model

# The retention queue order within a segment: highest predicted risk first, ties broken by the
# lower subscriber id. The risk is negated so both keys sort ascending, a form every backend ranks.
ChurnRiskPrediction.segment_rank = model.Property(
    f"{ChurnRiskPrediction} has {Integer:segment_rank} in its segment"
)
segment = String.ref()
model.where(
    ChurnRiskPrediction.subscriber.segment == segment,
    segment_rank := aggs.rank(-ChurnRiskPrediction.predicted_risk, ChurnRiskPrediction.sub_id).per(segment),
).define(ChurnRiskPrediction.segment_rank(segment_rank))

# The number of scored subscribers in each segment.
ScoredPerSegment = model.Relationship(f"segment {String:segment} has {Integer:n_scored} scored subscribers")
model.where(ChurnRiskPrediction.subscriber.segment == segment).define(
    ScoredPerSegment(segment, aggs.count(ChurnRiskPrediction).per(segment))
)

# The root mean squared error of the predicted risk against the subscribers' actual risk score.
TestRmse = model.Relationship(f"the predicted churn risk has a root mean squared error of {Float:rmse}")
error = ChurnRiskPrediction.predicted_risk - ChurnRiskPrediction.subscriber.churn_risk_score
model.where(mean_squared_error := aggs.avg(ChurnRiskPrediction, error * error)).define(
    TestRmse(math.sqrt(mean_squared_error))
)
