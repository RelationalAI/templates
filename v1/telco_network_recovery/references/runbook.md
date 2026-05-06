# Runbook: Telco WEST Recovery — Multi-Reasoner Walkthrough

Walk-through of the chained-reasoner pattern this template is built on. One realistic business thread — **WEST region recovery** — traced across all five RAI reasoner families, each stage writing properties back to the same ontology that downstream stages consume.

The template's combined script (`telco_network_recovery.py`) implements the predictive, rules, graph, and prescriptive stages directly; this runbook frames them with a descriptive Stage 1 diagnosis and a Stage 6 interpretation, so a non-OR reader can follow the full reasoning thread end-to-end.

---

## How to read this runbook

This runbook serves two audiences:

- **Reading top-to-bottom**: the narrative + ASCII visualizations show what the chain produces stage-by-stage, with the same business framing the stakeholder would see.
- **Per-stage skill blocks**: the boxed `Skill / Prompt` callout at the start of each stage is the recipe — load that RAI agent skill, give it that prompt against the bundled demo data in `../data/`, and the agent will reproduce the stage.

---

## TL;DR — the chain in one screen

```
WEST is bleeding $791K/quarter from a network operations crisis.
The chain produces a $5M plan that recovers 122 Gbps capacity
across all 15 critical towers, prioritized by social blast radius.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Descriptive  ──►  WEST: Q3-Q4 revenue −22% to −26%,
                              avail 94.6 vs 99.5, 15 of 81 DEGRADED.
                              Retention angle? No — 0 high-risk
                              subs; this is operational.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  CellTower.is_critical_restore  (15)
                              4 derived health metrics + a compound
                              flag: WEST + DEGRADED + health < 0.85.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Graph        ──►  Subscriber.influence_score  (PageRank)
                              CellTower.weighted_impact  (15)
                              404 distinct subs (33% of base) route
                              calls through a critical tower.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Predictive   ──►  CellTower.projected_demand_growth (15)
                 (GNN)        WEST: 0.993×  ── shrinking ~0.7%/yr
                              while 8 other regions sit at +0.59 to +0.75%/day.
  ─────────────────────────────────────────────────────────────────
  STAGE 5  Prescriptive ──►  TowerUpgradeOption.selected  (15)
                              OPTIMAL · 12 GOLD · 2 SILVER · 1 BRONZE
                              $4.96M of $5M (binding) · 122 Gbps
                              164 of 200 install-weeks (slack)
  ─────────────────────────────────────────────────────────────────
```

A single-reasoner approach can't answer this. Descriptive alone tells the story but no plan. Rules alone identifies broken towers but not which matter most. Graph alone ranks subscribers but doesn't decide. Predictive alone forecasts but doesn't act. Prescriptive alone has no way to weigh "important" without rules + graph upstream.

---

## Step 0 — Scope the question with `rai-discovery`

> **Skill:** `rai-discovery` ·
> **Prompt:** "WEST is missing revenue targets while every other region grows. Diagnose whether this is a subscriber-retention problem or a network-operations problem, then produce a defensible tower-upgrade plan inside a $5M capex cap and a 200 install-crew-week schedule that prioritizes towers by both who depends on them and where regional demand is heading."

Discovery classifies the question by reasoner family and tells you which downstream skills to load:

| Sub-question | Reasoner | Skill |
|---|---|---|
| Where is the revenue bleed coming from, and is it retention or operational? | Descriptive | `rai-querying` |
| Which WEST towers are technically broken enough to be in scope for upgrade? | Rules | `rai-rules-authoring` |
| Whose service depends on each broken tower — what is the social blast radius? | Graph (PageRank) | `rai-graph-analysis` |
| Is regional demand growing or contracting at those sites over the forward horizon? | Predictive (GNN) | _no public skill yet — see `v1/subscriber_retention/` and `v1/demand_forecasting/` as worked-example references_ |
| Given the cost cap and install-crew budget, which tier should each critical tower receive? | Prescriptive (MIP) | `rai-prescriptive-problem-formulation` |
| Which constraint is binding, and what would change if we relaxed it? | Prescriptive (post-solve) | `rai-prescriptive-results-interpretation` |

Discovery's output is a *plan*, not code. Everything that follows materializes that plan.

