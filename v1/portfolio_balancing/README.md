---
title: "Portfolio Balancing"
description: "Multi-reasoner template: rules-based compliance, covariance clustering, and bi-objective Markowitz optimization that uses solver shadow prices to trace the risk-return frontier, with a crisis-regime stress test."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Prescriptive
  - Rules-based
  - Graph
tags:
  - Quadratic Programming
  - Risk Minimization
  - Portfolio Optimization
  - Multi-Objective
  - Sensitivity Analysis
  - Shadow Prices
  - Scenario Analysis
  - HiGHS
  - Multi-Reasoner
  - Chained Reasoning
  - Compliance
  - Graph Analysis
  - Community Detection
  - Stress Testing
---

# Portfolio Balancing

## What this template is for

Portfolio managers don't want to pay twice for the same exposure -- if two funds track nearly the same benchmark, owning both is one bet with worse bookkeeping. This template chains four reasoning stages on a single shared ontology to build compliant, risk-optimized portfolios across an 8-stock universe and stress-test them under a crisis regime.

It uses RelationalAI's **rules**, **graph**, and **prescriptive** reasoners in a chained workflow:

1. **Rules** scan the current book for compliance violations -- overconcentrated holdings (> 15% of balance), sector concentration (> 30%), and high-risk traders -- as derived Relationships.
2. **Graph** builds a correlation graph from the covariance matrix, runs Louvain clustering, and picks the highest-Sharpe stock per cluster as the cluster's **representative**. 8 stocks collapse to 5 distinct bets; near-duplicates are dropped from the investable universe rather than capped within it.
3. **Prescriptive optimization** solves a bi-objective Markowitz QP on the representative-only universe under position and sector caps, using the solver's shadow prices (constraint duals) to trace the efficient frontier efficiently across a `Scenario` Concept that combines three budgets and two regimes.
4. **Crisis stress test** is the same `solve_epsilon` call -- no separate model -- but `Scenario.regime` picks a PSD-preserving shrinkage covariance, so base and crisis frontiers come out of one pipeline.

Each stage writes derived properties the next reads directly: Rules define the thresholds Stage 3 enforces as constraints, Stage 2's `Stock.is_representative` shapes the decision space, and the stress test reads `Stock.regime_covar` keyed by `Scenario.regime`. See "How it works" for the full data flow.

## Why this problem matters

The cost of paying twice for one exposure is concrete: allocating $4k to one fund and $5k to a near-identical one is functionally a single $9k bet with worse bookkeeping. Sector labels alone miss this: two tech ETFs can share a Technology label and still be near-duplicates, or two instruments from different sectors can co-move strongly enough that owning both is redundant. And base-case optimization is optimistic -- under crisis regimes (correlations spike toward 1), everything that hasn't been deduplicated hurts twice.

The four-stage approach addresses each gap. Stage 1 surfaces existing violations in the current book (diagnostic). Stage 2 clusters by return covariance and picks the highest-Sharpe representative per cluster, collapsing redundant bets. Stage 3 optimizes over the representative-only universe under position and sector limits. Stage 4 re-solves under a PSD-preserving crisis covariance to stress the resulting portfolio.

### Key design patterns demonstrated

