"""Supplier Reliability (prescriptive optimization) template: the model.

This package declares a sourcing optimization model in RelationalAI that
minimizes total sourcing cost subject to supplier capacity and product demand, then
reads back the *marginals* a planner asks next (and stress-tests supplier reliability
with disruption scenarios):

- Load sample CSVs describing suppliers, products, and supplier-product supply options.
- Model those entities as *concepts* with typed properties.
- Choose non-negative order quantities for each supply option.
- Enforce supplier capacity limits and product demand satisfaction.
- Minimize total cost.

A plain solve answers "what is the cheapest sourcing plan?". Configuring the baseline solve
with ``sensitivity=True`` ALSO answers the marginal questions -- in one solve, with the
answers read off the variable / constraint objects (the same attribute style as ``.name``
or ``.lower``) and published through relationships the queries select:

- **Shadow price** of a supplier's capacity (``cap.shadow_price``): how much total
  cost moves per unit of capacity. A capacity with room to spare prices at zero; a
  nonzero price marks a binding bottleneck -- so this ranks which supplier to expand
  first. (One way only: slack => zero price, nonzero price => binding.)
- **Shadow price** of a product's demand (``meet.shadow_price``): the marginal cost
  to serve one more unit of that product.
- **Reduced cost** of a supply lane (``qty_var.reduced_cost``) and its **basis
  status** (``qty_var.basis_status``): which lanes are priced out versus in use.

A constraint declared with ``keyed_by={"supplier": Supplier}`` carries an entity
back-pointer to what it grounds over (``cap.supplier`` / ``meet.product``), so a
marginal joins to that entity's own data by ENTITY KEY (``cap.supplier.capacity``)
-- never by parsing the constraint name string. (A variable's back-pointer, such as
``qty_var.supplyorder``, is derived automatically from its field names; a
constraint's is declared.)

Modeling approach:
- Phase A: one baseline Problem solved with sensitivity; the marginals are read off the
  captured variable / constraint handles.
- Phase B: disruption scenarios (exclude SupplierC, exclude SupplierB), each a
  separate Problem with a where= filter -- a FINITE structural change the local
  marginals contextualize but do not by themselves predict.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs all three solves. Then
    `python -m queries.sourcing_report` prints the baseline plan with its capacity / demand
    shadow prices, lane reduced costs and basis status, then an order plan per disruption
    scenario and a summary table with termination status and objective value from the
    deployed model.
"""

from .reasoning import (
    EXCLUDED_SUPPLIERS,
    BaselineCost,
    BaselineOrder,
    BaselineStatus,
    CapacityShadowPrice,
    DemandShadowPrice,
    LaneBasisStatus,
    LaneReducedCost,
    scenarios,
)
from .schema import Product, Supplier, SupplyOption, SupplyOrder, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "EXCLUDED_SUPPLIERS",
    "BaselineCost",
    "BaselineOrder",
    "BaselineStatus",
    "CapacityShadowPrice",
    "DemandShadowPrice",
    "LaneBasisStatus",
    "LaneReducedCost",
    "Product",
    "Supplier",
    "SupplyOption",
    "SupplyOrder",
    "model",
    "scenarios",
]
