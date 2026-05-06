# Runbook: Portfolio Balancing — Multi-Reasoner Walkthrough

Walk-through of the chained-reasoner pattern this template is built on. One realistic portfolio thread — **rebalance an 8-stock universe under compliance + crisis stress** — traced across rules, graph, and prescriptive reasoners, each stage writing properties back to the same ontology that downstream stages consume.

The template's combined script (`portfolio_balancing.py`) implements all four stages directly; this runbook expands the surrounding narrative — what each prompt asks, what shape of output to expect, and how each enrichment feeds the next — so a reader can follow the reasoning thread end-to-end without re-running the script.

---

## TL;DR — the chain in one screen

```
The current book breaks compliance on 4 holdings + 2 sectors. Naive
"diversification" hides correlated bets. The chain collapses 8 stocks
into 5 distinct cluster representatives, traces the efficient frontier
under base + crisis covariance, and shows crisis vol sits 25-30% above
base at every lambda — without the cluster collapse, the gap would grow.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Rules        ──►  Holding.is_overconcentrated         (4)
                              Holding.is_sector_concentrated      (2)
                              User.is_high_risk_trader            (2)
                              4 holdings > 15% of balance, 2 sectors
                              > 30%, 2 traders with risk > 0.8 + flagged.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Graph        ──►  Stock.variance / volatility / correlation
                              Stock.cluster, Stock.is_representative (5)
                              4 edges (|rho| >= 0.3), 5 Louvain clusters,
                              intra +0.683 vs inter +0.131.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Stock.x_quantity (per Scenario)
                 (QP)         6 scenarios = 3 budgets x 2 regimes.
                              Anchors + 5 epsilon points = 7-point
                              frontier per scenario. Knee at eps_1.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Stress       ──►  Stock.regime_covar (PSD-preserving)
                              Crisis vol 25-30% above base at every
                              lambda. Gap peaks mid-frontier, narrows
                              toward the concentrated end.
  ─────────────────────────────────────────────────────────────────
```

A single-reasoner approach can't answer this. Rules alone flag broken positions but don't rebuild the book. Graph alone clusters stocks but doesn't allocate. Prescriptive alone solves a Markowitz QP — but on the full universe it stacks near-duplicate cluster members, and on a single covariance it ignores regime risk. Each stage feeds the next: rules surface the violations, graph collapses redundant bets, prescriptive optimizes over the reduced universe across both regimes in one solve.

---

## How to read this runbook

This runbook serves two audiences:

- **Reading top-to-bottom**: the narrative + ASCII visualizations show what the chain produces stage-by-stage, with the same business framing the stakeholder would see.
- **Per-stage skill blocks**: the boxed `Skill / Prompt` callout at the start of each stage is the recipe — load that RAI agent skill, give it that prompt against the bundled demo data, and the agent will reproduce the stage.

---

## Step 0 — Scope the question with `rai-discovery`

> **Skill:** `rai-discovery` ·
> **Prompt:** "Our 8-stock book breaks compliance and concentrates risk. Rebuild it under Markowitz mean-variance with caps, deduplicate redundant bets via correlation clustering, and stress-test under crisis. What questions does each reasoner family handle?"

Discovery classifies the question by reasoner family and tells you which downstream skills to load:

| Sub-question | Reasoner | Skill |
|---|---|---|
| Where is the current book breaking compliance (per-stock, per-sector, per-trader)? | Rules | `rai-rules-authoring` |
| Which stocks are really the same bet (correlation clusters + cluster representative)? | Graph | `rai-graph-analysis` |
| What's the optimal allocation under position + sector caps for each (budget, regime) scenario? | Prescriptive | `rai-prescriptive-problem-formulation` |
| How does the optimal portfolio degrade under a PSD-preserving crisis covariance? | Prescriptive (re-solve) | `rai-prescriptive-solver-management` + `rai-prescriptive-results-interpretation` |

Discovery's output is a *plan*, not code. Everything that follows materializes that plan.

---

## Setup

See the template's main `README.md` for installation, RAI connection setup, and how to run the script. The narrative below follows the actual stage outputs of `portfolio_balancing.py` against the bundled CSVs in `../data/`.

**Prerequisites**

- Template's `data/` CSVs available — `returns.csv` (8 stocks), `covar.csv` (64 covariance entries), `users.csv`, `accounts.csv`, `holdings.csv`, `transactions.csv`. Or your own Snowflake schema with equivalent tables.
- `raiconfig.yaml` pointing at your RAI engine
- Python >= 3.10 with `relationalai >= 1.0.14`

