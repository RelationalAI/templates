"""Load the sample tables, targets, and foreign-key constraints into the model."""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics.std import math, numbers

from .schema import ForeignKey, Table, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
scale_factor = 1.0

# Load schema and constraint data
schema_df = read_csv(DATA_DIR / "testgen_schema.csv")
constraints_df = read_csv(DATA_DIR / "testgen_constraints.csv")
targets_df = read_csv(DATA_DIR / "testgen_targets.csv")

# Load the tables. Each count is scaled by scale_factor and truncated to a whole number.
table_data = model.data(targets_df)
model.define(
    t := Table.new(table_name=table_data.table_name),
    t.target_rows(numbers.integer(math.floor(table_data.target_rows * scale_factor))),
    t.min_rows(numbers.integer(math.floor(table_data.min_rows * scale_factor))),
    t.max_rows(numbers.integer(math.floor(table_data.max_rows * scale_factor))),
    t.priority(table_data.priority),
)

# Extract FK relationships from schema. The bounds each foreign key declares are combined
# here because the constraints CSV has blank cells, which model.data does not load reliably.
fk_df = schema_df[schema_df['is_foreign_key']].copy()

fk_objs = []
for _, fk_row in fk_df.iterrows():
    child_table = fk_row['table_name']
    parent_table = fk_row['references_table']

    # The constraints on this foreign key: same child table, column, and parent table.
    rules = constraints_df[
        (constraints_df['table_name'] == child_table) &
        (constraints_df['column_name'] == fk_row['column_name']) &
        (constraints_df['related_table'] == parent_table)
    ]

    # Children per parent: every declared bound applies, so the range is their
    # intersection. Mandatory participation means at least 1 unless it states a minimum;
    # with nothing declared, there is no lower bound and at most 100.
    kind = rules['constraint_type']
    mins = list(rules.loc[kind.isin(['cardinality_bound', 'frequency']), 'min_value'].dropna())
    mins += list(rules.loc[kind == 'mandatory_participation', 'min_value'].fillna(1))
    maxes = list(rules.loc[kind.isin(['cardinality_bound', 'frequency']), 'max_value'].dropna())
    min_per = int(max(mins, default=0))
    max_per = int(min(maxes, default=100))

    coverage = rules.loc[kind == 'coverage', 'percentage'].dropna()
    coverage_pct = float(coverage.max()) / 100.0 if len(coverage) else 0.0

    fk_objs.append({
        'child': child_table,
        'column_name': fk_row['column_name'],
        'parent': parent_table,
        'min_per': min_per,
        'max_per': max_per,
        'coverage': coverage_pct
    })

# Load the foreign keys with their combined bounds.
fk_data = model.data(
    DataFrame(fk_objs, columns=['child', 'column_name', 'parent', 'min_per', 'max_per', 'coverage'])
)
child, parent = Table.ref(), Table.ref()
model.where(child.table_name == fk_data['child'], parent.table_name == fk_data['parent']).define(
    fk := ForeignKey.new(child=child, column_name=fk_data['column_name']),
    fk.parent(parent),
    fk.min_per(fk_data['min_per']),
    fk.max_per(fk_data['max_per']),
    fk.coverage(fk_data['coverage']),
)
