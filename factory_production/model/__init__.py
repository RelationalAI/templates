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

A constraint declared with ``keyed_by={"factory": Factory}`` carries an entity
back-pointer to what it grounds over (``cap.factory``), so a marginal joins to that
entity's own data by ENTITY KEY (``cap.factory.avail``) -- never by parsing the
constraint name string. (A variable's back-pointer, such as ``quantity_var.product``,
is derived automatically from its field names; a constraint's is declared.)

Run:
    `rai models deploy --path model` deploys this model to the schema in raiconfig.yaml
    and waits for its first refresh, which runs the solve. Then
    `python -m queries.plan_and_sensitivity` prints the production plan, each factory's
    capacity shadow price, each product's reduced cost and basis status, and a
    per-factory capacity-utilization summary from the deployed model.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

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

# Guard the reference data. Every sensitivity check in the report is gated by a hard-coded
# factory/product name, so if data/ is edited those checks could silently pass on zero
# rows. Fail loudly here instead, with a clear message, the moment the data drifts.
EXPECTED_FACTORIES = {"steel_factory", "amazing_brewery"}
EXPECTED_PRODUCTS = {"bands", "coils", "stouts", "ales"}
if set(factory_csv["name"]) != EXPECTED_FACTORIES:
    raise ValueError(f"factories.csv changed: {set(factory_csv['name'])} != {EXPECTED_FACTORIES}")
if set(product_csv["name"]) != EXPECTED_PRODUCTS:
    raise ValueError(f"products.csv changed: {set(product_csv['name'])} != {EXPECTED_PRODUCTS}")
# Product names are unique across factories, so the report keys the plan by name alone.
if not product_csv["name"].is_unique:
    raise ValueError(f"product names are not unique across factories: {list(product_csv['name'])}")

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
# reduced cost in the report.
quantity_var = problem.solve_for(
    Product.x_quantity,
    name=["qty", Product.factory.name, Product.name],
    lower=0,
    upper=Product.demand,
)

# Constraint: each factory's total resource usage <= its available hours, over the
# factories that make products. Captured as a handle; ``keyed_by`` declares each
# instance's ENTITY KEY, so its shadow price reads back through that key (cap.factory),
# never by parsing the constraint name string; the per-factory name is a readable label.
cap = problem.satisfy(
    model.where(Product.factory == Factory).require(
        sum(Product.x_quantity / Product.rate)
        .where(Product.factory == Factory)
        .per(Factory)
        <= Factory.avail
    ),
    name=["cap", Factory.name],
    keyed_by={"factory": Factory},
)

# Objective: maximize total profit across all factories.
problem.maximize(sum(Product.profit * Product.x_quantity))

# Each refresh of the deployed model runs this solve, with sensitivity analysis.
problem.configure("highs", time_limit_sec=60, sensitivity=True)

# Deploy the rules behind problem.display() with the model.
problem.install_display_strings()

# The solve's status and objective, published through the model's own relationships.
SolveStatus = model.Relationship(f"factory production solve status is {String:status}")
TotalProfit = model.Relationship(f"factory production total profit is {Float:profit}")
model.define(SolveStatus(problem.termination_status()), TotalProfit(problem.objective_value()))


# --------------------------------------------------
# Customize
# --------------------------------------------------
# Try editing data/, redeploying, and re-running the report:
# - Raise amazing_brewery's demand caps (products.csv) until its 30 hrs bind: its
#   capacity shadow price jumps from 0 to positive once capacity becomes the bottleneck.
# - Lower steel_factory's avail (factories.csv): coils (the swing product) shrinks but
#   stays the swing down to just above 30 hrs, so the shadow price holds at 4200. At
#   exactly 30 hrs coils hits zero -- a degenerate breakpoint where the marginal is
#   one-sided -- and below 30 hrs bands can no longer fill its 6000 demand, so bands
#   becomes the swing and the price rises to 5000 (its own profit-per-hour, 25 x 200).
