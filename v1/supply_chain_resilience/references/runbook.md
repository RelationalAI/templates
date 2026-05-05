# Runbook: Supply Chain Resilience — Multi-Reasoner Walkthrough

Walk-through of the chained-reasoner pattern this template is built on. One realistic business thread — **risk-adjusted network flow with disruption scenarios** — traced across four RAI reasoning stages, each writing properties back to the same ontology that downstream stages consume.

The template's combined script (`supply_chain_resilience.py`) implements all four stages directly. This runbook expands the surrounding narrative — what each stage finds, why the next stage needs it, what the optimizer does with the enrichment — so a non-OR reader can follow the full reasoning thread end-to-end.

---

## TL;DR — the chain in one screen

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

A single-reasoner approach can't answer this. Reachability alone names the suppliers in scope but doesn't rank them. Graph alone ranks hubs but doesn't decide flow. Rules alone classifies suppliers but doesn't route around them. Prescriptive alone has no way to hard-block bad suppliers, surcharge watch suppliers, or penalize bottleneck hubs without those upstream signals.

---

## Setup

See the template's main `README.md` for installation, RAI connection setup, and how to run the script. The narrative below follows the actual stage outputs of `supply_chain_resilience.py` against the bundled CSVs in `../data/`.

---

## Stage 0 — Reachability: blast-radius pre-analysis


**Construction** — directed `Business` graph, edges from `Business.ships_to` (derived from `Shipment.supplier` -> `Shipment.customer`).

**Targets** — `Business.is_high_priority_customer` is set wherever a `Demand` with `priority == "HIGH"` is placed by that business. From the bundled data, this fires for **2 buyers**: B008 MegaCorp Enterprise and B009 TechGiant Inc (9 HIGH-priority demands between them, all for ProPhone X1 / ProTab T1).

**Algorithm** — `biz_graph.reachable(to=target_customer)` filtered to nodes with `business_type == "SUPPLIER"`.

```
Upstream supplier dependencies (HIGH-priority customers)

  MegaCorp Enterprise (B008)        depends on 6 suppliers:
    - CellChem China        (reliability 78%)   ← will become AVOID
    - EuroCell Poland       (reliability 88%)
    - EuroChip Germany      (reliability 94%)
    - EuroDisplay Czech     (reliability 91%)
    - GlassCorp Korea       (reliability 89%)
    - WaferTech Taiwan      (reliability 97%)

  TechGiant Inc       (B009)        depends on 6 suppliers:  (same set)

  ──────────────────────────────────────────────────────────────────
  Both HIGH-priority customers share the same 6-supplier upstream.
  CellChem (B017) sits in BOTH dependency cones — Stage 2 will flag
  it AVOID, and Stage 3's baseline already excludes it.
  ──────────────────────────────────────────────────────────────────

✓ Business.is_high_priority_customer written back (2 buyers)
```

The point of running reachability before the MILP: when the scenario in Stage 3 downgrades watch suppliers to avoid, the cost delta has to be read against this dependency map. If a downgraded supplier sits in zero customer cones, the optimizer just shrugs and the cost stays flat — which is exactly what happens here for the watch-tier supplier B003.

---

## Stage 1 — Graph: site centrality + connected components


**Construction:**
- Node concept: `Site` (31 sites)
- Edges: built from `Operation` rows where `op_type == "SHIP"` (undirected, unweighted)
- Aggregator: `"sum"` (collapse parallel ship lanes between the same pair)

**Algorithms:** `weakly_connected_component()` for cluster discovery, then `eigenvector_centrality()` for hub importance.

