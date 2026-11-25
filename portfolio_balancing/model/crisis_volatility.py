"""Crisis stress: the volatility of each frontier point, and the volatility of the same solve at the same
budget under the base and the crisis regime with the gap between them."""

from relationalai.semantics import Float
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import sqrt

# Declares FrontierPoint's risk, solve, and scenario, which the volatilities read.
from . import efficient_frontier  # noqa: F401
from .schema import FrontierPoint, model

# --------------------------------------------------
# Stage 4: Stress -- base vs crisis volatility
# --------------------------------------------------

# Volatility is the square root of a point's risk (its variance).
FrontierPoint.volatility = model.Property(f"{FrontierPoint} has {Float:volatility}")
model.define(FrontierPoint.volatility(sqrt(FrontierPoint.risk)))

# The volatility of the same solve at the same budget in the base and the crisis regime
# (this point's own, when it is in that regime); 0.0 when no scenario has that regime.
FrontierPoint.vol_base = model.Property(f"{FrontierPoint} has {Float:vol_base}")
FrontierPoint.vol_crisis = model.Property(f"{FrontierPoint} has {Float:vol_crisis}")
_twin = FrontierPoint.ref()


def _regime_volatility(regime_name):
    return (
        aggs.sum(_twin, _twin.volatility)
        .per(FrontierPoint)
        .where(
            _twin.solve == FrontierPoint.solve,
            _twin.scenario.budget == FrontierPoint.scenario.budget,
            _twin.scenario.regime.regime_name == regime_name,
        )
        | 0.0
    )


model.define(
    FrontierPoint.vol_base(_regime_volatility("base")),
    FrontierPoint.vol_crisis(_regime_volatility("crisis")),
)

# The crisis volatility less the base volatility, and that gap as a fraction of the base
# volatility (0.0 for a base volatility of zero).
FrontierPoint.vol_gap = model.Property(f"{FrontierPoint} has {Float:vol_gap}")
FrontierPoint.vol_gap_ratio = model.Property(f"{FrontierPoint} has {Float:vol_gap_ratio}")
model.define(FrontierPoint.vol_gap(FrontierPoint.vol_crisis - FrontierPoint.vol_base))
model.where(FrontierPoint.vol_base > 1e-9).define(
    FrontierPoint.vol_gap_ratio(FrontierPoint.vol_gap / FrontierPoint.vol_base)
)
model.where(FrontierPoint.vol_base <= 1e-9).define(FrontierPoint.vol_gap_ratio(0.0))
