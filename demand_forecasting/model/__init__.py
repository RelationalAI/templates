"""Demand-forecasting model: Favorita-shaped sales data and a regression GNN.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import Item, ItemFamily, Sale, Store, TestTable, TrainTable, ValTable, model
from .source import test_start, val_start

# isort: split
# The reasoning declares the graph and the GNN over the facts loaded above.
from .reasoning import gnn

__all__ = [
    "Item",
    "ItemFamily",
    "Sale",
    "Store",
    "TestTable",
    "TrainTable",
    "ValTable",
    "gnn",
    "model",
    "test_start",
    "val_start",
]
