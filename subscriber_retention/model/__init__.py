"""Subscriber-retention model: telco call data, PageRank and call-volume features, and a churn-risk GNN.

`rai models deploy --path model` deploys everything this package declares.
"""

from .reasoning import gnn
from .schema import Call, Subscriber, TestTable, TrainTable, ValTable, model
from .source import DATA_DIR

__all__ = [
    "Call",
    "DATA_DIR",
    "Subscriber",
    "TestTable",
    "TrainTable",
    "ValTable",
    "gnn",
    "model",
]