- **Shared compliance thresholds** -- `SECTOR_LIMIT` is defined once and enforced in both stages. `POSITION_LIMIT` (Stage 1 per-stock compliance) and `REP_POSITION_LIMIT` (Stage 3 per-representative cap) are deliberately different: a representative carries its cluster's combined exposure, so the construction-side cap is higher than the holdings-side compliance cap
- **Graph results feed optimization** -- Louvain cluster ids and per-cluster argmax (highest Sharpe) both persist on `Stock`, and the optimizer's `Stock.is_non_representative()` constraint forces non-reps to zero (complement defined positively because the prescriptive rewriter doesn't accept `model.not_()` in a solver `.where()`)
- **Collapse, don't cap** -- the graph stage reduces the investable universe to distinct bets rather than allowing all N stocks and capping within redundant groups
- **Scenario Concept for parameter sweeps** -- `Scenario` entities combine budget ($500, $1,000, $2,000) and regime (base, crisis) so each epsilon solve handles all six combinations in one call
- **Shadow-price-guided frontier** -- each `solve(sensitivity=True)` returns the return-constraint's dual (shadow price), which IS the frontier's local slope d(variance)/d(return). Three drivers (grid, adaptive, dichotomic) use that dual to place sample points; at equal solve budget the dual-guided drivers approximate the frontier far more tightly than blind even spacing
- **Epsilon constraint method** -- `solve_epsilon(eps_rate)` minimizes variance subject to a return-target floor, producing one Pareto point per call without manually fixing return values
- **PSD-preserving stress covariance** -- correlation shrinkage toward all-ones keeps the QP convex at every point, unlike naive off-diagonal scaling
- **Quadratic programming via HiGHS** -- the risk objective is quadratic (`x' * Cov * x`); HiGHS solves the convex QP to a global optimum and, with `sensitivity=True`, returns the duals the frontier search relies on
- **Anchor solves establish feasible range** -- Anchor 1 (minimize risk) and Anchor 2 (maximize return) bracket the return range before the frontier search

## Who this is for

- Quantitative analysts and portfolio managers exploring mean-variance optimization
- Data scientists learning quadratic programming with RelationalAI
- Finance students studying the Markowitz efficient frontier
- Anyone interested in risk-return trade-off analysis with scenario comparisons

## What you'll build

- A rules-based compliance pipeline using RAI derived properties and Relationships to flag overconcentrated holdings, sector concentration violations, and high-risk traders
- A correlation graph over stocks with Louvain community detection, plus per-cluster representative selection by highest Sharpe
- A quadratic programming model that minimizes portfolio variance subject to position and sector limits on a representative-only universe (non-reps forced to zero)
- Budget and no-short-selling constraints across multiple (budget, regime) scenarios
- Shadow-price-guided frontier tracing: three drivers (grid, adaptive, dichotomic) that use solver duals to sample the efficient frontier, compared head-to-head at equal solve budget
- Anchor solves to establish the feasible return range
- Pareto analysis with exact dual marginals (shadow prices) and knee detection
- A crisis-regime stress test using PSD-preserving correlation shrinkage to compare base vs crisis frontiers side-by-side

## What's included

