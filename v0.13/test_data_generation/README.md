---
title: "Test Data Generation"
description: "Determine feasible row counts for test database tables that satisfy schema constraints, then generate example synthetic rows."
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

> [!WARNING]
> This template uses the early access `relationalai.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

QA and data engineering teams often need synthetic datasets that are large enough for realistic testing, but still satisfy core schema constraints like foreign keys and parent–child cardinality rules.
Purely random generation tends to break referential integrity (for example, order lines pointing at non-existent orders) or produce unrealistic table size ratios.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to choose feasible row counts for each table that are as close as possible to your desired targets, subject to schema-derived constraints.

> [!NOTE]
> The optimization phase in this template solves for table-level row counts. The included Python record generator is a small, seeded example meant to show how you might turn those row counts into rows.

## Who this is for

- QA engineers and test automation developers who need repeatable datasets.
- Data engineers who need scalable dev/load-test datasets while maintaining realistic relationships.
- Anyone comfortable reading CSV schemas and running a Python script.

## What you’ll build

- A linear program (LP) that chooses per-table row counts within min/max bounds.
- Constraints that link child and parent table sizes based on foreign keys plus optional cardinality/coverage metadata.
- A priority-weighted objective that keeps important tables closer to their targets.
- A seeded, procedural generator that prints a small sample of synthetic rows.

## What’s included

- **Model + solve script**: `test_data_generation.py`
- **Sample data**: `data/testgen_schema.csv`, `data/testgen_constraints.csv`, `data/testgen_targets.csv`
- **Outputs**: solver status + objective, per-table row counts, and a preview of generated rows printed to stdout

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/test_data_generation.zip
   unzip test_data_generation.zip
   cd test_data_generation
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python test_data_generation.py
   ```

6. **Expected output (abridged)**

   ```text
   Status: OPTIMAL
   Total weighted deviation: 18000.00

   Optimal row counts:
     Customer: 100 rows (target: 100, deviation: 0)
     Product: 500 rows (target: 500, deviation: 0)
     ...

   ==================================================
   GENERATED TEST DATA
   ==================================================

   Customer: 100 rows
    customer_id                 email  region created_date
             ...
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ test_data_generation.py       # main runner / entrypoint
└─ data/                         # sample input CSVs
   ├─ testgen_constraints.csv
   ├─ testgen_schema.csv
   └─ testgen_targets.csv
```

**Start here**: `test_data_generation.py`

## Sample data

All sample inputs live under `data/`.

### `testgen_targets.csv`

Defines target row counts, min/max bounds, and per-table priorities.

| Column | Meaning |
| --- | --- |
| `table_name` | Table identifier used throughout the template |
| `target_rows` | Desired number of rows |
| `min_rows` | Minimum allowed rows |
| `max_rows` | Maximum allowed rows |
| `priority` | Priority used in the objective (1 is highest priority) |

### `testgen_schema.csv`

Describes tables and columns, including which columns are foreign keys and which parent table they reference.
The solver uses this file to discover table pairs that should be linked by constraints.

| Column | Meaning |
| --- | --- |
| `table_name` | Table containing the column |
| `column_name` | Column name |
| `column_type` | Data type label (for example, `int`, `string`, `date`) |
| `is_primary_key` | Whether the column is a primary key |
| `is_foreign_key` | Whether the column is a foreign key |
| `references_table` | Parent table name (for foreign keys) |
| `references_column` | Parent column name (for foreign keys) |
| `is_unique` | Whether values must be unique |
| `is_nullable` | Whether null values are allowed |
| `min_value` | Optional numeric lower bound (when present) |
| `max_value` | Optional numeric upper bound (when present) |

### `testgen_constraints.csv`

Adds constraint metadata that can create tension with targets.
In this template, the solver reads cardinality-style metadata per foreign-key table pair and (optionally) coverage percentages.

| Column | Meaning |
| --- | --- |
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

The optimization model is built around a single concept (`Table`) populated from `testgen_targets.csv`, plus two decision properties used by the solver.

- **Key entity**: `Table`
- **Inputs (loaded)**: `Table.table_name`, `Table.target_rows`, `Table.min_rows`, `Table.max_rows`, `Table.priority`
- **Decision variables**:
  - `Table.actual_rows` — solver-chosen row count (continuous)
  - `Table.deviation` — auxiliary variable used to model $|\text{actual} - \text{target}|$

## How it works

This section walks through the highlights in `test_data_generation.py`.

### Import libraries and configure inputs

First, the script sets up a data directory and an optional scaling knob for the target sizes:

```python
DATA_DIR = Path(__file__).parent / "data"
SCALE_FACTOR = 1.0

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pd.options.future.infer_string = False
```

### Load CSV inputs and build the model container

Next, it creates a Semantics `Model`, loads the three CSV inputs, and scales targets/bounds with `SCALE_FACTOR`:

```python
# Create a Semantics model container.
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

# Scale row-count targets and bounds.
targets_df = targets_df.copy()
targets_df["target_rows"] = (targets_df["target_rows"] * SCALE_FACTOR).astype(int)
targets_df["min_rows"] = (targets_df["min_rows"] * SCALE_FACTOR).astype(int)
targets_df["max_rows"] = (targets_df["max_rows"] * SCALE_FACTOR).astype(int)
```

### Define the `Table` concept and decision properties

Then it loads one `Table` entity per row in `testgen_targets.csv` and adds two solver-chosen properties (`actual_rows` and `deviation`):

