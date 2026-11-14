"""Load the sample tables, targets, and foreign-key constraints into the model."""

from pathlib import Path

import pandas as pd
from pandas import read_csv

from .schema import Table, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
scale_factor = 1.0

# Load schema and constraint data
schema_df = read_csv(DATA_DIR / "testgen_schema.csv")
constraints_df = read_csv(DATA_DIR / "testgen_constraints.csv")
targets_df = read_csv(DATA_DIR / "testgen_targets.csv")

# Scale targets
targets_df = targets_df.copy()
targets_df['target_rows'] = (targets_df['target_rows'] * scale_factor).astype(int)
targets_df['min_rows'] = (targets_df['min_rows'] * scale_factor).astype(int)
targets_df['max_rows'] = (targets_df['max_rows'] * scale_factor).astype(int)

table_data = model.data(targets_df)
model.define(
    t := Table.new(table_name=table_data.table_name),
    t.target_rows(table_data.target_rows),
    t.min_rows(table_data.min_rows),
    t.max_rows(table_data.max_rows),
    t.priority(table_data.priority),
)

# Extract FK relationships from schema
fk_df = schema_df[schema_df['is_foreign_key']].copy()
cardinality_constraints = constraints_df[
    constraints_df['constraint_type'].isin(['cardinality_bound', 'mandatory_participation', 'frequency'])
]

fk_objs = []
for _, fk_row in fk_df.iterrows():
    child_table = fk_row['table_name']
    parent_table = fk_row['references_table']

    card = cardinality_constraints[
        (cardinality_constraints['table_name'] == child_table) &
        (cardinality_constraints['related_table'] == parent_table)
    ]

    min_per = 1
    max_per = 100

    for _, c in card.iterrows():
        if c['constraint_type'] == 'cardinality_bound':
            min_per = int(c['min_value']) if not pd.isna(c['min_value']) else 1
            max_per = int(c['max_value']) if not pd.isna(c['max_value']) else 100
        elif c['constraint_type'] == 'frequency':
            max_per = int(c['max_value']) if not pd.isna(c['max_value']) else 100

    coverage = constraints_df[
        (constraints_df['constraint_type'] == 'coverage') &
        (constraints_df['table_name'] == child_table) &
        (constraints_df['related_table'] == parent_table)
    ]
    coverage_pct = 0.0
    if len(coverage) > 0:
        coverage_pct = float(coverage.iloc[0]['percentage']) / 100.0

    fk_objs.append({
        'child': child_table,
        'parent': parent_table,
        'min': min_per,
        'max': max_per,
        'coverage': coverage_pct
    })