- `portfolio_balancing.py` -- Main script with all four stages: rules-based compliance, covariance clustering (Louvain), bi-objective QP with shadow-price-guided frontier tracing, and crisis-regime stress test
- `data/returns.csv` -- Stock universe: index, ticker, sector, expected returns (8 stocks)
- `data/covar.csv` -- Covariance matrix entries (i, j, covariance value)
- `data/users.csv` -- User profiles with risk scores
- `data/accounts.csv` -- Account balances
- `data/holdings.csv` -- Current holdings per account and stock
- `data/transactions.csv` -- Transaction history with flagged-transaction indicators
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.
- A prescriptive-capable RAI engine. The frontier tracing solves the convex QP with HiGHS and requests sensitivity (`solve("highs", sensitivity=True)`), which returns the return-constraint duals (shadow prices) the frontier search relies on.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.9.0

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/portfolio_balancing.zip
   unzip portfolio_balancing.zip
   cd portfolio_balancing
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python portfolio_balancing.py
   ```

6. Expected output (sample -- full output covers all four stages):
   ```text
   ======================================================================
   STAGE 1: COMPLIANCE ANALYSIS (rules)
   ======================================================================

   --- Rule 1: Overconcentrated Holdings (position > 15% of balance) ---
     holding_id=1, ticker=AAPL, account_id=1, value=18000.00, balance=100000.00, pct=18.0%
     ...
   --- Rule 2: Sector Concentration (sector > 30% of balance) ---
     account_id=1, sector=Technology, sector_value=34000.00, pct=34.0%
     ...
   --- Rule 3: High Risk Traders (risk_score > 0.8 AND >5 flagged txns) ---
     user_id=1, name=Alice Chen, risk_score=0.85
     ...

   ======================================================================
   STAGE 2: GRAPH -- Covariance Clustering (Louvain)
   ======================================================================
     Correlation graph: 4 edges (|correlation| >= 0.3)
     Louvain communities: 5 cluster(s)
       Cluster 1 (size 3): AAPL (Technology), MSFT (Technology), GOOGL (Technology)
       Cluster 2 (size 2): JNJ (Healthcare), PFE (Healthcare)
       Cluster 3 (size 1): XOM (Energy)
       Cluster 4 (size 1): PG (Consumer Staples)
       Cluster 5 (size 1): JPM (Financials)

     Avg correlation: intra-cluster = +0.683, inter-cluster = +0.131

     Cluster representatives (5 of 8 stocks, picked by highest Sharpe):
       Cluster 1: GOOGL (Technology) -- Sharpe = 0.605
       Cluster 2: PFE (Healthcare) -- Sharpe = 0.530
       Cluster 3: XOM (Energy) -- Sharpe = 0.588
       Cluster 4: PG (Consumer Staples) -- Sharpe = 0.444
       Cluster 5: JPM (Financials) -- Sharpe = 0.500

   ======================================================================
   STAGE 3: BI-OBJECTIVE OPTIMIZATION
   (position + sector limits on representative universe; base & crisis regimes)
   ======================================================================

   ANCHOR SOLVE 1: Minimize risk (no return constraint)
   Status: OPTIMAL
     base_500:    return = 32.4336, risk =   1160.3926
     base_1000:   return = 64.8673, risk =   4641.5705
     base_2000:   return = 129.7346, risk =  18566.2819
     crisis_500:  return = 31.6873, risk =   1913.5995
     crisis_1000: return = 63.3745, risk =   7654.3981
     crisis_2000: return = 126.7490, risk =  30617.5925

   ANCHOR SOLVE 2: Maximize return (swap objective)
   Status: OPTIMAL
     base_500:    return = 42.0000
     base_1000:   return = 84.0000
     base_2000:   return = 168.0000
     crisis_500:  return = 42.0000
     crisis_1000: return = 84.0000
     crisis_2000: return = 168.0000

   Reference scenario 'base_1000': frontier spans expected return [64.8673, 84.0000]

   ======================================================================
   SENSITIVITY-GUIDED FRONTIER  (reference 'base_1000', 6-solve budget per method)
   ======================================================================
     running grid driver ...
     running adaptive driver ...
     running dichotomic driver ...

   Frontier approximation quality (same solve budget, lower gap = better):
     method        solves     max chord-gap
     --------------------------------------
     grid               6          557.9250
     adaptive           6          415.1730
     dichotomic         6          202.2972  <- tightest

   Shadow price = frontier slope (exact dual vs finite-difference secant):
     (dual = extra variance incurred per unit of additional required return)
         return      variance   dual (lambda)        secant
     ------------------------------------------------------
        64.8673     4641.5705            0.00            --
        71.2734     5181.9733          134.83         84.36
        75.9396     5946.0980          192.68        163.75
        80.4605     6944.2401          250.64        220.79
        83.1779     7809.1748          650.79        318.29
        84.0000     8528.0000         1098.00        874.39

   ======================================================================
   STAGE 4: CRISIS REGIME STRESS TEST
   (PSD-preserving correlation shrinkage, alpha = 0.7)
   ======================================================================

   EFFICIENT FRONTIER: Risk vs Return (per scenario, exact dual marginals)

     base_1000 (budget=1000, regime=base):
       #     Label     Return         Risk    Marginal   Knee
     --------------------------------------------------------
       1  min_risk      64.87    4641.5705        0.00
       2        p1      71.27    5181.9733      134.83
       3        p2      75.94    5946.0980      192.68
       4        p3      80.46    6944.2401      250.64  <--
       5        p4      83.18    7809.1748      650.79
       6        p5      84.00    8528.0000     1098.00

     (similar tables for base_500, base_2000, crisis_500, crisis_1000, crisis_2000)

     Volatility (sqrt risk) -- base vs crisis at each frontier point:

     Budget 1000:
         Label     vol_base   vol_crisis        gap    gap_%
     -------------------------------------------------------
      min_risk      68.1291      87.4894   +19.3603   +28.4%
            p1      71.9859      93.2657   +21.2798   +29.6%
            p2      77.1109      98.5270   +21.4161   +27.8%
            p3      83.3321     104.3961   +21.0640   +25.3%
            p4      88.3695     109.1925   +20.8230   +23.6%
            p5      92.3472     112.3478   +20.0006   +21.7%

     (similar tables for Budget 500 and Budget 2000, identical gap_% pattern)
   ```

   Crisis volatility sits ~22-30% above base at every frontier point and the gap peaks in the middle of the frontier (p1 at +29.6%), not at the concentrated end (p5 at +21.7%). That inversion is the payoff of the representative-only universe: at the concentrated end the optimizer is picking the highest-Sharpe distinct bet per cluster, which incidentally sits in sectors with lower crisis correlations (Energy, Consumer Staples). Without the representative collapse, the concentrated end would stack near-duplicates and see the crisis gap grow, not shrink.

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── portfolio_balancing.py
└── data/
    ├── returns.csv
    ├── covar.csv
    ├── users.csv
    ├── accounts.csv
    ├── holdings.csv
    └── transactions.csv
```

