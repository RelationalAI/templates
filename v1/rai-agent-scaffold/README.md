---
title: "Snowflake Intelligence Agent — RelationalAI Knowledge Graph"
description: "Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence."
experience_level: intermediate
industry: General
reasoning_types:
  - Descriptive
tags:
  - cortex-agent
  - snowflake-intelligence
  - knowledge-graph
  - natural-language
  - semantic-layer
---

## What this template is for

RelationalAI lets you map Snowflake tables into a semantic layer — concepts, properties, and relationships — that executes directly inside Snowflake. This template wires that semantic layer into a Snowflake Cortex agent so users can ask natural-language questions about their data from anywhere in Snowflake Intelligence.

The scaffold provides the full lifecycle tooling: define your model, test queries locally, deploy stored procedures and the agent, push updates, and tear everything down — all from a single CLI script.

## Who this is for

- Engineers and data modelers who have a Snowflake table they want to expose conversationally
- Teams building or evaluating RAI-powered Snowflake Intelligence integrations
- Assumed knowledge: basic Python, familiarity with Snowflake, some exposure to PyRel concepts (concepts, properties, model.define)

## What you'll build

- A PyRel semantic model (ontology) that maps your source table to typed concepts and properties
- A set of curated analytical queries the agent can execute on demand
- A deployed Snowflake Cortex agent with stored procedures backed by the model
- A Snowflake Intelligence integration that lets users ask natural-language questions against your data

## What's included

- **Model** (`ontology.example.py`): Example concept and property definitions with a parent/child hierarchy and label tagging pattern
- **Queries** (`queries.example.py`): Two example queries — category breakdown and label traceability — plus the `ToolRegistry` wiring
- **Runner** (`si_agent.py`): CLI for deploy / update / status / chat / teardown
- **Config template** (`rai-agent-config.example.yaml`): All instance-specific values in one place
- **Local smoke test** (`test_queries.example.py`): Runs both queries directly against Snowflake before deploying

## Prerequisites

### Access

- RelationalAI native app installed in your Snowflake account
- `ACCOUNTADMIN` role (or equivalent) with `CREATE PROCEDURE`, `CREATE STAGE`, and `CREATE AGENT` on the target schema
- The target schema must exist before deploying
- Change tracking enabled on the source table:
  ```sql
  ALTER TABLE <YOUR_DB>.<YOUR_SCHEMA>.<YOUR_TABLE> SET CHANGE_TRACKING = TRUE;
  ```

### Tools

- Python 3.10+
- `relationalai>=1.0.12`, `httpx`, `pyyaml` (see `pyproject.toml`)

## Quickstart

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Copy and fill in config files**

   ```bash
   cp rai-agent-config.example.yaml rai-agent-config.yaml
   cp ontology.example.py ontology.py
   cp queries.example.py queries.py
   cp test_queries.example.py test_queries.py
   ```

   Edit `rai-agent-config.yaml` with your agent name, database, schema, warehouse, model name, and source table.

   Create `raiconfig.yaml` with your Snowflake credentials (see Configuration below).

3. **Define your model**

   Edit `ontology.py` — replace the `Node`/`Edge` example with concepts and properties that match your source table.

4. **Define your queries**

   Edit `queries.py` — replace or extend the example query functions. Each function's docstring is what the LLM sees to decide when to call it.

5. **Test locally**

   ```bash
   RAI_CONFIG_FILE_PATH=raiconfig.yaml python test_queries.py
   ```

6. **Deploy**

   ```bash
   python si_agent.py deploy
   python si_agent.py status
   ```

7. **Test a question**

   ```bash
   python si_agent.py chat "what can I ask about?"
   ```

8. **Expected output**

   ```
   Deploying 'MY_AGENT_NAME' to MY_DATABASE.MY_SCHEMA ...
   Agent MY_AGENT_NAME: ACTIVE (2 tools registered)
   ```

## Template structure

```text
.
├── README.md                        # this file
├── pyproject.toml                   # dependencies
├── si_agent.py                      # deployment CLI — start here
├── rai-agent-config.example.yaml    # config template → copy to rai-agent-config.yaml
├── ontology.example.py              # model template → copy to ontology.py
├── queries.example.py               # query template → copy to queries.py
└── test_queries.example.py          # local smoke test → copy to test_queries.py
```

**Start here**: `python si_agent.py deploy`

## Configuration

### rai-agent-config.yaml

Single source of truth for all instance-specific values.

```yaml
agent:
  name: MY_AGENT_NAME               # Name shown in Snowflake Cortex Agents UI
  database: MY_DATABASE             # Snowflake database to deploy into
  schema: MY_SCHEMA                 # Schema to deploy into (must already exist)
  warehouse: MY_WAREHOUSE           # Warehouse for sproc execution
  model_name: MY_MODEL_NAME         # RAI Model name used internally in each sproc

model:
  source_table: MY_DB.MY_SCHEMA.MY_TABLE  # Fully-qualified source table
```

### raiconfig.yaml (gitignored)

Snowflake connection credentials used locally and during deployment.

```yaml
connections:
  sf:
    account:       # Snowflake account identifier
    user:          # Your Snowflake username
    password:      # Your password
    warehouse:     # Warehouse for query execution
    role:          # Must have CREATE PROCEDURE, CREATE STAGE, CREATE AGENT
    rai_app_name:  # Name of the RelationalAI native app (usually RELATIONALAI)
```

## Model overview

