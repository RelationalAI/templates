"""Demand-forecasting model: Favorita-shaped sales data and a regression GNN.

Modules: `temporal_split.py` (the validation and test cutoffs from the latest sale date, and the
Train, Val, and Test relationships), `demand_forecast.py` (the graph, the GNN, and its
predictions), `forecast_accuracy.py` (each predicted sale's forecast against its actual sales,
the weekly rollup per store city and item family, and the RMSEs), and `sales_summary.py` (the
record counts and the range of unit sales). Each module imports the modules whose declarations
it reads.

`rai models deploy --path model` deploys everything this package declares.
"""

from .demand_forecast import gnn
from .forecast_accuracy import SaleForecast, SaleRmse, WeeklyForecast, WeeklyRmse
from .sales_summary import SalesCounts, UnitSales
from .schema import Item, ItemFamily, Sale, Store, model
from .source import DATA_DIR
from .temporal_split import TestStart, ValStart

__all__ = [
    "DATA_DIR",
    "Item",
    "ItemFamily",
    "Sale",
    "SaleForecast",
    "SaleRmse",
    "SalesCounts",
    "Store",
    "TestStart",
    "UnitSales",
    "ValStart",
    "WeeklyForecast",
    "WeeklyRmse",
    "gnn",
    "model",
]
