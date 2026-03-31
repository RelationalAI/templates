# Recipe: Supply Chain Resilience

A multi-reasoner chain that identifies critical network infrastructure, flags delivery compliance issues, and optimizes sourcing allocation under disruption scenarios.

## Pattern

```
Predict (surface risk signals)
  -> Discover structure (identify critical infrastructure)
    -> Classify (combine signals into actionable flags)
      -> Optimize (make decisions informed by all of the above)
        -> Stress-test (explore scenarios)
```

## Stages

### Stage 1: Predict Supplier Delays
**Reasoner:** Predictive (pre-computed)
**Question:** "Which suppliers are likely to delay next quarter?"

**Inputs:**
- Pre-computed delay predictions with risk tier, probability, and confidence per supplier per quarter

**Outputs:**
- Per-supplier delay risk scores and tiers for the target quarter

**Notes:**
- Uses pre-computed predictions already present in the ontology
- No RAI predictive reasoner invocation needed -- this is a query over existing ML outputs
- Output feeds Stage 3 as an input signal for supplier risk classification

---

### Stage 2: Identify Critical Network Nodes
**Reasoner:** Graph
**Template:** `site-centrality-network/`
**Question:** "Which warehouses are most critical connectors in the supply network?"

**Inputs:**
- Site concept as nodes
- Operation relationships as edges (source_site -> output_site)
- capacity_per_day as edge weight

**Graph construction:**
- Undirected, weighted graph over Sites via Operations
- Algorithms: eigenvector centrality (influence) + betweenness centrality (bottleneck detection)

**Outputs:**
- Site centrality score -- feeds Stage 4 as allocation priority weight
- High-centrality sites become scenario targets in Stage 5

**Notes:**
- Independent of Stage 1 -- can run in parallel

---

### Stage 3: Flag Unreliable Suppliers and Late Shipments
**Reasoner:** Rules
**Template:** `shipment_compliance/`
**Question:** "Which shipments are late or at-risk, and which BOMs are single-sourced?"

**Inputs:**
- Business reliability scores (base ontology)
- Delay prediction risk tiers (from Stage 1)
- Shipment delivery dates and expected dates

**Rules:**
- Late shipment detection: actual delivery date exceeds expected delivery date
- Single-sourced BOM flag: bill of materials items with only one qualified supplier
- Supplier risk classification combining reliability score + predicted delay probability:
  - "avoid" -- low reliability AND high predicted delay
  - "watch" -- moderate risk on either dimension
  - "reliable" -- strong on both dimensions

**Outputs:**
- Per-shipment compliance flags (late, at-risk)
- Per-BOM single-source vulnerability flags
- Per-supplier risk class ("reliable" / "watch" / "avoid")
- Feeds Stage 4 as constraint filter (exclude "avoid") or cost penalty (surcharge "watch")

**Notes:**
- Depends on Stage 1 output (delay predictions)
- Independent of Stage 2

---

### Stage 4: Optimize Shipment Allocation
**Reasoner:** Prescriptive
**Template:** `supplier_reliability/`
**Question:** "How should we route shipments to minimize transport cost while meeting demand, respecting capacity, and accounting for supplier risk and network criticality?"

**Problem type:** Network flow

**Inputs (from ontology):**
- Operation cost per unit -- objective coefficient
- Operation capacity per day -- arc capacity constraint
- Demand quantity per SKU per business -- forcing constraint (demand satisfaction)
- Operation source and output sites -- network topology

**Inputs (from earlier stages):**
- Site centrality score (Stage 2) -- secondary objective term penalizing over-reliance on bottleneck sites
- Supplier risk class (Stage 3) -- constraint filter excluding "avoid" suppliers; cost penalty on "watch" suppliers

**Decision variables:**
- Flow quantity on each Operation arc per SKU

**Constraints:**
- Demand satisfaction: total inbound flow at each demand site >= demand quantity per SKU
- Capacity: flow on each Operation <= capacity per day
- Flow conservation: at interior sites, inflow = outflow per SKU
- Risk filter: no flow through Operations sourced from "avoid"-flagged suppliers
- Risk penalty: surcharge on flow through "watch"-flagged supplier Operations

**Objective:**
- Minimize: total transport cost + centrality-weighted bottleneck penalty + risk surcharge

**Outputs:**
- Optimal flow plan per Operation per SKU
- Total cost breakdown (transport, risk penalty, bottleneck penalty)

---

### Stage 5: Scenario Analysis
**Reasoner:** Prescriptive (re-solve)
**Question:** "How would the allocation plan change under disruptions?"

**Scenarios:**

| Scenario | Parameter Change | What to Observe |
|----------|-----------------|-----------------|
| Warehouse offline | Set capacity = 0 on all Operations involving a high-centrality Site | Cost increase, flow re-routing, feasibility |
| Demand surge | Scale demand quantity for a SKU or region by +X% | Cost increase, capacity saturation, infeasibility threshold |
| Supplier downgrade | Move a "watch" supplier to "avoid" | Re-routing cost, alternative supplier utilization |
| New supplier | Add an Operation with given cost/capacity parameters | Cost reduction, network resilience improvement |

**Notes:**
- Each scenario is a parameter modification + re-solve of Stage 4
- Compare total cost, flow distribution, and feasibility across scenarios
- High-centrality sites from Stage 2 are natural candidates for the "warehouse offline" scenario

---

## Stage Dependencies

```
Stage 1 (Predict) -----> Stage 3 (Rules) -----> Stage 4 (Optimize) --> Stage 5 (Scenarios)
Stage 2 (Graph)   --------------------------------^
```

- Stages 1 and 2 are independent -- run in parallel
- Stage 3 depends on Stage 1
- Stage 4 depends on Stages 2 and 3
- Stage 5 depends on Stage 4

---

## Templates Used

| Stage | Template Directory | Purpose |
|-------|--------------------|---------|
| Stage 2 | `site-centrality-network/` | Eigenvector and betweenness centrality on the supply network |
| Stage 3 | `shipment_compliance/` | Late shipment detection, single-source BOM flags, supplier risk classification |
| Stage 4 | `supplier_reliability/` | Cost-minimizing network flow allocation with disruption scenarios |

---

## Adapting This Recipe

This pattern generalizes to any domain where you can:

1. **Surface risk/prediction signals** from pre-computed or historical data
2. **Discover structural importance** in a relationship network
3. **Classify entities** by combining signals into actionable categories
4. **Optimize decisions** informed by predictions, structure, and classifications
5. **Stress-test** by varying parameters and re-solving

To adapt: replace the domain-specific concepts (Site, Operation, Business, Demand) with your equivalents, and adjust the rules/constraints to match your business logic. Each stage uses a standalone template that can also be run independently.
