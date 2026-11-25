"""Factory production (prescriptive optimization) template: the model.

This package declares a product-mix linear program in RelationalAI that
maximizes total profit subject to per-factory resource capacity, then reads back
the *marginals* a planner asks next:

- Load sample CSVs describing factories (resource availability) and the products
  each factory makes (production rate, unit profit, demand cap).
- Model them as *concepts* with typed properties.
- Choose a non-negative production quantity per product, capped by its demand.
- Limit each factory's total resource usage to its available hours.
- Maximize total profit.

A plain solve answers "what is the most profitable production plan?". Requesting
``sensitivity=True`` on the solve ALSO answers the marginal questions -- in one solve,
read off the variable / constraint objects (the same attribute style as ``.name`` or
``.lower``) and published through relationships the queries select:

- **Shadow price** of a factory's capacity (``cap.shadow_price``): how much total
  profit moves per extra hour of that factory. A capacity with idle hours prices at
  zero (it is not the bottleneck); a positive price flags a binding capacity worth
  expanding -- so this ranks which factory to expand first. (The implication runs one
  way: slack => zero price, and a positive price => binding; a binding capacity *can*
  still price at zero under degeneracy, though none does in this data.)
- **Reduced cost** of a product (``quantity_var.reduced_cost``) and its **basis
  status** (``quantity_var.basis_status``): a product held at its demand cap shows a
  positive reduced cost here (the extra profit per unit of demand allowed); the swing
  product that sets the binding factory's marginal price is BASIC at ~0.

Sign convention (the mirror image of a minimize-cost model): with a MAXIMIZE
objective, a binding ``<=`` capacity prices >= 0 and a product at its demand
*upper* bound has reduced cost >= 0. (Contrast the ``supplier_reliability``
template, which minimizes cost: there a binding ``<=`` capacity prices <= 0.) Note
the two sensitivity objects come from two different modeling choices: capacity is a
*constraint* (its marginal is a shadow price), while the demand cap is a variable
*upper bound* (its marginal is a reduced cost).

A constraint declared with ``keyed_by={"factory": Factory}`` carries an entity
back-pointer to what it grounds over (``cap.factory``), so a marginal joins to that
entity's own data by ENTITY KEY (``cap.factory.avail``) -- never by parsing the
constraint name string. (A variable's back-pointer, such as ``quantity_var.product``,
is derived automatically from its field names; a constraint's is declared.)

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve. Then
    `python -m queries.plan_and_sensitivity` prints the production plan, each factory's
    capacity shadow price, each product's reduced cost and basis status, and a
    per-factory capacity-utilization summary from the deployed model.
"""

from .reasoning import (
    CapacityShadowPrice,
    ProductBasisStatus,
    ProductReducedCost,
    SolveStatus,
    TotalProfit,
    problem,
)
from .schema import Factory, Product, model
from .source import DATA_DIR, EXPECTED_FACTORIES, EXPECTED_PRODUCTS

__all__ = [
    "CapacityShadowPrice",
    "DATA_DIR",
    "EXPECTED_FACTORIES",
    "EXPECTED_PRODUCTS",
    "Factory",
    "Product",
    "ProductBasisStatus",
    "ProductReducedCost",
    "SolveStatus",
    "TotalProfit",
    "model",
    "problem",
]