---

## Workflow

The runbook walks the same chain stage-by-stage, prompt-by-prompt, in agent-skill order. Each row maps to a section of the script.

| # | Step | Skill | Prompt | Expected Output |
|---|------|-------|--------|-----------------|
| 1 | Build ontology | `/rai-build-starter-ontology` | "Build a RAI ontology for portfolio balancing from the CSVs in `data/`. Concepts: Stock (index, ticker, sector, returns, covar), Sector (derived from Stock sectors), User (with risk_score), Account (balance, account_type), Holding (quantity, purchase_price, value), Transaction (amount, category, flagged indicator)." | Model `portfolio` with 6 user-facing concepts. 8 Stocks across 5 sectors (Technology x3, Healthcare x2, Financials, Energy, Consumer Staples). 6 Users, 4 Accounts, 15 Holdings, 21 Transactions. Pairwise `Stock.covar(i, j)` two-arg property loaded from the long-form covariance CSV (64 entries, symmetric). |
| 2 | Discovery | `/rai-discovery` | "What questions can we answer with this ontology? We want to surface compliance violations on the current book, then rebuild it under a Markowitz objective with crisis-regime stress." | Rules: position-limit, sector-concentration, high-risk-trader flags as derived Relationships. Graph: covariance clustering (Louvain on |correlation| >= threshold) -> per-cluster representative by Sharpe -> investable-universe collapse. Prescriptive: bi-objective QP via epsilon constraint over the representative-only universe, indexed by a `Scenario` Concept that combines budget and regime. Stress: same `solve_epsilon` call under a PSD-preserving crisis covariance. Predictive: DATA_GAP (no time series). |
| 3 | Stage 1 — Compliance: overconcentrated holdings | `/rai-rules-authoring` | "Define `Holding.value = quantity * purchase_price`, then flag `Holding.is_overconcentrated` whenever `value > POSITION_LIMIT * Account.balance` (default 15%)." | 4 holdings flagged: AAPL (Account 1, 18.0%), MSFT (Account 1, 16.0%), JNJ (Account 4, 16.0%), PFE (Account 4, 16.2%). All Account-1 (Alice Chen, balance $100K) and Account-4 (Dan Wilson, balance $80K) — both have multiple positions clipping the 15% cap. |
| 4 | Stage 1 — Compliance: sector concentration | `/rai-rules-authoring` | "Aggregate `Holding.value` per (Account, Sector) and flag `Holding.is_sector_concentrated` whenever the sector total > `SECTOR_LIMIT * Account.balance` (default 30%)." | 2 (account, sector) pairs flagged: Account 1 Technology 34.0% (AAPL + MSFT), Account 4 Healthcare 32.5% (JNJ + PFE). Pattern: the same accounts driving Stage 1.3 stack within a sector. Stage 3 enforces the same 30% cap as a hard constraint. |
| 5 | Stage 1 — Compliance: high-risk traders | `/rai-rules-authoring` | "Flag `User.is_high_risk_trader` whenever `risk_score > 0.8` AND > 5 flagged transactions." | 2 users flagged: Alice Chen (risk 0.85), Eve Taylor (risk 0.92). Both have multiple `Transaction.is_flagged == True` rows in the bundled data. Standalone signal — used as a reviewer trigger, not a solver constraint. |
| 6 | Stage 2 — Derive volatility + correlation in PyRel | `/rai-ontology-design` | "Add `Stock.variance` (covariance diagonal where i == j), `Stock.volatility = sqrt(variance)`, and pairwise `Stock.correlation(i, j) = covar(i, j) / (vol_i * vol_j)`. All in PyRel — no numpy precompute." | `Stock.variance` and `Stock.volatility` written for all 8 stocks. `Stock.correlation` two-arg property populated from the 64 covariance pairs. Volatilities span ~0.06 to ~0.10 (small dataset, daily-scale). Storing in the ontology lets every downstream stage read the same source of truth instead of recomputing. |
| 7 | Stage 2 — Cluster the correlation graph | `/rai-graph-analysis` | "Build an undirected `Graph` with `Stock` as `node_concept`. Add an edge wherever `|correlation| >= CORR_THRESHOLD` (default 0.3) and `i < j` (deduplicate symmetric pairs). Run Louvain and persist `Stock.cluster`." | 4 edges retained (8 stocks, sparse graph). Louvain yields 5 communities: Cluster 1 = {JNJ, PFE} (Healthcare), Cluster 2 = {AAPL, MSFT, GOOGL} (Technology), plus singletons Cluster 3 = {JPM}, Cluster 4 = {PG}, Cluster 5 = {XOM}. Intra-cluster avg correlation = +0.683, inter-cluster = +0.131 (~5x separation — clean). |
| 8 | Stage 2 — Pick cluster representatives by Sharpe | `/rai-graph-analysis` | "Define `Stock.sharpe = returns / volatility`. For each cluster, the stock whose Sharpe equals the cluster max is the representative — set `Stock.is_representative`. Singletons are their own representative. Define `Stock.is_non_representative` as the positive complement (the prescriptive rewriter doesn't accept `model.not_(...)` inside a solver `.where()`)." | 5 representatives picked from 8 stocks: Cluster 1 PFE (Healthcare, Sharpe 0.530), Cluster 2 GOOGL (Technology, 0.605), Cluster 3 JPM (Financials, 0.500), Cluster 4 PG (Consumer Staples, 0.444), Cluster 5 XOM (Energy, 0.588). Investable universe shrinks from 8 to 5. Non-representatives — AAPL, MSFT, JNJ — get `Stock.is_non_representative` and are forced to zero in Stage 3. |
| 9 | Stage 3 — Scenario + regime + decision variable | `/rai-prescriptive-problem-formulation` | "Define `Regime` (`base`, `crisis`) and a `Scenario` Concept indexed by name with `budget` and `regime` properties. Load 6 scenarios = {500, 1000, 2000} x {base, crisis}. Add `Stock.regime_covar(i, j, Regime) = base covariance for base; alpha * covar(i,j) + (1 - alpha) * vol_i * vol_j for crisis` (PSD-preserving correlation shrinkage in covariance units, alpha = 0.7). Decision variable: `Stock.x_quantity(Stock, Scenario)` continuous." | 1 `Stock.x_quantity` property, 8 stocks x 6 scenarios = 48 continuous variables (40 of which will be hard-zero from the representative-only constraint). Regime-conditioned covariance lives in the ontology — the QP picks each scenario's matching regime without any branching in solver code. |
| 10 | Stage 3 — Compliance constraints on the decision variable | `/rai-prescriptive-problem-formulation` | "Add: non-negative (`x_qty >= 0`); fully invested per scenario (`sum(x) == Scenario.budget`); per-rep position cap (`x_qty <= REP_POSITION_LIMIT * Scenario.budget`, default 0.30); per-sector cap (`sum(x_qty per sector) <= SECTOR_LIMIT * Scenario.budget`, default 0.30); representative-only (`x_qty == 0` where `Stock.is_non_representative()`)." | 5 constraint families. `REP_POSITION_LIMIT = 0.30` is intentionally higher than Stage 1's `POSITION_LIMIT = 0.15`: a representative carries its cluster's combined exposure, and feasibility requires `REP_POSITION_LIMIT * num_reps >= 1.0` (5 x 0.30 = 1.5, OK). `SECTOR_LIMIT = 0.30` is reused verbatim from Stage 1's compliance threshold — same parameter binds the existing book and the rebuilt one. |
| 11 | Stage 3 — Anchors + epsilon sweep | `/rai-prescriptive-solver-management` | "Anchor 1: minimize risk (no return constraint). Anchor 2: maximize return. Compute return-rate range across all 6 scenarios. Then sweep 5 interior epsilon-rate points uniformly across the rate range and resolve `min risk s.t. return_rate >= eps_rate`. Use Ipopt, time limit 60s." | Per-scenario rate range: [0.0634, 0.0840] per unit invested (regime-independent because `Stock.returns` is regime-independent — only the covariance differs). 7 solves total: 2 anchors + 5 epsilon points = 42 optimal portfolios (6 scenarios x 7 points), all `LOCALLY_SOLVED`. base_500 anchor 1: return 32.43, risk 1160.39. base_500 anchor 2: return 42.00. crisis_500 anchor 1: return 31.69, risk 1913.60 — same investable universe, different regime covariance. |
| 12 | Stage 3 — Pareto + knee | `/rai-prescriptive-results-interpretation` | "For each scenario, list the 7-point frontier (return, risk). Print marginal `delta_risk / delta_return` between adjacent points and identify the knee — where the marginal jumps most." | base_500: returns 32.43 -> 33.41 -> 35.12 -> 36.84 -> 38.56 -> 40.28; risk 1160 -> 1177 -> 1263 -> 1386 -> 1546 -> 1742. Marginal climbs 16.85 -> 49.94 -> 71.72 -> 93.03 -> 114.43. Knee at Point 2 (`eps_1`) — marginal cost jumps ~3x beyond. base_1000 / base_2000 / crisis_* show the same shape (risk scales as budget^2 because the QP is quadratic, but the rate-form frontier is identical). |
| 13 | Stage 4 — Crisis stress comparison | `/rai-prescriptive-results-interpretation` | "From the Stage 3 sweep, emit a side-by-side `vol_base` vs `vol_crisis` table per (budget, lambda). Vol = sqrt(risk). Compute the absolute and percentage gap." | Same 7-point frontier resolved at each budget x regime. Crisis vol sits ~25-30% above base at every lambda. Budget 500: at `min_risk` vol_base 34.06 / vol_crisis 43.74 (+28.4%); at `eps_1` 34.30 / 44.54 (+29.8%); peaks at `eps_1`-`eps_2`; narrows to +25.2% at `eps_5`. The gap peaks mid-frontier and narrows toward the concentrated end — the inversion is the payoff of the cluster collapse: at the concentrated end the optimizer holds the highest-Sharpe distinct bet per cluster (weighted toward Energy/Consumer Staples here, which carry lower crisis correlations than the middle of the frontier). Without the representative collapse, the concentrated end would stack near-duplicates and the crisis gap would grow instead of shrink. |

