# Employee Directory Example

A concrete, runnable example for the `rai-agent-scaffold` template. It models a
small company org chart and exposes it as a Snowflake Intelligence agent so users
can ask natural-language questions like:

- *"How many people are in each department?"*
- *"Who does Alice Smith report to?"*
- *"Show me all direct reports for the engineering lead."*

## What's in this folder

| File | Purpose |
|---|---|
| `data/employees.csv` | 12-row sample dataset — upload this to Snowflake as your source table |
| `ontology.py` | Semantic model: `Employee` and `ReportsTo` concepts |
| `queries.py` | Two queries: `headcount_by_department` and `direct_reports` |
| `test_queries.py` | Local smoke test — run before deploying |
| `rai-agent-config.example.yaml` | Pre-filled config template |

## Quickstart

**1. Upload sample data to Snowflake**

Create a table from `data/employees.csv`. The table must have these columns:
`EMPLOYEE_ID`, `NAME`, `DEPARTMENT`, `TITLE`, `MANAGER_ID`.

Enable change tracking on the table:

```sql
ALTER TABLE MY_DB.MY_SCHEMA.EMPLOYEES SET CHANGE_TRACKING = TRUE;
```

**2. Copy files to the parent scaffold directory**

```bash
cd v1/rai-agent-scaffold

cp example/ontology.py ontology.py
cp example/queries.py queries.py
cp example/test_queries.py test_queries.py
cp example/rai-agent-config.example.yaml rai-agent-config.yaml
```

**3. Fill in config**

Edit `rai-agent-config.yaml` — set your `database`, `schema`, `warehouse`,
and `source_table` (the fully-qualified EMPLOYEES table you just created).

**4. Test locally**

```bash
RAI_CONFIG_FILE_PATH=raiconfig.yaml python test_queries.py
```

Expected output:

```text
QUERY 1: headcount_by_department
   department  headcount
  Engineering          4
      Product          3
       Design          3

QUERY 2: direct_reports
    manager_name       manager_title   department      report_name         report_title
      Sarah Chen  VP of Engineering  Engineering      Alice Smith    Senior Engineer
      Alice Smith    Senior Engineer  Engineering       Bob Jones            Engineer
      Alice Smith    Senior Engineer  Engineering      Rachel Kim             Engineer
      ...
```

**5. Deploy and test the agent**

```bash
python si_agent.py deploy
python si_agent.py status
python si_agent.py chat "how many people are in each department?"
```

## Ontology at a glance

The source table has one row per employee. The model derives two concepts:

- **Employee** — identified by `EMPLOYEE_ID`. Has `name`, `department`, and `title`.
- **ReportsTo** — identified by `(MANAGER_ID, EMPLOYEE_ID)`. Represents a direct
  reporting relationship. Employees with a null `MANAGER_ID` (department heads)
  have no `ReportsTo` edge and are treated as root nodes.

```text
EMPLOYEES table
    EMPLOYEE_ID  NAME          DEPARTMENT   TITLE               MANAGER_ID
    E001         Sarah Chen    Engineering  VP of Engineering    (null)
    E002         Alice Smith   Engineering  Senior Engineer      E001
    E003         Bob Jones     Engineering  Engineer             E002
    ...
         │
         ▼
    Employee(id=E001, name="Sarah Chen", department="Engineering", ...)
    Employee(id=E002, name="Alice Smith", ...)
    ReportsTo(manager_id=E001, employee_id=E002)
    ReportsTo(manager_id=E002, employee_id=E003)
    ...
```

## Adapting to your own data

This example uses a flat table where each employee row carries both the
employee's own attributes and a reference to their manager. To use your own
employee table:

1. Ensure the table has at minimum: an employee ID column, a department column,
   and a manager ID column (nullable for top-level employees).
2. Update the column references in `ontology.py` (`src.EMPLOYEE_ID`, `src.MANAGER_ID`,
   etc.) to match your actual column names.
3. Update `source_table` in `rai-agent-config.yaml`.
4. Re-run `test_queries.py` to validate before deploying.
