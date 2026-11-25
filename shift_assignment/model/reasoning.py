"""Shift assignment decision problem: a feasible roster per coverage scenario, in one solve."""

from relationalai.semantics import Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Scenario, Shift, Worker, model

# Parameters
max_shifts = 1  # Maximum shifts per worker

# Decision variable — triple-arg: Worker x Shift x Scenario
Worker.x_assign = model.Property(f"{Worker} has {Shift} in {Scenario} if {Integer:assigned}")

# Ref for binding multi-arg variable in constraints
assigned_ref = Integer.ref()

problem = Problem(model, Integer, name="shift_assignment")

# Variable: binary assignment per available worker-shift-scenario
problem.solve_for(
    Worker.x_assign(Shift, Scenario, assigned_ref),
    type="bin",
    name=["x", Scenario.name, Worker.name, Shift.name],
    where=[Worker.available_for(Shift)],
)

# Constraint: minimum coverage per shift (per scenario)
coverage_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Worker, assigned_ref).per(Shift, Scenario) >= Scenario.min_coverage)
problem.satisfy(coverage_ic)

# Constraint: max shifts per worker (per scenario)
workload_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Shift, assigned_ref).per(Worker, Scenario) <= max_shifts)
problem.satisfy(workload_ic)

# Constraint: max workers per shift (capacity limit per scenario)
capacity_ic = model.where(
    Worker.x_assign(Shift, Scenario, assigned_ref),
).require(sum(Worker, assigned_ref).per(Shift, Scenario) <= Shift.capacity)
problem.satisfy(capacity_ic)

# Each refresh of the deployed model runs this solve (one solve for all scenarios).
problem.configure("minizinc", time_limit_sec=60)

# The solve's status, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"shift assignment solve status is {String:status}")
model.define(SolveStatus(problem.termination_status()))
