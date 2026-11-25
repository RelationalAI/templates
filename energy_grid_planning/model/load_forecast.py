"""Load forecast: each substation's predicted peak load, its growth over the current load, and the first
forecast month in which the predicted load exceeds its capacity."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.math import maximum

from .schema import DemandForecast, Substation, model

# --------------------------------------------------
# Stage 1: Forecast -- Substation Load
# --------------------------------------------------
# Enrich each Substation with a predicted_load property consumed by downstream
# stages: the maximum DemandForecast per substation.
Substation.predicted_load = model.Property(f"{Substation} has {Float:predicted_load}")
model.define(
    Substation.predicted_load(
        aggs.max(DemandForecast.predicted_load_mw)
        .where(DemandForecast.substation(Substation))
        .per(Substation)
    )
)

# Growth of the predicted peak over the current load (floored at 0.1 MW, so an idle
# substation still gets a growth figure), and the first forecast month whose
# predicted load exceeds the substation's capacity.
Substation.growth_rate = model.Property(f"{Substation} has load growth {Float:growth_rate}")
model.define(
    Substation.growth_rate(
        (Substation.predicted_load - Substation.current_load_mw)
        / maximum(Substation.current_load_mw, 0.1)
    )
)
Substation.breach_period = model.Property(
    f"{Substation} first exceeds capacity at {Integer:breach_period} months"
)
model.define(
    Substation.breach_period(
        aggs.min(DemandForecast.forecast_period)
        .where(
            DemandForecast.substation(Substation),
            DemandForecast.predicted_load_mw > Substation.max_capacity_mw,
        )
        .per(Substation)
    )
)
