"""Retail markdown (prescriptive optimization) template.

This script demonstrates a retail markdown mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing products, discount options, and weekly demand multipliers.
- Choose exactly one discount level per product per week.
- Enforce a price ladder so discounts can only increase over time.
- Bound weekly sales by demand (base demand × discount lift × weekly multiplier).
- Track cumulative sales and ensure inventory is not exceeded.
- Maximize total revenue from discounted sales plus salvage value of leftover inventory.

Run:
    `python retail_markdown.py`

Output:
    Prints the solver termination status, objective value (sales + salvage), and
    three tables showing selected discounts, sales, and cumulative sales.
"""

from pathlib import Path
from time import time_ns

import pandas
from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, data, std, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model(
    f"retail_markdown_{time_ns()}",
    config=globals().get("config", None),
)

# Product concept: products with inventory, pricing, and demand parameters.
Product = model.Concept("Product")
Product.name = model.Property("{Product} has {name:string}")
Product.initial_price = model.Property("{Product} has {initial_price:float}")
Product.cost = model.Property("{Product} has {cost:float}")
Product.initial_inventory = model.Property("{Product} has {initial_inventory:int}")
Product.base_demand = model.Property("{Product} has {base_demand:float}")
Product.salvage_rate = model.Property("{Product} has {salvage_rate:float}")

# Load product data from CSV.
data(read_csv(DATA_DIR / "products.csv")).into(Product, keys=["name"])

# Discount concept: discount levels and their demand lift factors.
Discount = model.Concept("Discount")
Discount.level = model.Property("{Discount} has {level:int}")
Discount.discount_pct = model.Property("{Discount} has {discount_pct:float}")
Discount.demand_lift = model.Property("{Discount} has {demand_lift:float}")

# Load discount data from CSV.
data(read_csv(DATA_DIR / "discounts.csv")).into(Discount, keys=["level"])

# Week demand multipliers: loaded as a Python dict for use in per-week constraints.
# Note: Week is not defined as a Concept because non-solver concepts in satisfy()
# where clauses can cause "Uninitialized property: error_<concept>" in RAI v0.13.
weeks_df = read_csv(DATA_DIR / "weeks.csv")
demand_multiplier = dict(zip(weeks_df["week_num"], weeks_df["demand_multiplier"]))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Parameters.
week_start = 1
week_end = 4
weeks = std.range(week_start, week_end + 1)

t = Integer.ref()
d = Discount.ref()

# Create a continuous optimization model with a MILP formulation.
s = SolverModel(model, "cont")

# Product.x_selected decision variable: select exactly one discount per product-week.
Product.x_selected = model.Property("{Product} in week {t:int} at discount {d:Discount} is {selected:float}")
x_sel = Float.ref()
s.solve_for(
    Product.x_selected(t, d, x_sel),
    type="bin",
    name=["select", Product.name, t, d.discount_pct],
    where=[t == weeks],
)

# Product.x_sales decision variable: units sold at the chosen discount.
Product.x_sales = model.Property("{Product} in week {t:int} at discount {d:Discount} has {sales:float}")
x_sales = Float.ref()
s.solve_for(
    Product.x_sales(t, d, x_sales),
    type="cont",
    lower=0,
    name=["sales", Product.name, t, d.discount_pct],
    where=[t == weeks],
)

# Product.x_cum_sales decision variable: cumulative sales through each week.
Product.x_cum_sales = model.Property("{Product} through week {t:int} has {cum_sales:float}")
x_cum = Float.ref()
s.solve_for(
    Product.x_cum_sales(t, x_cum),
    type="cont",
    lower=0,
    name=["cum", Product.name, t],
    where=[t == weeks],
)

# Constraint: one discount level selected per product per week.
one_discount_per_week = where(
    Product.x_selected(t, d, x_sel)
).require(
    sum(x_sel).per(Product, t) == 1
)
s.satisfy(one_discount_per_week)

# Constraint: price ladder - discounts can only increase (prices can only decrease).
d1, d2 = Discount.ref(), Discount.ref()
x_sel1, x_sel2 = Float.ref(), Float.ref()
price_ladder = where(
    Product.x_selected(t, d1, x_sel1),
    Product.x_selected(t + 1, d2, x_sel2),
    d2.level < d1.level,
    t >= week_start,
    t < week_end
).require(
    x_sel1 + x_sel2 <= 1
)
s.satisfy(price_ladder)

# Constraint: sales only occur at the selected discount level.
for wk, dm in demand_multiplier.items():
    sales_limit = where(
        Product.x_selected(wk, d, x_sel),
        Product.x_sales(wk, d, x_sales)
    ).require(
        x_sales <= Product.base_demand * d.demand_lift * dm * x_sel
    )
    s.satisfy(sales_limit)

# Constraint: cumulative sales tracking - week 1.
x_sales_w1, x_cum_w1 = Float.ref(), Float.ref()
cum_sales_week_1 = where(
    Product.x_sales(week_start, d, x_sales_w1),
    Product.x_cum_sales(week_start, x_cum_w1)
).require(
    x_cum_w1 == sum(x_sales_w1).per(Product)
)
s.satisfy(cum_sales_week_1)

# Constraint: cumulative sales tracking - weeks 2+.
x_sales_t, x_cum_t, x_cum_prev = Float.ref(), Float.ref(), Float.ref()
cum_sales_weeks_2_plus = where(
    Product.x_sales(t, d, x_sales_t),
    Product.x_cum_sales(t, x_cum_t),
    Product.x_cum_sales(t - 1, x_cum_prev),
    t > week_start,
    t <= week_end
).require(
    x_cum_t == x_cum_prev + sum(x_sales_t).per(Product, t)
)
s.satisfy(cum_sales_weeks_2_plus)

# Constraint: cumulative sales cannot exceed initial inventory.
inventory_limit = where(
    Product.x_cum_sales(t, x_cum)
).require(
    x_cum <= Product.initial_inventory
)
s.satisfy(inventory_limit)

# Objective: maximize revenue from sales plus salvage value of remaining inventory.
revenue = sum(
    x_sales * Product.initial_price * (1 - d.discount_pct / 100)
).where(
    Product.x_sales(t, d, x_sales)
)

x_cum_final = Float.ref()
salvage = sum(
    (Product.initial_inventory - x_cum_final) * Product.initial_price * Product.salvage_rate
).where(
    Product.x_cum_sales(week_end, x_cum_final)
)

s.maximize(revenue + salvage)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

resources = model._to_executor().resources
solver = Solver("highs", resources=resources)
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total revenue (sales + salvage): ${s.objective_value:.2f}")

df = s.variable_values().to_df()

print("\n=== Selected Discounts by Product-Week ===")
selected = df[df["name"].str.startswith("select") & (df["value"] > 0.5)]
print(selected.to_string(index=False))

print("\n=== Sales by Product-Week ===")
sales = df[df["name"].str.startswith("sales") & (df["value"] > 0.01)]
print(sales.to_string(index=False))

print("\n=== Cumulative Sales by Product-Week ===")
cum = df[df["name"].str.startswith("cum")]
print(cum.to_string(index=False))