---

## Stage 1 — Rules: compliance scan

> **Skill:** `rai-rules-authoring` ·
> **Prompt:** "Flag any holding worth more than 15% of its account, any sector worth more than 30% of the account, and any user with a risk score above 0.8 and more than five flagged transactions."

```
COMPLIANCE VIOLATIONS — current book (4 accounts, 15 holdings, 6 users)

  Rule 1: Holding.is_overconcentrated  (position > 15% of balance)
  ────────────────────────────────────────────────────────────────
    AAPL  Account 1   $18,000 / $100,000   18.0%  ─── Alice Chen
    MSFT  Account 1   $16,000 / $100,000   16.0%
    JNJ   Account 4   $12,800 /  $80,000   16.0%  ─── Dan Wilson
    PFE   Account 4   $13,000 /  $80,000   16.2%

  Rule 2: Holding.is_sector_concentrated  (sector > 30% of balance)
  ────────────────────────────────────────────────────────────────
    Account 1   Technology    $34,000 / $100,000   34.0%
    Account 4   Healthcare    $25,800 /  $80,000   32.2%

  Rule 3: User.is_high_risk_trader  (risk_score > 0.8 AND >5 flagged txns)
  ────────────────────────────────────────────────────────────────
    Alice Chen   risk_score 0.85   ── flagged transactions
    Eve Taylor   risk_score 0.92

  ──────────────────────────────────────────────────────────────────
  The same accounts that breach the per-stock cap also breach the
  sector cap — Stage 3 will use the SECTOR_LIMIT (0.30) as a hard
  constraint when rebuilding both books. The trader flag is a
  reviewer signal, not a solver input.
  ──────────────────────────────────────────────────────────────────

  Holding.is_overconcentrated         [4]
  Holding.is_sector_concentrated      [2]
  User.is_high_risk_trader            [2]
```

