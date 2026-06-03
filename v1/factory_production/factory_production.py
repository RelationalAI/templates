"""Factory production (prescriptive optimization) template.

This script demonstrates a product-mix linear program in RelationalAI that
maximizes total profit subject to per-factory resource capacity, then reads back
the *marginals* a planner asks next:

- Load sample CSVs describing factories (resource availability) and the products
  each factory makes (production rate, unit profit, demand cap).
- Model them as *concepts* with typed properties.
- Choose a non-negative production quantity per product, capped by its demand.
- Limit each factory's total resource usage to its available hours.
- Maximize total profit.

A plain solve answers "what is the most profitable production plan?". Requesting
``solve(sensitivity=True)`` ALSO answers the marginal questions -- in one solve,
read straight off the variable / constraint objects (the same attribute style as
``.name`` or ``.lower``):

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

Each constraint carries an entity back-pointer to what it grounds over
(``cap.factory``), just like a variable points back to its product
(``quantity_var.product``), so a marginal joins to that entity's own data by ENTITY
KEY (``cap.factory.avail``) -- never by parsing the constraint name string.

Run:
    `python factory_production.py`

Output:
    Prints the production plan, each factory's capacity shadow price, each product's
    reduced cost and basis status, and a per-factory capacity-utilization summary.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("factory_production")
Concept, Property = model.Concept, model.Property

# Factory concept: factories with total resource availability (hours).
Factory = Concept("Factory", identify_by={"name": String})
Factory.avail = Property(f"{Factory} has {Float:avail}")

# Load factories from CSV.
factory_csv = read_csv(DATA_DIR / "factories.csv")
model.define(Factory.new(model.data(factory_csv).to_schema()))

# Product concept: products with production rate, unit profit, demand cap, and parent factory.
Product = Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = Property(f"{Product} is produced by {Factory}")
Product.rate = Property(f"{Product} has {Float:rate}")
Product.profit = Property(f"{Product} has {Float:profit}")
Product.demand = Property(f"{Product} has {Integer:demand}")

# Load products from CSV and link each product to its factory.
product_csv = read_csv(DATA_DIR / "products.csv")
product_data = model.data(product_csv)
model.define(
    p := Product.new(name=product_data.name, factory_name=product_data.factory_name),
    p.rate(product_data.rate),
    p.profit(product_data.profit),
    p.demand(product_data.demand),
)
model.define(Product.factory(Factory)).where(
    Product.factory_name(product_data.factory_name),
    Factory.name(product_data.factory_name),
)

# Guard the reference data. Every sensitivity assertion below is gated by a hard-coded
# factory/product name, so if data/ is edited those asserts could silently pass on zero
# rows. Fail loudly here instead, with a clear message, the moment the data drifts.
EXPECTED_FACTORIES = {"steel_factory", "amazing_brewery"}
EXPECTED_PRODUCTS = {"bands", "coils", "stouts", "ales"}
assert set(factory_csv["name"]) == EXPECTED_FACTORIES, (
    f"factories.csv changed: {set(factory_csv['name'])} != {EXPECTED_FACTORIES}"
)
assert set(product_csv["name"]) == EXPECTED_PRODUCTS, (
    f"products.csv changed: {set(product_csv['name'])} != {EXPECTED_PRODUCTS}"
)
# Product names are unique across factories, so the plan is keyed by name alone below.
assert product_csv["name"].is_unique, (
    f"product names are not unique across factories: {list(product_csv['name'])}"
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Variable: quantity[product] = amount produced (0 .. demand cap).
Product.x_quantity = Property(f"{Product} has {Float:quantity}")

# --------------------------------------------------
# Baseline solve with sensitivity analysis
# --------------------------------------------------
# One product-mix LP over ALL factories. They share no resources, so the joint
# optimum is just each factory solved independently -- but a single solve lets us
# read every factory's marginals side by side off the captured handles.

problem = Problem(model, Float)

# Variable: production quantity per product. The demand cap is the variable's UPPER
# BOUND (not a separate constraint), so its marginal surfaces as the variable's
# reduced cost below. populate=False keeps the solution read explicit via values().
quantity_var = problem.solve_for(
    Product.x_quantity,
    name=["qty", Product.factory.name, Product.name],
    lower=0,
    upper=Product.demand,
    populate=False,
)

# Constraint: each factory's total resource usage <= its available hours. Captured as
# a handle and named per factory so each instance's shadow price reads back through the
# constraint's ENTITY KEY (cap.factory), never by parsing the constraint name string.
cap = problem.satisfy(
    model.require(
        sum(Product.x_quantity / Product.rate)
        .where(Product.factory == Factory)
        .per(Factory)
        <= Factory.avail
    ),
    name=["cap", Factory.name],
)

# Objective: maximize total profit across all factories.
problem.maximize(sum(Product.profit * Product.x_quantity))

problem.display()
problem.solve("highs", time_limit_sec=60, sensitivity=True)
si = problem.solve_info()
si.display()

assert si.termination_status == "OPTIMAL"
assert si.sensitivity is True
# Optimum: steel_factory fills all 40 hrs (bands to its 6000 cap = 30 hrs, coils takes
# the last 10 hrs = 1400 units); amazing_brewery makes both products to their demand
# caps in 25 of its 30 hrs. Profit = 192000 + 8000 = 200000.
assert si.objective_value is not None and abs(si.objective_value - 200000) < 0.01

print(f"\nBaseline status: {si.termination_status}, total profit: {si.objective_value:.2f}")

# --- The solved production plan -------------------------------------------------
# Read every product's solved quantity once via values(0, ref) on the variable (no
# populate). Columns are aliased so the printed headers read as factory / product /
# quantity; this one frame feeds the plan table, the plan assertion, and the capacity
# summary below.
plan_ref = Float.ref()
plan_df = (
    model.select(
        quantity_var.product.factory.name.alias("factory"),
        quantity_var.product.name.alias("product"),
        quantity_var.product.factory.avail.alias("avail"),
        quantity_var.product.rate.alias("rate"),
        plan_ref.alias("quantity"),
    )
    .where(quantity_var.values(0, plan_ref))
    .to_df()
    .sort_values(["factory", "product"], ignore_index=True)
)
print("\nProduction plan:")
produced = plan_df.loc[plan_df["quantity"] > 1e-6, ["factory", "product", "quantity"]]
print(produced.to_string(index=False))

# Pin the whole plan, not just the objective scalar: in general a matching objective is
# necessary but not sufficient, because a different product mix could reach the same
# profit. This LP's optimum happens to be unique (each factory's hours pin its plan), so
# pinning the quantities both guards against a regression and documents that uniqueness.
# Product names are unique across factories (asserted above), so the per-name lookup is a
# single row; tolerance is tight because the vertices here are exactly integral.
EXPECTED_PLAN = {"bands": 6000.0, "coils": 1400.0, "stouts": 1000.0, "ales": 2000.0}
for product_name, expected_qty in EXPECTED_PLAN.items():
    actual_qty = plan_df.loc[plan_df["product"] == product_name, "quantity"].sum()
    assert abs(actual_qty - expected_qty) < 0.01, (
        f"{product_name}: expected {expected_qty}, got {actual_qty}"
    )

# --- Capacity shadow prices: which factory to expand first ----------------------
# A constraint carries an entity back-pointer (cap.factory), so a shadow price joins
# to that factory's own data by KEY -- no name parsing, no pandas join.
cap_df = (
    model.select(
        cap.factory.name.alias("factory"),
        cap.factory.avail.alias("avail"),
        cap.shadow_price.alias("shadow_price"),
    )
    .to_df()
    .sort_values("factory", ignore_index=True)
)
print("\nFactory capacity shadow prices (d profit / d hour):")
print(cap_df.to_string(index=False))
# Maximize + a <= capacity => shadow_price >= 0: an extra hour can only help. The
# implication runs one way: a factory with idle hours prices at 0 (slack -- its
# bottleneck is demand, not capacity), and a positive price marks a binding capacity.
# steel_factory is full (binding) and carries the marginal value of an hour; every other
# factory has spare hours (slack) and prices at 0.
model.where(cap.factory.name == "steel_factory").require(cap.shadow_price > 1e-6)
model.where(cap.factory.name != "steel_factory").require(
    std.math.abs(cap.shadow_price) < 1e-6
)

# --- Reduced costs: which products are demand-capped? ---------------------------
# Each marginal reads straight off the variable; the variable's back-pointer
# (quantity_var.product) joins it to the product's factory by ENTITY KEY.
rc_df = (
    model.select(
        quantity_var.product.factory.name.alias("factory"),
        quantity_var.product.name.alias("product"),
        quantity_var.reduced_cost.alias("reduced_cost"),
        quantity_var.basis_status.alias("basis_status"),
    )
    .to_df()
    .sort_values(["factory", "product"], ignore_index=True)
)
print("\nProduct reduced costs and basis status:")
print(rc_df.to_string(index=False))
# A product pinned at its demand cap is NONBASIC_AT_UPPER with reduced_cost >= 0 (the
# extra profit from one more unit of allowed demand); the swing product that sets a
# binding factory's marginal price is BASIC at ~0. Here bands, stouts and ales sit at
# their demand caps; coils is the swing product in steel_factory. Assert BOTH halves of
# the lesson -- the reduced cost AND the basis status -- so a regression in either is loud.
for capped in ("bands", "stouts", "ales"):
    model.where(quantity_var.product.name == capped).require(
        quantity_var.reduced_cost > 1e-6
    )
    model.where(quantity_var.product.name == capped).require(
        quantity_var.basis_status == "NONBASIC_AT_UPPER"
    )
# coils is basic (interior, between 0 and its demand cap): reduced cost ~0, status BASIC.
# This coils read runs AFTER the requires above, and a query is what validates pending
# relational requires -- so the same select that fetches coils also checks them. Zero-
# checks use a HiGHS float tolerance (1e-4); the requires use 1e-6 (both are exact-0 here).
coils_df = (
    model.select(
        quantity_var.reduced_cost.alias("reduced_cost"),
        quantity_var.basis_status.alias("basis_status"),
    )
    .where(quantity_var.product.name == "coils")
    .to_df()
)
assert (coils_df["reduced_cost"].abs() < 1e-4).all()
assert (coils_df["basis_status"] == "BASIC").all()

# --- Acting on it: which factory's capacity is the bottleneck? ------------------
# With a maximize objective every capacity shadow price is >= 0, so the largest one is
# the factory whose marginal hour earns the most -- the capacity to expand first.
bottleneck = max(zip(cap_df["factory"], cap_df["shadow_price"]), key=lambda fp: fp[1])
print(
    f"\nMost profit-sensitive capacity: {bottleneck[0]} (d profit / d hour = {bottleneck[1]:+.2f})"
)

# --------------------------------------------------
# Summary — capacity utilization per factory
# --------------------------------------------------
# Ties the shadow prices above back to the plan: in this data the binding factory has
# zero idle hours and a positive shadow price, while idle hours mean slack and a zero
# price. Only idle => zero-price holds in general; a binding capacity can still price at
# zero under degeneracy, so read the prices, not just the idle column.
plan_df["hours"] = plan_df["quantity"] / plan_df["rate"]
util = (
    plan_df.groupby("factory")
    .agg(avail=("avail", "first"), hours_used=("hours", "sum"))
    .reset_index()
)
util["idle"] = util["avail"] - util["hours_used"]
print("\n" + "=" * 50)
print("Factory Capacity Summary")
print("=" * 50)
print(util.to_string(index=False))

# --------------------------------------------------
# Customize
# --------------------------------------------------
# Try editing data/ and re-running:
# - Raise amazing_brewery's demand caps (products.csv) until its 30 hrs bind: its
#   capacity shadow price jumps from 0 to positive once capacity becomes the bottleneck.
# - Lower steel_factory's avail (factories.csv): coils (the swing product) shrinks but
#   stays the swing down to just above 30 hrs, so the shadow price holds at 4200. At
#   exactly 30 hrs coils hits zero -- a degenerate breakpoint where the marginal is
#   one-sided -- and below 30 hrs bands can no longer fill its 6000 demand, so bands
#   becomes the swing and the price rises to 5000 (its own profit-per-hour, 25 x 200).
