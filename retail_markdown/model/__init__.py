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
    `rai models deploy --path model` deploys this model to the schema in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.markdown_plan` then prints the report from the deployed model.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("retail_markdown")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).resolve().parents[1] / "data"

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
Week_ref = Week.ref()
Discount_ref = Discount.ref()
selection_ref = Float.ref()
sales_ref = Float.ref()
cumulative_ref = Float.ref()

problem = Problem(model, Float)

# Variable: select[product, week, discount] = 1 if that discount is active
Product.x_select = model.Property(f"{Product} in {Week} has {Discount} if {Float:x}")
problem.solve_for(
    Product.x_select(Week_ref, Discount_ref, selection_ref),
    type="bin",
    name=["select", Product.name, Week_ref.num, Discount_ref.discount_pct],
)

# Variable: sales[product, week, discount] = units sold at that discount level
Product.x_sales = model.Property(f"{Product} in {Week} at {Discount} has {Float:y}")
problem.solve_for(
    Product.x_sales(Week_ref, Discount_ref, sales_ref),
    type="cont",
    lower=0,
    name=["sales", Product.name, Week_ref.num, Discount_ref.discount_pct],
)

# Variable: cuml_sales[product, week] = cumulative units sold through that week
Product.x_cuml_sales = model.Property(f"{Product} up to {Week} has {Float:z}")
problem.solve_for(
    Product.x_cuml_sales(Week_ref, cumulative_ref),
    type="cont",
    lower=0,
    name=["cuml", Product.name, Week_ref.num],
)

# Constraint: exactly one discount level per product-week (one-hot selection)
problem.satisfy(model.where(Product.x_select(Week_ref, Discount_ref, selection_ref)).require(
    sum(Discount_ref, selection_ref).per(Product, Week_ref) == 1
))

# Constraint: price ladder — discounts can only increase week-over-week
Discount_inner = Discount.ref()
Week_inner = Week.ref()
selection_inner = Float.ref()
problem.satisfy(model.where(
    Product.x_select(Week_ref, Discount_ref, selection_ref),
    Product.x_select(Week_inner, Discount_inner, selection_inner),
    Week_inner.num == Week_ref.num + 1,
    Discount_inner.level < Discount_ref.level,
).require(
    selection_ref + selection_inner <= 1
))

# Constraint: sales bounded by demand x lift x multiplier x selection indicator
problem.satisfy(model.where(
    Product.x_select(Week_ref, Discount_ref, selection_ref),
    Product.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    sales_ref <= Product.base_demand * Discount_ref.demand_lift * Week_ref.demand_multiplier * selection_ref
))

# Constraint: cumulative sales — first week
problem.satisfy(model.where(
    Week_ref.num == 1,
    Product.x_cuml_sales(Week_ref, cumulative_ref),
    Product.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    cumulative_ref == sum(Discount_ref, sales_ref).per(Product, Week_ref)
))

# Constraint: cumulative sales — subsequent weeks
Week_prev = Week.ref()
cumulative_prev = Float.ref()
problem.satisfy(model.where(
    Week_ref.num > 1,
    Week_prev.num == Week_ref.num - 1,
    Product.x_cuml_sales(Week_ref, cumulative_ref),
    Product.x_cuml_sales(Week_prev, cumulative_prev),
    Product.x_sales(Week_ref, Discount_ref, sales_ref),
).require(
    cumulative_ref == cumulative_prev + sum(Discount_ref, sales_ref).per(Product, Week_ref)
))

# Constraint: cumulative sales cannot exceed initial inventory
problem.satisfy(model.where(Product.x_cuml_sales(Week_ref, cumulative_ref)).require(
    cumulative_ref <= Product.initial_inventory
))

# Objective: maximize revenue from sales plus salvage value of remaining inventory
revenue = sum(
    Product, Week_ref, Discount_ref,
    Product.initial_price * (1 - Discount_ref.discount_pct / 100) * sales_ref,
).where(Product.x_sales(Week_ref, Discount_ref, sales_ref))
salvage = sum(
    Product, Week_ref,
    Product.initial_price * Product.salvage_rate * (Product.initial_inventory - cumulative_ref),
).where(
    Product.x_cuml_sales(Week_ref, cumulative_ref),
    Week_ref.num == num_weeks,
)
problem.maximize(revenue + salvage)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# Deploy the rules behind problem.display() with the model.
problem.install_display_strings()

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"retail markdown solve status is {String:status}")
TotalRevenue = model.Relationship(f"retail markdown total revenue is {Float:revenue}")
model.define(SolveStatus(problem.termination_status()), TotalRevenue(problem.objective_value()))