`POSITION_LIMIT` (0.15) and `SECTOR_LIMIT` (0.30) are top-level constants. `SECTOR_LIMIT` is reused verbatim by Stage 3; `POSITION_LIMIT` is replaced in Stage 3 by `REP_POSITION_LIMIT = 0.30` because a representative carries its cluster's combined exposure (and 5 reps x 0.20 = 1.00 would already pin the budget — 0.30 leaves headroom).

---

## Stage 2 — Graph: covariance clustering + cluster representatives

> **Skill:** `rai-graph-analysis` ·
> **Prompt:** "Cluster stocks by correlation — anything above 0.3 absolute is a redundant bet. Pick one representative per cluster (highest Sharpe ratio) and force the rest to zero in optimization."

**Construction** — undirected, unweighted graph:
- Node concept: `Stock` (8 nodes)
- Edges built from the derived `Stock.correlation(i, j)` property where `|correlation| >= 0.3` and `i < j`
- Aggregator: `"sum"` (no parallel edges expected)

**Algorithm:** `louvain()` for community detection.

**Volatility, correlation, and crisis covariance are all PyRel derived properties** — no numpy precompute. The covariance matrix loaded from `covar.csv` is the only solver input not derived from another property.

```
DERIVED IN PYREL
  Stock.variance         <- covar(i, j) where i == j
  Stock.volatility       <- sqrt(variance)
  Stock.correlation(i,j) <- covar(i, j) / (vol_i * vol_j)

CORRELATION GRAPH
  Edges with |correlation| >= 0.30:    4
  Stocks above threshold pairwise:     {AAPL,MSFT}, {AAPL,GOOGL},
                                       {MSFT,GOOGL}, {JNJ,PFE}

LOUVAIN COMMUNITIES                   5 clusters
  Cluster 1 (size 2):  JNJ (Healthcare), PFE (Healthcare)
  Cluster 2 (size 3):  AAPL (Technology), MSFT (Technology),
                       GOOGL (Technology)
  Cluster 3 (size 1):  JPM (Financials)              ← singleton
  Cluster 4 (size 1):  PG  (Consumer Staples)        ← singleton
  Cluster 5 (size 1):  XOM (Energy)                  ← singleton

  Avg correlation:  intra-cluster = +0.683
                    inter-cluster = +0.131           ── ~5x separation
```