```
Connected components: 2

  Component A: 25 sites (APAC + AMERICAS, joined by S004->S006 long-haul)
  Component B:  6 sites (EMEA distribution loop)

Top critical sites — eigenvector centrality (FACTORY/DC only)

  S004  TechAssembly Factory     (FACTORY,  APAC)       0.5016  ████████████  ★ central hub
  S006  West Coast DC            (DC,       AMERICAS)   0.3895  █████████
  S003  PowerCell Facility       (FACTORY,  APAC)       0.3688  █████████      ⚠ also Stage 2 watch
  S002  DisplayCorp Plant        (FACTORY,  APAC)       0.3145  ████████
  S001  ChipTech Factory         (FACTORY,  APAC)       0.3145  ████████
  S012  SiliconWorks Factory     (FACTORY,  APAC)       0.2456  ██████
  S013  ScreenTech Plant         (FACTORY,  APAC)       0.2456  ██████
  S014  EnergyPlus Facility      (FACTORY,  APAC)       0.2280  ██████

  ──────────────────────────────────────────────────────────────────
  S004 TechAssembly is the convergence point: every APAC component
  factory ships into it before finished goods radiate to DCs.
  S003 PowerCell shows up here AND in Stage 2 — structural and
  behavioural risk overlap on the same supplier.
  ──────────────────────────────────────────────────────────────────

✓ Site.centrality written back, normalized to [0, 1]
  (S004 = 1.000, S006 = 0.776, S003 = 0.735, ...)
```

---

## Stage 2 — Rules: supplier risk classification


**Late-shipment context** (computed in pandas, not RAI):

```
Late shipments: 37 of 262 (14%)

  B006 West Coast DC    7 late   ████████
  B007 East Coast DC    5 late   ██████
  B004 TechAssembly     4 late   █████
  B022 EMEA DC Central  3 late   ████
  B003 PowerCell        2 late   ███     ← also high predicted Q1
  B017 CellChem         2 late   ███     ← also low reliability
```

**Properties added to the ontology** (via `model.where(...).define(...)`):

```python
# Rule 1 — reliability gate
m.where(Business.reliability_score < 0.80).define(Business.is_unreliable())

# Rule 2 — ML delay-risk gate (Q1-2025 GNN predictions)
m.where(
    DelayPrediction.supplier_business(Business),
    DelayPrediction.fiscal_quarter == "Q1-2025",
    DelayPrediction.predicted_delay_prob > 0.15,
).define(Business.has_high_delay_risk())

# Rule 3 — union into watch level (rule chaining)
m.where(Business.is_unreliable()).define(Business.is_watch_level())
m.where(Business.has_high_delay_risk()).define(Business.is_watch_level())

# Rule 4 — escalate HIGH-priority demands
m.where(Demand.priority == "HIGH").define(Demand.is_escalated())
```

**Resulting classification** (Python combines the two RAI flags into avoid/watch/reliable):

```
Supplier risk classification

  [X] B017  CellChem China      reliability 0.78  Q1 delay 0.22  ── AVOID
  [!] B003  PowerCell Ltd       reliability 0.81  Q1 delay 0.28  ── WATCH
  [ ] B005  GlobalBuild Inc     reliability 0.85                 ── reliable
  [ ] B014  EnergyPlus India    reliability 0.85                 ── reliable
  [ ] B024  EuroAssembly Pol    reliability 0.87                 ── reliable
  [ ] B020  EuroCell Poland     reliability 0.88                 ── reliable
  [ ] B002  DisplayCorp         reliability 0.88                 ── reliable
  [ ] B016  GlassCorp Korea     reliability 0.89                 ── reliable
  [ ] B004  TechAssembly Co     reliability 0.90                 ── reliable
  [ ] B019  EuroDisplay Czech   reliability 0.91                 ── reliable
  [ ] B012  SiliconWorks Corp   reliability 0.91                 ── reliable
  [ ] B013  ScreenTech Japan    reliability 0.93                 ── reliable
  [ ] B018  EuroChip Germany    reliability 0.94                 ── reliable
  [ ] B001  ChipTech Industries reliability 0.95                 ── reliable
  [ ] B015  WaferTech Taiwan    reliability 0.97                 ── reliable

  AVOID  =  is_unreliable AND has_high_delay_risk    (both flags)
  WATCH  =  is_unreliable OR  has_high_delay_risk    (one flag)

Escalated demands (HIGH priority): 9   ── all from B008 / B009

✓ Business.is_unreliable             [1 supplier:  B017]
✓ Business.has_high_delay_risk       [2 suppliers: B003, B017]
✓ Business.is_watch_level            [2 suppliers: B003, B017]
✓ Demand.is_escalated                [9 demands]
```

