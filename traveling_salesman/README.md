---
title: "Traveling Salesman"
description: "Find the shortest route that visits every city exactly once and returns home. A self-contained starting point for building route optimization on RelationalAI."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Routing
  - Mixed-Integer Programming (MIP)
  - Combinatorial Optimization
  - Miller-Tucker-Zemlin (MTZ)
---

## What this template is for

A delivery driver, a service technician, or a drilling head has a list of stops and needs the cheapest way to visit them all and come back. The traveling salesman problem (TSP) captures exactly this: given a set of locations and the distances between them, find the shortest tour that visits every location once and returns to the start. It is one of the most studied problems in optimization and shows up across route planning, delivery logistics, circuit-board drilling, and scheduling.

This template solves a small TSP instance end to end and gives you a clear, self-contained starting point for building route optimization on RelationalAI.

**Reasoning approach:** the tour is found with prescriptive reasoning — a mixed-integer program (MIP) whose binary variables choose which edges are on the route and whose Miller-Tucker-Zemlin (MTZ) auxiliary variables rule out disconnected subtours.

## Who this is for

- Operations researchers learning TSP formulations
- Logistics planners building route optimization prototypes
- Students studying combinatorial optimization
- Developers exploring mixed-integer programming with RelationalAI

## What you'll build

- An optimal tour visiting every node exactly once, returned as the set of selected edges with a total distance.
- A prescriptive MIP formulation with binary edge decisions and integer ordering variables, expressed directly on the ontology.
- Degree constraints guaranteeing exactly one in-edge and one out-edge per node.
- Miller-Tucker-Zemlin subtour elimination that keeps the solution a single connected cycle.

Built using **prescriptive reasoning** (mixed-integer programming with the HiGHS solver).

## What's included

- `model/__init__.py` -- ontology, MTZ formulation, and solver configuration; `rai models deploy --path model` deploys it to your Snowflake account, where each refresh runs the solve
- `queries/tour.py` -- prints the report from the deployed model: the solve status, the tour distance, and the tour edges
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/edges.csv` -- 12 directed edges between 4 nodes with distances
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (Quickstart step 4 below covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 2.1.1`)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.TRAVELING_SALESMAN_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.TRAVELING_SALESMAN_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/traveling_salesman.zip), unzip it, and enter the template directory:

   ```bash
   unzip traveling_salesman.zip
   cd traveling_salesman
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: traveling_salesman_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.TRAVELING_SALESMAN               # published views and tables
     identity:
       internal_schema: <DB>.TRAVELING_SALESMAN_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.tour
   ```

   ```text
   HiGHS: OPTIMAL, tour distance=8.5

   Tour edges:
      from  to
   0     1   2
   1     2   4
   2     3   1
   3     4   3
   ```

   The formulation printed above the status line is trimmed here. Before printing, the report checks the problem's size against the deployed model's distinct edges and nodes (one variable per edge and per node, one minimization objective), and it stops unless the termination status is `OPTIMAL`. The tour is 1, 2, 4, 3 and back to 1, for a total distance of 8.5. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.TRAVELING_SALESMAN_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
traveling_salesman/
├── README.md            # this file
├── pyproject.toml       # dependencies
├── model/
│   └── __init__.py      # the deployed model (ontology, MTZ formulation, solve)
├── queries/
│   └── tour.py          # report from the deployed model
└── data/
    └── edges.csv        # 12 directed edges between 4 nodes, with distances
```

**Start here:** deploy with `rai models deploy --path model` and run `python -m queries.tour` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

`data/edges.csv` is a directed distance matrix with the columns `i`, `j`, and `dist`: a distance `dist` for traveling from node `i` to node `j`. The bundled instance has 12 directed edges connecting 4 nodes, with an edge in both directions between every pair, so the graph is strongly connected and a tour always exists. Nodes are not listed in their own file; the model derives them from the edge endpoints.

## Model overview

The model has two concepts: the `Edge` rows loaded from CSV, and the `Node` set derived from edge endpoints. The optimizer adds one decision per edge and one ordering value per node.

- **Key entities**: `Edge` (a directed leg with a distance), `Node` (a location to visit).
- **Primary identifiers**: an `Edge` is identified by its endpoint pair `(i, j)`; a `Node` is identified by its index `v`.
- **Important invariants**: distances are non-negative; every node needs exactly one in-edge and one out-edge; the selected edges must form a single cycle (no subtours).

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model loads the directed edges with their distances from CSV, then derives the `Node` set from the edge endpoints so nodes never need their own file. On the ontology it lays down the decision variables the solver will fill in: a binary variable per edge (1 if the edge is on the tour) and an integer ordering value per node used for subtour elimination.

Two families of constraints shape the tour. Degree constraints require exactly one incoming and one outgoing selected edge at every node, so the route enters and leaves each stop once. Miller-Tucker-Zemlin (MTZ) constraints tie the ordering values together: whenever an edge is selected, the destination's order must exceed the source's, which is what rules out disconnected subtours and forces a single connected cycle. The objective minimizes the total distance of the selected edges, and the HiGHS solver returns the optimal tour.

```text
edges.csv → load edges → derive nodes → edge + ordering variables → degree + MTZ constraints → minimize distance → optimal tour
```

See `model/__init__.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace `data/edges.csv` with your own city-to-city distance matrix, as a list of directed edges with the columns `i`, `j`, and `dist`, or change the `read_csv(...)` path in `model/__init__.py`.
- Provide an edge in both directions for every pair of nodes so the graph stays strongly connected. Asymmetric costs are supported: give the forward and reverse edges different `dist` values.

### Tune parameters

- The solve time cap is `time_limit_sec` (default 60) in the `problem.configure("highs", ...)` call. Lower it to accept a near-optimal tour sooner on larger instances.

### Extend the model

- Add time windows by introducing per-node arrival-time variables and constraints.
- Visualize the result by plotting the nodes and the selected edges with a plotting library such as matplotlib.

### Scale up / productionize

- The MTZ formulation is compact and works well for small to medium instances (up to roughly 50 nodes). Its subtour-elimination constraints grow with the square of the node count, so solves slow down as instances grow.
- For production-scale routing (100+ stops), move to specialized TSP solvers or cutting-plane / branch-and-cut formulations.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Ensure `edges.csv` contains edges in both directions for every pair of nodes (the graph must be strongly connected).
- Verify that node indices are consistent: every node referenced in an edge must appear as both a source and a destination.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4).
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Slow solve times for larger instances</summary>

- The MTZ formulation has O(n^2) subtour elimination constraints, which can be slow for large n.
- Consider reducing the `time_limit_sec` parameter and accepting near-optimal solutions.
- For production-scale TSP (100+ cities), consider specialized TSP solvers or cutting-plane approaches.

</details>

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used here.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and deriving one concept from another (nodes from edges).

### Language / modeling reference

- [Constraints and objectives](https://docs.relational.ai/) — `satisfy()`, `require()`, `minimize()`, and per-group aggregation with `.per(...)`.

### CLI / SDK guides

- [RelationalAI Python SDK](https://docs.relational.ai/) — installing and configuring the `relationalai` package and connecting to Snowflake.

## Support

- File issues at the RelationalAI templates repository.