Singletons (Cluster 3-5) are their own representatives. The non-trivial choice happens inside Cluster 1 (JNJ vs PFE) and Cluster 2 (AAPL/MSFT/GOOGL):

```
REPRESENTATIVE = HIGHEST SHARPE PER CLUSTER  (returns / volatility)

  Cluster 1 (Healthcare):
    JNJ    Sharpe 0.500           PFE    Sharpe 0.530   ← REP

  Cluster 2 (Technology):
    AAPL   Sharpe 0.582           MSFT   Sharpe 0.560
    GOOGL  Sharpe 0.605   ← REP

  Cluster 3 (Financials):  JPM   Sharpe 0.500   ← REP (singleton)
  Cluster 4 (Consumer Staples): PG  Sharpe 0.444   ← REP (singleton)
  Cluster 5 (Energy):  XOM   Sharpe 0.588   ← REP (singleton)

  ──────────────────────────────────────────────────────────────────
  Investable universe collapses 8 -> 5.
  AAPL, MSFT, JNJ get Stock.is_non_representative — Stage 3 forces
  their decision variables to zero.

  This is "collapse, don't cap" — Stage 3 doesn't allow the full 8
  with caps inside a redundant cluster; it removes the duplicates
  before the optimizer sees them.
  ──────────────────────────────────────────────────────────────────

  ✓ Stock.variance / volatility / correlation written back  [8 / 8 / 64]
  ✓ Stock.cluster, Stock.sharpe, Stock.cluster_max_sharpe   [8 each]
  ✓ Stock.is_representative                                 [5]
  ✓ Stock.is_non_representative                             [3]
```

---

## Stage 3 — Prescriptive: bi-objective QP with epsilon constraint

> **Skill:** `rai-prescriptive-problem-formulation` ·
> **Prompt:** "Build a Markowitz mean-variance frontier across 6 scenarios = 3 budgets × 2 regimes. Position cap 30% of budget, sector cap 30%, non-representatives forced to zero. Anchor with min-risk and max-return, then sweep 5 epsilon points across the return range."

```
FORMULATION

  Decision variable
    Stock.x_quantity(Stock, Scenario)   continuous, >= 0
      8 stocks x 6 scenarios = 48 vars
      40 forced to 0 by Stock.is_non_representative()
      8 active = 5 representatives x — wait: 5 reps x 6 scenarios = 30
      (the 18 singleton non-rep slots are also forced — same effect)

  Scenarios (3 budgets x 2 regimes = 6 tuples)
    base_500  base_1000  base_2000   crisis_500  crisis_1000  crisis_2000

  Constraints (per scenario)
    1. Non-negative                  x_qty >= 0
    2. Fully invested                sum(x_qty) == Scenario.budget
    3. Per-rep position              x_qty <= 0.30 * Scenario.budget
    4. Per-sector                    sum(x_qty per sector) <= 0.30 * Scenario.budget
    5. Representative-only           x_qty == 0 where is_non_representative

  Risk objective (regime-aware)
    minimize  Sigma_ij  regime_covar(i, j, Scenario.regime) * x_i * x_j
              └── PyRel-derived per regime; PSD-preserving for crisis ──┘

  Return constraint (epsilon, scaled by budget)
    sum(Stock.returns * x_qty)  >=  eps_rate * Scenario.budget

──────────────────────────────────────────────────────────────────────
SOLVE  (Ipopt, time limit 60s)   →   LOCALLY_SOLVED
  Anchor 1 (min risk)   + Anchor 2 (max return)   + 5 epsilon points
  = 7 solves, 42 optimal portfolios (one per scenario per point)
──────────────────────────────────────────────────────────────────────

ANCHOR 1 — minimize risk (no return floor)
  base_500     return  32.43    risk  1,160.39
  base_1000    return  64.87    risk  4,641.57
  base_2000    return 129.73    risk 18,566.28
  crisis_500   return  31.69    risk  1,913.60   ← higher risk, same universe
  crisis_1000  return  63.37    risk  7,654.40
  crisis_2000  return 126.75    risk 30,617.59

ANCHOR 2 — maximize return
  base_500 / crisis_500       return  42.00
  base_1000 / crisis_1000     return  84.00
  base_2000 / crisis_2000     return 168.00
                              (returns are regime-independent)

Return-rate range  [0.0634, 0.0840]  per unit invested
Epsilon sweep      5 interior points evenly spaced across the range
```