Stage 3 reads `is_watch_level` for the surcharge term and `is_unreliable AND has_high_delay_risk` (collapsed to the `avoid` set) for the hard block.

---

## Stage 3 — Prescriptive: risk-adjusted minimum-cost flow


```
FORMULATION

  Decision variables
    Operation.x_flow        (continuous, 70 ops, 0 ≤ x ≤ capacity_per_day)
    Demand.x_unmet          (continuous slack, 20 demands, ≥ 0)

  Constraints
    1. Demand satisfaction
       Σ x_flow into customer-site for the demanded SKU + x_unmet ≥ quantity
    2. Avoid suppliers blocked
       For every operation sourced from B017 (CellChem):  x_flow == 0
    3. (Scenario only) Site offline / extra blocks

  Objective (minimize)
    Σ Operation.cost_per_unit · x_flow                              ── transport
    + RISK_SURCHARGE       · Σ x_flow on watch-supplier ops          ── Stage 2
    + CENTRALITY_WEIGHT    · Σ x_flow · Site.centrality              ── Stage 1
    + UNMET_PENALTY        · Σ x_unmet                               ── slack

  Tunables: UNMET_PENALTY=100, RISK_SURCHARGE=5, CENTRALITY_WEIGHT=2,
            DELAY_PROB_THRESHOLD=0.15, RELIABILITY_THRESHOLD=0.80,
            PREDICTION_QUARTER="Q1-2025"

──────────────────────────────────────────────────────────────────────
SOLVE  (HiGHS)   →   OPTIMAL    8 active flows    $1,865.00    0 unmet
──────────────────────────────────────────────────────────────────────

✓ Operation.x_flow / Demand.x_unmet written back as model properties.
```

The baseline buys: enough finished-goods flow on the shortest cost-weighted lanes to cover all 20 demand orders in full. CellChem's operations (B017) are hard-blocked. PowerCell (B003) operations carry a +5/unit surcharge — the optimizer accepts a small amount of B003-sourced flow only when no cheaper non-watch alternative exists.

### Reading the solve

- **8 active flows from 70 candidate operations** — the network is sparse at optimum; most capacity is idle.
- **$1,865 total cost** vs. unconstrained transport cost would be ~$1,500 — the centrality and watch-surcharge terms together add ~$365.
- **Zero unmet demand** — capacity is plentiful, so the slack term is inactive at baseline.

---

## Scenario analysis — quantify disruption


The same `solve_flow(...)` function re-runs with modified constraints. Two scenarios surface different aspects of the chain's value:

```
SCENARIO COMPARISON

  Scenario                  Status     Cost          Δ vs baseline   Unmet
  ────────────────────────  ────────   ──────────   ──────────────   ─────
  Baseline                  OPTIMAL    $1,865.00          —              0
  Site S004 offline         OPTIMAL    $3,515.00    +88.5%               0
  Watch->Avoid              OPTIMAL    $1,865.00     +0.0%               0
```

**Scenario A — top-centrality site offline (S004 TechAssembly).** The optimizer reroutes finished goods through S005 GlobalBuild Plant (Mexico) and longer EMEA lanes; cost jumps 88.5% but all demand is still covered. This is the **structural-risk** signal: losing the highest-centrality node forces expensive secondary routing.

**Scenario B — downgrade all watch suppliers to avoid.** Adds B003 PowerCell to the hard-block set. **Cost is unchanged.** Why? B003 wasn't on any optimal lane — the centrality penalty + risk surcharge already discouraged the optimizer from routing through it at baseline. **This asymmetry is the punchline:** structural risk (Stage 1) costs 88.5% to disrupt; behavioural risk on already-deprioritized suppliers (Stage 2) costs 0% to harden against. The chain reveals which mitigations actually move the needle.