---

## Setup

See the template's main `README.md` for installation, RAI connection setup, and how to run the script. The narrative below follows the actual stage outputs of `telco_network_recovery.py`.

---

## Stage 1 — Descriptive: diagnose WEST

> **Skill:** `rai-querying` ·
> **Prompt:** "Run a regional triage on the daily KPIs and tower fleet for Q3–Q4 2024. Compare WEST against the other eight regions on network availability, churn rate, daily revenue, and the revenue-forecast vs. actual gap, and break down the WEST tower fleet by status. Identify the top performance offenders by per-tower packet loss and latency, and check whether any WEST subscribers carry elevated churn risk. Conclude whether this looks like a retention problem or an operational one."

```
Q4 2024 — Daily KPIs by region

                avg avail %       avg churn rate     avg daily revenue
              ──────────────     ────────────────    ──────────────────
  WEST          94.60  ███       0.0256  █████████   $72,558  ███████
  CENTRAL       99.52  ████████  0.0046  █              $101,517  ██████████
  SOUTH         99.53  ████████  0.0049  █              $102,030  ██████████
  EAST          99.55  ████████  0.0049  █              $103,840  ██████████
  NORTH         99.56  ████████  0.0050  █              $103,810  ██████████
  NORTHEAST     99.56  ████████  0.0050  █               $99,569  ██████████
  SOUTHEAST     99.58  ████████  0.0050  █              $100,429  ██████████
  NORTHWEST     99.54  ████████  0.0049  █              $100,995  ██████████
  SOUTHWEST     99.55  ████████  0.0049  █              $101,716  ██████████
                                                      ▲
  WEST is 5× worse on availability AND churn,         │
  ~30% lower on daily revenue.                        │
                                                      │
  Q3-Q4 monthly revenue gaps stack to $791K:    ──────┘

   Sep 2024   forecast $1.40M  →  actual $1.04M  ── −25.9%  (−$362K)
   Oct 2024   forecast $0.94M  →  actual $0.70M  ── −25.1%  (−$236K)
   Nov 2024   forecast $0.88M  →  actual $0.68M  ── −22.0%  (−$193K)

  WEST tower fleet (81 towers)

       ACTIVE        ████████████████████████  49
       DEGRADED      ███████                   15   ← 15 critical_restore
       MAINTENANCE   ████████                  17

  Top performance offenders (NetworkPerformance, all WEST DEGRADED):
       TWR-0015 ── 8.87% loss  190ms  (424 measurements)
       TWR-0014 ── 8.75% loss  189ms  (273 measurements)
       TWR-0010 ── 8.73% loss  188ms  (429 measurements)
       (… all 15 cluster 8.1-8.9% loss / 185-200ms latency)
       ────────────────────────────────────────
       Healthy WEST towers sit at <1% loss / ~30ms latency.

  Retention angle? Zero subs in collections, zero with churn_risk ≥ 0.5.
  High-risk subscribers concentrate in SOUTH/NORTH/CENTRAL, not WEST.
  This is a NETWORK-side crisis, not subscriber retention.
```

Subscriber.churn_risk_score is a static feature that hasn't caught up to WEST's empirical churn (TimeSeriesMetric.churn_rate of 2.6% is 5x other regions). The thread focuses on infrastructure recovery.

---

## Stage 2 — Rules: flag critical_restore towers

> **Skill:** `rai-rules-authoring` ·
> **Prompt:** "Define per-tower derived averages for packet loss, latency, and error rate from the network-performance measurements, plus an average equipment-health score from the two-hop join through network equipment to equipment-health snapshots. Then add a unary critical-restore flag on the tower that fires when the tower is in WEST and either DEGRADED with average health below 0.85, or shows average packet loss above 5% with the same health threshold (so an ACTIVE-but-failing tower is still caught)."

**Properties added to the ontology** (via `model.define(...)`):
- `CellTower.avg_packet_loss` (Float) — `aggs.avg(NetworkPerformance.packet_loss_pct).per(CellTower)`
- `CellTower.avg_latency_ms` (Float)
- `CellTower.avg_error_rate` (Float)
- `CellTower.avg_health_score` (Float) — across attached equipment via two-hop join

**Rule** — `CellTower.is_critical_restore` (unary `Relationship`):

