---
title: "Network Flow Planning"
description: "Plan a multi-tier distribution flow that decides which fulfillment centers to open and how much to ship on every lane to satisfy customer demand at minimum cost."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Mixed-Integer Programming
  - Network Flow
  - Facility Location
  - Flow Conservation
  - Cost Minimization
---

## What this template is for

This template uses **Prescriptive** reasoning to solve a multi-tier supply-chain network design problem in a single MILP. Distribution networks usually decide two things at once:

- **How much to flow on each lane** in a multi-tier network (warehouses → transit hubs → fulfillment centers → customers).
- **Which fulfillment centers to open**, paying a fixed cost per opened facility.

Routing flow alone is a continuous LP; opening facilities alone is a combinatorial selection problem. Real planning teams must do both together because the cheapest open-set depends on the routing, and the cheapest routing depends on which FCs are open.

The template models all sites with one `Site` concept distinguished by a `type` property (warehouse / hub / fulfillment center / customer). Each site type contributes the constraints that match its role:

- **Warehouses** have inventory; outflow is bounded by inventory.
- **Transit hubs** have no inventory or capacity; inflow must equal outflow.
- **Fulfillment centers** have a capacity and a fixed open cost; total inflow is bounded by `capacity × x_open`, and the binary `x_open` adds `fixed_cost` to the objective when 1.
- **Customers** are demand sinks; inflow must meet aggregate demand at the site.

The objective minimizes transport cost plus fixed-cost FC opening cost.

## Who this is for

- Supply-chain planners and operations researchers building multi-echelon distribution models
- Data scientists learning facility-location MILPs alongside flow-conservation networks
- Developers exploring how to encode a multi-tier topology in a single concept with a typed role property

## What you'll build

- A four-tier distribution network (warehouses, transit hubs, fulfillment centers, customers) modeled with a single `Site` concept and a `type` property
- A directed `Lane` concept for transport links with cost and capacity
- A `Demand` concept for customer orders
- A MILP that simultaneously decides (a) the binary open-decision per fulfillment center and (b) the continuous flow on every lane
- Constraints covering source supply, transit-node flow conservation, FC capacity gated by the open decision, and demand satisfaction at customers
- A combined objective: minimize transport cost + sum of fixed costs of opened FCs

## What's included

- `model/__init__.py` — the model; `rai models deploy --path model` deploys it
- `queries/network_plan.py` — prints the report from the deployed model
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/sites.csv` — 12 sites: 3 warehouses, 3 transit hubs, 3 fulfillment centers, 3 customers
- `data/lanes.csv` — 17 directed lanes connecting the tiers, each with a cost-per-unit and capacity
- `data/demand.csv` — 3 customer demands (NYC 180, LA 120, Houston 150)
- `pyproject.toml` — Python package configuration with dependencies

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 2.1.1

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.NETWORK_FLOW_PLANNING_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.NETWORK_FLOW_PLANNING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/network_flow_planning.zip), unzip it, and enter the template directory:

   ```bash
   unzip network_flow_planning.zip
   cd network_flow_planning
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
       name: network_flow_planning_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.NETWORK_FLOW_PLANNING               # published views and tables
     identity:
       internal_schema: <DB>.NETWORK_FLOW_PLANNING_META      # solver inputs, results, refresh procedures
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
   python -m queries.network_plan
   ```

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 5280.0

   Status: OPTIMAL
   Total cost: $5,280.00

   Opened fulfillment centers:
     fulfillment_center  capacity  fixed_cost
   0       FC_Northeast     350.0      1500.0
   1       FC_Southwest     200.0      1200.0

   Active flows:
              from_site           to_site   flow  unit_cost
   0  Chicago_Warehouse       Memphis_Hub  200.0        2.0
   1   Dallas_Warehouse    KansasCity_Hub  250.0        2.5
   2       FC_Northeast       Customer_LA   70.0        5.0
   3       FC_Northeast      Customer_NYC  180.0        1.0
   4       FC_Southwest  Customer_Houston  150.0        1.0
   5       FC_Southwest       Customer_LA   50.0        3.5
   6     KansasCity_Hub      FC_Northeast   50.0        2.0
   7     KansasCity_Hub      FC_Southwest  200.0        1.5
   8        Memphis_Hub      FC_Northeast  200.0        1.5
   ```

   The formulation printed above the solve result is trimmed here. The optimizer opens the two largest fulfillment centers and routes LA's demand split across both — the savings from not opening FC_West ($1,000 fixed) outweigh the extra transport cost incurred by routing 120 units of LA demand through the more expensive FC_Northeast and FC_Southwest paths. The report checks the solve's termination status and stops unless it is OPTIMAL.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.NETWORK_FLOW_PLANNING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── model/
