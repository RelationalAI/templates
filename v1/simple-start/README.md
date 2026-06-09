---
title: "Simple Start"
description: "A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI."
experience_level: beginner
industry: "Cross-Industry"
featured: true
reasoning_types:
  - Graph
tags:
  - getting-started
  - graphs
  - betweenness-centrality
sidebar:
  order: 1
---

## What this template is for

This template is a minimal, runnable notebook designed to help you get up and running with RelationalAI against Snowflake.
It walks through a small end-to-end example: create a Snowflake table, model it as a graph in RelationalAI, and compute a basic graph metric.

## Who this is for

- Anyone new to RelationalAI who wants a quick win with a notebook
- Users comfortable running Jupyter and making small edits

## What you’ll build

- A working notebook that connects to Snowflake via your RelationalAI configuration
- A small graph model built from a Snowflake `CONNECTIONS` table
- A queryable graph representation
- Betweenness centrality scores for each station

## What’s included

- **Model**: `Station` and `Connection` concepts, plus a derived graph edge relation
- **Runner**: `simple-start.ipynb` as the primary notebook
- **Sample data**: a small Snowflake table created by the notebook
- **Outputs**: pandas DataFrames with table preview, edge list, and betweenness centrality

## Prerequisites

- Python >= 3.10
- A Snowflake account with the RelationalAI Native App installed
- A Snowflake user and role that can:
  - Create schemas and tables or write into a schema you control
  - Create and refresh a stream into the RelationalAI app, as prompted by the notebook

## Quickstart

1. **Download the ZIP file for this template and extract it:**

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/simple-start.zip
   unzip simple-start.zip
   cd simple-start
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   From the template folder, which is `v1/simple-start` if you cloned the full repository:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure credentials**

   This notebook reads data from Snowflake and executes RelationalAI queries, so you need a working RelationalAI and Snowflake configuration.

   If you use the RelationalAI CLI, run:

   ```bash
   rai init
   ```

   If you have multiple profiles, set one explicitly:

   ```bash
   export RAI_PROFILE=<your_profile>
   ```

5. **Start Jupyter**

   ```bash
   jupyter notebook
   ```

6. **Run the template**

   Open `simple-start.ipynb` and run the cells top-to-bottom or "Run All".

7. **Expected output**

   You should see:

   - A preview of the Snowflake `CONNECTIONS` table.
   - An edge list DataFrame, with one row per connection.
   - A DataFrame of betweenness centrality values, sorted in descending order.

## How it works

At a high level, the notebook:

1. Creates and populates the `CONNECTIONS` table in Snowflake.
2. Defines `Station` and `Connection` concepts and loads them from the Snowflake source table.
3. Builds an undirected graph from the station connectivity relation.
4. Lists the resulting edges as a table.
5. Computes betweenness centrality and queries the scores into a pandas DataFrame.

> [!TIP]
> At any point after step 2 you can run `inspect.schema(model)` to see exactly what's registered. See [Inspect the model schema](#inspect-the-model-schema) below.

## Inspect the model schema

`relationalai.semantics.inspect` (available in `relationalai>=1.0.14`) gives you a public, typed view of what has actually been registered on the model: concepts, properties (with type metadata enriched from the backing `TableSchema` where available), relationships, and data sources. It's the recommended way to sanity-check a model before querying, especially after edits or across long sessions.

Import it once:

```python
from relationalai.semantics import inspect
```

### `inspect.schema(model)` -- full schema

Call `inspect.schema(model)` to see every concept, its identity fields, properties, relationships, and bound data sources. Add a new cell to the notebook immediately after the cell that defines `Station.connections` (so the relationship is already registered):

```python
print(inspect.schema(model))
```

Expected output for this template:

```text
Model: SimpleStart
==================

  Station
    Identity:
      id: Integer
    Relationships:
      Station is connected to Station:other_station

  Connection
    Identity:
      src: Station
      dst: Station

  Data Sources:
    RAI_DEMO.SIMPLE_START.CONNECTIONS [station_1: Any, station_2: Any]
```

`ModelSchema.__str__` also prints a trailing `Defines: (N rules)` section listing the registered rules once at least one `model.define(...)` has been executed. It's omitted above for brevity.

`schema(model)` returns a frozen `ModelSchema` dataclass with dict-style lookup and JSON serialization:

```python
schema = inspect.schema(model)
# Dict-style access: fetch one concept by name.
schema["Station"]
# JSON-safe full view.
schema.to_dict()
```

### `inspect.fields(rel)` -- select every field of a relationship

`inspect.fields()` returns a tuple of `FieldRef` objects for a relationship, directly splattable into `select()`. The benefit is that you don't hard-code field names, and inherited properties are handled automatically. Compare:

```python
# Hand-coded: you have to know the field names, and keep this line in sync if the
# relationship signature changes.
model.select(Station.connections["other_station"]).to_df()

# With inspect.fields: expands to every selectable field of the relationship.
model.select(*inspect.fields(Station.connections)).to_df()
```

### `inspect.to_concept(obj)` -- resolve a DSL handle to its underlying Concept

`inspect.to_concept()` accepts any DSL handle (a `Concept`, a chain like `Station.connections`, a reference, or an expression) and returns the underlying `Concept`. Useful when writing helpers that should work uniformly across handle shapes:

```python
# Accepts any DSL handle, returns the Concept it resolves to.
concept = inspect.to_concept(Station.connections)

# Defensive variant: pass default= to get that value back instead of raising when
# the handle can't be resolved to a single Concept. Handy for helpers that accept
# unknown-shape inputs.
concept_or_none = inspect.to_concept(some_handle, default=None)
```

## Customize this template

**Use your own data:**

- Replace `RAI_DEMO.SIMPLE_START.CONNECTIONS` with your own edge table.
- Ensure your table has two columns that represent the endpoints of each edge.

**Extend the model:**

- Add node attributes (for example, station type, capacity, region) and join them to `Station`.
- Add additional graph analytics supported by the `Graph` reasoner.

## Troubleshooting

<details>
  <summary>Jupyter can’t import <code>relationalai</code> or uses the wrong environment</summary>

- Confirm your virtual environment is active: <code>which python</code> should point to <code>.venv</code>.
- Reinstall dependencies: <code>python -m pip install .</code>.
- In Jupyter or VS Code, select the kernel that points to the <code>.venv</code> interpreter.

</details>

<details>
  <summary>Authentication or configuration fails when the notebook runs queries</summary>

- Make sure your RelationalAI and Snowflake configuration is present and correct.
- If you use the RelationalAI CLI, run <code>rai init</code> to create or update your config.
- If you have multiple profiles, set <code>RAI_PROFILE</code> to the one you want.

</details>

<details>
  <summary>The notebook can’t create the demo table or schema</summary>

- Ensure your Snowflake role can create schemas and tables in the target database.
- Alternatively, edit the notebook to write into a database or schema you control.

</details>