```python
# Branch 1: WEST + DEGRADED + degraded equipment health
m.where(
    CellTower.region == "WEST",
    CellTower.status == "DEGRADED",
    CellTower.avg_health_score < 0.85,   # health is 0-1 scale
).define(CellTower.is_critical_restore())

# Branch 2: WEST + poor performance + degraded health (catches ACTIVE-but-failing)
m.where(
    CellTower.region == "WEST",
    CellTower.avg_packet_loss > 5.0,
    CellTower.avg_health_score < 0.85,
).define(CellTower.is_critical_restore())
```

```
RULE FIRES → 15 towers flagged is_critical_restore  (all WEST DEGRADED)

  TWR-0010 ── health 0.48  loss 8.73%  cap_gbps 18  ███
  TWR-0015 ── health 0.60  loss 8.87%  cap_gbps 60  ██████
  TWR-0009 ── health 0.62  loss 8.49%  cap_gbps 17  ███
  TWR-0012 ── health 0.63  loss 8.59%  cap_gbps 84  █████████
  TWR-0008 ── health 0.64  loss 8.51%  cap_gbps 71  ████████
  TWR-0014 ── health 0.66  loss 8.75%  cap_gbps 36  █████
  TWR-0002 ── health 0.66  loss 8.56%  cap_gbps 17  ███
  TWR-0001 ── health 0.66  loss 8.56%  cap_gbps 31  █████
  TWR-0011 ── health 0.66  loss 8.68%  cap_gbps 61  ███████
  TWR-0005 ── health 0.68  loss 8.12%  cap_gbps 94  ██████████
  TWR-0003 ── health 0.69  loss 8.45%  cap_gbps 43  █████
  TWR-0007 ── health 0.72  loss 8.54%  cap_gbps 17  ███
  TWR-0013 ── health 0.77  loss 8.62%  cap_gbps 94  ██████████
  TWR-0006 ── health 0.78  loss 8.51%  cap_gbps 37  █████
  TWR-0004 ── health 0.81  loss 8.54%  cap_gbps 64  ███████

✓ is_critical_restore written back to CellTower (15 rows)
✓ avg_packet_loss / avg_latency_ms / avg_error_rate / avg_health_score
  written back to all CellTowers (250 rows)
```

Branch 2 didn't fire — none of WEST's ACTIVE towers fall below health 0.85. The 15 flagged are exactly the WEST DEGRADED set, all with packet loss 8.1–8.9% and latency 185–200ms — sharp gap from the rest of WEST.

---

## Stage 3 — Graph: subscriber influence + tower blast radius

> **Skill:** `rai-graph-analysis` ·
> **Prompt:** "Build a directed subscriber-to-subscriber call graph from the call-detail records, with caller pointing to callee and parallel calls between the same pair summed into a single edge. Score each subscriber with PageRank and write that influence back to the subscriber. Then per critical-restore tower, aggregate the distinct subscribers whose calls route through it and the sum of their PageRank — that's the social blast radius if the tower fails."

**Construction** — Pattern 3 (`edge_concept`):
- Node concept: `Subscriber` (1,200 nodes)
- Edge concept: `CallDetailRecord`, with `caller`→`callee` (directed)
- Aggregator: `"sum"` (collapse parallel calls between the same pair)

**Algorithm:** `pagerank()` (default for directed graphs).

