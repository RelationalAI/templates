"""Smoker-status model: people, their connections, and a binary-classification GNN.

`rai models deploy --path model` deploys everything this package declares. `smoker_gnn.py` holds
the graph, the GNN, and the published predictions; `prediction_metrics.py` holds the table row
counts and the test-set accuracy, ROC-AUC, and class shares, and imports the module whose
declarations it reads.
"""

from .schema import People, Related, TestTable, TrainTable, ValidationTable, model
from .source import DATA_DIR

# isort: split
# The graph, the GNN, and the metrics are declared over the facts loaded above.
from .prediction_metrics import ClassShare, DataSummary, TestAccuracy, TestAuc, TestCohort
from .smoker_gnn import SmokerPrediction, gnn

__all__ = [
    "DATA_DIR",
    "ClassShare",
    "DataSummary",
    "People",
    "Related",
    "SmokerPrediction",
    "TestAccuracy",
    "TestAuc",
    "TestCohort",
    "TestTable",
    "TrainTable",
    "ValidationTable",
    "gnn",
    "model",
]
