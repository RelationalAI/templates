"""Demand-forecasting model: Favorita-shaped sales data and a regression GNN.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import Item, ItemFamily, Sale, Store, TestTable, TrainTable, ValTable, model
from .source import DATA_DIR, TEST_START, VAL_START

# isort: split
# The reasoning declares the graph and the GNN over the facts loaded above.
from .reasoning import gnn

__all__ = [
    "DATA_DIR",
    "Item",
    "ItemFamily",
    "Sale",
    "Store",
    "TEST_START",
    "TestTable",
    "TrainTable",
    "VAL_START",
    "ValTable",
    "gnn",
    "model",
]
