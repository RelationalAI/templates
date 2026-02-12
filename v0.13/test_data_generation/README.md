---
title: "Test Data Generation"
description: "Determine optimal row counts for test database tables that satisfy schema constraints, then generate valid test data."
featured: false
experience_level: intermediate
industry: "Data Engineering"
reasoning_types:
  - Prescriptive
tags:
  - Design
  - LP
  - Data
---

## What this template is for

QA and data engineering teams often need synthetic datasets that are large enough for realistic testing, but still satisfy core schema constraints like foreign keys and cardinality rules. Random generation tends to break referential integrity (for example, order lines pointing at non-existent orders) or produce unrealistic parent-child ratios.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose feasible row counts for each table that are as close as possible to your desired targets, subject to schema-derived constraints.

## Who this is for

- QA engineers and test automation developers who need repeatable datasets.
- Data engineers who need scalable dev/load-test datasets while maintaining realistic relationships.
- Anyone comfortable reading CSV schemas and running a Python script.

## What you’ll build

- An optimization model that computes feasible row counts per table.
- A small, deterministic synthetic data generator (seeded) that produces sample rows.
- A printed summary showing solver status, objective value, and the chosen row counts.

## What’s included

- **Model**: A linear optimization formulation that (a) keeps each table within min/max bounds, and (b) enforces parent-child constraints derived from foreign keys and constraint metadata.
- **Runner**: A single script, `test_data_generation.py`, that loads CSVs, solves, and prints results.
- **Sample data**: CSVs describing the schema, constraints, and target row counts.
- **Outputs**: Solver status + objective, per-table row counts, and a small preview of generated rows.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python 3.10+.

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/test_data_generation.zip
   unzip test_data_generation.zip
   cd test_data_generation
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   python -m pip install -U pip
   python -m pip install .
   ```

4. Configure your Snowflake connection and RAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python test_data_generation.py
   ```

6. Expected output (abridged):

   ```text
   Status: OPTIMAL
   Total weighted deviation: 18000.00

   Optimal row counts:
     Customer: 100 rows (target: 100, deviation: 0)
     Product: 500 rows (target: 500, deviation: 0)
     ...
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ test_data_generation.py       # Main script (entry point)
└─ data/                         # Sample input CSVs
   ├─ testgen_constraints.csv
   ├─ testgen_schema.csv
   └─ testgen_targets.csv
```

**Start here**: `test_data_generation.py`.

## Sample data

All sample inputs live under `data/`.

### `testgen_targets.csv`

Defines target row counts, bounds, and per-table priorities.

| Column | Meaning |
|---|---|
| `table_name` | Table identifier used throughout the template |
| `target_rows` | Desired number of rows |
| `min_rows` | Minimum allowed rows |
| `max_rows` | Maximum allowed rows |
| `priority` | Weighting input used in the objective (1 is highest priority) |

### `testgen_schema.csv`

Describes table columns and key metadata, including foreign key references.

| Column | Meaning |
|---|---|
| `table_name` | Table containing the column |
| `column_name` | Column name |
| `column_type` | Data type label used by the generator (for example, `int`, `string`, `date`) |
| `is_primary_key` | Whether the column is a primary key |
| `is_foreign_key` | Whether the column is a foreign key |
| `references_table` | Parent table name (for foreign keys) |
| `references_column` | Parent column name (for foreign keys) |
| `is_unique` | Whether values must be unique |
| `is_nullable` | Whether null values are allowed |
| `min_value` | Optional numeric lower bound (when present) |
| `max_value` | Optional numeric upper bound (when present) |

### `testgen_constraints.csv`

Additional constraints (cardinality, coverage, frequency, and value domains) that can create tension with targets.

| Column | Meaning |
|---|---|
| `constraint_type` | Constraint kind (for example, `cardinality_bound`, `mandatory_participation`, `coverage`, `frequency`, `value_domain`) |
| `table_name` | Child/source table |
| `column_name` | Column the constraint applies to |
| `related_table` | Related/parent table (when applicable) |
| `related_column` | Related/parent column (when applicable) |
| `min_value` | Minimum value for the constraint (when applicable) |
| `max_value` | Maximum value for the constraint (when applicable) |
| `percentage` | Coverage percent (when applicable) |
| `description` | Human-readable summary |

## Model overview

- **Key entity**: `Table` represents each table in the schema.
- **Decision variables**:
  - `Table.actual_rows`: chosen row count (continuous, bounded).
  - `Table.deviation`: auxiliary variable to measure deviation from the target.
