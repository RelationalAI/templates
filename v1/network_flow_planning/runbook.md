# Network Flow Planning — Analyst Runbook

A logistics planner has to make two coupled decisions at once: which fulfillment centers (each with a fixed opening cost) to open, and how much product to ship on every lane of a four-tier distribution network (warehouses → hubs → fulfillment centers → customers) to meet demand. Routing flow alone is a continuous problem, but choosing which centers to open is combinatorial — and the cheapest open-set depends on the routing. The dataset is 12 sites, 17 directed lanes, and 3 customer demands. The analysis solves both decisions jointly as one mixed-integer program minimizing transport cost plus fixed opening cost.

```text
12 sites (4 tiers, FCs carry fixed costs) · 17 directed lanes (cost, capacity) · 3 customer demands (450 total)
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: continuous flow per lane + binary "open this fulfillment center?"
   • constraints: warehouse supply; flow conservation at hubs and FCs;
     FC inflow ≤ capacity only if opened; customer demand met
   • objective: minimize sum(lane cost x flow) + sum(FC fixed cost x open)
   • HiGHS mixed-integer program                 -> OPTIMAL, $5,280
      │
      ▼
/rai-prescriptive-results-interpretation
   • open FC_Northeast + FC_Southwest; FC_West stays closed
   • skipping FC_West saves its $1,000 fixed cost — worth more than the route it would unlock
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Site`/`Lane`/`Demand` concepts the build step created, and the interpret step reads the `Lane.x_flow` and `Site.x_open` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/sites.csv` (each site has a type — warehouse, hub, fulfillment center, or customer — plus inventory, capacity, and a fixed cost), `data/lanes.csv` (each directed lane links a source site to a destination site with a per-unit cost and a capacity), and `data/demand.csv` (each customer site has a demand quantity). Model the lane as a relationship between a source and a destination site.

**Response:** Loads `Site` (12: 3 warehouses, 3 hubs, 3 fulfillment centers with fixed costs, 3 customers), `Lane` (17 directed links, each with `cost_per_unit` and `capacity`), and `Demand` (3: NYC 180, LA 120, Houston 150 — 450 total).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 12 `Site` (typed across four tiers, fulfillment centers carrying `capacity` and `fixed_cost`), 17 `Lane` (directed, with `cost_per_unit` and `capacity`), and 3 `Demand` (one per customer, 450 units total) — forming a warehouse-to-hub-to-FC-to-customer flow network.

## 3. Open centers and route flow at minimum cost

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Which fulfillment centers should we open, and how much should we ship on each lane, to meet every customer's demand at minimum total cost? Use a continuous flow per lane (bounded by its capacity) and a binary open decision per fulfillment center. Warehouse outflow can't exceed inventory, flow must balance at each hub and center, a center can only receive flow if it's open (inflow up to its capacity), and each customer's inflow must meet its demand. Minimize total transport cost plus fixed opening cost, and persist both decisions to the ontology.

**Response:** OPTIMAL (HiGHS), total cost **$5,280** (relative gap 0.0). 20 variables (17 continuous lane flows + 3 binary open decisions) and 15 constraints; flows and open decisions are written back as `Lane.x_flow` and `Site.x_open`.

## 4. Read the network plan

**Prompt:** /rai-prescriptive-results-interpretation Which centers open, how does product flow to each customer, and why is one center left closed?

**Response:** The plan opens **FC_Northeast and FC_Southwest** and leaves **FC_West closed** — its $1,000 fixed cost outweighs the cheaper LA route it would unlock, so LA's 120 units are split across the two open centers instead (70 from Northeast, 50 from Southwest). Nine lanes carry flow: warehouses feed the Memphis and Kansas City hubs, which feed the two open centers, which serve NYC (180), Houston (150), and the split LA demand. Total cost $5,280 — the open/closed trade-off, not lane capacity, is what shapes the plan.

## Data

Bundled CSVs in `data/`: 12 sites, 17 lanes, 3 demands. Full model in `network_flow_planning.py`.
