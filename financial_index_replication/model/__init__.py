"""Financial index replication model: bundled sample data and the decision problem.

Modules: `portfolio_selection.py` (the replication policy and the decision problem that picks
the basket), `index_correlation.py` (each stock's correlation with the index, which picks the
baseline), `tracking_quality.py` (monthly replica and baseline returns against the index and
their tracking errors), and `portfolio_exposure.py` (sector exposure and turnover). Each module
imports the modules whose declarations it reads.

`rai models deploy --path model` deploys everything this package declares.
"""

from .index_correlation import BASELINE_NAMES
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
    BaselineTrackingError,
    MeanAbsResidual,
    TrackingMonth,
)

__all__ = [
    "BASELINE_NAMES",
    "DATA_DIR",
    "MAX_ADV_PARTICIPATION",
    "MAX_WEIGHT",
    "MONTHS_PER_YEAR",
    "N_REPLICATION_NAMES",
    "PORTFOLIO_VALUE",
    "SECTOR_ACTIVE_BAND",
    "AnnualizedTrackingError",
    "BaselineTrackingError",
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
