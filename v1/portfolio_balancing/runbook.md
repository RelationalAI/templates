# Runbook: Portfolio Balancing — Multi-Reasoner Walkthrough

Rebalance an 8-stock book under compliance + crisis stress. Rules surface broken positions, graph collapses redundant bets via correlation clustering, prescriptive solves a Markowitz QP across 6 (budget, regime) scenarios. No single reasoner does all three: rules don't allocate, graph doesn't optimize, prescriptive on the full universe stacks near-duplicate cluster members.

## The chain

```
The current book breaks compliance on 4 holdings + 2 sectors. Naive
"diversification" hides correlated bets. The chain collapses 8 stocks
into 5 distinct cluster representatives, traces the efficient frontier
with solver shadow prices (each return-floor dual IS the frontier slope),
and shows crisis vol sits 22-30% above base at every frontier point —
without the cluster collapse, the gap would grow.

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
              (QP, HiGHS)     6 scenarios = 3 budgets x 2 regimes.
                              solve(sensitivity=True): each return-floor dual
                              IS the frontier slope d(var)/d(return). Three
                              drivers (grid/adaptive/dichotomic) place 6 points
                              at equal budget; dichotomic tightest (max chord-
                              gap 202 vs grid 558). Reference base_1000 knee at p3.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Stress       ──►  Stock.regime_covar (PSD-preserving)
                              Crisis vol 22-30% above base across
                              the frontier. Gap peaks mid-frontier
                              (p1 at +29.6%), narrows toward the
                              concentrated end (p5 at +21.7%).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-ontology Build a portfolio ontology from the CSVs in data/. The covariance file is in long form (stock_i, stock_j, value) — model it as a binary property on Stock rather than a separate Concept. Promote sector to its own Concept so downstream rules can aggregate exposure per sector.
```

**Response**

Concepts: `Stock` (with binary `Stock.covar(Stock, Stock)` property carrying covariance), `Sector`, `User`, `Account`, `Holding`, `Transaction` — bound to the bundled CSVs (8 stocks, 64 covariance entries). Stage 3 adds the `Regime` and `Scenario` Concepts (2 regimes x 3 budgets = 6 scenarios).

### 2. Examine ontology

**Prompt**

```
/rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

Concepts: 8 `Stock` across 5 `Sector`, the binary `Stock.covar` covariance property (64 entries), 6 `User`, 4 `Account`, 15 `Holding`, 21 `Transaction` — Stage 3 will introduce `Regime` and `Scenario`.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery Our 8-stock book breaks compliance and concentrates risk. Rebuild it under Markowitz mean-variance with caps, deduplicate redundant bets via correlation clustering, and stress-test under crisis. What questions does each reasoner family handle?
```

**Response**

Plan: rules for compliance flags, graph for correlation clustering + representatives, prescriptive QP indexed by Scenario, stress as regime-swap re-solve.

### 4. Compliance scan

**Prompt**

```
/rai-pyrel Which holdings are overconcentrated (worth more than 15% of their account), which (account, sector) pairs are overweight (more than 30% of the account), and which traders are high-risk (risk score above 0.8 with more than five flagged transactions)?
```

**Response**

4 holdings flagged (AAPL/MSFT on Account 1, JNJ/PFE on Account 4); 2 (account, sector) pairs flagged (Account 1 Tech 34.0%, Account 4 Healthcare 32.2%); 2 users flagged (Alice Chen 0.85, Eve Taylor 0.92).

### 5. Cluster correlated bets

**Prompt**

```
/rai-graph-analysis Which stocks act as redundant bets — pairs with absolute return correlation of at least 0.3? Group them into clusters, pick one representative per cluster by highest Sharpe ratio, and flag the rest so downstream optimization can exclude them.
```

**Response**

4 edges (|rho| >= 0.3), 5 Louvain clusters, intra +0.683 vs inter +0.131. 5 representatives picked: PFE, GOOGL, JPM, PG, XOM. AAPL/MSFT/JNJ flagged `is_non_representative`.

### 6. Solve mean-variance frontier

**Prompt**

```
/rai-prescriptive-problem What's the Markowitz mean-variance frontier across our 6 scenarios (3 budgets — 500, 1000, 2000 — times 2 regimes — base, crisis)? Each scenario must be fully invested; cap any single position at 30% of budget and any sector at 30%; only invest in cluster representatives. Solve with sensitivity enabled so each return-floor constraint returns its shadow price. Trace 6 frontier points per scenario by dual-guided sampling: start from the min-risk and max-return anchors, then add each next return target where the two bracketing points' shadow prices (their tangents) predict the largest gap to the chord — not on a uniform grid, which over-samples the flat low-risk end and crowds the max-return wall.
```

**Response**

48 decision vars (`Stock.x_quantity`, 8 stocks x 6 scenarios; non-reps forced to 0). Constraint families: non-negativity, budget equality (sum = budget per scenario), position cap (30%), sector cap (30%), non-representative = 0, plus a per-scenario epsilon return-rate floor on the sweep solves. HiGHS solves the convex QP to `OPTIMAL` with `sensitivity=True`, returning each return-floor's dual. The reference scenario base_1000 spans return [64.87, 84.00] (rate [0.0649, 0.0840]).

### 7. Read the frontier

**Prompt**

```
/rai-prescriptive-results For the reference scenario (base_1000), list the Pareto frontier with each point's exact shadow price (the return-floor dual), and find the knee — the last point before the marginal risk per unit return jumps the most. Treat the knee as the largest ratio jump between consecutive duals.
```

**Response**

Reference base_1000 frontier: return 64.87 -> 84.00, variance 4641.57 -> 8528.00 across 6 points. The exact return-floor duals rise 0 -> 134.83 -> 192.68 -> 250.64 -> 650.79 -> 1098.00. Knee at p3 — the last point before the largest ratio jump in consecutive duals (250.64 -> 650.79).

### 8. Stress under crisis

**Prompt**

```
/rai-pyrel + /rai-prescriptive-results How much does volatility expand at each frontier point under crisis covariance — where correlations shrink 30% of the way toward all-ones (preserving positive semi-definiteness) — versus the base regime?
```

**Response**

Crisis vol runs 22-30% above base at every frontier point (budget 1000: min_risk 68.13 -> 87.49 at +28.4%, p1 71.99 -> 93.27 at +29.6%). The gap peaks at p1 (+29.6%) and narrows to +21.7% at p5. The gap_% pattern is identical across all three budgets.

### 9. Persist solution concepts into the ontology

**Prompt**

```
/rai-ontology Add a FrontierPoint concept indexed by (Scenario, eps_label) that materializes each Pareto point's metadata: return, risk, marginal risk-per-return, knee flag, base-regime volatility, crisis-regime volatility, and the percentage gap between them.
```

**Response**

Ontology gains a `FrontierPoint(Scenario, eps_label)` Concept (6 scenarios x up to 6 points; adjacent targets that collapse are deduped) with `return`, `risk`, `marginal_risk_per_return`, `is_knee`, `vol_base`, `vol_crisis`, `vol_gap`, `vol_gap_pct`. The frontier shape (base_1000 return 64.87->84.00, variance 4641->8528), knee at p3, and the crisis vol gap (+28.4% min_risk -> +29.6% peak at p1 -> +21.7% at p5) are now queryable as ontology rather than stdout.

## Data

Bundled CSVs in `data/`: `returns.csv` (8 stocks across 5 sectors), `covar.csv` (64 symmetric covariance entries), plus `users.csv` (6), `accounts.csv` (4), `holdings.csv` (15), `transactions.csv` (21). All four stages run in `portfolio_balancing.py`.