```
PageRank — top 10 social influencers (of 1,200 subscribers)

  SUB-CON-00900   CONSUMER     $3,793 LTV   ████████████  0.002963
  SUB-CON-00723   CONSUMER     $3,049 LTV   ████████████  0.002956
  SUB-CON-00262   CONSUMER     $3,764 LTV   ███████████   0.002790
  SUB-CON-00274   CONSUMER     $2,850 LTV   ███████████   0.002695
  SUB-ENT-0038    ENTERPRISE  $283,233 LTV  ██████████    0.002637  ★
  SUB-CON-00705   CONSUMER       $765 LTV   ██████████    0.002599
  SUB-CON-00393   CONSUMER     $3,219 LTV   ██████████    0.002581
  SUB-ENT-0001    ENTERPRISE  $393,340 LTV  ██████████    0.002575  ★
  SUB-CON-01066   CONSUMER     $1,146 LTV   ██████████    0.002570
  SUB-CON-00762   CONSUMER       $307 LTV   ██████████    0.002525

  ★ Top enterprise accounts also rank — heavy inbound call traffic.
    PageRank captures structural influence independent of LTV.

Per-critical-tower blast radius (sorted by weighted_impact)

  TWR-0014  61 subs  ████████████  0.0502   ← largest social footprint
  TWR-0008  56 subs  ██████████    0.0430
  TWR-0011  48 subs  ██████████    0.0428
  TWR-0012  50 subs  █████████     0.0394
  TWR-0003  43 subs  █████████     0.0393
  TWR-0013  46 subs  █████████     0.0379
  TWR-0004  46 subs  █████████     0.0378
  TWR-0010  48 subs  █████████     0.0375
  TWR-0015  45 subs  ████████      0.0361
  TWR-0002  46 subs  ████████      0.0331
  TWR-0007  44 subs  ████████      0.0330
  TWR-0005  45 subs  ████████      0.0330
  TWR-0009  44 subs  ████████      0.0330
  TWR-0001  41 subs  ████████      0.0322
  TWR-0006  41 subs  ████████      0.0316

  ──────────────────────────────────────────────────────────────────
  404 distinct subscribers (33% of the 1,200-sub base) route at least
  one call through a critical WEST tower. TWR-0014's failure ripples
  to 61 subs whose combined social influence is highest.
  ──────────────────────────────────────────────────────────────────

✓ Subscriber.influence_score written back to all 1,200 subscribers
✓ CellTower.impact_count + weighted_impact written back to CellTower
```

---

## Stage 4 — Predictive: forecast WEST capacity demand

> **Skill:** _no public skill yet — see `v1/subscriber_retention/` and `v1/demand_forecasting/` as worked-example references_ ·
> **Prompt:** "Train a regression GNN on per-region daily KPIs predicting subscriber growth rate. Use same-region 1-day-lag temporal edges, region as a category feature, and three lag features (previous-day growth, previous-week growth, and a 7-day rolling mean) computed before load. Train on rows before November 2024, validate on November, test on December, then bind each region's mean predicted growth back to every cell tower in that region as a per-tower demand multiplier."

**Method:** GNN node regression on `TimeSeriesMetric` (composite key `metric_date` + `region`). Target: `subscriber_growth_rate`. Features: the other 12 daily KPIs + 3 lag features (`prev_day_growth`, `prev_week_growth`, `growth_7d_mean`) + `region` as a category. Graph: same-region 1-day-lag temporal edges. Train < 2024-11-01 (includes the Sep–Oct WEST decline onset); validate on Nov 2024; test on Dec 2024.

```
Per-region GNN-predicted subscriber-growth-rate (Dec 2024 test horizon)

  CENTRAL    ─────  +0.0075  ████████  ▲
  EAST       ─────  +0.0073  ████████  │
  NORTH      ─────  +0.0071  ████████  │  8 regions cluster
  NORTHEAST  ─────  +0.0070  ████████  │  +0.59 to +0.75%/day
  NORTHWEST  ─────  +0.0067  ████████  │  (mean predicted growth)
  SOUTH      ─────  +0.0065  ████████  │
  SOUTHEAST  ─────  +0.0063  ███████   │
  SOUTHWEST  ─────  +0.0059  ███████   ▼
                            ▲
                            │
  WEST       ───── −0.0071                      ← anomaly: contracting
                                                 multiplier 0.993×

  ──────────────────────────────────────────────────────────────────
  WEST projection: 0.7% demand decline over the test horizon.
  Stage 5 picks up this multiplier as the 3rd objective coefficient.
  ──────────────────────────────────────────────────────────────────

✓ CellTower.projected_demand_growth written back to all 15 critical towers
  (uniform 0.992871 — regional, not per-tower)
```

**Stage 5 objective with the predictive term:**

```
objective = sum( selected[t,tier] *
                 capacity_increase_gbps[t,tier] *
                 weighted_impact[t] *
                 projected_demand_growth[t] )    # ← Stage 4 contribution
```