The example ontology models a hierarchical dataset (e.g. a bill-of-materials or org structure) sourced from a single Snowflake table.

- **Key entities**: `Node` (a record in the source table), `Edge` (a parent→child link between nodes)
- **Primary identifiers**: `Node` is identified by `id` (string); `Edge` by `(parent_id, child_id)`
- **Important invariants**: null `id` rows are silently dropped by null propagation — do not coalesce nulls to a sentinel

### Concepts

**Node** — Represents a record in the source table, deduplicated by `id`.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | string | Yes | Loaded from `parent_id` and `child_id` columns |
| `category` | string | No | Required for `per()`-based aggregation queries |
| `label` | string | No | Optional classification tag; used by `label_trace` query |

**Edge** — Represents a directed parent→child link between two nodes.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `parent_id` | string | Yes | FK to `Node.id` |
| `child_id` | string | Yes | FK to `Node.id` |

## How it works

1. `ontology.py` maps source table rows into `Node` and `Edge` concepts via `model.define()`
2. `queries.py` defines query functions that return `rai.Fragment` objects; each function's docstring is verbalized to the LLM
3. `si_agent.py deploy` packages `ontology.py` and `queries.py` as Snowflake stored procedures and registers a Cortex agent
4. Snowflake Intelligence routes natural-language questions to the agent, which selects and executes the appropriate query
5. Results are verbalized and returned as a natural-language response

```text
Snowflake table → ontology.py → RAI model → queries.py → stored procs → Cortex agent → Snowflake Intelligence
```

## Customize this template

### Use your own data

- Set `model.source_table` in `rai-agent-config.yaml` to your fully-qualified table name
- In `ontology.py`, replace `Node`/`Edge` with concepts that match your domain
- Column names in `model.define()` must match your actual table columns

### Add a new query

1. Write a function in `queries.py` returning a `rai.Fragment` with a clear docstring
2. Bind and register it in `build_tool_registry` → `QueryCatalog`
3. Test locally: `python test_queries.py`
4. Push to Snowflake: `python si_agent.py update`

### Seed labels

In `ontology.py` inside `initialize()`:

```python
node = Node.ref()
model.define(node.label("MY_LABEL")).where(node.id == "some-identifier")
```

Then run `python si_agent.py update`.

### Scale up / productionize

- Pin `relationalai` to a specific version in `pyproject.toml` for reproducible deploys
- Run `si_agent.py update` in CI after merging changes to `ontology.py` or `queries.py`
- Use a dedicated warehouse sized for your query volume

## Troubleshooting

<details>
  <summary>Why did deployment fail with a permissions error?</summary>

  - Confirm your Snowflake role has `CREATE PROCEDURE`, `CREATE STAGE`, and `CREATE AGENT` on the target schema.
  - Verify the target schema already exists — the deploy step does not create it automatically.
</details>

<details>
  <summary>Why is my source table not found?</summary>

  - Check that `model.source_table` in `rai-agent-config.yaml` is fully qualified (`DB.SCHEMA.TABLE`).
  - Confirm change tracking is enabled: `ALTER TABLE ... SET CHANGE_TRACKING = TRUE`.
</details>

<details>
  <summary>Why do local test queries return duplicate rows?</summary>

  - This is a known local-execution quirk: `.to_df()` may return one row per `(node, category)` because `node` stays a free variable. Add `.drop_duplicates()` as shown in `test_queries.example.py`. The deployed sproc returns correctly aggregated results.
</details>

<details>
  <summary>Why did the sproc fail with an httpx import error?</summary>

  - `httpx` is not auto-installed as a transitive dep in Snowflake sprocs. It is explicitly added via `_EXTRA_PACKAGES` in `si_agent.py` — ensure you have not removed it.
</details>

<details>
  <summary>Why does the agent appear inactive after deploy?</summary>

  - Run `python si_agent.py status` to see the full deployment state.
  - If the agent shows as pending, wait a few seconds and re-check — Cortex agent registration is asynchronous.
</details>

## Known workarounds

| Issue | Workaround applied |
|---|---|
| `snowflake-telemetry-python` conflicts with `relationalai>=1.0.x` opentelemetry dependency | Remove `snowflake-telemetry-python` from the sproc package list in the installed library (`relationalai/agent/cortex/cortex_tool_resources.py` ~line 278). Re-apply after upgrading `relationalai`. |
| `httpx` not auto-installed as a transitive dep in Snowflake sprocs | Added `"httpx"` to `_EXTRA_PACKAGES` in `si_agent.py`. |
| Local `.to_df()` returns one row per node for count queries | Added `.drop_duplicates()` in `test_queries.example.py`. |

## Learn more

### Core concepts

- [RelationalAI Concepts & Properties](https://docs.relational.ai) — How `model.Concept`, `model.Property`, and `model.define()` work
- [Cortex Agents overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents) — Snowflake's agent framework

### Language / modeling reference

- [PyRel v1 documentation](https://docs.relational.ai) — Full language reference for `relationalai.semantics`
- [ToolRegistry & QueryCatalog API](https://docs.relational.ai) — How to register queries for agent use

### Deeper dives

- [Snowflake Intelligence](https://docs.snowflake.com/en/user-guide/snowflake-intelligence) — How to promote a Cortex agent to Snowflake Intelligence

## Support

- File issues or ask questions at [RelationalAI Community](https://relational.ai/community)
- For template bugs, open an issue in this repository
