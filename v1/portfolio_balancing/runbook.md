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
                              Min-risk anchor + 5 epsilon points = 6-point
                              frontier per scenario. Knee at eps_1.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Stress       ──►  Stock.regime_covar (PSD-preserving)
                              Crisis vol 25-30% above base across
                              the frontier. Gap peaks mid-frontier
                              (eps_1..eps_2 at +29.8%), narrows
                              toward the concentrated end (+25.2%).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

- Prompt: `/rai-build-starter-ontology Build a portfolio ontology from the CSVs in data/ covering stocks, sectors, the covariance matrix, accounts, holdings, users, and transactions.`
- Response: Concepts: `Stock` (with binary `Stock.covar(Stock, Stock)` property carrying covariance), `Sector`, `User`, `Account`, `Holding`, `Transaction` — bound to the bundled CSVs (8 stocks, 64 covariance entries). Stage 3 adds the `Regime` and `Scenario` Concepts (2 regimes x 3 budgets = 6 scenarios).

### 2. Examine ontology

- Prompt: `/rai-querying Show the ontology as a concept-relationship diagram and report row counts per concept.`
- Response: Concepts: 8 `Stock` across 5 `Sector`, the binary `Stock.covar` covariance property (64 entries), 6 `User`, 4 `Account`, 15 `Holding`, 21 `Transaction` — Stage 5 will introduce `Regime` and `Scenario`.

### 3. Discover reasoner questions

- Prompt: `/rai-discovery Our 8-stock book breaks compliance and concentrates risk. Rebuild it under Markowitz mean-variance with caps, deduplicate redundant bets via correlation clustering, and stress-test under crisis. What questions does each reasoner family handle?`
- Response: Plan: rules for compliance flags, graph for correlation clustering + representatives, prescriptive QP indexed by Scenario, stress as regime-swap re-solve.

### 4. Compliance scan

- Prompt: `/rai-rules-authoring Flag any holding worth more than 15% of its account, any sector worth more than 30% of the account, and any user with a risk score above 0.8 and more than five flagged transactions.`
- Response: 4 holdings flagged (AAPL/MSFT on Account 1, JNJ/PFE on Account 4); 2 (account, sector) pairs flagged (Account 1 Tech 34.0%, Account 4 Healthcare 32.2%); 2 users flagged (Alice Chen 0.85, Eve Taylor 0.92).

### 5. Cluster correlated bets

- Prompt: `/rai-graph-analysis Cluster stocks by correlation — anything above 0.3 absolute is a redundant bet. Pick one representative per cluster (highest Sharpe ratio) and only invest in those.`
- Response: 4 edges (|rho| >= 0.3), 5 Louvain clusters, intra +0.683 vs inter +0.131. 5 representatives picked: PFE, GOOGL, JPM, PG, XOM. AAPL/MSFT/JNJ flagged `is_non_representative`.

### 6. Solve mean-variance frontier

- Prompt: `/rai-prescriptive-problem-formulation Build a Markowitz mean-variance frontier across 6 scenarios = 3 budgets x 2 regimes. Position cap 30% of budget, sector cap 30%, only invest in cluster representatives. Anchor at min-risk and max-return, then sweep 5 epsilon points across the return range.`
- Response: 48 decision vars (`Stock.x_quantity`, 8 stocks x 6 scenarios; non-reps forced to 0). Constraint families: non-negativity, budget equality (sum = budget per scenario), position cap (30%), sector cap (30%), non-representative = 0, plus epsilon return-rate floor on sweep solves. Return-rate range [0.0634, 0.0840]. 6-point frontier per scenario (min-risk anchor + 5 epsilon points); 7 solves per scenario x 6 scenarios = 42 `LOCALLY_SOLVED` portfolios via Ipopt.

### 7. Read the frontier

- Prompt: `/rai-prescriptive-results-interpretation For each scenario, list the six-point Pareto frontier and find the knee — where does the marginal risk per unit return jump the most?`
- Response: base_500 frontier: returns 32.43 -> 40.28, risk 1160 -> 1742. Marginal `delta_risk/delta_return` jumps ~3x at eps_1 (knee). Same shape across all 6 scenarios — risk scales as budget^2, rate-form frontier is budget-independent.

### 8. Stress under crisis

- Prompt: `/rai-prescriptive-solver-management + /rai-prescriptive-results-interpretation Stress-test the frontier under crisis: shrink correlations toward all-ones with weight 0.7 on base covariance + 0.3 on outer-product. How much volatility expansion at each frontier point?`
- Response: Crisis vol 25-30% above base across the frontier (budget 500: min_risk 34.06 -> 43.74 at +28.4%, eps_1 34.30 -> 44.54 at +29.8% peak). Gap peaks mid-frontier (eps_1..eps_2 at +29.8%), narrows to +25.2% at eps_5 — the cluster-collapse payoff.

### 9. Persist solution concepts into the ontology

- Prompt: `/rai-ontology-design The chain already writes the compliance flags, cluster id + representative flag, Stock.x_quantity(Scenario), and Stock.regime_covar. What's still only in pandas/stdout: per-(scenario, frontier-point) metadata (return, risk, marginal risk/return, knee flag) and the base-vs-crisis volatility comparison. Add a FrontierPoint(Scenario, eps_label) Concept holding all post-solve frontier metadata.`
- Response: Ontology gains a `FrontierPoint(Scenario, eps_label)` Concept (36 rows = 6 scenarios x 6 points) with `return`, `risk`, `marginal_risk_per_return`, `is_knee`, `vol_base`, `vol_crisis`, `vol_gap`, `vol_gap_pct`. The frontier shape (32.43->40.28 / 1160->1742 in base_500), knee at eps_1, and crisis vol gap (+28.4% min_risk -> +29.8% peak -> +25.2% eps_5) are now queryable as ontology rather than stdout.

## Data

Bundled CSVs in `data/`: `returns.csv` (8 stocks across 5 sectors), `covar.csv` (64 symmetric covariance entries), plus `users.csv` (6), `accounts.csv` (4), `holdings.csv` (15), `transactions.csv` (21). All four stages run in `portfolio_balancing.py`.
