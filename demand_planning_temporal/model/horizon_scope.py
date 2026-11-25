"""Horizon scope: the week of each demand order, the orders inside each planning horizon, and the
order counts."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime

from .schema import DemandOrder, OrderInPlan, model
from .source import SCENARIO_VALUES, planning_start

# DATE-TO-PERIOD MAPPING: weeks since planning_start, so the week of planning_start itself is 1
# and an order due before it falls in week 0 or earlier.
model.define(
    DemandOrder.week_num(
        datetime.date.diff(
            "day",
            datetime.date.fromisoformat(planning_start),
            datetime.date.fromisoformat(DemandOrder.due_date),
        )
        // 7
        + 1
    )
)

# DATE FILTERING: an order is in a horizon's plan when it is due from planning_start through that
# horizon's planning_end. ISO date strings compare as dates.
for planning_end in SCENARIO_VALUES:
    model.where(
        DemandOrder.due_date >= planning_start, DemandOrder.due_date <= planning_end
    ).define(OrderInPlan(DemandOrder, planning_end))

# The number of orders, and the number inside each horizon's plan (zero for an empty horizon).
NumOrders = model.Relationship(f"there are {Integer:num_orders} demand orders")
PlanOrderCount = model.Relationship(
    f"the plan ending {String:planning_end} has {Integer:n_orders} demand orders in scope"
)
model.define(NumOrders(aggs.count(DemandOrder)))
for planning_end in SCENARIO_VALUES:
    model.define(
        PlanOrderCount(
            planning_end, aggs.count(DemandOrder).where(OrderInPlan(DemandOrder, planning_end)) | 0
        )
    )
