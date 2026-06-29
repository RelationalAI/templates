# Humanitarian Aid Supply Chain — Analyst Runbook

When a crisis hits, response coordinators have to route aid through a network of distribution points fast, and they need to know two different things: where aid naturally concentrates as it flows through the network, and which points are the most-connected coordination hubs. The dataset is 18 distribution points and 28 supply routes, forming a directed graph weighted by each route's throughput (capacity times reliability, divided by distance). The analysis runs two complementary centrality algorithms and combines them into strategic categories.

```text
18 distribution points (type, region, capacity, population) · 28 supply routes (directed, weighted = capacity x reliability / distance)
      │
      ▼
/rai-graph-analysis
   • PageRank (influence flowing along routes)   -> Emergency Field Hospital (0.1097): where aid concentrates
   • weighted degree centrality (connectivity)   -> Central Warehouse (9 routes): top coordination hub
   • combine on 70th-percentile thresholds       -> 2 critical hubs · 4 influential endpoints · 4 connectors
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the graph steps read the `DistributionPoint`/`SupplyRoute` graph the build step created.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/distribution_points.csv` (each point has a type, a region, a capacity, and a population served) and `data/supply_routes.csv` (each directed route links two points and has a route capacity, a reliability score, and a distance). Derive a route flow weight as route capacity times reliability divided by distance, and model the route as a directed relationship from one point to another carrying that flow weight.

**Response:** Loads `DistributionPoint` (18, with `type`, `region`, `capacity`, `population_served`) and `SupplyRoute` (28 directed routes, each with `route_capacity`, `reliability_score`, `distance_km`, and a derived `flow_weight`) — a directed, flow-weighted supply network serving 152,000 people.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** One node concept, `DistributionPoint` (18), connected by `SupplyRoute` (28 directed, flow-weighted edges) — about 3.1 routes per point, total network capacity ~64,600 units.

## 3. Rank points by influence and by connectivity

**Prompt:** /rai-graph-analysis Two questions on the flow-weighted route graph: first, where does aid concentrate when influence flows along the routes — the points that many high-flow routes ultimately feed into (PageRank)? Second, which points are the most-connected coordination hubs — the highest total weighted connections (weighted degree centrality)? Report the top points by each.

**Response:** The two metrics rank different nodes, which is the point. By **PageRank** (where aid concentrates), the top point is the **Emergency Field Hospital (0.1097)**, followed by Remote Highland Camp and Central Warehouse. By **weighted degree centrality** (raw connectivity), the top is the **Central Warehouse (46.75, 9 routes)** — the busiest transshipment hub. Influence and connectivity are not the same: a field hospital absorbs flow without being highly connected, while the warehouse is a connector that routes aid onward.

## 4. Classify points strategically

**Prompt:** /rai-graph-analysis Combine the two metrics into strategic categories using a high/low cutoff at roughly the top 30% (70th percentile) of each: critical coordination hubs (high on both), influential endpoints (high influence but lower connectivity), and network connectors (high connectivity but lower influence). Which points fall in each?

**Response:** **2 critical coordination hubs** — Emergency Field Hospital and Central Warehouse (high on both metrics), the points to harden and add redundancy around first. **4 influential endpoints** (high PageRank, lower connectivity) such as Remote Highland Camp and Food Distribution Point West — demand sinks where aid pools. **4 network connectors** (high connectivity, lower influence) such as the International Airport Hub and NGO Coordination Hub — throughput routers whose loss would fragment the network. The split tells coordinators where to add capacity (hubs), pre-position stock (endpoints), and build backup routes (connectors).

## Data

Bundled CSVs in `data/`: 18 distribution points, 28 supply routes. Entry point `humanitarian_aid_supply_chain.py` (shared model in `model_setup.py`; `app.py` is an optional Streamlit UI).
