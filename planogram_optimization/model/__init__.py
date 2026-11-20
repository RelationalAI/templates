"""Planogram Optimization (predict-then-optimize) template: the model.

This package demonstrates a predictive + prescriptive shelf-allocation problem
in RelationalAI:

- Decide integer facing counts per SKU on each shelf.
- Per-(SKU, facing_count) expected weekly demand comes from a vendored
  prediction table (a stand-in for any per-(SKU, k) regression model).
- The predict->CSP hand-off is an *element-style decision-indexed table
  lookup*: for each SKU, `Sku.realized_demand` is bound to the
  `PredictedDemand.demand_units` row whose `facings_count` matches the chosen
  `Sku.facings`. Pure CSP -- no bilinearity, no big-M, no SOS2.
- Solve as a maximization problem (MiniZinc) and inspect the allocation.

Modeling approach:
- One free integer decision per SKU (`facings` in `[0, max_facings]`) plus
  two integer variables pinned by ICs: `realized_demand` (via the lookup)
  and `active` (a 0/1 indicator coupled to `facings` by a linear-inequality
  pair so the per-category active-SKU cardinality is expressible as
  `sum(Sku.active).per(Category)`).
- Capacity, cardinality, and the active-iff-facings coupling are pure
  relational arithmetic constraints. The implies-bodied table lookup is
  solver-only; the report re-validates `(sku_id, facings) -> demand_units`
  against the deployed demand table via a Python dict lookup.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve.
    `python -m queries.facings_plan` then prints the report from the deployed model.
"""

from .reasoning import SolveStatus, TotalDemand, problem
from .schema import Category, PredictedDemand, Shelf, Sku, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Category",
    "PredictedDemand",
    "Shelf",
    "Sku",
    "SolveStatus",
    "TotalDemand",
    "model",
    "problem",
]
