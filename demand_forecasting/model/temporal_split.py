"""Temporal split: the test and validation cutoffs derived from the latest sale date, and the Train,
Val, and Test relationships of the sales on each side of them."""

from relationalai.semantics import DateTime
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime

# Declares Sale.date and Sale.unit_sales, the columns of the loaded sales.
from . import source  # noqa: F401
from .schema import Sale, Test, Train, Val, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

TEST_DAYS = 60  # last 60 days as test window
VAL_DAYS = 60  # 60 days before test as validation

# --------------------------------------------------
# Train / Val / Test split (temporal)
# --------------------------------------------------
# Forecast use cases require temporal splits: training on the past, evaluating
# on the future. Random splits leak future signal into training.

# The test window is the last TEST_DAYS days of sales; the validation window is
# the VAL_DAYS days before it.
LatestSale = model.Relationship(f"the latest sale is on {DateTime:latest}")
TestStart = model.Relationship(f"the test window starts on {DateTime:test_start}")
ValStart = model.Relationship(f"the validation window starts on {DateTime:val_start}")
model.define(LatestSale(aggs.max(Sale.date)))
_latest, _test_start, _val_start = DateTime.ref(), DateTime.ref(), DateTime.ref()
model.where(LatestSale(_latest)).define(
    TestStart(datetime.datetime.subtract(_latest, datetime.days(TEST_DAYS - 1)))
)
model.where(TestStart(_test_start)).define(
    ValStart(datetime.datetime.subtract(_test_start, datetime.days(VAL_DAYS)))
)

# Train: before the validation window. Val: from the validation window up to the
# test window. Test: from the test window on. The GNN trains on the past and
# evaluates on the future.
model.where(ValStart(_val_start), Sale.date < _val_start).define(
    Train(Sale, Sale.date, Sale.unit_sales)
)
model.where(
    ValStart(_val_start), TestStart(_test_start), Sale.date >= _val_start, Sale.date < _test_start
).define(Val(Sale, Sale.date, Sale.unit_sales))
model.where(TestStart(_test_start), Sale.date >= _test_start).define(Test(Sale, Sale.date))