## How it works

This section walks through the highlights in `portfolio_balancing.py`.

### Reasoner overview

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1 | Rules | Holding, Account, User, Transaction, Stock | Holding.is_overconcentrated, Holding.is_sector_concentrated, User.is_high_risk_trader | 4 overconcentrated holdings (AAPL 18%, MSFT 16%, JNJ 16%, PFE 16.2%). 2 sector concentrations (Technology 34%, Healthcare 32.2%). 2 high-risk traders (Alice Chen 0.85, Eve Taylor 0.92). |
| 2 | Graph (Louvain) | Stock.covar (diagonal for variance), derived Stock.correlation filtered at threshold 0.3 | Stock.variance, Stock.volatility, Stock.correlation, Stock.cluster, Stock.sharpe, Stock.cluster_max_sharpe, Stock.is_representative | 4 edges retained after thresholding. Louvain yields 5 clusters; 5 representatives picked by highest Sharpe (one per cluster). Collapses 8 stocks to 5 distinct bets. |
| 3 | Prescriptive (QP) | Stock.returns, Stock.regime_covar, Stock.is_representative, Scenario.budget, Scenario.regime | Stock.x_quantity indexed by Scenario (non-reps forced to 0) | Min-risk and max-return anchors bracket the frontier. `solve(sensitivity=True)` returns the constraint dual (shadow price) at each point; three drivers (grid/adaptive/dichotomic) use it to place 6 samples, dichotomic giving the tightest approximation (max chord-gap 202 vs grid 558). Knee detected at p3 -- the last point before the exact dual accelerates most (250.64 -> 650.79). |
| 4 | Prescriptive (stress) | Stock.regime_covar under "crisis" regime | (shares Stock.x_quantity with Stage 3) | Crisis volatility ~22-30% higher than base at every frontier point; gap peaks mid-frontier (p1 at +29.6%) and narrows toward the concentrated end (p5 at +21.7%). The representative-only universe keeps the concentrated end from stacking near-duplicate bets that would otherwise amplify crisis vol. |

All four stages share a single RAI model. Compliance thresholds are defined once at the top of the script. Stage 1 uses `POSITION_LIMIT = 0.15` and `SECTOR_LIMIT = 0.30` to flag existing violations as derived Relationships. Stage 3 re-uses `SECTOR_LIMIT` but applies `REP_POSITION_LIMIT = 0.30` to the decision variable: after representative collapse each cluster has exactly one carrier, so its cap is legitimately higher than a per-stock compliance cap.

### How the reasoners chain

Each stage writes derived properties the next reads directly. Stage 1's thresholds (`POSITION_LIMIT`, `SECTOR_LIMIT`) become Stage 3 constraints. Stage 2's `Stock.is_representative` and `Stock.is_non_representative` shape Stage 3's decision space (non-reps forced to zero). Stage 4 uses the same `solve_epsilon` call as Stage 3 -- the `Regime` concept keyed into `Stock.regime_covar` makes base vs crisis a scenario view on the same solve, not a separate model. The Reasoner overview table above names each property that crosses a stage boundary.

### Multi-scenario Pareto frontier in one pipeline

