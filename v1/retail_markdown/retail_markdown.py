"""Retail markdown (prescriptive optimization) template.

This script demonstrates a retail markdown mixed-integer linear optimization (MILP)
workflow in RelationalAI:

- Load sample CSVs describing products, discount levels, and weekly demand multipliers.
- Model products, discounts, and weeks as *concepts* with typed properties.
- Choose exactly one discount level per product per week (binary selection).
- Enforce a price ladder so discounts can only increase over time.
- Bound weekly sales by demand (base demand x discount lift x weekly multiplier).
- Track cumulative sales and ensure inventory is not exceeded.
- Maximize total revenue from discounted sales plus salvage value of leftover inventory.

Run:
    `python retail_markdown.py`

Output:
    Prints the solver termination status, objective value (sales + salvage), and
    three tables showing selected discounts, sales, and cumulative sales.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("retail_markdown")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: products with inventory and demand info
Product = model.Concept("Product", identify_by={"name": String})
Product.initial_price = model.Property(f"{Product} has {Float:initial_price}")
Product.cost = model.Property(f"{Product} has {Float:cost}")
Product.initial_inventory = model.Property(f"{Product} has {Integer:initial_inventory}")
Product.base_demand = model.Property(f"{Product} has {Float:base_demand}")
Product.salvage_rate = model.Property(f"{Product} has {Float:salvage_rate}")
product_csv = read_csv(data_dir / "products.csv")
model.define(Product.new(model.data(product_csv).to_schema()))

# Concept: discount levels with percentage and demand lift
Discount = model.Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")
discount_csv = read_csv(data_dir / "discounts.csv")
model.define(Discount.new(model.data(discount_csv).to_schema()))

# Concept: weeks with seasonal demand multipliers
Week = model.Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")
week_csv = read_csv(data_dir / "weeks.csv")
model.define(Week.new(model.data(week_csv).to_schema()))

# Rule: total number of weeks (stored to enable last-week constraint)
num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Helper refs
w = Week.ref()
d = Discount.ref()
x = Float.ref()
y = Float.ref()
z = Float.ref()

s = Problem(model, Float)

# Variable: select[product, week, discount] = 1 if that discount is active
Product.x_select = model.Property(f"{Product} in {Week} has {Discount} if {Float:x}")
s.solve_for(
    Product.x_select(w, d, x),
    type="bin",
    name=["select", Product.name, w.num, d.discount_pct],
)

# Variable: sales[product, week, discount] = units sold at that discount level
Product.x_sales = model.Property(f"{Product} in {Week} at {Discount} has {Float:y}")
s.solve_for(
    Product.x_sales(w, d, y),
    type="cont",
    lower=0,
    name=["sales", Product.name, w.num, d.discount_pct],
)

# Variable: cuml_sales[product, week] = cumulative units sold through that week
Product.x_cuml_sales = model.Property(f"{Product} up to {Week} has {Float:z}")
s.solve_for(
    Product.x_cuml_sales(w, z),
    type="cont",
    lower=0,
    name=["cuml", Product.name, w.num],
)

# Constraint: exactly one discount level per product-week (one-hot selection)
s.satisfy(model.where(Product.x_select(w, d, x)).require(
    sum(d, x).per(Product, w) == 1
))

# Constraint: price ladder — discounts can only increase week-over-week
d2 = Discount.ref()
w2 = Week.ref()
x2 = Float.ref()
s.satisfy(model.where(
    Product.x_select(w, d, x),
    Product.x_select(w2, d2, x2),
    w2.num == w.num + 1,
    d2.level < d.level,
).require(
    x + x2 <= 1
))

# Constraint: sales bounded by demand × lift × multiplier × selection indicator
s.satisfy(model.where(
    Product.x_select(w, d, x),
    Product.x_sales(w, d, y),
).require(
    y <= Product.base_demand * d.demand_lift * w.demand_multiplier * x
))

# Constraint: cumulative sales — first week
s.satisfy(model.where(
    w.num == 1,
    Product.x_cuml_sales(w, z),
    Product.x_sales(w, d, y),
).require(
    z == sum(d, y).per(Product, w)
))

# Constraint: cumulative sales — subsequent weeks
w_prev = Week.ref()
z_prev = Float.ref()
s.satisfy(model.where(
    w.num > 1,
    w_prev.num == w.num - 1,
    Product.x_cuml_sales(w, z),
    Product.x_cuml_sales(w_prev, z_prev),
    Product.x_sales(w, d, y),
).require(
    z == z_prev + sum(d, y).per(Product, w)
))

# Constraint: cumulative sales cannot exceed initial inventory
s.satisfy(model.where(Product.x_cuml_sales(w, z)).require(
    z <= Product.initial_inventory
))

# Objective: maximize revenue from sales plus salvage value of remaining inventory
revenue = sum(
    Product.initial_price * (1 - d.discount_pct / 100) * x
).where(Product.x_sales(w, d, x))
salvage = sum(
    Product.initial_price * Product.salvage_rate * (Product.initial_inventory - z)
).where(
    Product.x_cuml_sales(w, z),
    w.num == num_weeks
)
s.maximize(revenue + salvage)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total revenue (sales + salvage): ${s.objective_value:.2f}")

# Extract solution via model.select() — properties are populated after solve
print("\n=== Selected Discounts by Product-Week ===")
selected_df = model.select(
    Product.name.alias("product"), w.num.alias("week"),
    d.discount_pct.alias("discount_pct"),
).where(Product.x_select(w, d, x), x > 0.5).to_df()
print(selected_df.to_string(index=False))

print("\n=== Sales by Product-Week ===")
sales_df = model.select(
    Product.name.alias("product"), w.num.alias("week"),
    d.discount_pct.alias("discount_pct"), y.alias("units_sold"),
).where(Product.x_sales(w, d, y), y > 0.01).to_df()
print(sales_df.to_string(index=False))

print("\n=== Cumulative Sales by Product-Week ===")
cuml_df = model.select(
    Product.name.alias("product"), w.num.alias("week"),
    z.alias("cumulative_sold"),
).where(Product.x_cuml_sales(w, z)).to_df()
print(cuml_df.to_string(index=False))