---

## Stage 3 — Reading the frontier (per scenario)

> **Skill:** `rai-prescriptive-results-interpretation` ·
> **Prompt:** "For each scenario, list the seven-point Pareto frontier and find the knee — where does the marginal risk per unit return jump the most? Is the rate-form frontier shape consistent across budgets?"

```
EFFICIENT FRONTIER — base_500  (budget = 500, regime = base)

  #     Label       Return        Risk
  ────────────────────────────────────────
  1     min_risk     32.43    1,160.39
  2        eps_1     33.41    1,176.78    ← KNEE
  3        eps_2     35.12    1,262.61
  4        eps_3     36.84    1,385.89
  5        eps_4     38.56    1,545.79
  6        eps_5     40.28    1,742.47
  7     max_return   42.00    (separate anchor)

  Marginal delta_risk / delta_return:
    min_risk → eps_1     16.85
    eps_1   → eps_2     49.94    ← +3.0x  ── KNEE
    eps_2   → eps_3     71.72
    eps_3   → eps_4     93.03
    eps_4   → eps_5    114.43

  ──────────────────────────────────────────────────────────────────
  base_1000 / base_2000 / crisis_* show the SAME shape — risk scales
  as budget^2 (the QP is quadratic in x), but the rate-form frontier
  and the knee location are budget-independent.
  ──────────────────────────────────────────────────────────────────

  ✓ Stock.x_quantity written back, indexed by (Stock, Scenario)
```

---

## Stage 4 — Crisis stress test

> **Skill:** `rai-prescriptive-solver-management` + `rai-prescriptive-results-interpretation` ·
> **Prompt:** "Stress-test the frontier under crisis: shrink correlations toward all-ones with weight 0.7 on base covariance + 0.3 on outer-product. How much volatility expansion at each frontier point — does the gap peak mid-frontier or at the concentrated end?"

Same `solve_epsilon` call, no separate model — `Scenario.regime` selects between two `Stock.regime_covar` definitions:

- `base`:   Sigma(i, j)
- `crisis`: alpha * Sigma(i, j) + (1 - alpha) * vol_i * vol_j   (alpha = 0.7)

The crisis formula is correlation shrinkage toward all-ones (`rho_crisis = alpha * rho + (1 - alpha) * J`) re-expressed in covariance units. PSD is preserved by construction (convex combination of PSD matrices), so every lambda solves cleanly.

```
VOLATILITY COMPARISON  vol = sqrt(risk)

  Budget 500:
       Label     vol_base    vol_crisis      gap     gap_%
       ────────────────────────────────────────────────────
    min_risk      34.06        43.74      +9.68    +28.4%
       eps_1      34.30        44.54     +10.24    +29.8%   ← peak
       eps_2      35.53        46.11     +10.58    +29.8%
       eps_3      37.23        47.94     +10.72    +28.8%
       eps_4      39.32        49.99     +10.68    +27.2%
       eps_5      41.74        52.27     +10.53    +25.2%

  Budget 1000 + Budget 2000: same gap_% pattern (vol scales with budget;
  the rate-form gap is budget-independent).

  ──────────────────────────────────────────────────────────────────
  Crisis vol sits 25-30% above base at EVERY lambda. The gap PEAKS in
  the middle of the frontier (eps_1..eps_2 at +29.8%) and NARROWS at
  the concentrated end (eps_5 at +25.2%).

  Why the inversion: at the concentrated end the optimizer is picking
  the highest-Sharpe distinct bet per cluster — the bundled data
  weights this toward Energy + Consumer Staples, which happen to
  carry lower crisis correlations than the middle of the frontier.
  Without the representative collapse, the concentrated end would
  stack near-duplicates and the crisis gap would GROW, not shrink.
  ──────────────────────────────────────────────────────────────────

  ✓ Stock.regime_covar written back (64 base + 64 crisis = 128 entries)
```

