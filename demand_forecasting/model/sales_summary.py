"""Sales summary: the number of stores, items, and sales, the number of sales in each temporal
split, and the range and mean of unit sales."""

from relationalai.semantics import DateTime, Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# Declares Sale.unit_sales, a column of the loaded sales.
from . import source  # noqa: F401
from .schema import Item, Sale, Store, Test, Train, Val, model

SalesCounts = model.Relationship(
    f"the data has {Integer:stores} stores, {Integer:items} items and {Integer:sales} sales, "
    f"split into {Integer:train} train, {Integer:val} validation and {Integer:test} test sales"
)
_timestamp, _target = DateTime.ref(), Integer.ref()
model.define(
    SalesCounts(
        aggs.count(Store),
        aggs.count(Item),
        aggs.count(Sale),
        aggs.count(Sale).where(Train(Sale, _timestamp, _target)) | 0,
        aggs.count(Sale).where(Val(Sale, _timestamp, _target)) | 0,
        aggs.count(Sale).where(Test(Sale, _timestamp)) | 0,
    )
)

UnitSales = model.Relationship(
    f"unit sales range from {Integer:min_sales} to {Integer:max_sales} with mean {Float:mean_sales}"
)
model.define(
    UnitSales(
        aggs.min(Sale.unit_sales),
        aggs.max(Sale.unit_sales),
        aggs.avg(Sale, floats.float(Sale.unit_sales)),
    )
)
