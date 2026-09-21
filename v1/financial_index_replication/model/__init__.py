"""Financial index replication model and bundled sample data."""

from .schema import ReturnDate, Sector, Stock, model
from .source import DATA_DIR, index_returns_csv, stock_returns_csv, stocks_csv

__all__ = [
    "DATA_DIR",
    "ReturnDate",
    "Sector",
    "Stock",
    "index_returns_csv",
    "model",
    "stock_returns_csv",
    "stocks_csv",
]
