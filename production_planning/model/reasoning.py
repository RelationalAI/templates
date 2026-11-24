"""Production planning problem: integer quantities per machine and product that maximize profit."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Machine, Product, Rate, Scenario, model

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Decision concept: production quantities for each machine/product
Production = model.Concept("Production")
Production.rate = model.Property(f"{Production} uses {Rate}", short_name="rate")
model.define(Production.new(rate=Rate))

# Decision variable — indexed by Scenario (multi-argument Property)
Production.x_quantity = model.Property(f"{Production} in {Scenario} has {Float:quantity}")

# Ref for binding multi-arg variable in constraints
x_qty = Float.ref()

problem = Problem(model, Float, name="production_planning")

# Variable: production quantity (integer, non-negative)
problem.solve_for(
    Production.x_quantity(Scenario, x_qty),
    name=["qty", Scenario.name, Production.rate.machine.name, Production.rate.product.name],
    lower=0, type="int",
)

# Constraint: machine capacity (per machine, per scenario)
problem.satisfy(model.where(
    Production.x_quantity(Scenario, x_qty),
    Production.rate.machine(Machine),
).require(
    sum(x_qty * Production.rate.hours_per_unit)
    .where(Production.rate.machine == Machine)
    .per(Machine, Scenario)
    <= Machine.hours_available
))

# Constraint: meet demand scaled by multiplier (per product, per scenario)
problem.satisfy(model.where(
    Production.x_quantity(Scenario, x_qty),
    Production.rate.product(Product),
).require(
    sum(Production, x_qty)
    .where(Production.rate.product == Product)
    .per(Product, Scenario)
    >= Product.demand * Scenario.demand_multiplier
))

# Objective: maximize total profit
problem.maximize(
    sum(Production, Scenario, x_qty * Production.rate.product.profit)
    .where(Production.x_quantity(Scenario, x_qty))
)

# --------------------------------------------------
# Solve (single solve for all scenarios)
# --------------------------------------------------

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"production planning solve status is {String:status}")
TotalProfit = model.Relationship(f"production planning total profit is {Float:profit}")
model.define(SolveStatus(problem.termination_status()), TotalProfit(problem.objective_value()))