`Scenario` combines three budgets and two regimes -- six tuples. Each `solve_epsilon(eps_rate)` call returns one optimal allocation per tuple, so a single solve prices all six scenarios at once. The three frontier drivers share a solve cache, so running all of them costs roughly one budget's worth of unique solves rather than 3x. Two consequences:

1. Base and crisis are comparable at equal budget and equal return target: the vol gap is a pure regime effect, not a re-fitting artifact.
2. Adding a fourth regime or a fifth budget is a data edit in `scenario_data`, not a code change in `solve_epsilon`. Scenarios are data.

### Stage 1: Rules-based compliance analysis

The first stage defines compliance flags as RAI derived properties and Relationships. The model loads portfolio data (users, accounts, holdings, transactions) alongside the stock universe, then evaluates three rules using two configurable thresholds:

```python
POSITION_LIMIT = 0.15   # max fraction of budget per stock
SECTOR_LIMIT = 0.30     # max fraction of budget per sector
```

**Rule 1 -- Overconcentrated holdings**: a holding whose value exceeds `POSITION_LIMIT` of the account balance. The holding value is a derived property:

```python
Holding.value = model.Property(f"{Holding} has value {Float:holding_value}")
model.define(Holding.value(Holding.quantity * Holding.purchase_price))

Holding.is_overconcentrated = model.Relationship(f"{Holding} is overconcentrated")
AccountR1 = Account.ref()
model.where(
    Holding.account(AccountR1),
    Holding.value > POSITION_LIMIT * AccountR1.balance,
).define(Holding.is_overconcentrated())
```

**Rule 2 -- Sector concentration**: total holdings in a sector exceeding `SECTOR_LIMIT` of the account balance. Uses aggregation to sum holding values per (account, sector):

```python
sector_exposure = sum(HoldingSC.value).where(
    HoldingSC.account(AccountSC),
    HoldingSC.stock(StockSC),
    StockSC.sector_ref(SectorSC),
).per(AccountSC, SectorSC)

model.where(
    Holding.account(AccountSC),
    Holding.stock(StockR2),
    StockR2.sector_ref(SectorSC),
    sector_exposure > SECTOR_LIMIT * AccountSC.balance,
).define(Holding.is_sector_concentrated())
```

**Rule 3 -- High-risk traders**: users with `risk_score > 0.8` and more than 5 flagged transactions. Flagged transaction count is computed via aggregation:

```python
flagged_count = sum(TransactionHR.is_flagged_val).where(
    TransactionHR.user(User),
).per(User)

model.where(
    User.risk_score > 0.8,
    flagged_count > 5,
).define(User.is_high_risk_trader())
```

### Stage 2: Graph -- covariance clustering

Volatility and correlation are derived in PyRel from the base covariance, so the ontology is the single source of truth for every similarity metric. `Stock.variance` picks the covariance diagonal, `Stock.volatility` applies `sqrt(variance)` via `relationalai.semantics.std.math.sqrt`, and `Stock.correlation(i, j) = covar(i, j) / (vol_i * vol_j)`:

```python
Stock.volatility = model.Property(f"{Stock} has {Float:stock_volatility}")
model.define(Stock.volatility(sqrt(Stock.variance)))

Stock.correlation = model.Property(
    f"{Stock} and {Stock} have correlation {Float:stock_correlation}"
)
PairedStockCorr = Stock.ref()
cov_ij_ref = Float.ref()
model.where(
    Stock.covar(PairedStockCorr, cov_ij_ref),
).define(
    Stock.correlation(
        PairedStockCorr,
        cov_ij_ref / (Stock.volatility * PairedStockCorr.volatility),
    )
)
```

The `Graph` reasoner builds an undirected graph with `Stock` as the node concept. Edges are filtered in PyRel directly against the derived correlation property -- no upstream edge list required:

```python
corr_graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Stock,
    aggregator="sum",
)

stock_i_ref = Stock.ref()
stock_j_ref = Stock.ref()
corr_ref = Float.ref()
model.define(corr_graph.Edge.new(src=stock_i_ref, dst=stock_j_ref)).where(
    stock_i_ref.correlation(stock_j_ref, corr_ref),
    stock_i_ref.index < stock_j_ref.index,
    math_abs(corr_ref) >= CORR_THRESHOLD,
)
```

