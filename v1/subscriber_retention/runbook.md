# Runbook: Subscriber Retention — Multi-Reasoner Walkthrough

A telco retention team wants a per-subscriber churn-risk score that uses more than plan attributes and demographics — it should also reflect where each subscriber sits in the call network. This chain computes call-graph centrality, feeds it as a feature into a graph neural network (GNN) that scores churn risk, and surfaces the highest-risk subscribers per segment as a retention queue. The graph signal and the predictive model are different reasoners working on one ontology.

## The chain

```
1,200 subscribers and a 6,000-edge call graph. The chain scores each subscriber's
call-network centrality, then trains a GNN to predict churn risk per subscriber,
reaching a test RMSE of ~0.14 — a network-aware retention queue.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Subscriber.pagerank                (1,200)
                             + Subscriber.outgoing_calls / incoming_calls
                             PageRank on the directed call graph plus
                             call-volume counts — the network features.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Predictive   ──►  Subscriber.predictions             (test set)
                  (GNN)      A GNN regresses churn_risk_score from plan,
                             demographic, AND graph features. Test RMSE ~0.14.
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build an ontology from data/telco_mini/: subscribers.csv (each subscriber has a segment, type, status, lifetime value, NPS, signup date, and a churn risk score), plans_contracts.csv (each subscriber's plan — type, monthly rate, data limit, term, auto-renew, early-termination fee — joined onto the subscriber), and call_detail_records.csv (each call is from one subscriber to another). Model the call as a relationship between subscribers.
```

**Response**

Loads `Subscriber` (1,200, with plan attributes joined on, segment mix PREMIUM/STANDARD/BUDGET/ENTERPRISE_PREMIUM/HIGH_VALUE_INFLUENCER, and a `churn_risk_score` target in [0, 1]) and `Call` (6,000 call records) forming a directed subscriber-to-subscriber call graph.

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

`Subscriber` (1,200, with plan + demographic attributes and the churn target) and `Call` (6,000 directed call edges among subscribers, ~5,985 distinct caller-callee pairs). The churn score averages about 0.24 across the base.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We want a per-subscriber churn-risk score that also accounts for how central each subscriber is in the call network. How should we break this down?
```

**Response**

Routes to a graph step (score each subscriber's call-network centrality and call volume) feeding a predictive step (a GNN that learns churn risk from plan, demographic, and graph features).

### 4. Compute call-network features

**Prompt**

```
/rai-graph-analysis On the directed call graph, score each subscriber's influence with PageRank, and also count each subscriber's outgoing and incoming calls. Persist these as Subscriber.pagerank, Subscriber.outgoing_calls, and Subscriber.incoming_calls so the churn model can use them as features.
```

**Response**

PageRank runs over all 1,200 subscribers on the directed call graph, and per-subscriber outgoing/incoming call counts are derived. The three values are written back as `Subscriber.pagerank`, `Subscriber.outgoing_calls`, and `Subscriber.incoming_calls` — the network features the GNN will read alongside plan and demographic attributes.

### 5. Train the churn model

**Prompt**

```
/rai-predictive-modeling + /rai-predictive-training Train a graph neural network to predict each subscriber's churn_risk_score (a continuous 0-to-1 regression) from their plan attributes, demographics, and the graph features (pagerank, outgoing/incoming calls), using the call graph as the GNN's message-passing edges. Train on the training split, evaluate on the held-out test split with RMSE, and write the predictions back to the ontology.
```

**Response**

A GNN regression head trains on the subscriber call graph (features: segment, plan type, lifetime value, NPS, pagerank, call counts, etc.) and evaluates at **test RMSE ≈ 0.14**. Predictions are written back as `Subscriber.predictions` over the held-out test subscribers.

### 6. Build the retention queue

**Prompt**

```
/rai-querying For each segment, which test-set subscribers have the highest predicted churn risk — the retention queue to action first?
```

**Response**

Joining predictions back to subscriber metadata and ranking by predicted risk within each segment gives a per-segment retention queue, surfacing the network-central, high-value subscribers (enterprise and influencer accounts) as priority targets. On this small synthetic base the predictions cluster near each segment's mean risk (~0.22–0.26) — the template demonstrates the network-aware pipeline shape; a production dataset with real churn signal would spread the scores and sharpen the ranking.

## Data

Bundled CSVs in `data/telco_mini/`: 1,200 subscribers, 1,200 plan contracts, 6,000 call detail records (plus billing events for the customize section). Train/validation/test splits are derived in the script, stratified by segment. Full chain in `subscriber_retention.py`.
