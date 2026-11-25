"""Weekly demand: the demand of each site and SKU in each week of each planning horizon, zero for
weeks without orders."""

from relationalai.semantics import Integer, std
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

# Defines DemandOrder.week_num and OrderInPlan, the order scope the weekly demand sums.
from . import horizon_scope  # noqa: F401
from .schema import DemandOrder, OrderInPlan, ProdCapacity, WeeklyDemand, model
from .source import SCENARIO_VALUES, weeks_in_horizon

# A row for each site-SKU pair with capacity, in each week of each horizon.
_week = Integer.ref()
for planning_end in SCENARIO_VALUES:
    model.where(_week == std.common.range(1, weeks_in_horizon(planning_end) + 1)).define(
        WeeklyDemand.new(
            wk_planning_end=planning_end,
            wk_site_id=ProdCapacity.site_id,
            wk_sku_id=ProdCapacity.sku_id,
            wk_week_num=_week,
        )
    )

# The quantity ordered for the pair in the week by the horizon's orders, zero when none.
model.define(
    WeeklyDemand.wk_quantity(
        aggs.sum(DemandOrder, floats.float(DemandOrder.quantity))
        .per(WeeklyDemand)
        .where(
            OrderInPlan(DemandOrder, WeeklyDemand.wk_planning_end),
            DemandOrder.week_num == WeeklyDemand.wk_week_num,
            DemandOrder.site_id == WeeklyDemand.wk_site_id,
            DemandOrder.sku_id == WeeklyDemand.wk_sku_id,
        )
        | 0.0
    )
)