Louvain community detection runs directly on the graph and returns (node, cluster_id) pairs. The cluster id is persisted as a `Stock` property so downstream stages can consume it:

```python
community = corr_graph.louvain()
cluster_label = Integer.ref("cluster_label")
Stock.cluster = model.Property(f"{Stock} in cluster {Integer:cluster_id}")
stock_clust_ref = Stock.ref()
model.define(stock_clust_ref.cluster(cluster_label)).where(
    community(stock_clust_ref, cluster_label)
)
```

The script reports cluster sizes and intra- vs inter-cluster average correlation as a sanity check that the clustering separates co-moving stocks from independent ones.

After clustering, Stage 2 picks one representative per cluster -- the stock with the highest Sharpe ratio -- using per-group argmax in PyRel. Only the representatives will be eligible for allocation in Stage 3:

```python
Stock.sharpe = model.Property(f"{Stock} has Sharpe {Float:stock_sharpe}")
model.define(Stock.sharpe(Stock.returns / Stock.volatility))

peer_for_max = Stock.ref()
Stock.cluster_max_sharpe = model.Property(
    f"{Stock} has cluster max Sharpe {Float:cluster_max_sharpe}"
)
model.define(
    Stock.cluster_max_sharpe(
        aggs.max(peer_for_max.sharpe)
        .where(peer_for_max.cluster == Stock.cluster)
        .per(Stock)
    )
)

Stock.is_representative = model.Relationship(f"{Stock} is cluster representative")
model.where(Stock.sharpe == Stock.cluster_max_sharpe).define(
    Stock.is_representative()
)
```

### Stage 3: Bi-objective optimization

#### Scenario concept and decision variables

The `Stock` concept (defined earlier for all stages) carries ticker, sector, expected returns, and the base covariance matrix. Stage 2 added `Stock.variance`, `Stock.volatility`, `Stock.correlation`, `Stock.cluster`, `Stock.sharpe`, `Stock.cluster_max_sharpe`, `Stock.is_representative`, and `Stock.is_non_representative` on top. Stage 3 consumes the representative flag via its compliance constraints, and adds budget-and-regime scenarios, regime-conditioned covariance, and decision variables.

Scenarios combine budget and regime so each epsilon solve handles all six (budget, regime) combinations simultaneously:

```python
Regime = model.Concept("Regime", identify_by={"regime_name": String})
model.define(Regime.new(regime_name="base"))
model.define(Regime.new(regime_name="crisis"))

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
Scenario.regime = model.Property(f"{Scenario} in {Regime}")
scenario_data = model.data(
    [
        ("base_500", 500, "base"),
        ("base_1000", 1000, "base"),
        ("base_2000", 2000, "base"),
        ("crisis_500", 500, "crisis"),
        ("crisis_1000", 1000, "crisis"),
        ("crisis_2000", 2000, "crisis"),
    ],
    columns=["name", "budget", "regime"],
)
model.define(
    s := Scenario.new(name=scenario_data["name"]),
    s.budget(scenario_data["budget"]),
)
# Link Scenario to Regime by matching the regime name from the data.
scenario_link_ref = Scenario.ref()
regime_link_ref = Regime.ref()
model.where(
    scenario_link_ref.name == scenario_data["name"],
    regime_link_ref.regime_name == scenario_data["regime"],
).define(scenario_link_ref.regime(regime_link_ref))
```

#### Define decision variables, constraints, and objective

Each stock gets a continuous quantity variable indexed by Scenario (multi-argument Property).

```python
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
```

Two concentration limits plus a representative-only filter are added via `_add_compliance_constraints`. Position and sector caps behave as before; the `Stock.is_non_representative()` relation forces every non-representative stock to zero allocation, which is how the graph stage's redundancy removal shows up at solve time. The complement is defined positively because the prescriptive rewriter can't accept `model.not_(...)` inside a solver constraint:

