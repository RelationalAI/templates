---
title: "Portfolio Balancing"
description: "Compliance screening, covariance clustering, and bi-objective Markowitz optimization that traces the risk-return frontier with solver shadow prices, plus a crisis-regime stress test."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Prescriptive
  - Rules-based
  - Graph
tags:
  - Multi-Reasoner
  - Portfolio Optimization
  - Quadratic Programming
  - Community Detection
  - Sensitivity Analysis
  - Stress Testing
---

## What this template is for

Portfolio managers don't want to pay twice for the same exposure -- if two funds track nearly the same benchmark, owning both is one bet with worse bookkeeping. Sector labels alone miss this: two tech funds can share a Technology label and still be near-duplicates, or two instruments from different sectors can co-move strongly enough that owning both is redundant. And a base-case optimization is optimistic -- under a crisis regime, correlations spike toward one and everything that hasn't been deduplicated hurts twice.

This template builds compliant, risk-optimized portfolios that avoid that trap, then stress-tests them under a crisis regime, all on one shared ontology across an 8-stock universe. **It chains RelationalAI's rules, graph, and prescriptive reasoners: rules flag compliance violations in the current book, a covariance graph collapses near-duplicate bets via Louvain clustering, and a bi-objective Markowitz quadratic program (QP) traces the risk-return frontier using solver shadow prices — then re-solves the same model under a crisis covariance.** See *How it works* for the stage-by-stage data flow.

## Who this is for

- Quantitative analysts and portfolio managers exploring mean-variance optimization
- Data scientists learning quadratic programming with RelationalAI
- Finance students studying the Markowitz efficient frontier
- Anyone interested in risk-return trade-off analysis with scenario comparisons
- **Assumed knowledge**: comfortable reading Python; the Markowitz, covariance, and optimization terms are explained as they come up. As a multi-reasoner template, it goes faster if you have followed a single-reasoner template first, but no deep RelationalAI experience is required to run it.

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
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
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

6. Expected output. The script prints all four stages in turn; the tail of the run confirms a successful frontier trace and stress test. A few representative lines:

   ```text
   STAGE 2: GRAPH -- Covariance Clustering (Louvain)
     Louvain communities: 5 cluster(s)
     Cluster representatives (5 of 8 stocks, picked by highest Sharpe): ...

   SENSITIVITY-GUIDED FRONTIER  (reference 'base_1000', 6-solve budget per method)
     method        solves     max chord-gap
     grid               6          557.9250
     adaptive           6          415.1730
     dichotomic         6          202.2972  <- tightest

   STAGE 4: CRISIS REGIME STRESS TEST
     Crisis volatility ~22-30% above base at every frontier point.
   ```

   Crisis volatility sits ~22-30% above base at every frontier point and the gap peaks in the middle of the frontier, not at the concentrated end. That inversion is the payoff of the representative-only universe: at the concentrated end the optimizer picks the highest-Sharpe distinct bet per cluster, which sits in sectors with lower crisis correlations (Energy, Consumer Staples). The full stage-by-stage printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
portfolio_balancing/
  portfolio_balancing.py    # Main script (4 chained stages: rules, graph, QP, stress test)
  data/
    returns.csv             # 8-stock universe: index, ticker, sector, expected returns
    covar.csv               # covariance matrix entries (i, j, covar)
    users.csv               # user profiles with risk scores
    accounts.csv            # account balances
    holdings.csv            # current holdings per account and stock
    transactions.csv        # transaction history with flagged-transaction indicators
  README.md                 # this file
  runbook.md                # analyst-facing paste-testable walkthrough
  pyproject.toml            # dependencies