```python
# Table concept: represents a table in the schema.
Table = model.Concept("Table")

# Load table data from CSV.
data(targets_df).into(Table, keys=["table_name"])

# Table.actual_rows decision property: solver-chosen row count per table.
Table.actual_rows = model.Property("{Table} has actual {actual_rows:float}")

# Table.deviation decision property: absolute deviation from the target.
Table.deviation = model.Property("{Table} has {deviation:float}")
```

### Extract foreign keys and constraint metadata

With inputs loaded, the script scans `testgen_schema.csv` for foreign keys and joins in any per-table-pair metadata (like cardinality bounds and coverage percentages) from `testgen_constraints.csv`:

```python
# Extract foreign key relationships from the schema.
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

    fk_objs.append(
        {
            "child": child_table,
            "parent": parent_table,
            "min": min_per,
            "max": max_per,
            "coverage": coverage_pct,
        }
    )
```

### Define variables, constraints, and objective

With the feasible region defined at the table level, the script declares two variable families and linearizes the absolute deviation from each target:

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

Then it links child and parent table sizes using `where(...).require(...)` for each discovered foreign key pair (including optional mandatory participation and coverage constraints):

```python
# Constraint: referential integrity - child rows bounded by parent capacity.
# These constraints link specific table pairs via their actual_rows variables.
Table2 = Table.ref()
for fk_info in fk_objs:
    child_name = fk_info["child"]
    parent_name = fk_info["parent"]

    # Upper bound: can't have more children than max per parent.
    s.satisfy(
        where(
            Table.table_name == child_name,
            Table2.table_name == parent_name
        ).require(Table.actual_rows <= Table2.actual_rows * fk_info["max"])
    )

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
        s.satisfy(
            where(
                Table.table_name == child_name,
                Table2.table_name == parent_name
            ).require(Table.actual_rows >= Table2.actual_rows * min_per)
        )

# Constraint: coverage requirements
for fk_info in fk_objs:
    if fk_info["coverage"] > 0:
        child_name = fk_info["child"]
        parent_name = fk_info["parent"]
        s.satisfy(
            where(
                Table.table_name == child_name,
                Table2.table_name == parent_name
            ).require(Table.actual_rows >= fk_info["coverage"] * Table2.actual_rows)
        )
```

Finally, it minimizes a priority-weighted deviation (higher priority means a higher penalty for missing the target):

```python
# Objective: minimize weighted deviation from targets
# Weight by priority (higher priority = more important to match target)
total_deviation = rai_sum(Table.deviation * (11 - Table.priority))
s.minimize(total_deviation)
```

### Solve and generate example rows

The script solves with the HiGHS backend and prints a summary:

```python
solver = Solver("highs")
s.solve(solver, time_limit_sec=60)

print(f"Status: {s.termination_status}")
print(f"Total weighted deviation: {s.objective_value:.2f}")
```

Then it rounds the continuous solution to integers for reporting and for driving the generator:

```python
# Extract row counts
row_counts = {}
results_df = select(Table.table_name, Table.actual_rows, Table.target_rows).to_df()
for _, row in results_df.iterrows():
    actual = int(round(row["actual_rows"]))
    target = int(row["target_rows"])
    row_counts[row["table_name"]] = {"actual": actual, "target": target}
```

To close the loop, it generates a small set of synthetic records and prints a preview of each table:

```python
# Generate data and show samples.
print("\n" + "=" * 50)
print("GENERATED TEST DATA")
print("=" * 50)

generated_data = generate_test_data(row_counts)
for table, df in generated_data.items():
    print(f"\n{table}: {len(df)} rows")
    print(df.head(3).to_string(index=False))
```

## Customize this template

### Use your own schema and constraints

- Replace the files in `data/` with your own versions that follow the same headers.
- Start by updating `testgen_targets.csv` (targets + bounds), then ensure foreign keys are reflected in `testgen_schema.csv`.

### Tune dataset size quickly

- Change `SCALE_FACTOR` in `test_data_generation.py` to scale all targets/bounds at once.

### Adjust priorities

- If some tables must match targets more closely than others, change `priority` in `testgen_targets.csv`. Higher priority tables are penalized more heavily in the objective.

### Export generated data

- The template prints a preview. If you want CSV outputs, add `df.to_csv(...)` calls after generation.

## Troubleshooting

<details>
<summary>I get <code>ModuleNotFoundError</code> when running the script</summary>

- Confirm you activated your virtual environment: <code>source .venv/bin/activate</code>.
- Reinstall dependencies from the template root: <code>python -m pip install .</code>.

</details>

<details>
<summary><code>rai init</code> fails or the script can’t authenticate</summary>

- Re-run <code>rai init</code> and confirm your Snowflake account has the RAI Native App installed.
- If you use multiple profiles, set <code>RAI_PROFILE</code> before running: <code>export RAI_PROFILE=&lt;profile&gt;</code>.
- Verify your Snowflake role/warehouse has access to the RelationalAI Native App.

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
<summary>The row counts look “off by 1” versus my targets</summary>

- The solver uses continuous variables and the script rounds to integers when printing and generating.
- If you need exact integer row counts, consider switching to an integer model (MILP) for <code>Table.actual_rows</code>.

</details>

<details>
<summary>I expected larger output tables</summary>

- The script prints only a preview of generated data using <code>df.head(3)</code>.
- To export full tables, add a <code>df.to_csv(...)</code> step after generation.

</details>

<details>
<summary>The generated tables don’t include all schema columns</summary>

- The included generator is intentionally small and only produces a subset of the columns described in <code>testgen_schema.csv</code>.
- Extend <code>generate_test_data(...)</code> to populate additional columns (including nullable fields, value domains, and min/max bounds).

</details>