**Snowflake setup for the GNN:** the template's main script computes lag features (prev-day, prev-week, 7-day mean) and same-region 1-day-lag temporal edges in pandas before loading, so no extra Snowflake DDL is required. To run on your own Snowflake schema instead of the bundled CSV, the equivalent SQL would be a typed copy of the time-series table plus per-region `LAG()` window functions.

**Caveats:**
- The GNN was tuned for a single 80-epoch run with seed-42 reproducibility; production deployment would expand to a multi-seed average + a held-out holdout window.
- The WEST projection partially encodes the same network-degradation pattern Stages 2/3 flagged ("things have gotten worse and we expect them to keep getting worse if we don't act"). For an independent baseline, train on a pre-degradation slice (H1 2024 only) and compare.

---

## Stage 5 — Prescriptive: tower upgrade selection MIP

> **Skill:** `rai-prescriptive-problem-formulation` ·
> **Prompt:** "Pick at most one upgrade tier (BRONZE, SILVER, or GOLD) per critical-restore tower using a binary decision variable on the tower-upgrade-option junction. Stay within a $5M total cost cap and 200 total install crew-weeks. Maximize the sum across selected options of capacity-increase × tower weighted-impact × tower projected-demand-growth, so the optimizer favors towers that are both broken and high-blast-radius, scaled by the regional demand forecast. Solve with Gurobi."

```
FORMULATION

  Decision variable
    TowerUpgradeOption.selected  (binary)
      45 binaries = 15 critical-restore towers × {BRONZE, SILVER, GOLD}

  Constraints
    1. At-most-one tier per tower      sum(selected).per(CellTower) ≤ 1
    2. Total cost                      Σ selected · cost ≤ $5,000,000
    3. Total install_weeks             Σ selected · install_weeks ≤ 200

  Objective (maximize)
    Σ selected · capacity_increase_gbps · weighted_impact · projected_demand_growth
                  └────── Step 2 (rules) ─────┘└── Stage 3 ──┘└── Stage 4 ──┘

──────────────────────────────────────────────────────────────────────
SOLVE  (Gurobi)   →   OPTIMAL    15 active flows    122 Gbps    $4,956,843
──────────────────────────────────────────────────────────────────────

Tower-tier assignment (sorted by weighted_impact)

  TWR-0014  ── GOLD     +6 Gbps   $350,864   wgt 0.0502  ████████████
  TWR-0008  ── GOLD    +10 Gbps   $416,455   wgt 0.0430  ██████████
  TWR-0011  ── GOLD     +9 Gbps   $481,914   wgt 0.0428  ██████████
  TWR-0012  ── GOLD     +8 Gbps   $445,825   wgt 0.0394  █████████
  TWR-0003  ── GOLD    +11 Gbps   $360,785   wgt 0.0393  █████████
  TWR-0013  ── GOLD     +9 Gbps   $273,831   wgt 0.0379  █████████
  TWR-0004  ── GOLD     +9 Gbps   $275,353   wgt 0.0378  █████████
  TWR-0010  ── GOLD    +12 Gbps   $332,694   wgt 0.0375  █████████
  TWR-0015  ── GOLD    +11 Gbps   $438,932   wgt 0.0361  ████████
  TWR-0002  ── GOLD    +11 Gbps   $420,363   wgt 0.0331  ████████
  TWR-0007  ── GOLD     +9 Gbps   $416,640   wgt 0.0330  ████████
  TWR-0005  ── SILVER   +3 Gbps   $220,435   wgt 0.0330  ████████  ⚐
  TWR-0009  ── BRONZE   +3 Gbps    $97,784   wgt 0.0330  ████████  ⚐
  TWR-0001  ── GOLD     +6 Gbps   $274,561   wgt 0.0322  ████████
  TWR-0006  ── SILVER   +5 Gbps   $150,407   wgt 0.0316  ████████  ⚐

  ⚐ Lowest weighted_impact towers — solver buys cheaper tiers
    to free budget for the higher-impact GOLDs.

Budget gauge
  Cost          ████████████████████████████████████████  $4,956,843 / $5,000,000  ── BINDING
  Install-wks   █████████████████████████████████          164 / 200            (slack: 36)

Headline metrics
  Capacity restored:   122 Gbps
  Tier mix:            12 GOLD · 2 SILVER · 1 BRONZE
  Towers covered:      15 of 15 (no triage tradeoff)
  Subs serviced:       404 distinct (33% of all 1,200)
  Objective without Stage 4 (Σ capacity × weighted_impact):    4.6024
  Objective with Stage 4 (× 0.992871 uniform multiplier):      4.5696

✓ TowerUpgradeOption.selected written back — the optimization output
  is now a queryable property of the model.
```

