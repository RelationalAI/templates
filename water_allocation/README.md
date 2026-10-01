---
title: "Water Allocation"
description: "Minimize the cost of distributing water from sources to users with nonlinear transmission losses."
featured: false
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Prescriptive
tags:
  - Resource Allocation
  - Network Flow
  - Nonlinear Programming
  - Ipopt
---

## What this template is for

Water utilities must distribute water from multiple sources — reservoirs, groundwater — to multiple user groups such as municipal, industrial, and agricultural demand. Each source has a limited capacity and a different extraction cost, and every connection in the distribution network has a maximum flow rate and a transmission loss that reduces the amount actually delivered. Losses grow as a pipe runs closer to capacity, so a plan that ignores that effect over-promises delivery on its busiest routes.

The goal is the minimum-cost allocation that still meets every user's demand once realistic, utilization-dependent losses are accounted for.

**A prescriptive reasoner finds the least-cost allocation that meets every demand while honoring source capacities and utilization-dependent transmission losses.**

## Who this is for

- Water resource planners and utility operations analysts
- Engineers modeling distribution networks with capacity and loss
- Developers learning network flow optimization with RelationalAI

## What you'll build

- A minimum-cost water-distribution plan — a flow allocation across every source-to-user connection — solved with the Ipopt nonlinear solver.
- Source-capacity constraints limiting total outflow per source, and per-connection flow upper bounds.
- Demand constraints that model utilization-dependent transmission losses, so delivered volume reflects how hard each route is being pushed.

Built using **prescriptive reasoning** (nonlinear program over continuous flow variables, with a quadratic loss term).

## What's included

- **Model**: a single-stage nonlinear optimization on a shared ontology — `Source`, `User`, and `Connection` concepts wired to the bundled CSVs.
- **Runner**: `water_allocation.py` — a single Python script that builds the model, constraints, and objective and calls the solver against a Snowflake-connected RAI account.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: a small water-distribution network of sources, user groups, and the connections between them. See *Sample data* below.
- **Outputs**: solver status, total cost, and the per-connection flow allocations.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.0.14`).

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/water_allocation.zip
   unzip water_allocation.zip
   cd water_allocation
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

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python water_allocation.py
   ```

6. Expected output (a few lines confirm a successful run):
   ```text
   Status: LOCALLY_SOLVED
   Total cost: $853.39

   Flow allocations:
     Reservoir_A     Municipal  400.00
     Reservoir_B  Agricultural  182.06
     ...
   ```

   The full printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
water_allocation/
  water_allocation.py   # Main script (network model, constraints, solver call)
  data/
    sources.csv         # Water sources with capacity and cost per unit
    users.csv           # User groups with demand and priority
    connections.csv     # Network connections with max flow and loss rate
  README.md             # this file
  runbook.md            # analyst-facing paste-testable walkthrough
  pyproject.toml        # dependencies
```

**Start here**: run `python water_allocation.py` for the full solve end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is a small, illustrative water-distribution network — designed to teach the nonlinear flow formulation on a Snowflake-connected RAI account, not to match a specific utility's system.

- **`sources.csv`** — water sources, each with a `capacity` and a `cost_per_unit`.
- **`users.csv`** — user groups, each with a `demand` and a `priority`.
- **`connections.csv`** — source-to-user links, each with a `max_flow` and a `loss_rate` (the fraction lost at full utilization).

## Model overview

A single shared ontology holds the network. The `Connection` concept carries the flow decision variable the solver assigns.

- **Key entities**: `Source` (reservoirs, groundwater), `User` (demand groups), `Connection` (source-to-user links).
- **Primary identifiers**: integer `id` on `Source` and `User`; `Connection` is identified by its `source` and `user` endpoints.
- **Important invariants**: `capacity`, `demand`, `max_flow`, and `cost_per_unit` are non-negative; `loss_rate` is a fraction in `[0, 1]`; each connection's flow is continuous and bounded between 0 and its `max_flow`.

For the full concept and property definitions, see `water_allocation.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

This is a network-flow problem: source-capacity limits, per-connection flow bounds, and demand constraints whose nonlinear loss term makes it quadratic, solved with the Ipopt nonlinear solver.

The script loads three concepts from CSV — sources with a capacity and an extraction cost, users with a demand, and connections that link a source to a user with a maximum flow and a loss rate. Each connection then gets a continuous flow decision variable, bounded between zero and its maximum flow, that the solver assigns.

Two families of constraints shape the plan. A source-capacity constraint holds the total outflow from each source within its capacity. A demand constraint requires each user's effective inflow — the flow delivered after losses — to meet its demand. The loss term is where the nonlinearity enters: the fraction lost on a connection grows with how hard the route is being pushed, so effective delivery falls as a connection approaches its maximum flow. That utilization-dependent loss makes the demand constraint quadratic, which is why the model needs the Ipopt nonlinear solver rather than a linear one. The objective minimizes total extraction cost across all flows, so the solver leans on cheaper sources and lightly loaded routes.

```text
sources/users/connections CSVs → per-connection flow variables → capacity + loss-adjusted demand constraints → minimize cost → allocation plan
```

See `water_allocation.py` for the implementation, and `runbook.md` to reproduce it step by step with the RAI skills.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names shown in *Sample data* above (`sources.csv`, `users.csv`, `connections.csv`).
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.
- Confirm `source_id` and `user_id` in `connections.csv` match the `id` columns in `sources.csv` and `users.csv` — a mismatched key silently drops the connection.

### Tune parameters

- **Source capacity and cost** — edit `capacity` and `cost_per_unit` in `sources.csv` to change which sources the solver prefers.
- **Loss rate** — `loss_rate` in `connections.csv` controls how steeply delivery falls as a route approaches capacity.

### Extend the model

- **Add seasonal variation** by introducing time periods with different source capacities and user demands.
- **Include priority-based allocation** using the `priority` field to penalize unmet demand differently for each user group.
- **Add minimum flow requirements** on certain connections to model contractual obligations.
- **Extend the network** with intermediate nodes (pumping stations, treatment plants) that add processing costs or additional capacity constraints.

### Scale up / productionize

- Replace the `data/` CSV bundle with CDC ingestion from your upstream source and demand systems.
- The bundled network is small; the formulation scales to whatever the Ipopt solver can handle in your solve budget. Pin dependencies via `pyproject.toml` for reproducible runs.

## Troubleshooting

<details>
<summary><code>Status: INFEASIBLE</code></summary>

Total source capacity (after losses) is insufficient to meet all user demands. Check that the sum of source capacities minus worst-case losses covers total demand. You can increase source capacity in `sources.csv`, reduce demands in `users.csv`, or add new connections in `connections.csv`.
</details>

<details>
<summary>Some connections show zero flow</summary>

The solver avoids expensive routes when cheaper alternatives exist. If a source has a high cost per unit, its connections may carry zero flow. This is expected behavior for a cost-minimizing solution.
</details>

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that your account has the RAI Native App installed and that your user has the required permissions.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `model.select(...)` / `sum`.
- [Ontology modeling](https://docs.relational.ai/) — concepts, properties, and relationships that back this network model.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, decision variables, constraints, objective.
- [Nonlinear solving with Ipopt](https://docs.relational.ai/) — when a quadratic or nonlinear constraint requires the nonlinear solver.

## Support

- File issues at the RelationalAI templates repository.
