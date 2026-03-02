---
title: "Simple Start"
description: "A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI."
experience_level: beginner
industry: "General"
featured: true
reasoning_types:
  - Graph
tags:
  - getting-started
  - graphs
  - betweenness-centrality
---

## What this template is for

This template is a minimal, runnable notebook designed to help you get up and running with RelationalAI against Snowflake.
It walks through a tiny end-to-end example: create a simple Snowflake table, model it as a graph in RelationalAI, and compute a basic graph metric.

## Who this is for

- Anyone new to RelationalAI who wants a short “first success” notebook
- Users comfortable running Jupyter and making small edits

## What you’ll build

- A working notebook that connects to Snowflake via your RelationalAI configuration
- A small graph model built from a Snowflake `CONNECTIONS` table
- A queryable graph representation (edge list)
- Betweenness centrality scores for each station

## What’s included

- **Model**: `Station` and `Connection` concepts, plus a derived graph edge relation
- **Runner**: `simple-start.ipynb` (primary notebook)
- **Sample data**: a small Snowflake table created by the notebook (`RAI_DEMO.SIMPLE_START.CONNECTIONS`)
- **Outputs**: pandas DataFrames (table preview, edge list, and betweenness centrality)

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed
- A Snowflake user/role that can:
  - create schemas/tables (or write into a schema you control)
  - create/refresh a stream into the RelationalAI app (as prompted by the notebook)

### Tools

- Python >= 3.10
- Jupyter Notebook/Lab

This template installs:

- `relationalai==1.0.0a8`
- `jupyter`

## Quickstart

1. **Download the ZIP file for this template and extract it:**

   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/simple-start.zip
   unzip simple-start.zip
   cd simple-start
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   From the template folder (this is `v1/simple-start` if you cloned the full repository):

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

   This notebook reads data from Snowflake and executes RelationalAI queries, so you need a working RelationalAI/Snowflake configuration.

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

   Open `simple-start.ipynb` and run the cells top-to-bottom (or "Run All").

7. **Expected output**

   You should see:

   - A preview of the Snowflake `CONNECTIONS` table.
   - An edge list DataFrame (one row per connection).
   - A DataFrame of betweenness centrality values (sorted descending).

## Template structure

```text
.
├─ README.md
├─ pyproject.toml           # Python dependencies for running the notebook
└─ simple-start.ipynb       # start here (main notebook)
```

**Start here**: `simple-start.ipynb`

## Sample data

The notebook creates a small Snowflake table:

- `RAI_DEMO.SIMPLE_START.CONNECTIONS(station_1 int, station_2 int)`

Each row represents a connection between two power station IDs.

## Model overview

The notebook models two core concepts and then builds a graph representation.

The `Station` concept represents a power station:

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | integer | Yes | Station identifier from `station_1` / `station_2` |

The `Connection` concept represents a connection between two stations:

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `src` | relationship | Yes | Source `Station` |
| `dst` | relationship | Yes | Destination `Station` |

The model also defines a station-to-station connectivity relationship (used to populate the graph edge relation).

## How it works

At a high level, the notebook:

1. Creates and populates the `CONNECTIONS` table in Snowflake.
2. Defines `Station` and `Connection` concepts and loads them from the Snowflake source table.
3. Builds an undirected graph from the station connectivity relation.
4. Lists the resulting edges as a table.
5. Computes betweenness centrality and queries the scores into a pandas DataFrame.

## Customize this template

### Use your own data

- Replace `RAI_DEMO.SIMPLE_START.CONNECTIONS` with your own edge table.
- Ensure your table has two columns that represent the endpoints of each edge.

### Extend the model

- Add node attributes (for example, station type, capacity, region) and join them to `Station`.
- Add additional graph analytics supported by the `Graph` reasoner.

## Troubleshooting

<details>
  <summary>Jupyter can’t import <code>relationalai</code> (or uses the wrong environment)</summary>

- Confirm your virtual environment is active: <code>which python</code> should point to <code>.venv</code>.
- Reinstall dependencies: <code>python -m pip install .</code>.
- In Jupyter/VS Code, select the kernel that points to the <code>.venv</code> interpreter.

</details>

<details>
  <summary>Authentication/configuration fails when the notebook runs queries</summary>

- Make sure your RelationalAI/Snowflake configuration is present and correct.
- If you use the RelationalAI CLI, run <code>rai init</code> to create/update your config.
- If you have multiple profiles, set <code>RAI_PROFILE</code> to the one you want.

</details>

<details>
  <summary>The notebook can’t create the demo table/schema</summary>

- Ensure your Snowflake role can create schemas/tables in the target database.
- Alternatively, edit the notebook to write into a database/schema you control.

</details>

## Learn more

- RelationalAI documentation: https://docs.relational.ai/build
- Jupyter documentation: https://jupyter.org/documentation
- Snowflake documentation: https://docs.snowflake.com/

Include the top 5–8 failure modes with specific fixes.
Here are some examples:

<details>
	<summary>Why did dependency installation fail?</summary>

	- Confirm you’re using the recommended runtime version (Python/Node) for this template.
	- Use a fresh virtual environment and re-install dependencies.
	- On macOS/Linux, check for missing system libraries if you see compiler/build errors.
</details>

<details>
	<summary>Why did data loading fail (schema/format issues)?</summary>

	- Verify input files match the expected headers and types.
	- Check delimiter/quoting/encoding (CSV UTF-8 is the safest default).
	- Confirm required columns are present and not entirely null/empty.
</details>

<details>
	<summary>Why are my results empty or unexpected?</summary>

	- Sanity-check the input data (row counts, key coverage, date ranges).
	- Check that join keys line up (IDs/codes match across files).
	- Start from the smallest query/output and work forward through the pipeline.
</details>

## Learn more

This section is the “map” into the RelationalAI docs. Keep it curated.

Group links by purpose, and add a one-line description for each.

### Core concepts

- (Link) — What it teaches and how it relates to this template
- (Link)

### Language / modeling reference

- (Link)
- (Link)

### CLI / SDK guides

- (Link)
- (Link)

### Deeper dives (optional)

- (Link) — “If you want to extend X, read this next”

## Support

- Where to ask questions / file issues
