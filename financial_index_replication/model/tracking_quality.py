"""Tracking quality: each month's replica and baseline returns and their differences from the
index, and the annualized tracking errors and mean absolute residual that summarize them."""

from relationalai.semantics import Float, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

# Declares Stock.x_weight, the solved replication weights the replica return reads.
from . import portfolio_selection  # noqa: F401
from .index_correlation import BASELINE_NAMES
from .schema import ReturnMonth, Stock, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

MONTHS_PER_YEAR = 12

# --------------------------------------------------
# Monthly returns and differences from the index
# --------------------------------------------------

# One row per month, kept apart from ReturnMonth: the solve reads ReturnMonth, so a
# property computed from the solution there fails the deploy.
TrackingMonth = model.Concept("TrackingMonth", identify_by={"date": String})
TrackingMonth.replica_return = model.Property(
    f"{TrackingMonth} has replica return {Float:replica_return}"
)
TrackingMonth.replica_difference = model.Property(
    f"{TrackingMonth} has replica difference {Float:replica_difference}"
)
TrackingMonth.baseline_return = model.Property(
    f"{TrackingMonth} has baseline return {Float:baseline_return}"
)
TrackingMonth.baseline_difference = model.Property(
    f"{TrackingMonth} has baseline difference {Float:baseline_difference}"
)
model.define(TrackingMonth.new(date=ReturnMonth.date))

# The replica's return is the weighted sum of the stock returns of the month; the
# baseline's is their mean over the BASELINE_NAMES stocks most correlated with the
# index. Each difference is that return less the index return.
_return = Float.ref()
_priced = (Stock.monthly_return(ReturnMonth, _return), ReturnMonth.date == TrackingMonth.date)
model.define(
    TrackingMonth.replica_return(
        aggs.sum(Stock, Stock.x_weight * _return).per(TrackingMonth).where(*_priced)
    )
)
model.define(
    TrackingMonth.baseline_return(
        aggs.avg(Stock, _return)
        .per(TrackingMonth)
        .where(*_priced, Stock.correlation_rank <= BASELINE_NAMES)
    )
)
model.where(ReturnMonth.date == TrackingMonth.date).define(
    TrackingMonth.replica_difference(TrackingMonth.replica_return - ReturnMonth.index_return)
)
model.where(ReturnMonth.date == TrackingMonth.date).define(
    TrackingMonth.baseline_difference(TrackingMonth.baseline_return - ReturnMonth.index_return)
)

# --------------------------------------------------
# Summary measures
# --------------------------------------------------

# Annualized tracking error: the root mean square of the monthly differences,
# scaled by the square root of the months in a year.
AnnualizedTrackingError = model.Relationship(
    f"the replica's annualized tracking error is {Float:tracking_error}"
)
model.define(
    AnnualizedTrackingError(
        math.sqrt(
            aggs.avg(
                TrackingMonth, TrackingMonth.replica_difference * TrackingMonth.replica_difference
            )
        )
        * math.sqrt(MONTHS_PER_YEAR)
    )
)
BaselineTrackingError = model.Relationship(
    f"the baseline's annualized tracking error is {Float:tracking_error}"
)
model.define(
    BaselineTrackingError(
        math.sqrt(
            aggs.avg(
                TrackingMonth, TrackingMonth.baseline_difference * TrackingMonth.baseline_difference
            )
        )
        * math.sqrt(MONTHS_PER_YEAR)
    )
)

# Mean absolute monthly difference of the replica from the index.
MeanAbsResidual = model.Relationship(
    f"the replica's mean absolute monthly residual is {Float:residual}"
)
model.define(MeanAbsResidual(aggs.avg(TrackingMonth, math.abs(TrackingMonth.replica_difference))))
