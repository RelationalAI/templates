"""Capacity inputs: each site-SKU pair's starting inventory and weekly holding cost."""

from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

from .schema import SKU, InitialInventory, ProdCapacity, model

# Starting inventory of a pair: its recorded quantity, zero when the pair has no record.
model.define(
    ProdCapacity.initial_inventory(
        aggs.sum(InitialInventory, floats.float(InitialInventory.quantity))
        .per(ProdCapacity)
        .where(
            InitialInventory.site_id == ProdCapacity.site_id,
            InitialInventory.sku_id == ProdCapacity.sku_id,
        )
        | 0.0
    )
)

# Holding cost per week of a pair: its SKU's, so the solver expressions read a property of
# ProdCapacity rather than a traversal through SKU (which raises functional-dependency issues).
model.where(SKU.id == ProdCapacity.sku_id).define(
    ProdCapacity.holding_cost_per_week(SKU.holding_cost_per_week)
)
