"""Smoker-status model: people, their connections, and a binary-classification GNN.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import People, Related, TestTable, TrainTable, ValidationTable, model
from .source import DATA_DIR

# isort: split
# The reasoning declares the graph and the GNN over the facts loaded above.
from .reasoning import SmokerPrediction, gnn

__all__ = [
    "DATA_DIR",
    "People",
    "Related",
    "SmokerPrediction",
    "TestTable",
    "TrainTable",
    "ValidationTable",
    "gnn",
    "model",
]
