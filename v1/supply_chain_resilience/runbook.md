# Runbook: Supply Chain Resilience — Multi-Reasoner Walkthrough

Two HIGH-priority customers depend on a network of upstream suppliers, some of which are unreliable or delay-prone. A planner needs a risk-adjusted routing plan: the minimum-cost way to fulfill all open demand while steering flow away from risky suppliers and bottleneck hubs, plus an estimate of how much a disruption would cost. The chain produces that plan and prices two disruption scenarios against it. The dataset has 7 concepts — 31 sites, 31 businesses, 9 SKUs, 70 operations, 20 demand orders, 262 shipments, and 36 quarterly delay predictions.

This is traced across four RAI reasoning stages. Each stage writes properties back to the same ontology that downstream stages consume, so the optimizer can hard-block bad suppliers, surcharge watch suppliers, and weight bottleneck hubs using upstream graph and rules signals.

## The chain

```
Two HIGH-priority customers depend on 6 upstream suppliers — one of which
(PowerCell, B003) is flagged "watch" by rules. The chain produces a
$1,865 baseline plan, then quantifies disruption: top hub offline = +88.5%,
watch->avoid downgrade = +0.0% (optimizer already routed around it).

  ─────────────────────────────────────────────────────────────────
  STAGE 0  Reachability ──►  Business.is_high_priority_customer (2)
                              Upstream supplier dependency map for
                              each HIGH-priority customer (B008, B009).
  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Site.centrality  (normalized)
                              Top hubs: S004 TechAssembly 1.000,
                              S006 West Coast DC 0.776, S003 PowerCell 0.735.
                              2 weakly-connected components.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Business.is_unreliable           (1)
                              Business.has_high_delay_risk    (2)
                              Business.is_watch_level         (2)
                              Demand.is_escalated             (9)
                              [X] B017 avoid · [!] B003 watch
                              37 of 262 shipments late (14%).
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Operation.x_flow / Demand.x_unmet
                              OPTIMAL · $1,865 · 8 active flows · 0 unmet
                              + 2 scenario re-solves (S004 offline, watch->avoid)
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a supply chain ontology from the CSVs in data/. It should have a Site (a physical location with a region), a Business (a supplier, manufacturer, warehouse, or buyer, each at a site, with a reliability score), a SKU, an Operation (a shipping lane between two sites carrying a SKU at a per-unit cost — model it as the network edge the optimizer will route flow over), a Demand order (a quantity of a SKU requested by a business, with a priority), a Shipment (a historical movement with an on-time/late flag), and a quarterly DelayPrediction per supplier. Wire Operations between their origin and destination Sites so the shipment graph can be traced, and link Demand and Shipment back to their Business and SKU.
```

**Response**

Concepts: `Site`, `Business`, `SKU`, `Operation`, `Demand`, `Shipment`, `DelayPrediction` — bound to the bundled CSVs (31 sites, 31 businesses, 9 SKUs, 70 operations, 20 demands, 262 shipments, 36 delay predictions).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

7 concepts: 31 `Site` (APAC / AMERICAS / EMEA), 31 `Business` (suppliers / manufacturers / warehouses / buyers), 9 `SKU`, 70 `Operation`, 20 `Demand` (9 HIGH-priority), 262 `Shipment` (37 late, 14%), 36 quarterly `DelayPrediction`.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We need a risk-adjusted routing plan. What's our exposure to each supplier, which sites are bottlenecks, which suppliers are unreliable, what does the minimum-cost flow look like once those risks are priced in, and how robust is that plan to disruptions?
```

**Response**

Reasoner-routing plan: (1) Graph reachability for upstream supplier exposure, (2) Graph centrality for hub identification, (3) Rules for supplier reliability classification, (4) Prescriptive MILP for risk-adjusted flow, (5) Scenario re-solves for disruption quantification.

### 4. Map upstream supplier exposure

**Prompt**

```
/rai-graph-analysis Which suppliers do our HIGH-priority customers transitively depend on through the shipment graph, and what are those suppliers' reliability scores?
```

**Response**

`Business.is_high_priority_customer` (2 buyers: B008 MegaCorp Enterprise, B009 TechGiant Inc); each transitively depends on the same 6 SUPPLIER-typed upstream nodes (B015, B016, B017, B018, B019, B020).

### 5. Rank network hubs

**Prompt**

```
/rai-graph-analysis Which sites are the most influential hubs in the supply network — sites that connect to other influential sites, not just sites with many direct connections? Build the graph from SHIP-type operations (undirected). Persist the centrality score, normalized to [0,1] by dividing by the max, back to each site as Site.centrality so the optimizer can use it as a bottleneck weight.
```

**Response**

`Site.centrality` normalized [0,1]: S004=1.000, S006=0.776, S003=0.735; 2 weakly-connected components.

### 6. Classify supplier reliability

**Prompt**

```
/rai-rules-authoring Which suppliers are unreliable (reliability score below 0.80) or high-delay-risk (Q1 delay prediction above 0.15), and how should we tier them — 'avoid' (both flags fire), 'watch' (either flag fires), or 'reliable' (neither)? Also flag any HIGH-priority demand orders as escalated so downstream solves can prioritize them.
```

**Response**

`is_unreliable` (1: B017), `has_high_delay_risk` (2: B003, B017), `is_watch_level` (2), `Demand.is_escalated` (9).

### 7. Solve risk-adjusted flow

**Prompt**

```
/rai-prescriptive-problem-formulation What's the minimum-cost shipping plan that fulfills all open demand, hard-blocks 'avoid' suppliers (x_flow == 0), adds a $5/unit surcharge on 'watch' suppliers, weights each unit of flow into a destination site by 2.0 × that site's centrality (so flow into high-centrality hubs costs more), and penalizes unmet demand at $100/unit?
```

**Response**

OPTIMAL · $1,865 · 8 active flows · 0 unmet. MILP on `Operation.x_flow` + `Demand.x_unmet`; objective = transport + risk surcharge + centrality weight + unmet penalty.

### 8. Quantify disruption scenarios

**Prompt**

```
/rai-prescriptive-solver-management + /rai-prescriptive-results-interpretation Re-solve with the highest-centrality site offline, and again with watch-level suppliers downgraded to avoid. What's the cost delta in each, and why are they asymmetric?
```

**Response**

Baseline OPTIMAL $1,865 / 8 flows / 0 unmet; S004 offline +88.5%; watch->avoid +0.0% (B003 already off optimal lanes).

### 9. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology-design Add a RoutingScenario concept that materializes each scenario solve (Baseline, S004-offline, Watch->Avoid) with its status, total cost, cost delta versus baseline, active flow count, unmet total, and any blocked businesses.
```

**Response**

Ontology gains a `RoutingScenario` Concept (3 rows: Baseline, S004-offline, Watch-Avoid) with `status`, `total_cost`, `cost_delta_pct`, `active_flow_count`, `unmet_total`, `blocked_businesses`. The disruption deltas — Baseline $1,865 / 8 flows / 0 unmet, S004-offline +88.5%, Watch->Avoid +0.0% — are queryable as ontology rather than scenario-comparison stdout.

## Data

Bundled CSVs in `data/`: 31 sites (APAC/AMERICAS/EMEA), 31 businesses, 9 SKUs, 70 operations, 20 demand orders, 262 shipments (37 late), 36 quarterly delay predictions. Combined script with stage banners: `supply_chain_resilience.py`.
