# Markdown Optimization:
# Set discount levels across weeks to maximize revenue while clearing inventory

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, data, require, std, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

model = Model("markdown", config=globals().get("config", None), use_lqp=False)

# --------------------------------------------------
# Load Data and Define Ontology
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Products with inventory and demand info
Product = model.Concept("Product")
Product.id = model.Property("{Product} has {id:int}")
Product.name = model.Property("{Product} has {name:string}")
Product.initial_price = model.Property("{Product} has {initial_price:float}")
Product.cost = model.Property("{Product} has {cost:float}")
Product.initial_inventory = model.Property("{Product} has {initial_inventory:int}")
Product.base_demand = model.Property("{Product} has {base_demand:float}")
Product.salvage_rate = model.Property("{Product} has {salvage_rate:float}")
data(read_csv(data_dir / "products.csv")).into(Product, keys=["id"])

# Discount levels with demand lift
Discount = model.Concept("Discount")
Discount.id = model.Property("{Discount} has {id:int}")
Discount.level = model.Property("{Discount} has {level:int}")
Discount.discount_pct = model.Property("{Discount} has {discount_pct:float}")
Discount.demand_lift = model.Property("{Discount} has {demand_lift:float}")
data(read_csv(data_dir / "discounts.csv")).into(Discount, keys=["id"])

# Time periods with demand multipliers
TimePeriod = model.Concept("TimePeriod")
TimePeriod.week_num = model.Property("{TimePeriod} has {week_num:int}")
TimePeriod.demand_multiplier = model.Property("{TimePeriod} has {demand_multiplier:float}")
data(read_csv(data_dir / "weeks.csv")).into(TimePeriod, keys=["week_num"])

# --------------------------------------------------
# Define Decision Variables
# --------------------------------------------------

week_start = 1
week_end = 4
weeks = std.range(week_start, week_end + 1)

# Helper refs
t = Integer.ref()
p = Product.ref()
d = Discount.ref()

# Discount selection: binary for each product-week-discount combination
Product.selected = model.Property("{Product} in week {t:int} at discount {d:Discount} is {selected:float}")

# Sales: continuous for each product-week-discount combination
Product.sales = model.Property("{Product} in week {t:int} at discount {d:Discount} has {sales:float}")

# Cumulative sales: for inventory tracking
Product.cum_sales = model.Property("{Product} through week {t:int} has {cum_sales:float}")

# --------------------------------------------------
# Set Up Solver Model
# --------------------------------------------------

s = SolverModel(model, "cont", use_pb=True)

x_sel = Float.ref()
s.solve_for(
    Product.selected(t, d, x_sel),
    type="bin",
    name=["sel", Product.name, t, d.discount_pct],
    where=[t == weeks]
)

x_sales = Float.ref()
s.solve_for(
    Product.sales(t, d, x_sales),
    lower=0,
    name=["sales", Product.name, t, d.discount_pct],
    where=[t == weeks]
)

x_cum = Float.ref()
s.solve_for(
    Product.cum_sales(t, x_cum),
    lower=0,
    name=["cum", Product.name, t],
    where=[t == weeks]
)

# --------------------------------------------------
# Define Constraints
# --------------------------------------------------

# 1. Exactly one discount level per product-week
s.satisfy(where(
    Product.selected(t, d, x_sel)
).require(
    sum(x_sel).per(Product, t) == 1
))

# 2. Price ladder: discounts can only increase (prices can only decrease)
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

# 3. Sales can only occur at selected discount level
w = TimePeriod.ref()
s.satisfy(where(
    Product.selected(t, d, x_sel),
    Product.sales(t, d, x_sales),
    w.week_num == t
).require(
    x_sales <= Product.base_demand * d.demand_lift * w.demand_multiplier * x_sel
))

# 4. Cumulative sales definition - week 1
x_sales_w1, x_cum_w1 = Float.ref(), Float.ref()
s.satisfy(where(
    Product.sales(week_start, d, x_sales_w1),
    Product.cum_sales(week_start, x_cum_w1)
).require(
    x_cum_w1 == sum(x_sales_w1).per(Product)
))

# 4. Cumulative sales definition - weeks 2+
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

# 5. Cumulative sales cannot exceed initial inventory
s.satisfy(where(
    Product.cum_sales(t, x_cum)
).require(
    x_cum <= Product.initial_inventory
))

# --------------------------------------------------
# Define Objective
# --------------------------------------------------

# Revenue = sum(sales * price * (1 - discount_pct/100))
revenue = sum(x_sales * Product.initial_price * (1 - d.discount_pct / 100)).where(
    Product.sales(t, d, x_sales)
)

# Salvage value = (initial_inventory - final_cum_sales) * price * salvage_rate
x_cum_final = Float.ref()
salvage = sum(
    (Product.initial_inventory - x_cum_final) * Product.initial_price * Product.salvage_rate
).where(
    Product.cum_sales(week_end, x_cum_final)
)

s.maximize(revenue + salvage)

# --------------------------------------------------
# Solve and Display Results
# --------------------------------------------------

solver = Solver("highs", resources=model._to_executor().resources)
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total revenue (sales + salvage): ${s.objective_value:.2f}")

# Display results from variable_values (complex time-indexed relations)
df = s.variable_values().to_df()

print("\n=== Selected Discounts by Product-Week ===")
selected = df[df["name"].str.startswith("sel") & (df["float"] > 0.5)]
print(selected.to_string(index=False))

print("\n=== Sales by Product-Week ===")
sales = df[df["name"].str.startswith("sales") & (df["float"] > 0.01)]
print(sales.to_string(index=False))

print("\n=== Cumulative Sales by Product-Week ===")
cum = df[df["name"].str.startswith("cum")]
print(cum.to_string(index=False))