(Cross-check the Stage 0 dependency map: B003 wasn't in either HIGH-priority customer's *direct* upstream — it ships components to manufacturers, who then route via the optimizer's preferred S004/S005 corridor. Reachability surfaced the supplier; centrality + objective weights ensured baseline never relied on it.)

---

## The chain — accretive ontology enrichment

```
THE SUPPLY-CHAIN-RESILIENCE CHAIN

  STAGE 0  REACHABILITY (directed Business graph)
  "Which suppliers do my high-priority customers transitively depend on?"
  reads:   Shipment.supplier / .customer  ──►  Business.ships_to (derived)
           Demand.priority == "HIGH"      ──►  Business.is_high_priority_customer
  writes:  Business.is_high_priority_customer    ── 2 buyers
                         │
                         ▼
  STAGE 1  GRAPH (eigenvector centrality, WCC)
  "Which sites are network bottlenecks?"
  reads:   Operation (op_type == "SHIP"), Site
  writes:  Site.centrality                       ── normalized [0,1] per site
                         │
                         ▼
  STAGE 2  RULES (chained derivations)
  "Which suppliers are risky, and which demands are escalated?"
  reads:   Business.reliability_score, DelayPrediction, Demand.priority
  writes:  Business.is_unreliable                ── 1 supplier
           Business.has_high_delay_risk          ── 2 suppliers
           Business.is_watch_level               ── 2 suppliers
           Demand.is_escalated                   ── 9 demands
                         │
                         ▼
  STAGE 3  PRESCRIPTIVE (HiGHS LP)
  "What's the minimum-cost flow plan that respects all of the above?"
  reads:   Site.centrality              ──►  objective coefficient (penalty)
           Business.is_watch_level      ──►  objective coefficient (surcharge)
           {avoid suppliers}            ──►  hard block (x_flow == 0)
           Operation cost / capacity / SKU, Demand quantity / SKU / business
  writes:  Operation.x_flow             ── 8 active flows
           Demand.x_unmet               ── 0 across all 20 demands
                         │
                         ▼
                   Re-solve per scenario (S004 offline, watch->avoid)
                   → cost-of-disruption table

  ──────────────────────────────────────────────────────────────────
  No glue. No DataFrame ping-pong. No re-derivation per-reasoner.
  Four stages, one ontology, one accretive thread.
  ──────────────────────────────────────────────────────────────────
```

---

## Why the chain matters (vs. any single stage)

| Stage alone | What it tells you | What it doesn't |
|---|---|---|
| Reachability alone | "These 6 suppliers feed my critical customers" | Which are risky; which the optimizer would have used anyway |
| Graph alone | "S004 is the central hub" | Whether losing it is recoverable; at what cost |
| Rules alone | "B017 avoid, B003 watch" | Whether routing actually depends on them |
| Prescriptive alone | (degenerate — no risk filter, no bottleneck weight) | Picks cheapest lanes regardless of supplier risk or hub fragility |

| Combined | Output |
|---|---|
| Reachability -> Graph | Customer-supplier dependency map + structural hub ranking |
| + Rules | Per-supplier risk class (avoid / watch / reliable) on top of the dependency map |
| + Prescriptive | Risk-adjusted min-cost flow ($1,865) + scenario deltas (+88.5% on S004 offline, +0% on watch->avoid) |

**Multi-reasoner chaining grounded in (and contributing to) the ontology.**

---

## Optional extension — predictive forecasting

The bundled `delay_prediction.csv` is treated as already-trained ML output (a quarterly per-supplier delay probability table, `model_version='gnn_v2.0'`). A natural extension to the template is to replace the static CSV with a live GNN that retrains on `Shipment.delay_days` history. Skill: `/rai-predictive-modeling` + `/rai-predictive-training`. Reference templates with end-to-end GNN training: `templates/v1/fraud-detection`, `templates/v1/retail_planning`. The downstream stages (rules + prescriptive) wouldn't change — they read `DelayPrediction.predicted_delay_prob` either way.

---

## Agent prompt sequence — recreate this template skill-by-skill

Each row is a single agent prompt. Skills are loaded in order; each writes properties the next stage reads.

| # | Skill | Prompt | What it produces |
|---|-------|--------|------------------|
| 1 | `/rai-build-starter-ontology` | "Build a starter ontology for a supply-chain dataset with 7 CSVs: site, business, operation, sku, demand, shipment, delay_prediction. Use Site/Business/Operation/SKU/Demand/Shipment/DelayPrediction as concepts. Render the result as an ASCII concept-relationship diagram." | Concepts, properties, relationships matching `supply_chain_resilience.py` lines 57–250 |
| 2 | `/rai-discovery` | "Given this ontology, what questions can each reasoner family answer? Group by graph / rules / prescriptive." | A reasoner-routing plan that covers Stages 0–3 below |
| 3 | `/rai-graph-analysis` | "Build a directed Business graph from Shipment.supplier->Shipment.customer. Run upstream reachability from every Business with a HIGH-priority demand. List the suppliers each high-priority customer transitively depends on." | Stage 0 — `Business.is_high_priority_customer`, blast-radius dependency map |
| 4 | `/rai-graph-analysis` | "Build an undirected Site graph from Operation rows where op_type == 'SHIP'. Compute weakly-connected components, then eigenvector centrality (filter to FACTORY/DC). Normalize and write the score back as Site.centrality." | Stage 1 — `Site.centrality` |
| 5 | `/rai-rules-authoring` | "Define three derived relationships on Business: is_unreliable (reliability_score < 0.80), has_high_delay_risk (any DelayPrediction for Q1-2025 with predicted_delay_prob > 0.15), and is_watch_level (union of the two). Also flag Demand.is_escalated for HIGH priority. Print the avoid (both flags) / watch (one flag) / reliable classification." | Stage 2 — risk flags, escalation flag |
| 6 | `/rai-prescriptive-problem-formulation` | "Formulate a minimum-cost network flow on Operation.x_flow with Demand.x_unmet slack. Constraint: inbound flow at customer site for demanded SKU + slack >= quantity. Hard-block operations sourced from avoid-tier businesses. Objective: transport cost + RISK_SURCHARGE * watch-supplier flow + CENTRALITY_WEIGHT * Σ flow · Site.centrality + UNMET_PENALTY * Σ unmet. Describe the formulation before solving — decision variables, constraints, objective, tunables." | Stage 3 formulation |
| 7 | `/rai-prescriptive-solver-management` | "Solve with HiGHS, time limit 120s. Report status, objective value, count of active flows, and total unmet demand." | Baseline solve — OPTIMAL, $1,865, 8 flows, 0 unmet |
| 8 | `/rai-prescriptive-results-interpretation` | "Re-solve two scenarios side-by-side: (a) top-centrality site offline (S004 TechAssembly), (b) all watch-level suppliers downgraded to avoid. Show cost delta vs baseline as a table. Explain why the deltas are asymmetric." | Scenario table + interpretation (S004 offline = +88.5%, watch->avoid = +0%) |

---

## Data Reference

- **Source data**: bundled CSVs in `../data/` — 31 sites across APAC / AMERICAS / EMEA, 31 businesses (6 suppliers, 6 component manufacturers, 2 manufacturers, 8 warehouses, 9 buyers), 9 SKUs (raw materials -> components -> finished goods ProPhone X1 / ProTab T1), 70 operations (SHIP + TRANSFER), 20 demand orders (9 HIGH, 5 MEDIUM, 6 LOW), 262 historical shipments (37 late), 36 quarterly delay predictions (4 quarters × 9 suppliers). To run against your own Snowflake schema instead, swap `read_csv(...)` for typed `model.Table(...)` loads against the equivalent table set.
- **Ontology**: defined inline in `../supply_chain_resilience.py` (lines 57–250) — 7 concepts plus the derived `Business.ships_to` and `Operation.source_business` relationships.
- **Stages**: implemented in `../supply_chain_resilience.py` as a single combined script with stage banners (`STAGE 0` through `STAGE 3` plus `SCENARIO ANALYSIS`).