```python
def _add_compliance_constraints(problem):
    # Position limit: each representative <= REP_POSITION_LIMIT * budget.
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty <= REP_POSITION_LIMIT * Scenario.budget))

    # Sector limit: total allocation to stocks in same sector <= SECTOR_LIMIT * budget.
    sector_alloc = sum(x_qty).where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.sector == s_sector_ref.sector,
    ).per(Scenario, s_sector_ref.sector)
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sector_alloc <= SECTOR_LIMIT * Scenario.budget))

    # Representative-only: non-representative stocks forced to zero.
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.is_non_representative(),
    ).require(x_qty == 0))
```

The risk objective is quadratic in the decision variables and uses the regime-conditioned covariance: each Scenario picks its matching regime's covariance, so base and crisis scenarios solve against different covariances in the same call.

```python
problem.minimize(
    sum(regime_cov_val * x_qty * x_qty_paired)
    .where(
        Stock.regime_covar(PairedStock, Scenario.regime, regime_cov_val),
        Stock.x_quantity(Scenario, x_qty),
        PairedStock.x_quantity(Scenario, x_qty_paired),
    )
)
```

#### Solve anchors, then trace the frontier with shadow prices

Two anchor solves establish the feasible return range. Anchor 1 minimizes risk with no return constraint; Anchor 2 maximizes return. The span is measured on a single reference scenario (`base_1000`).

```python
result1 = solve_epsilon(eps_rate=None)   # min-risk anchor
```

Each interior solve minimizes variance subject to a return-target floor and requests sensitivity information, so HiGHS returns the return constraint's **dual** -- the shadow price. By the envelope theorem that dual is exactly the frontier's local slope d(variance)/d(return), so one solve yields both a Pareto point and the slope there, with no finite differencing.

```python
problem.solve("highs", time_limit_sec=60, sensitivity=True)
# shadow_price = dual of the return-floor constraint = d(variance)/d(return)
```

Sign convention: minimizing variance subject to `return >= target`, the dual is non-negative with units of variance per unit return, and it rises monotonically along the frontier (variance gets more expensive as you demand more return).

Three drivers spend the same solve budget differently and are compared head-to-head:

- **grid** -- evenly spaced return targets, blind to the frontier's shape (the control).
- **adaptive** -- sizes each step by the current shadow price so points land evenly in variance space.
- **dichotomic** -- repeatedly splits the interval with the largest chord-vs-tangent gap, sampling where the two endpoints' shadow prices predict they meet (a dual-guided, epsilon-space analogue of NISE, not the classical Aneja-Nair weighted-sum scheme).

Quality is scored by **max chord-gap**: the largest variance error of linearly interpolating between solved points. At equal 6-solve budget the dual-guided drivers win decisively (dichotomic 202 vs grid 558), because the duals tell the search where the frontier curves most.

#### Pareto analysis output

The script prints the three-driver quality comparison, the shadow-price-vs-secant table (each exact dual next to the finite-difference slope it brackets), the efficient frontier per (budget, regime) scenario, and programmatic knee detection at the last point before the exact dual's largest ratio jump (where diminishing returns accelerate, not where the absolute dual is highest). The dichotomic frontier is materialized as the `FrontierPoint` Concept, with integrity constraints asserting that neither return nor risk decreases along it -- a relational statement of Pareto-efficiency.

### Stage 4: Crisis regime stress test

Crisis covariance is derived in PyRel via PSD-preserving correlation shrinkage, keyed by a `Regime` concept. The shrinkage formula `rho_crisis = alpha * rho + (1 - alpha) * J` re-expressed in covariance units becomes `cov_crisis(i, j) = alpha * cov(i, j) + (1 - alpha) * vol_i * vol_j` -- a convex combination of PSD matrices, so PSD is preserved by construction:

```python
Stock.regime_covar = model.Property(
    f"{Stock} and {Stock} in {Regime} have {Float:regime_covar}"
)

# Base regime: covariance unchanged.
model.where(
    Stock.covar(PairedStockBase, base_cov_ref),
    base_regime_ref.regime_name == "base",
).define(Stock.regime_covar(PairedStockBase, base_regime_ref, base_cov_ref))

# Crisis regime: convex combination of base covariance and vol_i * vol_j.
model.where(
    Stock.covar(PairedStockCrisis, crisis_cov_ref),
    crisis_regime_ref.regime_name == "crisis",
).define(
    Stock.regime_covar(
        PairedStockCrisis,
        crisis_regime_ref,
        CRISIS_ALPHA * crisis_cov_ref
        + (1 - CRISIS_ALPHA) * Stock.volatility * PairedStockCrisis.volatility,
    )
)
```

