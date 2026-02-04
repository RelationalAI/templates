# retail markdown problem:
# set discount levels across weeks to maximize revenue while clearing inventory

from pathlib import Path
from time import time_ns

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, data, std, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model(f"retail_markdown_{time_ns()}", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Define ontology & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Concept: products with inventory and demand info
Product = model.Concept("Product")
Product.name = model.Property("{Product} has {name:string}")
Product.initial_price = model.Property("{Product} has {initial_price:float}")
Product.cost = model.Property("{Product} has {cost:float}")
Product.initial_inventory = model.Property("{Product} has {initial_inventory:int}")
Product.base_demand = model.Property("{Product} has {base_demand:float}")
Product.salvage_rate = model.Property("{Product} has {salvage_rate:float}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["name"])

# Concept: discount levels with demand lift
Discount = model.Concept("Discount")
Discount.level = model.Property("{Discount} has {level:int}")
Discount.discount_pct = model.Property("{Discount} has {discount_pct:float}")
Discount.demand_lift = model.Property("{Discount} has {demand_lift:float}")
data(read_csv(data_dir / "discounts.csv")).into(Discount, keys=["level"])

# Concept: time periods with demand multipliers
# Note: Uses integer index pattern with std.range() for time-indexed variables.
# Future API may support Week as foreign key in multi-arity properties.
Week = model.Concept("Week")
Week.week_num = model.Property("{Week} has {week_num:int}")
Week.demand_multiplier = model.Property("{Week} has {demand_multiplier:float}")
data(read_csv(data_dir / "weeks.csv")).into(Week, keys=["week_num"])

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

# Parameters
week_start = 1
week_end = 4
weeks = std.range(week_start, week_end + 1)

t = Integer.ref()
d = Discount.ref()
w = Week.ref()

s = SolverModel(model, "cont", use_pb=True)

# Variable: select discount level for each product in each week
Product.selected = model.Property("{Product} in week {t:int} at discount {d:Discount} is {selected:float}")
x_sel = Float.ref()
s.solve_for(
    Product.selected(t, d, x_sel),
    type="bin",
    name=["select", Product.name, t, d.discount_pct],
    where=[t == weeks]
)

# Variable: sales for each product in each week at each discount level
Product.sales = model.Property("{Product} in week {t:int} at discount {d:Discount} has {sales:float}")
x_sales = Float.ref()
s.solve_for(
    Product.sales(t, d, x_sales),
    type="cont",
    lower=0,
    name=["sales", Product.name, t, d.discount_pct],
    where=[t == weeks]
)

# Variable: cumulative sales for each product up to each week
Product.cum_sales = model.Property("{Product} through week {t:int} has {cum_sales:float}")
x_cum = Float.ref()
s.solve_for(
    Product.cum_sales(t, x_cum),
    type="cont",
    lower=0,
    name=["cum", Product.name, t],
    where=[t == weeks]
)

# Constraint: one discount level selected per product per week
s.satisfy(where(
    Product.selected(t, d, x_sel)
).require(
    sum(x_sel).per(Product, t) == 1
))

# Constraint: price ladder - discounts can only increase (prices can only decrease)
d1, d2 = Discount.ref(), Discount.ref()
x_sel1, x_sel2 = Float.ref(), Float.ref()
s.satisfy(where(
    Product.selected(t, d1, x_sel1),
    Product.selected(t + 1, d2, x_sel2),
    d2.level < d1.level,
    t >= week_start,
    t < week_end
).require(
    x_sel1 + x_sel2 <= 1
))

# Constraint: sales only occur at the selected discount level
s.satisfy(where(
    Product.selected(t, d, x_sel),
    Product.sales(t, d, x_sales),
    w.week_num == t
).require(
    x_sales <= Product.base_demand * d.demand_lift * w.demand_multiplier * x_sel
))

# Constraint: cumulative sales tracking - week 1
x_sales_w1, x_cum_w1 = Float.ref(), Float.ref()
s.satisfy(where(
    Product.sales(week_start, d, x_sales_w1),
    Product.cum_sales(week_start, x_cum_w1)
).require(
    x_cum_w1 == sum(x_sales_w1).per(Product)
))

# Constraint: cumulative sales tracking - weeks 2+
x_sales_t, x_cum_t, x_cum_prev = Float.ref(), Float.ref(), Float.ref()
s.satisfy(where(
    Product.sales(t, d, x_sales_t),
    Product.cum_sales(t, x_cum_t),
    Product.cum_sales(t - 1, x_cum_prev),
    t > week_start,
    t <= week_end
).require(
    x_cum_t == x_cum_prev + sum(x_sales_t).per(Product, t)
))

# Constraint: cumulative sales cannot exceed initial inventory
s.satisfy(where(
    Product.cum_sales(t, x_cum)
).require(
    x_cum <= Product.initial_inventory
))

# Objective: maximize revenue from sales plus salvage value of remaining inventory
revenue = sum(x_sales * Product.initial_price * (1 - d.discount_pct / 100)).where(
    Product.sales(t, d, x_sales)
)

x_cum_final = Float.ref()
salvage = sum(
    (Product.initial_inventory - x_cum_final) * Product.initial_price * Product.salvage_rate
).where(
    Product.cum_sales(week_end, x_cum_final)
)

s.maximize(revenue + salvage)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs", resources=model._to_executor().resources)
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total revenue (sales + salvage): ${s.objective_value:.2f}")

df = s.variable_values().to_df()

print("\n=== Selected Discounts by Product-Week ===")
selected = df[df["name"].str.startswith("select") & (df["float"] > 0.5)]
print(selected.to_string(index=False))

print("\n=== Sales by Product-Week ===")
sales = df[df["name"].str.startswith("sales") & (df["float"] > 0.01)]
print(sales.to_string(index=False))

print("\n=== Cumulative Sales by Product-Week ===")
cum = df[df["name"].str.startswith("cum")]
print(cum.to_string(index=False))