(Full decision matrix: `outputs/stage5_solution.csv`.)

### Reading the solve

- **GOLD dominates** (12/15) — for towers with high social blast radius, GOLD's 6–12 Gbps uplift outweighs its higher cost.
- **Budget is binding** ($4.96M / $5M) — relaxing to $6M would let TWR-0009 jump from BRONZE to GOLD ($481K → +9 Gbps) and lift the objective meaningfully.
- **Install-weeks are not binding** (164/200) — schedule is the looser constraint; budget holds back the plan.
- **Stage 4's uniform multiplier doesn't shift tiers** — the forecast says WEST is contracting (-0.7%), so every upgrade is slightly less valuable in absolute terms, but relative tower priority is unchanged. **A non-uniform forecast would be the more revealing test of the chain's value** — if some WEST towers sat in growth pockets and others in decline, the tier mix would shift accordingly.

---

## Stage 6 — Interpretation

> **Skill:** `rai-prescriptive-results-interpretation` ·
> **Prompt:** "Summarize the optimal plan in business terms: total cost vs. budget, capacity restored, tier mix, towers covered, and how many subscribers stop being served by a critical tower over the install schedule. Identify which constraint is binding and what would change if it were relaxed by 10–20% (which tower would jump tiers, what the marginal capacity lift would be). List the per-stage ontology enrichments so the reader can see what each reasoner contributed back."

```
THE PLAN, IN BUSINESS TERMS

  • 122 Gbps of network capacity restored across all 15 critical towers
    within the $5M capex budget.
  • Every WEST DEGRADED tower gets an upgrade — no triage tradeoff.
  • Service-affected subscribers drop from 404 to ~0 over the install
    schedule (164 crew-weeks; 4-month rollout at 2 crews of 5).
  • Budget binding — if CFO can flex to $6M, promote TWR-0009 to GOLD
    for +9 Gbps marginal lift.

ONTOLOGY ENRICHMENT — what each stage contributed back

  Stage 2 (rules)         CellTower.is_critical_restore           [15]
                          CellTower.avg_packet_loss               [250]
                          CellTower.avg_latency_ms                [250]
                          CellTower.avg_error_rate                [250]
                          CellTower.avg_health_score              [250]

  Stage 3 (graph)         Subscriber.influence_score              [1,200]
                          CellTower.impact_count                  [120]
                          CellTower.weighted_impact               [120]

  Stage 4 (predictive)    CellTower.projected_demand_growth       [15]

  Stage 5 (prescriptive)  TowerUpgradeOption.selected             [45]

  ──────────────────────────────────────────────────────────────────
  Each stage reads what the previous stage wrote.
  Re-running any downstream stage automatically picks up enrichments.
  No glue code, no DataFrame round-trip — same ontology throughout.
  ──────────────────────────────────────────────────────────────────
```

---

## The chain — accretive ontology enrichment