Both regimes live on the same `Stock.regime_covar` property, keyed by the `Regime` concept, so Stage 3's objective can select the right covariance per scenario without branching:

After the Stage 3 frontier is traced, Stage 4 emits a side-by-side comparison of base and crisis volatility (`sqrt(risk)`) at each frontier point, grouped by budget. Crisis volatility is consistently ~22-30% higher than base. The gap peaks in the middle of the frontier (p1 at +29.6%) and narrows toward the concentrated end (p5 at +21.7%). That shape is the payoff of the representative-only universe: at the concentrated end the optimizer is picking the highest-Sharpe distinct bet per cluster (Energy and Consumer Staples in this dataset), which happen to have lower crisis correlations than the middle of the frontier. Without the representative collapse, the concentrated end would stack near-duplicates and the crisis gap would grow instead of shrink.

## Customize this template

- **Adjust compliance thresholds**: `POSITION_LIMIT` (default 0.15) applies in Stage 1 compliance rules (per-stock holdings). `REP_POSITION_LIMIT` (default 0.30) applies in Stage 3 optimization (per-representative allocation, which carries its cluster's combined exposure). `SECTOR_LIMIT` (default 0.30) applies to both. Note that `REP_POSITION_LIMIT` must satisfy `REP_POSITION_LIMIT * num_representatives >= 1.0` or the fully-invested constraint becomes infeasible.
- **Tune the correlation graph**: Raise or lower `CORR_THRESHOLD` (default 0.3) to control graph sparsity. Higher thresholds produce fewer edges and more singleton clusters; lower thresholds produce a denser graph and fewer, larger clusters.
- **Change the representative picking rule**: Stage 2 picks the highest-Sharpe stock per cluster. To pick differently, change the `Stock.cluster_max_sharpe` derivation -- e.g., replace `Stock.sharpe` with `Stock.returns` (highest return), `-Stock.volatility` (lowest vol), or a weighted blend. Singletons are always their own representative regardless of rule.
- **Adjust crisis severity**: Lower `CRISIS_ALPHA` (default 0.7) shrinks correlations harder toward all-ones (more severe crisis). `alpha = 1.0` is no crisis (base); `alpha = 0.0` is maximum crisis (all correlations = 1). Values between 0.5 and 0.9 give interesting comparisons while keeping the QP well-conditioned.
- **Add more stocks**: Extend `returns.csv` and `covar.csv` with additional assets and their covariance entries.
- **Add compliance rules**: Define additional Relationships in the rules stage (e.g., minimum holding period, transaction velocity limits).
- **Allow short selling**: Remove the non-negativity constraint to allow negative holdings.
- **Adjust frontier resolution**: Increase `N_SOLVES` for a finer-grained frontier. Because the three drivers share a solve cache, the total number of unique solves stays close to `N_SOLVES` rather than 3x.
- **Maximize return for given risk**: Flip the formulation to maximize expected return subject to a risk budget.
- **Transaction costs**: Add a linear or quadratic penalty term for rebalancing from an existing portfolio.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

A frontier solve becomes infeasible when its return-floor target exceeds what the position and sector limits allow at that budget; the error message names the return level that failed. Check that the Anchor 2 max-return output looks right for your data, then relax `REP_POSITION_LIMIT` or `SECTOR_LIMIT`, or raise the budget values in the scenario data. Reducing `N_SOLVES` only coarsens the frontier grid -- it does not fix infeasibility.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>Solver reports non-convex or numerical issues</summary>

Ensure the covariance matrix is symmetric and positive semi-definite. Check that `covar.csv` contains entries for all (i, j) pairs and that covar(i,j) == covar(j,i). HiGHS solves convex QPs to a global optimum and returns shadow prices (duals) when `sensitivity=True`.
</details>
