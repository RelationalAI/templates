# Water Allocation — Analyst Runbook

A water utility wants to meet every user group's demand at minimum sourcing cost across a distribution network where pushing more water through a connection loses more of it to transmission. The dataset is 3 supply sources (each with a capacity and a per-unit extraction cost), 3 user groups (each with a demand), and 9 network connections (each with a max flow rate and a utilization-dependent loss rate). The realistic twist — loss that grows with how hard a connection is pushed — makes the demand constraints quadratic, so the analysis solves a nonlinear program.

```text
3 sources (capacity, cost) · 3 users (demand) · 9 connections (max flow, loss rate)
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decision: continuous flow per connection, 0 ≤ flow ≤ max flow
   • constraints: outflow per source ≤ capacity; effective inflow per user ≥ demand
     where delivered = flow x (1 − loss_rate x flow / max_flow)  (nonlinear)
   • objective: minimize total sourcing cost = sum(flow x source cost)
   • Ipopt nonlinear program                     -> LOCALLY_SOLVED, $853.39
      │
      ▼
/rai-prescriptive-results-interpretation
   • 6 of 9 connections carry flow; the expensive Groundwater source is unused
   • Reservoir_A is pushed to its Municipal connection cap (400, binding)
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Source`/`User`/`Connection` concepts the build step created, and the interpret step reads the `Connection.x_flow` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/sources.csv` (each source has a capacity and a per-unit extraction cost), `data/users.csv` (each user has a demand), and `data/connections.csv` (each connection links a source to a user with a max flow rate and a loss rate). Model the connection as a relationship between a source and a user carrying its max-flow and loss-rate properties.

**Response:** Loads `Source` (3: Reservoir_A capacity 1000 / cost 0.5, Reservoir_B 800 / 0.6, Groundwater 500 / 0.8), `User` (3: Municipal demand 600, Industrial 400, Agricultural 500 — total 1500), and `Connection` (9, fully connected, each with `max_flow` and `loss_rate`).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 3 `Source` (capacity, cost), 3 `User` (demand), and 9 `Connection` (every source-to-user pair, with `max_flow` and `loss_rate`) — total demand 1500 against 2300 of total source capacity.

## 3. Minimize sourcing cost with transmission loss

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management What non-negative flow on each connection meets every user's demand at minimum total sourcing cost, given that each source's total outflow can't exceed its capacity and that transmission loss grows with utilization — the water delivered on a connection is flow times (1 minus loss_rate times flow over max_flow)? That delivered-water term is quadratic, so this needs a nonlinear solver. Persist the chosen flows to the ontology.

**Response:** LOCALLY_SOLVED (Ipopt nonlinear solver), total cost **$853.39**. 9 continuous flow variables (each bounded by its connection's max flow), 6 constraints (3 source-capacity, 3 nonlinear demand-satisfaction). Flows are written back as `Connection.x_flow`.

## 4. Read the allocation

**Prompt:** /rai-prescriptive-results-interpretation Which connections carry water and how much, and what does the plan reveal about the cheapest sourcing strategy?

**Response:** 6 of the 9 connections carry flow; all three **Groundwater** connections are zero — the solver avoids the most expensive source entirely and serves the network from the two cheaper reservoirs. Reservoir_A is pushed to its Municipal connection's max-flow cap (400.0, binding) and also supplies Agricultural and Industrial; Reservoir_B covers the remainder (Municipal 229, Agricultural 182, Industrial 178). Demand is met everywhere at $853.39.

## Data

Bundled CSVs in `data/`: 3 sources with capacity and cost, 3 users with demand, 9 connections with max-flow and loss-rate. Full model in `water_allocation.py`.
