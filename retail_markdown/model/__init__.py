"""Retail markdown (prescriptive optimization) template: the model.

This package demonstrates a retail markdown mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing products, discount levels, and weekly demand multipliers.
- Model products, discounts, and weeks as *concepts* with typed properties.
- Choose exactly one discount level per product per week (binary selection).
- Enforce a price ladder so discounts can only increase over time.
- Bound weekly sales by demand (base demand x discount lift x weekly multiplier).
- Track cumulative sales and ensure inventory is not exceeded.
- Maximize total revenue from discounted sales plus salvage value of leftover inventory.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.markdown_plan` then prints the report from the deployed model.
"""

from .reasoning import (
    Discount_ref,
    Week_ref,
    cumulative_ref,
    problem,
    sales_ref,
    selection_ref,
)
from .schema import Discount, Product, Week, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Discount",
    "Discount_ref",
    "Product",
    "Week",
    "Week_ref",
    "cumulative_ref",
    "model",
    "problem",
    "sales_ref",
    "selection_ref",
]