```
THE WEST RECOVERY CHAIN

  STAGE 1  DESCRIPTIVE
  "Where is the bleed coming from?"
  reads:   RevenueForecast, TimeSeriesMetric, NetworkPerformance, CellTower
  writes:  (situational summary — no ontology mutation)
                         │
                         ▼
  STAGE 2  RULES
  "Which towers are critical to restore?"
  reads:   NetworkPerformance, EquipmentHealth, NetworkEquipment, CellTower
  writes:  CellTower.is_critical_restore        ── 15 towers flagged
           CellTower.avg_packet_loss / latency_ms / error_rate / health_score
                         │
                         ▼
  STAGE 3  GRAPH (PageRank)
  "Whose service depends on these towers — and who is socially central?"
  reads:   CallDetailRecord (caller→callee), CDR.routed_through(CellTower)
  writes:  Subscriber.influence_score           ── per subscriber
           CellTower.impact_count               ── distinct subs served
           CellTower.weighted_impact            ── Σ subscriber influence
                         │
                         ▼
  STAGE 4  PREDICTIVE (GNN node regression)
  "What does the forecast say about future demand?"
  reads:   TimeSeriesMetric.subscriber_growth_rate × 365d × 9 regions
           + 12 daily KPIs + 3 lag features + same-region temporal edges
  writes:  CellTower.projected_demand_growth    ── per critical tower
                         │
                         ▼
  STAGE 5  PRESCRIPTIVE (gurobi MIP)
  "What's the optimal $5M tier-selection plan?"
  reads:   CellTower.is_critical_restore        ──►  decision-variable scope
           CellTower.weighted_impact            ──►  objective coefficient
           CellTower.projected_demand_growth    ──►  objective coefficient
           TowerUpgradeOption.cost / capacity_increase / install_weeks
  writes:  TowerUpgradeOption.selected          ── 15 upgrades chosen
                         │
                         ▼
                   Actionable plan,
                   grounded end-to-end in the same ontology.

  ──────────────────────────────────────────────────────────────────
  No glue. No DataFrame ping-pong. No re-derivation per-reasoner.
  Five reasoners, one ontology, one accretive thread.
  ──────────────────────────────────────────────────────────────────
```

---

## Why the chain matters (vs. any single stage)

| Stage alone | What it tells you | What it doesn't |
|---|---|---|
| Descriptive | "WEST is broken" | Which towers, how to fix |
| Rules alone | "These 15 towers are critical" | Which matter most; what to do |
| Graph alone | "These subscribers are influential" | Which towers serve them |
| Predictive alone | "WEST demand is contracting" | Where to spend the recovery budget |
| Prescriptive alone | (won't run — no flagged set, no impact weights, no forecast) | Whole pipeline misses |

| Combined | Output |
|---|---|
| Descriptive → Rules | Crisis scoped + critical-tower set flagged |
| + Graph | Each flagged tower scored by social blast radius |
| + Predictive | Forward-looking demand multiplier per tower |
| + Prescriptive | $5M plan, 122 Gbps, all 15 covered, prioritized by social impact |

**Multi-reasoner chaining grounded in (and contributing to) the ontology.**

---

## Adapting this recipe to a new domain

The chain pattern transfers cleanly. To rebuild for a different problem:

1. Re-run `rai-discovery` on the new business question — does it actually need all 5 reasoner families, or is one or two sufficient?
2. Strip the demo ontology to the concepts the new chain needs (lean is better for type inference and solver compile time).
3. Stage 1 (descriptive triage) is *optional but high-leverage*: it scopes the problem and rules out a misdiagnosis (e.g., is this a retention crisis or a network crisis?) before any rule, graph, GNN, or solver runs.
4. Stages 2–5 are the load-bearing chain: rules write the flag that scopes graph aggregations and the solver's decision variables; graph writes the per-entity impact weight that becomes a solver objective coefficient; predictive writes the forward-looking multiplier that becomes the second objective coefficient; prescriptive composes both upstream signals into the final plan.
5. Keep the validation checks at every stage: assert flagged-set size, PageRank top-N looks plausible, the GNN forecast separates the anomalous segment from the rest, the solve status is OPTIMAL, the objective is not zero, and at least one constraint is binding (otherwise you're under-constrained).

The shape this template demonstrates — *each reasoner writes a property the next reasoner reads* — is what makes the chain accretive rather than serial. The agent skills are how you reliably author each link.

---

## Data Reference

- **Source data**: bundled CSVs in `../data/` (the main template ships ~1.2 MB of synthetic-but-realistic telco data — 250 cell towers, 1,200 subscribers, 6,000 CDRs, 3,285 daily KPI rows across 9 regions).
- **Ontology**: the template's main script uses a focused 7-concept subset of a broader 18-concept telco knowledge graph (PostalArea, Subscriber, Contract, BillingEvent, CellTower, NetworkEquipment, EquipmentHealth, NetworkEvent, CallDetailRecord, SupplierOrder, Campaign, PromotionRedemption, RevenueForecast, NetworkPerformance, SupportTicket, TimeSeriesMetric, TowerUpgradeOption, Part) — sufficient for the four-stage chain.
- **Stages**: implemented in `../telco_network_recovery.py` as a single combined script with stage banners.
