"""Financial index replication model: bundled sample data and the decision problem.

`rai models deploy --path model` deploys everything this package declares.
"""

from .schema import ReturnMonth, Sector, Stock, model
from .source import DATA_DIR

# isort: split
# The decision problem declares variables and constraints over the facts loaded above.
from .reasoning import (
    MAX_ADV_PARTICIPATION,
    MAX_WEIGHT,
    MONTHS_PER_YEAR,
    N_REPLICATION_NAMES,
    PORTFOLIO_VALUE,
    SECTOR_ACTIVE_BAND,
    SolveStatus,
    TotalResidual,
    selected,
    stock_return,
    weight,
)

__all__ = [
    "DATA_DIR",
    "MAX_ADV_PARTICIPATION",
    "MAX_WEIGHT",
    "MONTHS_PER_YEAR",
    "N_REPLICATION_NAMES",
    "PORTFOLIO_VALUE",
    "SECTOR_ACTIVE_BAND",
    "ReturnMonth",
    "Sector",
    "SolveStatus",
    "Stock",
    "TotalResidual",
    "model",
    "selected",
    "stock_return",
    "weight",
]
