# Runbook: Warehouse Allocation — Multi-Reasoner Walkthrough

A distribution network must spread a fixed inventory budget of 2,000 units across 10 sites at minimum holding cost — while meeting every site's demand and making sure structurally important hub warehouses carry buffer stock proportional to how central they are in the route network. No single reasoner answers this: a graph reasoner scores each site's network importance, and that score becomes a hard floor in the allocation optimizer.

## The chain

```
10 sites (5 warehouses, 5 stores) on a 14-route network must hold ≤ 2,000 units.
The chain scores each site's network centrality, then allocates inventory so hub
warehouses carry centrality-proportional buffer stock — OPTIMAL at $13,713.29 holding cost.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Site.centrality                  (10)
                 (eigenvector/  Chicago_Hub 0.6314, Detroit 0.5116,
                  WCC/rule)     Dallas 0.3507 lead; stores all < 0.19.
                              1 connected component (unified network);
                              Route.is_cross_region flags 6 bridges.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Prescriptive ──►  Site.x_inventory                 (10)
                              Min holding cost s.t. demand + warehouse
                              floor = centrality × 200. OPTIMAL,
                              $13,713.29, ~951 units placed (budget slack).
                              The 4 hub centrality floors bind.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build an ontology from data/sites.csv (each site has a region, a type — warehouse or store — and a per-unit holding cost), data/routes.csv (each route links a source site to a destination site with a capacity and a transport cost), and data/demands.csv (each demand is a quantity at a site). Model the route as a relationship between sites.
```

**Response**

Loads `Site` (10: 5 warehouses, 5 stores, each with `region`, `type`, `holding_cost`), `Route` (14, with `capacity` and `transport_cost`), and `Demand` (8, total 710 units of demand across the stores plus some warehouses).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

Three concepts — 10 `Site`, 14 `Route` (source-to-destination, with capacity), and 8 `Demand` — forming a distribution network across four regions (Midwest, South, West, East).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We need to hold at most 2,000 units across 10 sites at minimum holding cost, meet every site's demand, and keep extra buffer stock at the warehouses that matter most to the network. How should we break this down?
```

**Response**

Routes to a graph step (score each site's structural importance in the route network and check the network is connected) feeding a prescriptive step (allocate inventory under a budget, demand floors, and centrality-proportional warehouse floors).

### 4. Score site centrality

**Prompt**

```
/rai-graph-analysis Which sites are the most structurally important in the route network — where a site is important if it's well-connected to other important sites — using the route capacities as edge weights? Persist each site's score as Site.centrality. Also confirm the network is a single connected component, and flag the routes that cross between regions.
```

**Response**

Eigenvector centrality (the "important neighbors make you important" measure) ranks **Chicago_Hub 0.6314, Detroit_DC 0.5116, Dallas_Hub 0.3507, Atlanta_DC 0.3214, Denver_DC 0.2127** at the top — all warehouses — while every store scores below 0.19. The network is a **single connected component**, and **6 routes are flagged cross-region** (`Route.is_cross_region`). `Site.centrality` is written back for the optimizer to read.

### 5. Allocate inventory

**Prompt**

```
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Allocate a non-negative number of units to each site to minimize total holding cost (units times each site's holding cost), keeping total units within the 2,000-unit budget, meeting every site's demand, and requiring each warehouse to hold at least its centrality score times 200 as buffer stock. Persist the allocation as Site.x_inventory.
```

**Response**

OPTIMAL (HiGHS), total holding cost **$13,713.29**. 10 continuous allocation variables, 14 constraints (1 budget cap, 8 demand floors, 5 warehouse centrality floors); `Site.x_inventory` written back.

### 6. Read the allocation

**Prompt**

```
/rai-prescriptive-results-interpretation How much inventory does each site hold, which constraints bind, and is the budget the limiting factor?
```

**Response**

About **951 of the 2,000 units** are placed, so the **budget is slack** — it isn't the binding limit. The **four hub warehouse centrality floors bind** (Chicago ~126, Detroit ~102, Dallas ~70, Denver ~43 units), pushing buffer stock above what demand alone needs; the stores each sit at exactly their demand (LA 120, NYC 150, Miami 100, Phoenix 90, Seattle 80). Atlanta holds 70 — its demand floor edges out its slightly lower centrality floor. The `Site.centrality` scores from the graph step, not the budget, shape where inventory concentrates.

## Data

Bundled CSVs in `data/`: 10 sites, 14 routes, 8 demands; inventory budget (2,000) and the centrality-to-floor multiplier (200) are constants in the script. Full chain in `warehouse_allocation.py`.
