"""Diet decision problem: least-cost food amounts per scenario, in one solve."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Food, Nutrient, Scenario, model

# Decision variable — indexed by Scenario (multi-argument Property)
Food.x_amount = model.Property(f"{Food} in {Scenario} has {Float:amount}")

# Ref for binding multi-arg variable in constraints
x_amt = Float.ref()

problem = Problem(model, Float, name="diet")

# Variable: amount of each food per scenario (non-negative)
problem.solve_for(Food.x_amount(Scenario, x_amt), name=["amt", Scenario.scenario_name, Food.name], lower=0)

# Constraint: nutrient bounds scaled by scenario parameter (per nutrient, per scenario)
nutrient_qty = Float.ref()
problem.satisfy(model.where(
    Food.x_amount(Scenario, x_amt),
    Food.contains(Nutrient, nutrient_qty),
).require(
    sum(Food, nutrient_qty * x_amt).per(Nutrient, Scenario) >= Nutrient.min * Scenario.nutrient_scaling,
    sum(Food, nutrient_qty * x_amt).per(Nutrient, Scenario) <= Nutrient.max * Scenario.nutrient_scaling,
))

# Objective: minimize total cost
problem.minimize(sum(Food, Scenario, Food.cost * x_amt).where(Food.x_amount(Scenario, x_amt)))

# Each refresh of the deployed model runs this solve (one solve for all scenarios).
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"diet solve status is {String:status}")
TotalCost = model.Relationship(f"diet total cost is {Float:cost}")
model.define(SolveStatus(problem.termination_status()), TotalCost(problem.objective_value()))
