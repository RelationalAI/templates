"""Test data generation decision problem: row counts closest to the targets, within the bounds."""

import pandas as pd
from relationalai.semantics import Float, String
from relationalai.semantics import sum as rai_sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Property, Table, model
from .source import constraints_df, fk_objs

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
# These constraints link specific table pairs via their actual_rows variables
ParentTable = Table.ref()
for fk_info in fk_objs:
    child_name = fk_info['child']
    parent_name = fk_info['parent']

    # Upper bound: can't have more children than max per parent
    problem.satisfy(model.require(
        Table.x_actual_rows <= ParentTable.x_actual_rows * fk_info['max']
    ).where(
        Table.table_name == child_name,
        ParentTable.table_name == parent_name
    ))

    # Lower bound: at least the declared minimum of children per parent
    if fk_info['min'] > 0:
        problem.satisfy(model.require(
            Table.x_actual_rows >= ParentTable.x_actual_rows * fk_info['min']
        ).where(
            Table.table_name == child_name,
            ParentTable.table_name == parent_name
        ))

    # Lower bound for mandatory participation
    mandatory = constraints_df[
        (constraints_df['constraint_type'] == 'mandatory_participation') &
        (constraints_df['table_name'] == child_name) &
        (constraints_df['related_table'] == parent_name)
    ]
    if len(mandatory) > 0:
        min_per = int(mandatory.iloc[0]['min_value']) if not pd.isna(mandatory.iloc[0]['min_value']) else 1
        problem.satisfy(model.require(
            Table.x_actual_rows >= ParentTable.x_actual_rows * min_per
        ).where(
            Table.table_name == child_name,
            ParentTable.table_name == parent_name
        ))

# Constraint: coverage requirements
for fk_info in fk_objs:
    if fk_info['coverage'] > 0:
        child_name = fk_info['child']
        parent_name = fk_info['parent']
        problem.satisfy(model.require(
            Table.x_actual_rows >= fk_info['coverage'] * ParentTable.x_actual_rows
        ).where(
            Table.table_name == child_name,
            ParentTable.table_name == parent_name
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
