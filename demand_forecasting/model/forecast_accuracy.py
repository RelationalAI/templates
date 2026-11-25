"""Forecast accuracy: each predicted sale's forecast against its actual sales, the weekly rollup per
store city and item family, and the test-set RMSE per sale and per weekly rollup."""

from relationalai.semantics import DateTime, Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime, floats, math

# Declare Sale.predictions, the GNN forecasts, and the loaded Sale, Store, and Item properties.
from . import demand_forecast, source  # noqa: F401
from .schema import Item, Sale, Store, model

# --------------------------------------------------
# Forecast of each predicted sale
# --------------------------------------------------
# One row per predicted sale, kept apart from Sale: the GNN reads Sale, so a Sale
# property derived from the predictions would make the predictions depend on
# themselves. A sale whose store or item is missing has no city or family.
SaleForecast = model.Concept("SaleForecast", identify_by={"sale_id": Integer})
SaleForecast.actual = model.Property(f"{SaleForecast} has actual sales {Float:actual}")
SaleForecast.predicted = model.Property(f"{SaleForecast} has forecast sales {Float:predicted}")
SaleForecast.error = model.Property(f"{SaleForecast} has forecast error {Float:error}")
SaleForecast.week_start = model.Property(
    f"{SaleForecast} is in the week starting {DateTime:week_start}"
)
SaleForecast.city = model.Property(f"{SaleForecast} is in the city {String:city}")
SaleForecast.family = model.Property(f"{SaleForecast} is of the family {String:family}")
model.define(SaleForecast.new(sale_id=Sale.sale_id)).where(Sale.predictions)
_of_sale = Sale.sale_id == SaleForecast.sale_id
model.define(SaleForecast.actual(floats.float(Sale.unit_sales))).where(_of_sale)
# The forecast is clipped at zero.
model.define(SaleForecast.predicted(math.maximum(Sale.predictions.predicted_value, 0.0))).where(
    Sale.predictions, _of_sale
)
model.define(SaleForecast.error(SaleForecast.predicted - SaleForecast.actual))
# The week starts at midnight on the Monday on or before the sale date, whatever the sale's time.
_sale_day = datetime.datetime.to_date(Sale.date)
model.define(
    SaleForecast.week_start(
        datetime.date.to_datetime(
            datetime.date.subtract(_sale_day, datetime.days(datetime.date.weekday(_sale_day)))
        )
    )
).where(_of_sale)
model.define(SaleForecast.city(Store.city)).where(_of_sale, Sale.store_id == Store.store_id)
model.define(SaleForecast.family(Item.family)).where(_of_sale, Sale.item_id == Item.item_id)

# --------------------------------------------------
# Weekly forecast per (city, item family)
# --------------------------------------------------
# Forecasts without a city or family are left out of the weekly rollup.
WeeklyForecast = model.Concept(
    "WeeklyForecast", identify_by={"city": String, "family": String, "week_start": DateTime}
)
WeeklyForecast.actual = model.Property(f"{WeeklyForecast} has actual sales {Float:actual}")
WeeklyForecast.predicted = model.Property(f"{WeeklyForecast} has forecast sales {Float:predicted}")
WeeklyForecast.error = model.Property(f"{WeeklyForecast} has forecast error {Float:error}")
WeeklyForecast.abs_err = model.Property(f"{WeeklyForecast} has absolute error {Float:abs_err}")
model.define(
    WeeklyForecast.new(
        city=SaleForecast.city, family=SaleForecast.family, week_start=SaleForecast.week_start
    )
)
_in_week = (
    SaleForecast.city == WeeklyForecast.city,
    SaleForecast.family == WeeklyForecast.family,
    SaleForecast.week_start == WeeklyForecast.week_start,
)
model.define(
    WeeklyForecast.actual(
        aggs.sum(SaleForecast, SaleForecast.actual).per(WeeklyForecast).where(*_in_week)
    ),
    WeeklyForecast.predicted(
        aggs.sum(SaleForecast, SaleForecast.predicted).per(WeeklyForecast).where(*_in_week)
    ),
)
model.define(WeeklyForecast.error(WeeklyForecast.predicted - WeeklyForecast.actual))
model.define(WeeklyForecast.abs_err(math.abs(WeeklyForecast.error)))

# --------------------------------------------------
# Test-set RMSE
# --------------------------------------------------
SaleRmse = model.Relationship(f"the test-set RMSE per sale is {Float:rmse}")
WeeklyRmse = model.Relationship(f"the test-set RMSE per (city, family, week) is {Float:rmse}")
model.define(SaleRmse(math.sqrt(aggs.avg(SaleForecast, SaleForecast.error * SaleForecast.error))))
model.define(
    WeeklyRmse(math.sqrt(aggs.avg(WeeklyForecast, WeeklyForecast.error * WeeklyForecast.error)))
)
