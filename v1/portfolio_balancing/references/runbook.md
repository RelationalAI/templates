# Runbook: Portfolio Balancing — Multi-Reasoner Walkthrough

Rebalance an 8-stock book under compliance + crisis stress. Rules surface broken positions, graph collapses redundant bets via correlation clustering, prescriptive solves a Markowitz QP across 6 (budget, regime) scenarios. No single reasoner does all three: rules don't allocate, graph doesn't optimize, prescriptive on the full universe stacks near-duplicate cluster members.

## The chain

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

## Workflow

### 0. Discovery

- Prompt: `/rai-discovery Our 8-stock book breaks compliance and concentrates risk. Rebuild it under Markowitz mean-variance with caps, deduplicate redundant bets via correlation clustering, and stress-test under crisis. What questions does each reasoner family handle?`
- Response: Plan: rules for compliance flags, graph for correlation clustering + representatives, prescriptive QP indexed by Scenario, stress as regime-swap re-solve.

### 1. Compliance scan

- Prompt: `/rai-rules-authoring Flag any holding worth more than 15% of its account, any sector worth more than 30% of the account, and any user with a risk score above 0.8 and more than five flagged transactions.`
- Response: 4 holdings flagged (AAPL/MSFT on Account 1, JNJ/PFE on Account 4); 2 (account, sector) pairs flagged (Account 1 Tech 34.0%, Account 4 Healthcare 32.2%); 2 users flagged (Alice Chen 0.85, Eve Taylor 0.92).

### 2. Cluster correlated bets

- Prompt: `/rai-graph-analysis Cluster stocks by correlation — anything above 0.3 absolute is a redundant bet. Pick one representative per cluster (highest Sharpe ratio) and force the rest to zero in optimization.`
- Response: 4 edges (|rho| >= 0.3), 5 Louvain clusters, intra +0.683 vs inter +0.131. 5 representatives picked: PFE, GOOGL, JPM, PG, XOM. AAPL/MSFT/JNJ flagged `is_non_representative`.

### 3. Solve mean-variance frontier

- Prompt: `/rai-prescriptive-problem-formulation Build a Markowitz mean-variance frontier across 6 scenarios = 3 budgets x 2 regimes. Position cap 30% of budget, sector cap 30%, non-representatives forced to zero. Anchor with min-risk and max-return, then sweep 5 epsilon points across the return range.`
- Response: 48 decision vars (8 stocks x 6 scenarios), 5 constraint families. Return-rate range [0.0634, 0.0840]. 7 solves x 6 scenarios = 42 `LOCALLY_SOLVED` portfolios via Ipopt.

### 4. Read the frontier

- Prompt: `/rai-prescriptive-results-interpretation For each scenario, list the seven-point Pareto frontier and find the knee — where does the marginal risk per unit return jump the most?`
- Response: base_500 frontier: returns 32.43 -> 40.28, risk 1160 -> 1742. Marginal `delta_risk/delta_return` jumps ~3x at eps_1 (knee). Same shape across all 6 scenarios — risk scales as budget^2, rate-form frontier is budget-independent.

### 5. Stress under crisis

- Prompt: `/rai-prescriptive-solver-management + /rai-prescriptive-results-interpretation Stress-test the frontier under crisis: shrink correlations toward all-ones with weight 0.7 on base covariance + 0.3 on outer-product. How much volatility expansion at each frontier point?`
- Response: Crisis vol +28-30% above base at every lambda (budget 500: min_risk 34.06 -> 43.74, eps_1 34.30 -> 44.54 peak). Gap peaks mid-frontier, narrows to +25.2% at eps_5 — the cluster-collapse payoff.

## Data

Bundled CSVs in `../data/`: `returns.csv` (8 stocks across 5 sectors), `covar.csv` (64 symmetric covariance entries), plus `users.csv` (6), `accounts.csv` (4), `holdings.csv` (15), `transactions.csv` (21). All four stages run in `../portfolio_balancing.py`.
