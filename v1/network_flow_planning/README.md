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

# Network Flow Planning

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

**Start here:** `python network_flow_planning.py`.

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

### Site

A node in the distribution network. The `type` property distinguishes the role each site plays.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/sites.csv` |
| `name` | String | No | Human-readable name |
| `type` | String | No | One of `WAREHOUSE`, `HUB`, `FULFILLMENT_CENTER`, `CUSTOMER` |
| `inventory` | Float | No | Available supply (warehouses only; 0 elsewhere) |
| `capacity` | Float | No | Throughput cap (FCs only; 0 elsewhere) |
| `fixed_cost` | Float | No | Fixed cost when opened (FCs only; 0 elsewhere) |

### Lane

A directed transport link between two sites with a per-unit cost and a flow capacity.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/lanes.csv` |
| `source` | Site | No | Origin site (Relationship) |
| `dest` | Site | No | Destination site (Relationship) |
| `cost_per_unit` | Float | No | Transport cost per unit of flow |
| `capacity` | Float | No | Maximum flow on this lane |

### Demand

A customer order placed at a particular site.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/demand.csv` |
| `site` | Site | No | Customer site (Relationship) |
| `quantity` | Float | No | Units required |
| `customer` | String | No | Order identifier (free text) |
| `priority` | Integer | No | Priority tier (not used by the model in this version) |

## How it works

### 1. Decision variables

Two variables drive the model:

```python
Lane.x_flow = model.Property(f"{Lane} carries {Float:flow}")
Site.x_open = model.Property(f"{Site} is open {Float:open}")

problem.solve_for(
    Lane.x_flow,
    lower=0,
    upper=Lane.capacity,
    name=["flow", Lane.id],
)

problem.solve_for(
    Site.x_open,
    type="bin",
    name=["open", Site.name],
    where=[Site.fixed_cost > 0],
)
```

The `where=[Site.fixed_cost > 0]` clause restricts the binary `x_open` to fulfillment centers only — warehouses, hubs, and customers don't get open-decision variables.

### 2. Constraints

Each site type contributes the constraint that matches its role.

**Source supply** at warehouses:

```python
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.inventory > 0,
).require(
    sum(out_lane.x_flow).where(out_lane.source == Site).per(Site) <= Site.inventory
))
```

**Flow conservation** at hubs and fulfillment centers (one per type):

```python
in_lane = Lane.ref()
out_lane = Lane.ref()
problem.satisfy(model.where(
    Site.type == "HUB",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    == sum(out_lane.x_flow).where(out_lane.source == Site).per(Site)
))
```

**FC capacity gated by open decision**:

```python
in_lane = Lane.ref()
problem.satisfy(model.where(
    Site.fixed_cost > 0,
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    <= Site.capacity * Site.x_open
))
```

**Demand satisfaction** at customers:

```python
in_lane = Lane.ref()
demand_ref = Demand.ref()
problem.satisfy(model.where(
    Site.type == "CUSTOMER",
).require(
    sum(in_lane.x_flow).where(in_lane.dest == Site).per(Site)
    >= sum(demand_ref.quantity).where(demand_ref.site == Site).per(Site)
))
```

### 3. Objective

The combined objective uses `model.union` so PyRel can sum two per-entity expressions of different concepts in one minimize call:

```python
problem.minimize(sum(model.union(
    Lane.cost_per_unit * Lane.x_flow,
    Site.fixed_cost * Site.x_open,
)))
```

Each branch is a per-entity expression (per `Lane` and per `Site`), aggregated by the outer `sum`.

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

## Related templates

- [`factory_production`](../factory_production/) — simpler single-site LP (no facility-open decision)
- [`production_planning`](../production_planning/) — multi-machine assignment with integer decisions
- [`supply_chain_transport`](../supply_chain_transport/) — TL/LTL piecewise transport-mode selection (a different MILP shape)
- [`supply_chain_resilience`](../supply_chain_resilience/) — multi-reasoner: graph + rules + prescriptive on supply-chain risk
- [`warehouse_allocation`](../warehouse_allocation/) — graph centrality feeding a downstream prescriptive allocation