- **Constraints**: bounds, referential integrity, mandatory participation, and coverage.
- **Objective**: minimize a priority-weighted sum of deviations from the targets.

## How it works

This section walks through the highlights in `test_data_generation.py`.

### Import libraries and configure inputs

First, the script defines the data directory, a scale factor for the targets, and a pandas option used across v0.13 templates:

```python
DATA_DIR = Path(__file__).parent / "data"
SCALE_FACTOR = 1.0

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pd.options.future.infer_string = False
```

### Define concepts and load CSV data

Next, the script creates a Semantics `Model` and loads the schema, constraints, and targets from CSV:

```python
model = Model(
    f"test_data_generation_{time_ns()}",
    config=globals().get("config", None),
    use_lqp=False,
)

# Load schema data from CSV.
schema_df = read_csv(DATA_DIR / "testgen_schema.csv")

# Load constraint data from CSV.
constraints_df = read_csv(DATA_DIR / "testgen_constraints.csv")

# Load row-count targets from CSV.
targets_df = read_csv(DATA_DIR / "testgen_targets.csv")
```

Then it creates the `Table` concept and loads one entity per row in `testgen_targets.csv`:

```python
# Table concept: represents a table in the schema.
Table = model.Concept("Table")

# Load table data from CSV.
data(targets_df).into(Table, keys=["table_name"])
```

### Define decision variables, constraints, and objective

With data loaded, the script creates a `SolverModel`, declares the decision variables, and linearizes the absolute deviation from targets:

```python
s = SolverModel(model, "cont", use_pb=True)

# Variable: actual row counts for each table
s.solve_for(
    Table.actual_rows,
    name=["n", Table.table_name],
    lower=Table.min_rows,
    upper=Table.max_rows,
)

# Variable: deviation from target (for objective)
s.solve_for(
    Table.deviation,
    name=["dev", Table.table_name],
    lower=0,
)

# Constraint: deviation captures |actual - target| (linearized)
s.satisfy(require(Table.deviation >= Table.actual_rows - Table.target_rows))
s.satisfy(require(Table.deviation >= Table.target_rows - Table.actual_rows))
```

It also adds referential integrity-style bounds for each foreign key relationship extracted from the schema metadata, plus optional coverage requirements when present.

Finally, it defines a priority-weighted objective:

```python
# Objective: minimize weighted deviation from targets
# Weight by priority (higher priority = more important to match target)
total_deviation = rai_sum(Table.deviation * (11 - Table.priority))
s.minimize(total_deviation)
```

### Solve and print results

Finally, the script solves with HiGHS and prints the status, objective, and per-table row counts:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total weighted deviation: {s.objective_value:.2f}")
```

As an optional second phase, it generates small sample tables procedurally (seeded) and prints the first few rows for each generated table.

## Customize this template

### Use your own schema and constraints

- Replace the files in `data/` with your own versions that follow the same headers.
- Start by updating `testgen_targets.csv` (targets + bounds), then ensure foreign keys are reflected in `testgen_schema.csv`.

### Tune the target scaling

To quickly generate a larger or smaller dataset without editing each target, change `SCALE_FACTOR` in the script.

### Adjust priorities

If some tables must match targets more closely than others, change `priority` in `testgen_targets.csv`. Higher priority tables are penalized more heavily in the objective.

## Troubleshooting

<details>
  <summary>I get <code>ModuleNotFoundError</code> when running the script</summary>

  - Confirm you activated your virtual environment: <code>source .venv/bin/activate</code>.
  - Reinstall dependencies from the template root: <code>python -m pip install .</code>.
</details>

<details>
  <summary>The script fails reading CSV files (missing file or columns)</summary>

  - Confirm you are running from the template folder that contains <code>data/</code>.
  - Verify the input filenames exist: <code>testgen_schema.csv</code>, <code>testgen_constraints.csv</code>, <code>testgen_targets.csv</code>.
  - Check that the CSV headers match the expected columns documented above.
</details>

<details>
  <summary>The solver returns <code>Status: INFEASIBLE</code></summary>

  - This usually indicates the target bounds and the parent-child constraints cannot be satisfied at the same time.
  - Start by widening <code>min_rows</code>/<code>max_rows</code> in <code>testgen_targets.csv</code> for the most constrained tables.
  - Check whether tight constraints (for example, low max cardinality or high frequency minimums) force row counts beyond your bounds.
</details>

<details>
  <summary>I expected larger output tables</summary>

  - The script prints only a preview of generated data using <code>df.head(3)</code>.
  - To export full tables, add a <code>df.to_csv(...)</code> step after generation (outside the template’s core logic).
</details>
