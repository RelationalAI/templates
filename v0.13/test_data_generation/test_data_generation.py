"""Test data generation (prescriptive optimization) template.

- Loads schema, constraints, and row-count targets from CSV.
- Solves an LP to choose feasible table row counts close to targets.
- Optionally generates synthetic records consistent with solved counts.

Run:
    python test_data_generation.py

Output:
    - Solver status and total weighted deviation.
    - Optimal row counts per table.
    - Sample generated rows per table.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random
import string as string_module
from time import time_ns

import pandas as pd
from pandas import DataFrame, read_csv

from relationalai.semantics import Model, data, require, select, sum as rai_sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
SCALE_FACTOR = 1.0

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False



# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model(
    f"test_data_generation_{time_ns()}",
    config=globals().get("config", None),
    use_lqp=False,
)

# Load schema and constraint data
schema_df = read_csv(DATA_DIR / "testgen_schema.csv")
constraints_df = read_csv(DATA_DIR / "testgen_constraints.csv")
targets_df = read_csv(DATA_DIR / "testgen_targets.csv")

# Scale targets
targets_df = targets_df.copy()
targets_df["target_rows"] = (targets_df["target_rows"] * SCALE_FACTOR).astype(int)
targets_df["min_rows"] = (targets_df["min_rows"] * SCALE_FACTOR).astype(int)
targets_df["max_rows"] = (targets_df["max_rows"] * SCALE_FACTOR).astype(int)

# Concept: database tables with row count targets
Table = model.Concept("Table")
data(targets_df).into(Table, keys=["table_name"])

# Decision variable properties
Table.actual_rows = model.Property("{Table} has actual {actual_rows:float}")
Table.deviation = model.Property("{Table} has {deviation:float}")

# Extract FK relationships from schema
fk_df = schema_df[schema_df["is_foreign_key"] == True].copy()
cardinality_constraints = constraints_df[
    constraints_df["constraint_type"].isin(
        ["cardinality_bound", "mandatory_participation", "frequency"]
    )
]

fk_objs = []
for _, fk_row in fk_df.iterrows():
    child_table = fk_row["table_name"]
    parent_table = fk_row["references_table"]

    card = cardinality_constraints[
        (cardinality_constraints["table_name"] == child_table)
        & (cardinality_constraints["related_table"] == parent_table)
    ]

    min_per = 1
    max_per = 100

    for _, c in card.iterrows():
        if c["constraint_type"] == "cardinality_bound":
            min_per = int(c["min_value"]) if not pd.isna(c["min_value"]) else 1
            max_per = int(c["max_value"]) if not pd.isna(c["max_value"]) else 100
        elif c["constraint_type"] == "frequency":
            max_per = int(c["max_value"]) if not pd.isna(c["max_value"]) else 100

    coverage = constraints_df[
        (constraints_df["constraint_type"] == "coverage")
        & (constraints_df["table_name"] == child_table)
        & (constraints_df["related_table"] == parent_table)
    ]
    coverage_pct = 0.0
    if len(coverage) > 0:
        coverage_pct = float(coverage.iloc[0]["percentage"]) / 100.0

    fk_objs.append({
        "child": child_table,
        "parent": parent_table,
        "min": min_per,
        "max": max_per,
        "coverage": coverage_pct,
    })

# --------------------------------------------------
# Model the problem
# --------------------------------------------------

s = SolverModel(model, "cont", use_pb=True)

# Variable: actual row counts for each table
s.solve_for(
    Table.actual_rows,
    name=["n", Table.table_name],
    lower=Table.min_rows,
    upper=Table.max_rows
)

# Variable: deviation from target (for objective)
s.solve_for(
    Table.deviation,
    name=["dev", Table.table_name],
    lower=0
)

# Constraint: deviation captures |actual - target| (linearized)
s.satisfy(require(Table.deviation >= Table.actual_rows - Table.target_rows))
s.satisfy(require(Table.deviation >= Table.target_rows - Table.actual_rows))

# Constraint: referential integrity - child rows bounded by parent capacity
# These constraints link specific table pairs via their actual_rows variables
Table2 = Table.ref()
for fk_info in fk_objs:
    child_name = fk_info["child"]
    parent_name = fk_info["parent"]

    # Upper bound: can't have more children than max per parent
    s.satisfy(where(
        Table.table_name == child_name,
        Table2.table_name == parent_name
    ).require(
        Table.actual_rows <= Table2.actual_rows * fk_info["max"]
    ))

    # Lower bound for mandatory participation
    mandatory = constraints_df[
        (constraints_df["constraint_type"] == "mandatory_participation")
        & (constraints_df["table_name"] == child_name)
        & (constraints_df["related_table"] == parent_name)
    ]
    if len(mandatory) > 0:
        min_per = (
            int(mandatory.iloc[0]["min_value"])
            if not pd.isna(mandatory.iloc[0]["min_value"])
            else 1
        )
        s.satisfy(where(
            Table.table_name == child_name,
            Table2.table_name == parent_name
        ).require(
            Table.actual_rows >= Table2.actual_rows * min_per
        ))

# Constraint: coverage requirements
for fk_info in fk_objs:
    if fk_info["coverage"] > 0:
        child_name = fk_info["child"]
        parent_name = fk_info["parent"]
        s.satisfy(where(
            Table.table_name == child_name,
            Table2.table_name == parent_name
        ).require(
            Table.actual_rows >= fk_info["coverage"] * Table2.actual_rows
        ))

# Objective: minimize weighted deviation from targets
# Weight by priority (higher priority = more important to match target)
total_deviation = rai_sum(Table.deviation * (11 - Table.priority))
s.minimize(total_deviation)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total weighted deviation: {s.objective_value:.2f}")

# Extract row counts
row_counts = {}
results_df = select(Table.table_name, Table.actual_rows, Table.target_rows).to_df()
for _, row in results_df.iterrows():
    actual = int(round(row['actual_rows']))
    target = int(row['target_rows'])
    row_counts[row['table_name']] = {'actual': actual, 'target': target}

print("\nOptimal row counts:")
for table, counts in row_counts.items():
    dev = abs(counts['actual'] - counts['target'])
    print(f"  {table}: {counts['actual']} rows (target: {counts['target']}, deviation: {dev})")

# --------------------------------------------------
# Phase 2: Generate actual test data (optional)
# --------------------------------------------------

def generate_test_data(row_counts, seed=42):
    """Generate actual test data records based on optimal row counts."""
    random.seed(seed)

    def random_email(i):
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'company.com']
        return f"user{i}_{''.join(random.choices(string_module.ascii_lowercase, k=4))}@{random.choice(domains)}"

    def random_date(start_year=2020, end_year=2024):
        start = date(start_year, 1, 1)
        end = date(end_year, 12, 31)
        delta = (end - start).days
        return start + timedelta(days=random.randint(0, delta))

    def random_float(min_val, max_val):
        return round(random.uniform(min_val, max_val), 2)

    generated = {}

    # Customer table
    n_customers = row_counts.get('Customer', {}).get('actual', 100)
    regions = ['North', 'South', 'East', 'West', 'Central']
    customers = [{'customer_id': i, 'email': random_email(i), 'region': random.choice(regions), 'created_date': random_date(2018, 2023)} for i in range(1, n_customers + 1)]
    generated['Customer'] = DataFrame(customers)

    # Product table
    n_products = row_counts.get('Product', {}).get('actual', 50)
    categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books']
    products = [{'product_id': i, 'name': f"{random.choice(categories)} Item {i}", 'category': random.choice(categories), 'price': random_float(0.99, 999.99)} for i in range(1, n_products + 1)]
    generated['Product'] = DataFrame(products)

    # Order table
    n_orders = row_counts.get('Order', {}).get('actual', 500)
    statuses = ['pending', 'shipped', 'delivered', 'cancelled']
    orders = [{'order_id': i, 'customer_id': random.randint(1, max(1, n_customers)), 'order_date': random_date(2023, 2024), 'status': random.choice(statuses)} for i in range(1, n_orders + 1)]
    generated['Order'] = DataFrame(orders)

    # OrderLine table
    n_orderlines = row_counts.get('OrderLine', {}).get('actual', 1500)
    orderlines = [{'orderline_id': i, 'order_id': random.randint(1, max(1, n_orders)), 'product_id': random.randint(1, max(1, n_products)), 'quantity': random.randint(1, 10), 'unit_price': random_float(0.99, 999.99)} for i in range(1, n_orderlines + 1)]
    generated['OrderLine'] = DataFrame(orderlines)

    # Supplier table
    n_suppliers = row_counts.get('Supplier', {}).get('actual', 50)
    countries = ['USA', 'China', 'Germany', 'Japan', 'UK']
    suppliers = [{'supplier_id': i, 'name': f"Supplier_{i}", 'country': random.choice(countries), 'reliability_score': random_float(50.0, 100.0)} for i in range(1, n_suppliers + 1)]
    generated['Supplier'] = DataFrame(suppliers)

    # SupplierProduct table
    n_supplier_products = row_counts.get('SupplierProduct', {}).get('actual', 200)
    supplier_products = [{'supplierproduct_id': i, 'supplier_id': random.randint(1, max(1, n_suppliers)), 'product_id': random.randint(1, max(1, n_products)), 'lead_time_days': random.randint(1, 90), 'unit_cost': random_float(0.50, 500.0)} for i in range(1, n_supplier_products + 1)]
    generated['SupplierProduct'] = DataFrame(supplier_products)

    return generated

# Generate data and show samples
print("\n" + "=" * 50)
print("GENERATED TEST DATA")
print("=" * 50)

generated_data = generate_test_data(row_counts)
for table, df in generated_data.items():
    print(f"\n{table}: {len(df)} rows")
    print(df.head(3).to_string(index=False))
