# Runbook: Supply Chain Resilience — Multi-Reasoner Walkthrough

Risk-adjusted network flow with disruption scenarios, traced across four RAI reasoning stages. Each stage writes properties back to the same ontology that downstream stages consume, so the optimizer can hard-block bad suppliers, surcharge watch suppliers, and weight bottleneck hubs using upstream graph and rules signals.

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

### 0. Discovery

- Prompt: `/rai-discovery We need a risk-adjusted routing plan. What's our exposure to each supplier, which sites are bottlenecks, which suppliers are unreliable, and what does the minimum-cost flow look like once those risks are priced in?`
- Response: Reasoner-routing plan covering Stages 0–3 (graph, rules, prescriptive).

### 1. Map upstream supplier exposure

- Prompt: `/rai-graph-analysis If a key supplier goes offline, which downstream buyers and finished products are at risk? For each HIGH-priority customer, list the suppliers it transitively depends on through the shipment graph, with their reliability scores.`
- Response: `Business.is_high_priority_customer` (2 buyers: B008, B009); shared 6-supplier upstream cone.

### 2. Rank network hubs

- Prompt: `/rai-graph-analysis Which sites are the most influential hubs in the supply network — sites that connect to other influential sites, not just sites with many direct connections? Persist the centrality score back to each site so the optimizer can use it as a bottleneck weight.`
- Response: `Site.centrality` normalized [0,1]: S004=1.000, S006=0.776, S003=0.735; 2 weakly-connected components.

### 3. Classify supplier reliability

- Prompt: `/rai-rules-authoring Rate each supplier's delivery reliability. Flag any with reliability score below 0.80 as unreliable, any with a Q1 delay prediction above 0.15 as high-delay-risk, and call them 'watch-level' if either fires. Suppliers with **both** flags are 'avoid' (hard-blocked downstream); suppliers with **either** flag are 'watch' (surcharged).`
- Response: `is_unreliable` (1: B017), `has_high_delay_risk` (2: B003, B017), `is_watch_level` (2), `Demand.is_escalated` (9).

### 4. Solve risk-adjusted flow

- Prompt: `/rai-prescriptive-problem-formulation Solve a minimum-cost flow that fulfills all open demand orders at minimum total transport cost. Hard-block 'avoid' suppliers, surcharge 'watch' suppliers $5/unit, weight bottleneck sites by their centrality, and penalize unmet demand at $100/unit.`
- Response: MILP on `Operation.x_flow` + `Demand.x_unmet`; objective = transport + risk surcharge + centrality weight + unmet penalty.

### 5. Quantify disruption scenarios

- Prompt: `/rai-prescriptive-solver-management + /rai-prescriptive-results-interpretation Re-solve with the highest-centrality site offline, and again with watch-level suppliers downgraded to avoid. What's the cost delta in each, and why are they asymmetric?`
- Response: Baseline OPTIMAL $1,865 / 8 flows / 0 unmet; S004 offline +88.5%; watch->avoid +0.0% (B003 already off optimal lanes).

## Data

Bundled CSVs in `../data/`: 31 sites (APAC/AMERICAS/EMEA), 31 businesses, 9 SKUs, 70 operations, 20 demand orders, 262 shipments (37 late), 36 quarterly delay predictions. Combined script with stage banners: `../supply_chain_resilience.py`.
