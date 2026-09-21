# Supply Chain Transport — Analyst Runbook

A freight planner has to decide, for each shipment, *when* to ship, *how much*, and by *which mode* — truckload (TL), which charges a fixed cost per truck but is cheap at volume, or less-than-truckload (LTL), which is cheaper for small loads but rises in priced tiers. Freight waiting in the warehouse also accrues holding cost. The dataset is 2 freight groups (each with inventory, transport, and arrival day-windows and a starting weight), the two modes, and the LTL rate tiers. The analysis solves a mixed-integer program that schedules and routes all freight on time at least total cost.

```text
2 freight groups (day-windows, weight) · 2 modes (TL fixed-per-truck, LTL piecewise) · LTL rate tiers
      │
      ▼
/rai-prescriptive-problem
   • decisions: when/how much to ship, by which mode; daily inventory; arrival day
   • constraints: inventory flow & deadline windows; ship-all (all-or-nothing); TL truck capacity;
     LTL piecewise rate tiers; arrival = departure + transit time
   • objective: minimize inventory holding + TL fixed truck cost + LTL piecewise cost
   • HiGHS mixed-integer program                 -> OPTIMAL (script total $1,444)
      │
      ▼
/rai-prescriptive-results
   • both groups ship by LTL within their windows; zero TL trucks
   • each light load's LTL cost is far below the $2,000-per-truck fixed charge
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `FreightGroup`/`TransportType`/`LTLSegment` concepts the build step created, and the interpret step reads the shipment and inventory decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/freight_groups.csv` — each freight group has an inventory window, a transport window, an arrival window (each a start and end day), and a starting weight. Also model two transport types — truckload (transit 2 days, $2,000 per truck, 24,000 lb capacity) and less-than-truckload (transit 3 days) — and the LTL cost segments as a piecewise per-pound rate: up to 6,000 lb at $0.18/lb, then up to 7,000 lb at $0.12/lb. Inventory holding costs 0.1% of weight per day held.

**Response:** Loads `FreightGroup` (2: fg1 4,000 lb, fg2 5,000 lb, each with inventory/transport/arrival day-windows), `TransportType` (2: TL transit 2 days, LTL transit 3 days), and `LTLSegment` (2 piecewise tiers: up to 6,000 lb at $0.18/lb, then to 7,000 lb at $0.12/lb).

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 2 `FreightGroup` (day-windows and starting weight), 2 `TransportType` (TL, LTL with transit times), and 2 `LTLSegment` (the LTL piecewise rate tiers). TL costs $2,000 per truck (24,000 lb capacity); inventory holding is 0.1% of weight per day held.

## 3. Schedule and route the freight

**Prompt:** /rai-prescriptive-problem For each freight group, decide when to ship, how much, and by which mode to minimize total cost. Track daily warehouse inventory (it must start at the group's weight and reach zero by the end), ship each group all at once within its transport window, set arrival day as departure plus the mode's transit time within the arrival window, cap truckload weight at truck capacity per truck used, and price LTL across its piecewise weight tiers. Minimize inventory holding cost plus truckload fixed cost plus LTL cost, and persist the decisions to the ontology.

**Response:** OPTIMAL (HiGHS), total cost **$1,444** (relative gap 0.0). 62 variables (continuous quantities and inventory, integer arrival days, binary mode/segment choices) and 52 constraints; the inventory, shipment, and arrival decisions are written back across the `FreightGroup`, `TransportType`, and `LTLSegment` concepts.

## 4. Read the shipping plan

**Prompt:** /rai-prescriptive-results How does the optimal plan ship each group, and why does it pick that mode?

**Response:** The plan ships **both groups by LTL on day 2** (9,000 lb combined), each arriving on day 5, and uses **zero truckload trucks**. LTL consolidation wins here: the combined LTL cost of $1,444 undercuts the $2,000 fixed cost of even a single TL truck, so paying per-pound on LTL beats committing to truckload at these volumes.

## Data

Bundled CSV in `data/`: 2 freight groups with day-windows and weights. The transport modes and LTL rate tiers are defined in the script, along with TL cost/capacity and the holding rate. Full model in `supply_chain_transport.py`.