**Why `Scenario` is a Concept, not a loop:** all 6 (budget, regime) tuples solve in a single call to the solver, against the matching `regime_covar`. Adding a fourth regime or a fifth budget is a data edit in `scenario_data`, not a change to `solve_epsilon`. Scenarios are data.

---

## Stage outputs — what each reasoner contributes back

```
ONTOLOGY ENRICHMENT — what each stage wrote back

  Stage 1 (rules)         Holding.value                           [15]
                          Holding.is_overconcentrated             [4]
                          Holding.is_sector_concentrated          [2]
                          User.is_high_risk_trader                [2]

  Stage 2 (graph)         Stock.variance                          [8]
                          Stock.volatility                        [8]
                          Stock.correlation (i, j)                [64]
                          Stock.cluster                           [8]
                          Stock.sharpe                            [8]
                          Stock.cluster_max_sharpe                [8]
                          Stock.is_representative                 [5]
                          Stock.is_non_representative             [3]

  Stage 3 (prescriptive)  Stock.regime_covar (i, j, Regime)       [128]
                          Stock.x_quantity (Stock, Scenario)      [48]

  Stage 4 (stress)        (terminal — vol_base vs vol_crisis table)

  ──────────────────────────────────────────────────────────────────
  Each stage reads what the previous stage wrote.
  Re-running any downstream stage automatically picks up enrichments.
  No glue code, no DataFrame round-trip — same ontology throughout.
  ──────────────────────────────────────────────────────────────────
```

---

## The chain — accretive ontology enrichment

```
THE PORTFOLIO-BALANCING CHAIN

  STAGE 1  RULES
  "Where is the current book breaking compliance?"
  reads:   Holding, Account, User, Transaction, Stock.sector
  writes:  Holding.value
           Holding.is_overconcentrated / is_sector_concentrated
           User.is_high_risk_trader
                         │
                         ▼
  STAGE 2  GRAPH (Louvain)
  "Which stocks are really the same bet?"
  reads:   Stock.covar (loaded), Stock.returns
  writes:  Stock.variance / volatility / correlation (i, j)
           Stock.cluster                  ── 5 communities
           Stock.sharpe / cluster_max_sharpe
           Stock.is_representative        ── 5 of 8 stocks
           Stock.is_non_representative    ── forced to zero in Stage 3
                         │
                         ▼
  STAGE 3  PRESCRIPTIVE (Ipopt QP)
  "What's the optimal allocation under position + sector caps,
   for each (budget, regime) scenario?"
  reads:   Stock.is_representative       ──►  decision-variable scope
           Stock.is_non_representative   ──►  hard-zero constraint
           Stock.returns                 ──►  epsilon return target
           Stock.regime_covar            ──►  quadratic risk objective
           Scenario.budget / regime      ──►  per-scenario constraints
           SECTOR_LIMIT (= Stage 1's)    ──►  hard sector cap
  writes:  Stock.regime_covar (PSD-preserving)  [base + crisis]
           Stock.x_quantity (Stock, Scenario)   [42 active portfolios]
                         │
                         ▼
  STAGE 4  STRESS (same solver, regime swap)
  "How does the optimal portfolio degrade under a crisis covariance?"
  reads:   Stock.regime_covar (regime = "crisis")
           Stage 3's pareto results
  writes:  (terminal — vol gap table)

  ──────────────────────────────────────────────────────────────────
  No glue. No DataFrame ping-pong. No re-derivation per-reasoner.
  Three reasoner families, one ontology, one accretive thread.
  Stage 4 is a regime swap on the same solve — not a separate model.
  ──────────────────────────────────────────────────────────────────
```

---

## Why the chain matters (vs. any single stage)

| Stage alone | What it tells you | What it doesn't |
|---|---|---|
| Rules alone | "4 holdings + 2 sectors break compliance" | How to rebuild the book |
| Graph alone | "AAPL/MSFT/GOOGL move together; JNJ/PFE move together" | Which to keep, how much to allocate |
| Prescriptive alone (full universe) | A "diversified" frontier that stacks near-duplicates inside a cluster | That two of those names are one bet — and that the crisis gap will grow under stress |
| Prescriptive alone (single regime) | A base-case efficient frontier | What it costs you when correlations spike |

| Combined | Output |
|---|---|
| Rules → Graph | Compliance violations + redundant-bet map |
| + Prescriptive (rep-only universe) | 7-point Pareto frontier per scenario; knee at eps_1 |
| + Stress (Scenario.regime swap) | Crisis vol 25-30% above base, gap narrows at concentrated end (the cluster-collapse payoff) |

