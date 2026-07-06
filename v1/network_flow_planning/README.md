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

- `network_flow_planning.py` — main script (single end-to-end run)
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/sites.csv` — 12 sites: 3 warehouses, 3 transit hubs, 3 fulfillment centers, 3 customers
- `data/lanes.csv` — 17 directed lanes connecting the tiers, each with a cost-per-unit and capacity
- `data/demand.csv` — 3 customer demands (NYC 180, LA 120, Houston 150)
- `pyproject.toml` — Python package configuration with dependencies

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.11.0

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/network_flow_planning.zip
   unzip network_flow_planning.zip
   cd network_flow_planning
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure Snowflake connection and RAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python network_flow_planning.py
   ```

6. Expected output (truncated):

   ```text
   Status: OPTIMAL
   Total cost: $5,280.00
   Opened fulfillment centers:
     fulfillment_center  capacity  fixed_cost
          FC_Northeast     350.0      1500.0
          FC_Southwest     200.0      1200.0
   Active flows:
              from_site           to_site   flow  unit_cost
      Chicago_Warehouse       Memphis_Hub  200.0        2.0
       Dallas_Warehouse    KansasCity_Hub  250.0        2.5
            Memphis_Hub      FC_Northeast  200.0        1.5
         KansasCity_Hub      FC_Northeast   50.0        2.0
         KansasCity_Hub      FC_Southwest  200.0        1.5
           FC_Northeast      Customer_NYC  180.0        1.0
           FC_Northeast       Customer_LA   70.0        5.0
           FC_Southwest  Customer_Houston  150.0        1.0
           FC_Southwest       Customer_LA   50.0        3.5
   ```

   The optimizer opens the two largest fulfillment centers and routes LA's demand split across both — the savings from not opening FC_West ($1,000 fixed) outweigh the extra transport cost incurred by routing 120 units of LA demand through the more expensive FC_Northeast and FC_Southwest paths.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── network_flow_planning.py        # main script (end-to-end)
└── data/
    ├── sites.csv                   # 12 sites across 4 types
    ├── lanes.csv                   # 17 directed transport lanes
    └── demand.csv                  # 3 customer demands
```

**Start here:** run `python network_flow_planning.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

- **Key entities**: `Site`, `Lane`, `Demand`.
- **Primary identifiers**: integer `id` on each of `Site`, `Lane`, and `Demand`, loaded from the corresponding CSV.
- **Important invariants**: `inventory`, `capacity`, `fixed_cost`, `cost_per_unit`, and `quantity` are non-negative; only fulfillment centers carry a positive `fixed_cost` (that is what scopes the binary open decision); every `Lane.source` / `Lane.dest` and every `Demand.site` resolves to a real `Site`.

For the full concept and property definitions, see `network_flow_planning.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model runs as a single MILP that decides flow on every lane and which fulfillment centers to open, in one solve.

**Decision variables.** Each lane carries a continuous `x_flow` bounded by its capacity. Each fulfillment center carries a binary `x_open`; the open decision is scoped to sites with a positive `fixed_cost`, so warehouses, hubs, and customers never get an open variable.

**Constraints.** Each site type contributes the constraint that matches its role. Warehouses cap total outflow at their inventory. Transit hubs and fulfillment centers conserve flow — inflow equals outflow. A fulfillment center's inflow is bounded by `capacity × x_open`, so an unopened FC (open = 0) can carry no flow and the fixed cost is only incurred when it is opened. Customers require inflow to meet their aggregate demand.

**Objective.** Minimize transport cost (per-unit lane cost times flow, summed over lanes) plus the fixed cost of every opened fulfillment center. The two cost terms live on different concepts (`Lane` and `Site`), so they are combined into one per-entity sum that the objective minimizes.

For the exact PyRel formulation, see `network_flow_planning.py`; `runbook.md` reproduces the model step by step with the RAI skills.

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
- The template solves with HiGHS by default (`problem.solve("highs")`); swap to `"gurobi"` for larger integer programs if a Gurobi-enabled engine is available.
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
  <summary>Why is <code>model.union</code> needed in the objective?</summary>

  PyRel disallows `+` between aggregated terms of different concepts. `model.union` lets the outer `sum` aggregate per-Lane and per-Site cost terms in a single objective. Each branch must be a per-entity expression, not a fully-aggregated scalar.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, `sum(...).per(...)`, and `model.union` for multi-concept objectives.
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
