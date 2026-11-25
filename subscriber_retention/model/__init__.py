"""Subscriber-retention model: telco call data, PageRank and call-volume features, and a churn-risk GNN.

`rai models deploy --path model` deploys everything this package declares. The model is split by
stage, and each module imports the modules whose declarations it reads:

- `call_signals.py`: the call graph, PageRank, and the call-volume features.
- `churn_predictor.py`: the churn-risk GNN and the predicted risk it publishes.
- `data_profile.py`: the data and split counts and the churn-risk score range.
- `prediction_summary.py`: each prediction's rank within its segment, the scored subscribers per
  segment, and the root mean squared error.
"""

from .call_signals import call_graph
from .churn_predictor import ChurnRiskPrediction, gnn
from .data_profile import ChurnRiskRange, DataCounts
from .prediction_summary import ScoredPerSegment, TestRmse
from .schema import Call, Subscriber, TestTable, TrainTable, ValTable, model
from .source import DATA_DIR

__all__ = [
    "Call",
    "ChurnRiskPrediction",
    "ChurnRiskRange",
    "DATA_DIR",
    "DataCounts",
    "ScoredPerSegment",
    "Subscriber",
    "TestRmse",
    "TestTable",
    "TrainTable",
    "ValTable",
    "call_graph",
    "gnn",
    "model",
]
