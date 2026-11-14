"""Factory production decision problem: maximize profit, with the marginals of one sensitivity solve."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Factory, Product, Property, model

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

problem = Problem(model, Float, name="factory_production")

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

# The solve's status and objective, which the deployed model publishes for the queries.
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