```

**Start here**: run `python portfolio_balancing.py` for the full four-stage chain end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled CSVs are illustrative demo data over a compact 8-stock universe, sized so the covariance clustering, frontier trace, and crisis stress test all produce a readable, interpretable result. Swap in your own universe and book to apply the template to a real portfolio.

- **`returns.csv`** (8 rows) — the stock universe: an integer `index`, `ticker`, `sector`, and expected `returns`.
- **`covar.csv`** — one row per `(i, j)` covariance-matrix entry; must be symmetric (`covar(i, j) == covar(j, i)`) and cover every pair.
- **`users.csv`** — user profiles with a `risk_score`.
- **`accounts.csv`** — account balances, each linked to a user.
- **`holdings.csv`** — current holdings per account and stock, with quantity and purchase price.
- **`transactions.csv`** — transaction history with an `is_flagged` indicator used by the high-risk-trader rule.

## Model overview

One shared ontology threads all four stages. Each stage reads properties earlier stages wrote and writes new ones for downstream stages.

- **Key entities**: `Stock`, `Sector`, `User`, `Account`, `Holding`, `Transaction`; plus the derived `Regime`, `Scenario`, and `FrontierPoint` concepts the optimization stages build.
- **Primary identifiers**: integer `index` on `Stock`; integer ids on `User`, `Account`, `Holding`, `Transaction`; string `sector_name` on `Sector`, `regime_name` on `Regime`, `name` on `Scenario`; composite key (`scenario_label` + `eps_label`) on `FrontierPoint`.
- **Important invariants**: the covariance matrix is symmetric and positive semi-definite; expected returns and balances are per-row data; `Stock.correlation` and `Stock.regime_covar` are derived in PyRel from the base covariance; non-representative stocks are forced to zero allocation at solve time.

The derived concepts the optimization stages build are `Regime` (`base` / `crisis`), `Scenario` (a `(budget, regime)` tuple — three budgets × two regimes give six tuples so one epsilon solve prices every combination at once), and `FrontierPoint` (a materialized Pareto point with return, risk, marginal, and knee flag).

For the full concept and property definitions — including every property each stage writes onto `Stock` — see `portfolio_balancing.py`; `runbook.md` builds them step by step with the RAI skills.

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

The first stage defines compliance flags as RAI derived properties and Relationships. The model loads portfolio data (users, accounts, holdings, transactions) alongside the stock universe, then evaluates three rules using two configurable thresholds — `POSITION_LIMIT` (max fraction of budget per stock, default 0.15) and `SECTOR_LIMIT` (max fraction per sector, default 0.30):

- **Rule 1 — Overconcentrated holdings**: flag any holding whose value (a derived `quantity × purchase_price`) exceeds `POSITION_LIMIT` of its account balance.
- **Rule 2 — Sector concentration**: sum holding values per (account, sector) and flag every holding in a sector whose total exceeds `SECTOR_LIMIT` of the account balance.
- **Rule 3 — High-risk traders**: flag users with `risk_score > 0.8` and more than 5 flagged transactions (the flagged count is an aggregation per user).

### Stage 2: Graph -- covariance clustering

Volatility and correlation are derived in PyRel from the base covariance, so the ontology is the single source of truth for every similarity metric: `variance` is the covariance diagonal, `volatility` is its square root, and `correlation(i, j) = covar(i, j) / (vol_i · vol_j)`. The graph reasoner then builds an undirected graph over `Stock`, with edges filtered directly against the derived correlation — an edge exists between two stocks whose absolute correlation clears `CORR_THRESHOLD`, so no upstream edge list is needed.

Louvain community detection runs on that graph and the resulting cluster id is persisted as a `Stock` property. The script reports cluster sizes and intra- vs inter-cluster average correlation as a sanity check that co-moving stocks group together. Finally, Stage 2 picks one representative per cluster — the highest-Sharpe stock (`returns / volatility`), via per-group argmax — and only those representatives are eligible for allocation in Stage 3. Singletons are their own representative.

### Stage 3: Bi-objective optimization

**Scenarios and decision variables.** Stage 3 consumes the representative flag from Stage 2 and adds budget-and-regime scenarios, regime-conditioned covariance, and the decision variables. A `Scenario` combines a budget and a regime, so the six `(budget, regime)` tuples are all priced in one epsilon solve. Each stock carries a continuous quantity variable indexed by `Scenario`.

**Constraints.** Three constraints shape the allocation: a position cap (each representative ≤ `REP_POSITION_LIMIT` of budget), a sector cap (total allocation per sector ≤ `SECTOR_LIMIT` of budget), and a representative-only filter that forces every non-representative stock to zero — this is how the graph stage's redundancy removal shows up at solve time. The complement (`is_non_representative`) is defined positively because the prescriptive rewriter can't accept a negation inside a solver constraint.

**Objective.** The risk objective is quadratic in the decision variables and uses the regime-conditioned covariance, so each scenario solves against its own regime's covariance in the same call.

**Anchors, then shadow-price-guided frontier tracing.** Two anchor solves bracket the feasible return range (min-risk with no return floor, then max-return), measured on the reference scenario `base_1000`. Each interior solve then minimizes variance subject to a return-target floor and requests sensitivity, so HiGHS returns the return constraint's **dual** — the shadow price. By the envelope theorem that dual is exactly the frontier's local slope d(variance)/d(return), so one solve yields both a Pareto point and its slope with no finite differencing. The dual is non-negative (variance per unit return) and rises monotonically along the frontier as return gets more expensive.

Three drivers spend the same solve budget differently and are compared head-to-head:

- **grid** -- evenly spaced return targets, blind to the frontier's shape (the control).
- **adaptive** -- sizes each step by the current shadow price so points land evenly in variance space.
- **dichotomic** -- repeatedly splits the interval with the largest chord-vs-tangent gap, sampling where the two endpoints' shadow prices predict they meet (a dual-guided, epsilon-space analogue of NISE, not the classical Aneja-Nair weighted-sum scheme).

Quality is scored by **max chord-gap**: the largest variance error of linearly interpolating between solved points. At equal 6-solve budget the dual-guided drivers win decisively (dichotomic 202 vs grid 558), because the duals tell the search where the frontier curves most.

**Pareto analysis output.** The script prints the three-driver quality comparison, the shadow-price-vs-secant table (each exact dual next to the finite-difference slope it brackets), the efficient frontier per (budget, regime) scenario, and programmatic knee detection at the last point before the exact dual's largest ratio jump (where diminishing returns accelerate, not where the absolute dual is highest). The dichotomic frontier is materialized as the `FrontierPoint` Concept, with integrity constraints asserting that neither return nor risk decreases along it -- a relational statement of Pareto-efficiency.

### Stage 4: Crisis regime stress test

Crisis covariance is derived in PyRel via PSD-preserving correlation shrinkage, keyed by the `Regime` concept. The shrinkage formula `rho_crisis = alpha · rho + (1 - alpha) · J`, re-expressed in covariance units, becomes `cov_crisis(i, j) = alpha · cov(i, j) + (1 - alpha) · vol_i · vol_j` — a convex combination of PSD matrices, so positive semi-definiteness is preserved by construction. The base regime leaves covariance unchanged. Both regimes live on the same `regime_covar` property keyed by `Regime`, so Stage 3's objective selects the right covariance per scenario without branching.

After the Stage 3 frontier is traced, Stage 4 emits a side-by-side comparison of base and crisis volatility (`sqrt(risk)`) at each frontier point, grouped by budget. Crisis volatility is consistently ~22-30% higher than base. The gap peaks in the middle of the frontier (p1 at +29.6%) and narrows toward the concentrated end (p5 at +21.7%). That shape is the payoff of the representative-only universe: at the concentrated end the optimizer is picking the highest-Sharpe distinct bet per cluster (Energy and Consumer Staples in this dataset), which happen to have lower crisis correlations than the middle of the frontier. Without the representative collapse, the concentrated end would stack near-duplicates and the crisis gap would grow instead of shrink.

For the exact PyRel formulation of all four stages, see `portfolio_balancing.py`; `runbook.md` reproduces them step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace the six CSV files with your own universe and book; the four-stage structure does not change.
- **Add more stocks**: extend `returns.csv` and `covar.csv` with additional assets and their covariance entries. Keep the covariance matrix symmetric (`covar(i, j) == covar(j, i)`) and complete over every pair.

### Tune parameters

- **Adjust compliance thresholds**: `POSITION_LIMIT` (default 0.15) applies in Stage 1 compliance rules (per-stock holdings). `REP_POSITION_LIMIT` (default 0.30) applies in Stage 3 optimization (per-representative allocation, which carries its cluster's combined exposure). `SECTOR_LIMIT` (default 0.30) applies to both. Note that `REP_POSITION_LIMIT` must satisfy `REP_POSITION_LIMIT * num_representatives >= 1.0` or the fully-invested constraint becomes infeasible.
- **Tune the correlation graph**: raise or lower `CORR_THRESHOLD` (default 0.3) to control graph sparsity. Higher thresholds produce fewer edges and more singleton clusters; lower thresholds produce a denser graph and fewer, larger clusters.
- **Adjust crisis severity**: lower `CRISIS_ALPHA` (default 0.7) shrinks correlations harder toward all-ones (more severe crisis). `alpha = 1.0` is no crisis (base); `alpha = 0.0` is maximum crisis (all correlations = 1). Values between 0.5 and 0.9 give interesting comparisons while keeping the QP well-conditioned.
- **Adjust frontier resolution**: increase `N_SOLVES` for a finer-grained frontier. Because the three drivers share a solve cache, the total number of unique solves stays close to `N_SOLVES` rather than 3x.

### Extend the model

- **Change the representative picking rule**: Stage 2 picks the highest-Sharpe stock per cluster. To pick differently, change the `Stock.cluster_max_sharpe` derivation -- e.g., replace `Stock.sharpe` with `Stock.returns` (highest return), `-Stock.volatility` (lowest vol), or a weighted blend. Singletons are always their own representative regardless of rule.
- **Add compliance rules**: define additional Relationships in the rules stage (e.g., minimum holding period, transaction velocity limits).
- **Allow short selling**: remove the non-negativity constraint to allow negative holdings.
- **Maximize return for given risk**: flip the formulation to maximize expected return subject to a risk budget.
- **Transaction costs**: add a linear or quadratic penalty term for rebalancing from an existing portfolio.

### Scale up / productionize

- Swap the `data/` CSV bundle for `model.data(snowflake_table)` calls to run against a live Snowflake-hosted universe and book.
- Add a fourth regime or a fifth budget as a data edit in `scenario_data` -- the `solve_epsilon` call is unchanged, since scenarios are data, not code.

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

## Learn more

### Core concepts

- [Multi-reasoner workflows](https://docs.relational.ai/) — chained reasoner patterns and ontology enrichment across stages.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)` / `aggs` / derived properties.

### Reasoner reference

- [Rules-based reasoner](https://docs.relational.ai/) — derived properties and Relationships for compliance flags.
- [Graph reasoner](https://docs.relational.ai/) — building graphs from ontology, Louvain community detection.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, quadratic objectives, sensitivity (duals / shadow prices), the epsilon-constraint frontier method.

## Support

- File issues at the RelationalAI templates repository.