│   └── __init__.py                 # the deployed model
├── queries/
│   └── network_plan.py             # report from the deployed model
└── data/
    ├── sites.csv                   # 12 sites across 4 types
    ├── lanes.csv                   # 17 directed transport lanes
    └── demand.csv                  # 3 customer demands
```

**Start here:** deploy with `rai models deploy --path model` and run `python -m queries.network_plan` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The data describes a small but non-trivial multi-tier network where the optimizer has a real choice between opening all three fulfillment centers vs. just two:

- **3 warehouses** with inventory (Chicago 500, Dallas 400, Atlanta 300).
- **3 transit hubs** (Memphis, Kansas City, St. Louis) — pass-through nodes.
- **3 fulfillment centers**:
  - **FC_Northeast** — capacity 350, fixed cost $1,500
  - **FC_Southwest** — capacity 200, fixed cost $1,200
  - **FC_West** — capacity 180, fixed cost $1,000 (cheapest direct path to LA but highest fixed cost per unit of capacity)
- **3 customers**: NYC (demand 180), LA (demand 120), Houston (demand 150). Total 450.

Lane costs are set so that opening FC_West would unlock the cheapest LA route (`FC_West → LA` at 1.5/unit). The optimizer must weigh that against the $1,000 fixed cost of opening it. With this data it elects not to.

## Model overview

The model uses three concepts. A single `Site` concept carries all four network tiers, distinguished by a `type` property, so warehouses, hubs, fulfillment centers, and customers share one entity and each contributes the constraint that matches its role.

- **Key entities**: `Site` — a node in the distribution network, its `type` distinguishing the role each plays (warehouse, hub, fulfillment center, customer); `Lane` — a directed transport link between two sites with a per-unit cost and a flow capacity; `Demand` — a customer order placed at a particular site.
- **Primary identifiers**: integer `id` on each of `Site`, `Lane`, and `Demand`, loaded from the corresponding CSV.
- **Important invariants**: `inventory`, `capacity`, `fixed_cost`, `cost_per_unit`, and `quantity` are non-negative; only fulfillment centers carry a positive `fixed_cost` (that is what scopes the binary open decision); every `Lane.source` / `Lane.dest` and every `Demand.site` resolves to a real `Site`.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model runs as a single MILP that decides flow on every lane and which fulfillment centers to open, in one solve.

**Decision variables.** Each lane carries a continuous `x_flow` bounded by its capacity. Each fulfillment center carries a binary `x_open`; the open decision is scoped to sites with a positive `fixed_cost`, so warehouses, hubs, and customers never get an open variable.

**Constraints.** Each site type contributes the constraint that matches its role. Warehouses cap total outflow at their inventory. Transit hubs and fulfillment centers conserve flow — inflow equals outflow. A fulfillment center's inflow is bounded by `capacity × x_open`, so an unopened FC (open = 0) can carry no flow and the fixed cost is only incurred when it is opened. Customers require inflow to meet their aggregate demand.

**Objective.** Minimize transport cost (per-unit lane cost times flow, summed over lanes) plus the fixed cost of every opened fulfillment center. The two cost terms live on different concepts (`Lane` and `Site`), so the objective adds one sum per concept.

For the exact PyRel formulation, see `model/__init__.py`; `runbook.md` reproduces the model step by step with the RAI skills.

```text
CSV inputs → load Site / Lane / Demand → flow + open decisions → role-based constraints → minimize transport + fixed cost → solve → export
```

## Customize this template

### Use your own data

Replace the three CSVs in `data/` with your own:

- `sites.csv` — every site needs an `id`, `name`, `type` (one of the four canonical strings), and the role-specific quantitative columns. Set unused columns to 0.
- `lanes.csv` — every lane needs a `source_id`, `dest_id`, `cost_per_unit`, and `capacity`.
- `demand.csv` — every demand row needs a `site_id` matching a `CUSTOMER` site, plus a `quantity`.

### Tune parameters

- Add or remove fulfillment centers by changing `sites.csv` (rows with `fixed_cost > 0`).
- Change FC fixed costs to study the open-set sensitivity — lowering FC_West's fixed cost below ~$345 will swing the optimum to opening it.
- Add lane capacity constraints to force splitting flow across multiple paths.

### Extend the model

- **Multiple SKUs.** Add an SKU concept and key flows by `(Lane, SKU)`. Replace the simple `Lane.x_flow` with `Lane.x_flow(SKU, ...)` and update aggregations to be `.per(Lane, SKU)`.
- **Service-level constraints.** Replace the hard demand-satisfaction constraint with a soft one and a slack variable, and add a service-level threshold.
- **Multi-period planning.** Index `Lane.x_flow` by a time period concept and add inventory carry-over constraints between periods.

### Scale up / productionize

- For a live network, replace the three `data/` CSVs with `model.data(snowflake_table)` calls so the model reads sites, lanes, and demand directly from your warehouse tables.
- The bundled data is 12 sites and 17 lanes; the MILP scales to whatever fits the prescriptive engine's solve budget. If solves grow slow, tighten lane capacities to prune the flow space or size up the engine.
- The template solves with HiGHS by default (`problem.configure("highs", time_limit_sec=60)`); swap to `"gurobi"` for larger integer programs if a Gurobi-enabled engine is available.
- Pin `relationalai` (see Prerequisites) so runs stay reproducible across environments.

## Troubleshooting

<details>
  <summary>Why does the optimizer open FC_West sometimes but not others?</summary>

  The decision is sensitive to FC_West's fixed cost relative to the savings from its cheaper LA route. With the bundled data, the savings from routing 120 LA units through FC_West (vs. via FC_Northeast and FC_Southwest) are smaller than the $1,000 fixed cost. Lower FC_West's fixed cost or raise the cost of `FC_Northeast → Customer_LA` and the optimum will flip.
</details>

<details>
  <summary>Why does <code>Site.x_open</code> get only three variables?</summary>

  The `where=[Site.fixed_cost > 0]` clause restricts the variable to fulfillment-center sites. Warehouses, hubs, and customers all have `fixed_cost = 0` and don't need an open decision. The constraint linking capacity to `x_open` is similarly scoped to FC sites.
</details>

<details>
  <summary>I changed the data and now demand is unmet.</summary>

  The hard demand-satisfaction constraint will make the problem infeasible if total reachable supply (warehouse inventory routed through opened FCs) is less than aggregate customer demand at any site. Verify there's a feasible path with enough capacity from a warehouse to every customer site, possibly through multiple FCs.
</details>

<details>
  <summary>Why does the objective add two sums?</summary>

  The transport cost lives on `Lane` and the fixed cost on `Site`, so each is summed over its own concept and the two totals are added. A single `sum` over `model.union(...)` of both terms is refused: a union keeps one copy of equal values, while the solver needs every lane's and every site's term.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` and `sum(...).per(...)`.
- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API: decision variables (`solve_for`), constraints (`satisfy`), and objectives (`minimize` / `maximize`).

### Language / modeling reference

- [Concepts and properties](https://docs.relational.ai/) — modeling multiple roles on one concept via a typed property, as `Site.type` does here.
- [Relationships](https://docs.relational.ai/) — directed links like `Lane.source` / `Lane.dest` and `Demand.site`.

### Deeper dives

- [Solver selection and diagnostics](https://docs.relational.ai/) — choosing HiGHS vs. Gurobi, reading termination status, and diagnosing infeasibility.

## Support

- File issues at the RelationalAI templates repository.

## Related templates

- [`factory_production`](../factory_production/) — simpler single-site LP (no facility-open decision)
- [`production_planning`](../production_planning/) — multi-machine assignment with integer decisions
- [`supply_chain_transport`](../supply_chain_transport/) — TL/LTL piecewise transport-mode selection (a different MILP shape)
- [`supply_chain_resilience`](../supply_chain_resilience/) — multi-reasoner: graph + rules + prescriptive on supply-chain risk
- [`warehouse_allocation`](../warehouse_allocation/) — graph centrality feeding a downstream prescriptive allocation
