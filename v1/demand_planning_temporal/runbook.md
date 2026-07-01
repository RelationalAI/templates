# Demand Planning (Temporal) — Analyst Runbook

A supply planner wants a least-cost, multi-week production-and-inventory plan: how much of each SKU to make at each site in each week to meet customer orders while honoring capacity, a service level, and safety stock. The dataset is 3 sites, 3 SKUs, 25 dated demand orders, and per-site-SKU production capacity and opening inventory. The analysis builds the weekly time grid, formulates a multi-period flow problem with inventory carryover, and sweeps three planning horizons (end-of-January, February, March) to show how cost grows as more weeks and orders come into scope.

```text
3 sites · 3 SKUs · 25 dated demand orders · per-site-SKU capacity + opening inventory
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decision: weekly production, end-of-week inventory, and unmet demand (all continuous ≥ 0)
   • constraints: inventory flow (inv[t] = inv[t-1] + production − demand); capacity;
     95% service level; safety stock ≥ 1 week of average demand
   • objective: minimize production + holding + unmet-demand penalty
   • horizons ending Jan / Feb / Mar in a scenario sweep  -> OPTIMAL all three; cost is pure holding, rising with horizon
      │
      ▼
/rai-prescriptive-results-interpretation
   • all demand met (0 unmet) in every horizon; cost rises with the horizon length
   • the abundant opening inventory covers demand — zero production, cost is pure holding
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Site`/`SKU`/`DemandOrder`/`ProdCapacity` concepts the build step created, and the interpret step reads the production, inventory, and unmet-demand decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/sites.csv` (each site has a weekly capacity), `data/skus.csv` (each SKU has a unit cost and a weekly holding cost), `data/demand_orders.csv` (each order is a quantity of one SKU due at one site on a due date), `data/production_capacity.csv` (max production per week and production cost for each site-SKU pair), and `data/initial_inventory.csv` (opening inventory per site-SKU). Link orders and capacities to their site and SKU.

**Response:** Loads `Site` (3: Chicago_DC, Atlanta_DC, Dallas_DC, each with `capacity_per_week`), `SKU` (3: Widget_A, Widget_B, Gadget_C, with `unit_cost` and `holding_cost_per_week`), `DemandOrder` (25, with `quantity` and `due_date`, linked to site and SKU), and `ProdCapacity` (9 site-SKU pairs, with `max_production_per_week`, `production_cost`, and opening inventory).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Four concepts — 3 `Site`, 3 `SKU`, 25 `DemandOrder` (linked to site and SKU), and 9 `ProdCapacity` (one per site-SKU pair, carrying capacity, production cost, and opening inventory). The orders span October 2025 through March 2026.

## 3. Build the least-cost multi-week plan across horizons

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Map each order's due date to a week and build a weekly time grid, then decide weekly production, end-of-week inventory, and any unmet demand per site-SKU (all non-negative). Inventory must carry over week to week — end-of-week inventory equals last week's inventory plus this week's production minus this week's demand, starting from opening inventory — weekly production can't exceed capacity, at least 95% of total demand must be met, and end-of-week inventory must stay above one week of average demand (safety stock). Minimize total cost — production plus holding plus a penalty on unmet demand. Solve three planning horizons in a scenario sweep — ending 2026-01-31, 2026-02-28, and 2026-03-31 — and persist the decisions to the ontology.

**Response:** OPTIMAL in all three horizons (HiGHS). Total cost **rises with the horizon** — a longer plan carries the same inventory for more weeks and pulls in more orders, so more holding cost accrues. (The absolute dollar totals depend on the planning-start date and how the weekly grid is anchored, so the reproducible result is the upward trend across horizons, not a specific figure.) Production, inventory, and unmet decisions are written back as `ProdCapacity.x_production`, `ProdCapacity.x_inventory`, and `DemandOrder.x_unmet`.

## 4. Read the plan across horizons

**Prompt:** /rai-prescriptive-results-interpretation Is all demand met in each horizon, what drives the cost, and why does cost rise as the horizon extends?

**Response:** All demand is met in every horizon — **unmet demand is zero** throughout, so the service-level and safety-stock constraints hold with slack. With opening inventory abundant relative to in-scope demand, the optimal plan **produces nothing and draws demand down from inventory**, so total cost is essentially holding cost on carried stock. Extending the horizon from January to March pulls in more weeks and more orders, accumulating more holding cost — which is why cost climbs steadily across the three horizons.

## Data

Bundled CSVs in `data/`: 3 sites, 3 SKUs, 25 demand orders, 9 production-capacity rows, 9 opening-inventory rows. The three horizon end dates are constants in the script. Full model in `demand_planning_temporal.py`.
