"""Portfolio exposure: each sector's solved weight against its benchmark weight, and the turnover
from the previous portfolio that the solved weights imply."""

from relationalai.semantics import Float, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

# Declares Stock.x_weight, the solved replication weights the exposures read.
from . import portfolio_selection  # noqa: F401
from .schema import Sector, Stock, model

# --------------------------------------------------
# Sector exposure
# --------------------------------------------------

# One row per sector, kept apart from Sector: the solve reads Sector, so a property
# computed from the solution there fails the deploy.
SectorExposure = model.Concept("SectorExposure", identify_by={"sector_name": String})
SectorExposure.weight = model.Property(f"{SectorExposure} holds {Float:weight} of the portfolio")
SectorExposure.benchmark_weight = model.Property(
    f"{SectorExposure} has benchmark weight {Float:benchmark_weight}"
)
SectorExposure.active_weight = model.Property(
    f"{SectorExposure} has active weight {Float:active_weight}"
)
model.define(SectorExposure.new(sector_name=Sector.sector_name))
model.define(
    SectorExposure.weight(
        aggs.sum(Stock, Stock.x_weight)
        .per(SectorExposure)
        .where(Stock.sector == SectorExposure.sector_name)
    )
)
model.define(SectorExposure.benchmark_weight(Sector.benchmark_weight)).where(
    Sector.sector_name == SectorExposure.sector_name
)
model.define(SectorExposure.active_weight(SectorExposure.weight - SectorExposure.benchmark_weight))

# --------------------------------------------------
# Turnover
# --------------------------------------------------

# Implied turnover: the sum over stocks of the absolute change from the previous weight.
ImpliedTurnover = model.Relationship(f"the replica's implied turnover is {Float:turnover}")
model.define(ImpliedTurnover(aggs.sum(Stock, math.abs(Stock.x_weight - Stock.previous_weight))))
