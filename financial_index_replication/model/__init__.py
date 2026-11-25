"""Financial index replication model: bundled sample data and the decision problem.

Modules: `portfolio_selection.py` (the replication policy and the decision problem that picks
the basket), `tracking_quality.py` (monthly replica returns against the index and their tracking
error), and `portfolio_exposure.py` (sector exposure and turnover). Each module imports the
modules whose declarations it reads.

`rai models deploy --path model` deploys everything this package declares.
"""

from .portfolio_exposure import ImpliedTurnover, SectorExposure
from .portfolio_selection import (
    MAX_ADV_PARTICIPATION,
    MAX_WEIGHT,
    N_REPLICATION_NAMES,
    PORTFOLIO_VALUE,
    SECTOR_ACTIVE_BAND,
    SolveStatus,
    TotalResidual,
    num_stocks,
    selected,
    stock_return,
    weight,
)
from .schema import ReturnMonth, Sector, Stock, model
from .source import DATA_DIR
from .tracking_quality import (
    MONTHS_PER_YEAR,
    AnnualizedTrackingError,
    MeanAbsResidual,
    TrackingMonth,
)

__all__ = [
    "DATA_DIR",
    "MAX_ADV_PARTICIPATION",
    "MAX_WEIGHT",
    "MONTHS_PER_YEAR",
    "N_REPLICATION_NAMES",
    "PORTFOLIO_VALUE",
    "SECTOR_ACTIVE_BAND",
    "AnnualizedTrackingError",
    "ImpliedTurnover",
    "MeanAbsResidual",
    "ReturnMonth",
    "Sector",
    "SectorExposure",
    "SolveStatus",
    "Stock",
    "TotalResidual",
    "TrackingMonth",
    "model",
    "num_stocks",
    "selected",
    "stock_return",
    "weight",
]
