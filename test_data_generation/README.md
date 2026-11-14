---
title: "Test Data Generation"
description: "Determine optimal row counts for test database tables satisfying schema and referential integrity constraints."
featured: false
experience_level: intermediate
industry: "Technology & Telecom"
reasoning_types:
  - Prescriptive
tags:
  - Test Data
  - Database Schema
  - Constraint Satisfaction
---

# Test Data Generation

## What this template is for

Generating realistic test databases requires careful coordination of row counts across tables. Foreign key relationships, cardinality bounds, and coverage requirements create complex interdependencies -- for example, if each order must have 1-3 line items, then 800 orders can have at most 2,400 order lines. Manually choosing row counts that satisfy all these constraints while staying close to target sizes is tedious and error-prone.

This template uses **Prescriptive** reasoning to find optimal row counts for each table in a test database. It encodes referential integrity constraints, cardinality bounds, mandatory participation rules, and coverage requirements as a linear program, then minimizes weighted deviation from target row counts. Higher-priority tables stay closer to their targets.

After determining row counts, the script generates actual test data records with realistic values -- emails, dates, prices, and proper foreign key references -- giving you a complete, constraint-consistent test dataset.

## Who this is for

- QA engineers who need realistic test databases with consistent referential integrity
- Database developers building test fixtures for integration testing
- Data engineers validating ETL pipelines with controlled synthetic data

## What you'll build

- A linear programming model that balances row count targets against schema constraints
- Referential integrity constraints encoding foreign key cardinality bounds
- Mandatory participation and coverage requirements
- A data generation phase that produces actual CSV-ready test records

## What's included

- `test_data_generation.py` -- Main script for row count optimization and data generation
- `data/testgen_schema.csv` -- Table and column definitions with types and foreign keys
- `data/testgen_constraints.csv` -- Cardinality bounds, coverage, and participation rules
- `data/testgen_targets.csv` -- Target, minimum, and maximum row counts per table with priorities
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (Quickstart step 4 below covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/test_data_generation.zip
   unzip test_data_generation.zip
   cd test_data_generation
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure: run `rai init` to create `raiconfig.yaml` with your Snowflake connection, set the connection `role` to the model role, then add a `deployment` section. Give each template its own schema pair so two deployed templates never share one.

   ```yaml
   reasoners:
     prescriptive:
       name: test_data_generation_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.TEST_DATA_GENERATION               # published views and tables
     identity:
       internal_schema: <DB>.TEST_DATA_GENERATION_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

   Without the `deployment` section, `python test_data_generation.py` stops with an error naming the missing setting.

   Before the first run, create the internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

   ```sql
   -- as the model role
   CREATE SCHEMA IF NOT EXISTS <DB>.TEST_DATA_GENERATION_META;

   -- as an administrator
   GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER USAGE ON SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.TEST_DATA_GENERATION_META TO APPLICATION <RAI_APP_NAME>;
   ```

   The deploy creates the public schema `<DB>.TEST_DATA_GENERATION` if it doesn't exist.

5. Run:
   ```bash
   python test_data_generation.py
   ```
   The script deploys the model, waits for the first refresh, which runs the solve, and prints the report from the deployed model. Each refresh of the deployed model runs the solve again; `rai models deploy` deploys without printing the report.

   Running the script again without changing the model redeploys nothing and does not solve again; it reports the latest refresh. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves. To solve again without a change, refresh the deployed model, then run the script:
   ```sql
   CALL <DB>.TEST_DATA_GENERATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```
   To remove the deployment, run `rai models teardown --force` from this directory; it keeps the two schemas.

6. Expected output:
   ```text
   Status: OPTIMAL
   Total weighted deviation: 1200.00

   Optimal row counts:
     Customer: 100 rows (target: 100, deviation: 0)
     Product: 500 rows (target: 500, deviation: 0)
     Order: 800 rows (target: 800, deviation: 0)
     OrderLine: 2400 rows (target: 5000, deviation: 2600)
     Supplier: 20 rows (target: 20, deviation: 0)
     SupplierProduct: 1500 rows (target: 1500, deviation: 0)

   ==================================================
   GENERATED TEST DATA
   ==================================================

   Customer: 100 rows
    customer_id                          email region created_date
              1  user1_abcd@gmail.com   North   2020-03-15

   Product: 500 rows
    product_id              name   category  price
             1  Electronics Item 1  Clothing  42.99

   Order: 800 rows
    order_id  customer_id  order_date    status
           1           47  2023-06-12  delivered
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── test_data_generation.py
└── data/
    ├── testgen_constraints.csv
    ├── testgen_schema.csv
    └── testgen_targets.csv
```

## How it works

### 1. Load schema metadata

The script reads three CSV files describing the database schema: table definitions with column types and foreign keys, constraints (cardinality bounds, coverage, mandatory participation), and row count targets with priorities:

```python
schema_df = read_csv(data_dir / "testgen_schema.csv")
constraints_df = read_csv(data_dir / "testgen_constraints.csv")
targets_df = read_csv(data_dir / "testgen_targets.csv")
```

### 2. Define decision variables

Each table gets two decision variables -- actual row count and deviation from target:

```python
Table.x_actual_rows = Property(f"{Table} has actual {Float:actual_rows}")
Table.x_deviation = Property(f"{Table} has {Float:deviation}")

problem.solve_for(Table.x_actual_rows, name=["n", Table.table_name], lower=Table.min_rows, upper=Table.max_rows)
problem.solve_for(Table.x_deviation, name=["dev", Table.table_name], lower=0)
```

### 3. Encode referential integrity constraints

Foreign key relationships impose bounds linking child and parent row counts. For example, if each order has 1-3 order lines, the OrderLine count must be between 1x and 3x the Order count:

```python
ParentTable = Table.ref()
problem.satisfy(model.require(
    Table.x_actual_rows <= ParentTable.x_actual_rows * fk_info['max']
).where(
    Table.table_name == child_name,
    ParentTable.table_name == parent_name
))
```

### 4. Minimize weighted deviation

The objective minimizes deviation from targets, weighted by priority so that critical tables stay closer to their targets:

```python
total_deviation = rai_sum(Table.x_deviation * (11 - Table.priority))
problem.minimize(total_deviation)
```

### 5. Generate test records

After solving, the script generates actual data records with realistic values using the computed row counts:

```python
generated_data = generate_test_data(row_counts)
```

## Customize this template

- **Add your own schema** by editing the three CSV files to match your database structure with its constraints and targets.
- **Adjust the scale factor** by changing `scale_factor` to proportionally scale all targets up or down.
- **Extend data generation** to produce additional column types or more realistic value distributions for your domain.
- **Add uniqueness constraints** to ensure generated foreign key references follow realistic distributions rather than uniform random.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

The constraints are contradictory -- for example, a cardinality bound may require more child rows than the maximum allows. Review `testgen_constraints.csv` and check that the min/max row ranges in `testgen_targets.csv` are compatible with the cardinality bounds. Widen the min/max row ranges or relax cardinality constraints.
</details>

<details>
<summary>Large deviations from target row counts</summary>

This is expected when constraints are tight. For example, if each order has at most 3 order lines and there are 800 orders, the OrderLine count cannot exceed 2,400 even if the target is 5,000. Review the constraints to understand which ones are binding.
</details>

<details>
<summary>ModuleNotFoundError: No module named 'relationalai'</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that your account has the RAI Native App installed and that your user has the required permissions.
</details>
