"""Shared schema and explicit source loaders for fraud detection."""

from .schema import (
    Account,
    Test,
    TestTable,
    Train,
    TrainTable,
    Transaction,
    Val,
    ValTable,
    model,
)
from .source import load_local_data, load_snowflake_data

__all__ = [
    "Account",
    "Test",
    "TestTable",
    "Train",
    "TrainTable",
    "Transaction",
    "Val",
    "ValTable",
    "load_local_data",
    "load_snowflake_data",
    "model",
]
