"""Row-count plan: the decision problem for row counts closest to the targets within the bounds,
and the plan's whole-row counts and deviations."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics import sum as rai_sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import math, numbers

from .schema import ForeignKey, Property, Table, model

# Decision variable properties
Table.x_actual_rows = Property(f"{Table} has actual {Float:actual_rows}")
Table.x_deviation = Property(f"{Table} has {Float:deviation}")

problem = Problem(model, Float, name="test_data_generation")

# Variable: actual row counts for each table
problem.solve_for(
    Table.x_actual_rows,
    name=["n", Table.table_name],
    lower=Table.min_rows,
    upper=Table.max_rows
)

# Variable: deviation from target (for objective)
problem.solve_for(
    Table.x_deviation,
    name=["dev", Table.table_name],
    lower=0
)

# Constraint: deviation captures |actual - target| (linearized)
problem.satisfy(model.where(Table).require(Table.x_deviation >= Table.x_actual_rows - Table.target_rows))
problem.satisfy(model.where(Table).require(Table.x_deviation >= Table.target_rows - Table.x_actual_rows))

# Constraint: referential integrity - child rows bounded by parent capacity
# These constraints link each foreign key's child and parent tables via their actual_rows
# variables.
ChildTable, ParentTable = Table.ref(), Table.ref()
foreign_key = [ForeignKey.child == ChildTable, ForeignKey.parent == ParentTable]

# Upper bound: can't have more children than max per parent
problem.satisfy(model.where(*foreign_key).require(
    ChildTable.x_actual_rows <= ParentTable.x_actual_rows * ForeignKey.max_per
))

# Lower bound: at least the declared minimum of children per parent (cardinality,
# frequency, or mandatory participation)
problem.satisfy(model.where(*foreign_key, ForeignKey.min_per > 0).require(
    ChildTable.x_actual_rows >= ParentTable.x_actual_rows * ForeignKey.min_per
))

# Constraint: coverage requirements
problem.satisfy(model.where(*foreign_key, ForeignKey.coverage > 0).require(
    ChildTable.x_actual_rows >= ForeignKey.coverage * ParentTable.x_actual_rows
))

# Objective: minimize weighted deviation from targets
# Weight by priority (higher priority = more important to match target)
total_deviation = rai_sum(Table.x_deviation * (11 - Table.priority))
problem.minimize(total_deviation)

# Each refresh of the deployed model runs this solve.
problem.configure("highs", time_limit_sec=60)

# The solve's status and objective, which the deployed model publishes for the queries.
SolveStatus = model.Relationship(f"test data generation solve status is {String:status}")
TotalDeviation = model.Relationship(
    f"test data generation total weighted deviation is {Float:total_deviation}"
)
model.define(SolveStatus(problem.termination_status()), TotalDeviation(problem.objective_value()))

# The plan's whole-row counts and each table's deviation from its target. They are computed
# from the solution, so they live on TablePlan, not Table: such a property on the concept the
# solve reads leaves the solution empty after the first refresh.
TablePlan = model.Concept("TablePlan", identify_by={"table": Table})
TablePlan.actual_rows = Property(f"{TablePlan} has {Integer:actual_rows} rows")
TablePlan.deviation = Property(f"{TablePlan} deviates from its target by {Integer:deviation}")
model.define(TablePlan.new(table=Table))
model.where(TablePlan.table == Table).define(
    TablePlan.actual_rows(numbers.integer(math.round(Table.x_actual_rows)))
)
model.where(TablePlan.table == Table).define(
    TablePlan.deviation(math.abs(TablePlan.actual_rows - Table.target_rows))
)