**Multi-reasoner chaining grounded in (and contributing to) the ontology.**

---

## Crisis Regime Construction

**Do not** naively scale off-diagonal covariance by a constant — it frequently breaks positive semidefiniteness, the lambda=0 pure min-variance solve fails (Ipopt rejects non-convex QP), and the whole frontier anchors wrong. PSD-preserving alternatives:

| Approach | Formula | Preserves PSD? |
|----------|---------|----------------|
| **Correlation shrinkage toward all-ones** (this template) | `rho' = alpha * rho + (1 - alpha) * J`, alpha in [0.6, 0.9]. In covariance units: `cov'(i,j) = alpha * cov(i,j) + (1 - alpha) * vol_i * vol_j` | Yes (convex combination of PSD matrices) |
| Eigenvalue flooring | Eigendecompose, replace lambda_i with max(lambda_i, eps), recompose | Yes by construction |
| Scale off-diagonals + PSD projection | Scale, then find nearest PSD matrix via eigendecomposition | Yes after projection |
| ~~Uniform 1.5x off-diagonals~~ | `Sigma'[i,j] = 1.5 * Sigma[i,j]` for i != j | **No** — frequently non-PSD |

`CRISIS_ALPHA = 0.7` produces a clearly "crisis-like" regime (intra-cluster correlations bump toward 1) while keeping the QP well-conditioned at every lambda. Lower values (0.5-0.6) give more severe crises; values > 0.9 get close to the base case.

---

## Data Reference

- **Source data**: bundled CSVs in `../data/` (8 stocks across 5 sectors with 64-entry symmetric covariance, 6 users, 4 accounts, 15 holdings, 21 transactions). To run against your own Snowflake schema instead, swap the `read_csv(...)` loads for `model.Table(...)` references in `portfolio_balancing.py`; the rest of the pipeline is unchanged.
- **Stages**: implemented in `../portfolio_balancing.py` as a single combined script with stage banners (Stage 1 → Stage 4).
- **Ontology**: 6 user-facing concepts (`Stock`, `Sector`, `User`, `Account`, `Holding`, `Transaction`) plus the `Regime` and `Scenario` concepts introduced in Stage 3. Run `inspect.schema(model)` after the pipeline (see template README) to dump the full concept/property/relationship surface, filtering out reasoner-owned concepts (`Variable`, `Constraint`, etc.) and the auto-generated `graph<id>_Edge` from Stage 2.

---

## Adapting this recipe to a new domain

The chain pattern transfers cleanly. To rebuild for a different problem:

1. Re-run `rai-discovery` on the new business question — does it actually need all four reasoner roles (rules, graph, prescriptive, prescriptive re-solve), or is one or two sufficient? A pure compliance audit stops after Stage 1; a rebalancer without redundant bets in the universe can skip Stage 2.
2. Strip the demo ontology to the concepts the new chain needs (lean is better for type inference and solver compile time). For portfolio variants, the load-bearing concepts are the asset entity (here `Stock`), its pairwise covariance, an entity that holds compliance thresholds (here `Account`), and the `Scenario` Concept that parameterizes the optimizer.
3. Stage 1 (rules) is where every threshold the optimizer will later enforce gets named once and reused — keep `SECTOR_LIMIT` (or its equivalent) shared between the compliance scan and the prescriptive constraints, so the rebuilt book obeys the same caps the diagnostic flagged.
4. Stages 2–4 are the load-bearing chain: Graph collapses redundant bets via clustering + per-cluster representative selection, writing `is_representative` and `is_non_representative` flags the optimizer reads. Prescriptive uses those flags to scope the decision variable and adds the position + sector caps. The stress-test stage is the *same solver call* under a regime-swapped covariance — `Scenario.regime` and `Stock.regime_covar(i, j, Regime)` keep base and crisis as data, not separate models.
5. Keep the validation checks at every stage: assert flagged-set size, the cluster count and intra-vs-inter average correlation gap, anchor solves return `LOCALLY_SOLVED`, the return-rate range is non-degenerate, and `REP_POSITION_LIMIT * num_representatives >= 1.0` so the fully-invested constraint stays feasible.
6. When constructing a stress regime, never naively scale off-diagonal covariance — eigenvalue flooring, projection to nearest PSD, or correlation shrinkage toward all-ones (this template) all preserve PSD; arbitrary scaling does not, and the min-risk anchor will fail.

The shape this template demonstrates — *each reasoner writes a property the next reasoner reads* — is what makes the chain accretive rather than serial. The agent skills are how you reliably author each link.
