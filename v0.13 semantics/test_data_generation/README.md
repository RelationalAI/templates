# Test Data Generation

Determine optimal row counts for test database tables that satisfy schema constraints, then generate valid test data.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Design |
| **Industry** | Data Engineering |
| **Method** | LP (Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

QA teams need realistic test data that satisfies all schema constraints (referential integrity, uniqueness, cardinality bounds) while matching target size and distribution specifications. Simply generating random data often violates foreign key relationships or produces unrealistic data distributions.

This template uses a two-phase approach:
1. **Phase 1 (LP)**: Optimize row counts for each table to best match targets while satisfying inter-table constraints
2. **Phase 2 (Procedural)**: Generate actual records with valid foreign keys based on optimal counts

## Why is optimization valuable?

- **Constraint satisfaction**: Generated data automatically satisfies all referential integrity and cardinality constraints
- **Target matching**: Row counts optimally balance conflicting targets when constraints make exact matches impossible
- **Realistic distributions**: Cardinality bounds ensure realistic parent-child relationships (e.g., 1-3 order lines per order)

## What are similar problems?

- **Database migration testing**: Generate test data matching production schemas before migrations
- **Load testing**: Create scaled datasets that maintain realistic relationships
- **Development environments**: Populate dev databases with valid sample data
- **Data masking**: Generate synthetic data that matches production patterns without real customer info

## Problem Details

### Model

**Concepts:**
- `Table`: Database tables with target row counts and bounds
- `ForeignKey`: Foreign key relationships with cardinality constraints

**Relationships:**
- `ForeignKey` links child `Table` to parent `Table`

### Decision Variables

- `Table.actual_rows` (continuous): Optimized row count for each table
- `Table.deviation` (continuous): Auxiliary variable for |actual - target|

### Objective

Minimize weighted deviation from target row counts:
```
minimize sum(priority_weight * |actual_rows - target_rows|)
```

### Constraints

1. **Bounds**: Row counts within min/max limits
2. **Referential integrity**: Child rows <= parent rows * max_per_parent
3. **Mandatory participation**: Child rows >= parent rows * min_per_parent (where required)
4. **Coverage**: Child rows >= coverage_pct * parent rows (where required)

## Data

Data files are located in the `data/` subdirectory.

### testgen_targets.csv

| Column | Description |
|--------|-------------|
| table_name | Name of the database table |
| target_rows | Desired number of rows |
| min_rows | Minimum acceptable rows |
| max_rows | Maximum acceptable rows |
| priority | Importance weight (1=highest, 10=lowest) |

### testgen_schema.csv

| Column | Description |
|--------|-------------|
| table_name | Table containing the column |
| column_name | Column name |
| data_type | Data type (int, string, date, etc.) |
| is_primary_key | True if primary key |
| is_foreign_key | True if foreign key |
| references_table | Parent table for foreign keys |
| references_column | Parent column for foreign keys |

### testgen_constraints.csv

| Column | Description |
|--------|-------------|
| constraint_type | Type: cardinality_bound, mandatory_participation, coverage, frequency, value_domain |
| table_name | Child/source table |
| column_name | Column involved |
| related_table | Parent/related table |
| min_value | Minimum for cardinality constraints |
| max_value | Maximum for cardinality constraints |
| percentage | Coverage percentage (0-100) |
| description | Human-readable description |

## Usage

```python
# Run directly to solve and generate data
python test_data_generation.py
```

Or import and use the generation function:

```python
# After solving, generate test data with custom row counts
from test_data_generation import generate_test_data

row_counts = {
    'Customer': {'actual': 100},
    'Product': {'actual': 50},
    'Order': {'actual': 500},
    'OrderLine': {'actual': 1500},
    'Supplier': {'actual': 50},
    'SupplierProduct': {'actual': 200}
}

generated_data = generate_test_data(row_counts, seed=42)
for table, df in generated_data.items():
    df.to_csv(f'{table}.csv', index=False)
```

## Expected Output

```
Status: OPTIMAL
Total weighted deviation: 18000.00

Optimal row counts:
  Customer: 1000 rows (target: 1000, deviation: 0)
  Product: 500 rows (target: 500, deviation: 0)
  Order: 1200 rows (target: 800, deviation: 400)
  OrderLine: 3600 rows (target: 5000, deviation: 1400)
  Supplier: 50 rows (target: 50, deviation: 0)
  SupplierProduct: 2500 rows (target: 2500, deviation: 0)

==================================================
GENERATED TEST DATA
==================================================

Customer: 1000 rows
customer_id              email       region created_date
          1  user1_abcd@gmail.com      North   2020-05-15
          2  user2_efgh@yahoo.com       East   2021-08-22
          3  user3_ijkl@company.com    South   2019-11-03
...
```

The output shows:
- **Order target conflict**: Target was 800 but constraint `OrderLine <= Order * 3` forced increase to 1200
- **OrderLine reduction**: Target was 5000 but can't exceed 1200 * 3 = 3600
- **Weighted resolution**: Higher-priority tables (Customer, Product) hit exact targets; lower-priority tables absorb deviations
