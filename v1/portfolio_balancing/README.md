---
title: "Portfolio Balancing"
description: "Multi-reasoner template: rules-based compliance analysis chained with bi-objective Markowitz optimization."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
    - Prescriptive
    - Rules-based
tags:
  - Quadratic Programming
  - Risk Minimization
  - Portfolio Optimization
  - Multi-Objective
  - Scenario Analysis
  - Ipopt
  - Multi-Reasoner
  - Chained Reasoning
  - Compliance
---

# Portfolio Balancing

## What this template is for

This template chains two reasoning stages to build compliant, risk-optimized portfolios across an 8-stock universe.

**Stage 1 -- Rules-based compliance analysis** uses RAI derived properties and Relationships to scan existing portfolio data (users, accounts, holdings, transactions) and flag violations: overconcentrated holdings (position value > 15% of account balance), sector concentration (sector exposure > 30% of account balance), and high-risk traders (risk score > 0.8 with more than 5 flagged transactions).

**Stage 2 -- Prescriptive reasoning (optimization)** uses bi-objective Markowitz mean-variance optimization to trace the efficient frontier between portfolio risk and expected return. Rather than fixing a single return target, the **epsilon constraint method** sweeps return targets across the feasible range, producing the full tradeoff curve. Position limit (15%) and sector limit (30%) constraints -- derived from the same compliance rules -- are enforced during optimization.

The template also demonstrates **Scenario Concept inside the epsilon loop**: budget levels are modeled as scenarios, so each epsilon solve handles all budget scenarios simultaneously. This reveals how the risk-return frontier shifts with available capital.

Both stages share a single RAI model. The compliance thresholds (`POSITION_LIMIT = 0.15`, `SECTOR_LIMIT = 0.30`) are defined once and enforced in both stages: Stage 1 flags existing violations as derived Relationships, and Stage 2 applies the same limits as hard constraints in the optimizer via `_add_compliance_constraints()`.

### Reasoner overview

| Stage | Reasoner | Reads from ontology | Writes to ontology | Role |
|-------|----------|---------------------|--------------------|------|
| 1 | Rules | Holding, Account, User, Transaction, Stock | Holding.is_overconcentrated, Holding.is_sector_concentrated, User.is_high_risk_trader | 4 overconcentrated holdings (AAPL 18%, MSFT 16%, JNJ 16%, PFE 16.2%). 2 sector concentrations (Technology 34%, Healthcare 32.2%). 2 high-risk traders (Alice Chen 0.85, Eve Taylor 0.92). |
| 2 | Prescriptive (QP) | Stock.returns, Stock.covar, Scenario.budget, POSITION_LIMIT, SECTOR_LIMIT | Stock.x_quantity indexed by Scenario | Min-risk return rate: 0.0666/unit. Max return rate: 0.0715/unit. Epsilon sweep traces 5 interior points. Knee at eps_1: marginal cost jumps 2.9x (13.01 → 37.41 risk/return). |

## Why this problem matters

Portfolio managers must balance competing objectives -- maximize expected return while minimizing variance -- subject to regulatory and internal compliance limits. A naive mean-variance optimization ignores position and sector concentration limits, producing portfolios that violate compliance. Conversely, compliance screening alone identifies violations but cannot propose a rebalanced portfolio that satisfies all constraints simultaneously.

The two-stage approach is necessary because compliance rules and optimization constraints share the same thresholds but serve different purposes. Stage 1 surfaces existing violations in the current portfolio (diagnostic). Stage 2 constructs new portfolios that satisfy those same limits by construction (prescriptive). The epsilon constraint method then traces the full efficient frontier -- revealing that the knee point at eps_1 is where marginal risk per unit of return jumps 2.9x, from 13.01 to 37.41 risk/return. Beyond this point, each additional unit of expected return costs substantially more portfolio variance.

### Key design patterns demonstrated

- **Shared compliance thresholds** -- `POSITION_LIMIT` and `SECTOR_LIMIT` are defined once and enforced in both rules (Stage 1 flags) and optimization (Stage 2 constraints), ensuring consistency
- **Scenario Concept for budget levels** -- `Scenario` entities ($500, $1,000, $2,000) parameterize the optimization so each epsilon solve handles all budget scenarios simultaneously in one call
- **Epsilon constraint method** -- `solve_epsilon(eps_rate)` sweeps return targets across the feasible range, producing the full Pareto frontier without manually fixing return values
- **Quadratic programming via Ipopt** -- the risk objective is quadratic (`x' * Cov * x`), solved with Ipopt's nonlinear optimizer rather than a linear MIP solver
- **Anchor solves establish feasible range** -- Anchor 1 (minimize risk, no return constraint) and Anchor 2 (maximize return) determine the return rate range before the epsilon sweep

## Who this is for

- Quantitative analysts and portfolio managers exploring mean-variance optimization
- Data scientists learning quadratic programming with RelationalAI
- Finance students studying the Markowitz efficient frontier
- Anyone interested in risk-return trade-off analysis with scenario comparisons

## What you'll build

- A rules-based compliance pipeline using RAI derived properties and Relationships to flag overconcentrated holdings, sector concentration violations, and high-risk traders
- A quadratic programming model that minimizes portfolio variance subject to position limit and sector limit constraints
- Budget and no-short-selling constraints across multiple budget scenarios
- Epsilon constraint method sweeping return targets to trace the efficient frontier
- Anchor solves to establish the feasible return range
- Pareto analysis with marginal cost and knee detection

## What's included

- `portfolio_balancing.py` -- Main script with Stage 1 (rules-based compliance) and Stage 2 (QP optimization with epsilon sweep)
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

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.13

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/portfolio_balancing.zip
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

6. Expected output:
   ```text
   ======================================================================
   STAGE 1: COMPLIANCE ANALYSIS (rules)
   ======================================================================

   --- Rule 1: Overconcentrated Holdings (position > 15% of balance) ---

     holding_id=1, ticker=AAPL, account_id=1, value=18000.00, balance=100000.00, pct=18.0%
     holding_id=2, ticker=MSFT, account_id=1, value=16000.00, balance=100000.00, pct=16.0%
     holding_id=13, ticker=JNJ, account_id=4, value=12800.00, balance=80000.00, pct=16.0%
     holding_id=14, ticker=PFE, account_id=4, value=13000.00, balance=80000.00, pct=16.2%

   --- Rule 2: Sector Concentration (sector > 30% of balance) ---

     account_id=1, sector=Technology, sector_value=34000.00, balance=100000.00, pct=34.0%
     account_id=4, sector=Healthcare, sector_value=25800.00, balance=80000.00, pct=32.2%

   --- Rule 3: High Risk Traders (risk_score > 0.8 AND >5 flagged txns) ---

     user_id=1, name=Alice Chen, risk_score=0.85
     user_id=5, name=Eve Taylor, risk_score=0.92

   ======================================================================
   STAGE 2: BI-OBJECTIVE OPTIMIZATION (with compliance constraints)
   ======================================================================

   ANCHOR SOLVE 1: Minimize risk (no return constraint)
   --------------------------------------------------
   Status: LOCALLY_SOLVED
     budget_500: return = 33.2993, risk = 1146.119161
     budget_1000: return = 66.5986, risk = 4584.476643
     budget_2000: return = 133.1971, risk = 18337.906571

   ANCHOR SOLVE 2: Maximize return (swap objective)
   --------------------------------------------------
   Status: LOCALLY_SOLVED
     budget_500: return = 35.7500
     budget_1000: return = 71.5000
     budget_2000: return = 143.0000

   Return rate range: [0.0666, 0.0715] per unit invested

   ======================================================================
   EPSILON SWEEP: 5 interior points
   Return rates: ['0.0674', '0.0682', '0.0690', '0.0699', '0.0707']
   ======================================================================
     Point 1 (rate=0.0674): LOCALLY_SOLVED
     Point 2 (rate=0.0682): LOCALLY_SOLVED
     Point 3 (rate=0.0690): LOCALLY_SOLVED
     Point 4 (rate=0.0699): LOCALLY_SOLVED
     Point 5 (rate=0.0707): LOCALLY_SOLVED

   ======================================================================
   EFFICIENT FRONTIER: Risk vs Return (per budget scenario)
   ======================================================================

     budget_500 (budget=500):
       #      Label     Return         Risk
       --------------------------------------
       1   min_risk      33.30    1146.1192
       2      eps_1      33.71    1151.4338
       3      eps_2      34.12    1166.7123
       4      eps_3      34.52    1188.5067
       5      eps_4      34.93    1216.2536
       6      eps_5      35.34    1252.4072

     Risk
       1252.4 |                                                 6|
              |                                                  |
              |                                           5      |
              |                                                  |
              |                                    4             |
              |                                                  |
              |                             3                    |
              |                                                  |
              |                      2                           |
              |                                                  |
              |                                                  |
       1146.1 |1                                                 |
              +--------------------------------------------------+
               33.30                                        35.34
                                    Return

     Marginal analysis:
         min_risk -> eps_1     : delta_risk=   +5.3146, delta_return= +0.4085, marginal=   13.01 risk/return
            eps_1 -> eps_2     : delta_risk=  +15.2786, delta_return= +0.4085, marginal=   37.41 risk/return
            eps_2 -> eps_3     : delta_risk=  +21.7943, delta_return= +0.4085, marginal=   53.36 risk/return
            eps_3 -> eps_4     : delta_risk=  +27.7470, delta_return= +0.4085, marginal=   67.93 risk/return
            eps_4 -> eps_5     : delta_risk=  +36.1535, delta_return= +0.4085, marginal=   88.51 risk/return

       Knee: Point 2 (eps_1) -- marginal cost jumps 2.9x beyond this point

       Knee-point allocations (budget_500):
         Stock 1: 32.70 units (return rate=0.0800)
         Stock 2: 73.99 units (return rate=0.0700)
         Stock 3: 31.95 units (return rate=0.0900)
         Stock 4: 75.00 units (return rate=0.0500)
         Stock 5: 75.00 units (return rate=0.0600)
         Stock 6: 61.64 units (return rate=0.0700)
         Stock 7: 74.72 units (return rate=0.1000)
         Stock 8: 75.00 units (return rate=0.0400)
   ```

   The Pareto frontier shows risk accelerating as return targets increase.
   The knee at eps_1 marks where marginal risk per unit of return jumps
   2.9x -- beyond this point, each additional unit of return costs
   substantially more portfolio variance.

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

### Stage 2: Bi-objective optimization

#### Scenario concept and decision variables

The `Stock` concept (defined earlier for both stages) carries ticker, sector, expected returns, and the covariance matrix. The optimization stage adds budget scenarios and decision variables on top of the shared model.

Budget levels are modeled as a Scenario Concept so each epsilon solve handles all budget scenarios simultaneously.

```python
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_500", 500), ("budget_1000", 1000), ("budget_2000", 2000)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))
```

#### Define decision variables, constraints, and objective

Each stock gets a continuous quantity variable indexed by Scenario (multi-argument Property).

```python
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
```

The `solve_epsilon` helper defines the shared constraints and objective, with an optional return-rate lower bound parameterized by `eps_rate`. The return target becomes a rate parameter swept by the epsilon loop, scaled by each scenario's budget.

Position limit and sector limit constraints (matching the Stage 1 compliance thresholds) are added via `_add_compliance_constraints`:

```python
def _add_compliance_constraints(p):
    # Position limit: each stock allocation <= POSITION_LIMIT * budget
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty <= POSITION_LIMIT * Scenario.budget))

    # Sector limit: total allocation to stocks in same sector <= SECTOR_LIMIT * budget
    sector_alloc = sum(x_qty).where(
        Stock.x_quantity(Scenario, x_qty),
        Stock.sector == s_sector_ref.sector,
    ).per(Scenario, s_sector_ref.sector)
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sector_alloc <= SECTOR_LIMIT * Scenario.budget))
```

The `solve_epsilon` function builds the full problem -- non-negativity, budget, compliance constraints, optional epsilon return floor, and the quadratic risk objective:

```python
def solve_epsilon(eps_rate=None):
    problem = Problem(model, Float)

    problem.solve_for(
        Stock.x_quantity(Scenario, x_qty),
        name=["qty", Scenario.name, Stock.index],
        populate=False,
    )

    # Non-negative
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty >= 0))

    # Budget per scenario
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) <= Scenario.budget))

    # Fully invested per scenario
    problem.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) >= Scenario.budget))

    # Compliance constraints (position + sector limits)
    _add_compliance_constraints(p)

    # EPSILON CONSTRAINT: return rate >= target rate (scaled by budget)
    if eps_rate is not None:
        problem.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_rate * Scenario.budget
        ))

    # Primary objective: minimize risk (quadratic via covariance matrix)
    problem.minimize(
        sum(covar_value * x_qty * x_qty_paired)
        .where(Stock.covar(PairedStock, covar_value),
               Stock.x_quantity(Scenario, x_qty),
               PairedStock.x_quantity(Scenario, x_qty_paired))
    )

    problem.solve("ipopt", time_limit_sec=60)
```

#### Solve anchor points and run the epsilon sweep

Two anchor solves establish the feasible return range. Anchor 1 minimizes risk with no return constraint (finding the minimum-risk portfolio). Anchor 2 maximizes return (finding the maximum achievable return).

```python
result1 = solve_epsilon(eps_rate=None)
```

The epsilon sweep then traces interior points between the anchors. Each solve minimizes risk subject to a return-rate floor that scales with budget, so all budget scenarios are handled in a single solve call per epsilon value.

```python
n_interior = 5
epsilon_rates = [
    return_rate_min + i * (return_rate_max - return_rate_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]

for i, rate in enumerate(epsilon_rates):
    result = solve_epsilon(eps_rate=rate)
    # ... extract per-scenario risk and return from result ...
```

#### Pareto analysis output

The script prints the efficient frontier for each budget scenario, showing how risk increases as the return target rises. Marginal analysis computes the incremental risk per unit of additional return, and a knee detector identifies the point where the marginal cost of return jumps sharply.

```python
for sn in scenario_names:
    pts = pareto[sn]
    # ...
    # Marginal analysis
    for j in range(len(pts) - 1):
        dr = pts[j+1]['risk'] - pts[j]['risk']
        dret = pts[j+1]['return_actual'] - pts[j]['return_actual']
        if abs(dret) > 1e-6:
            rate_val = dr / dret
            # ...
    # Knee detection
    if len(rates) >= 2:
        # ...
        print(f"\n    Knee: Point {knee_idx + 1} ({pts[knee_idx]['label']}) "
              f"-- marginal cost jumps {max_jump:.1f}x beyond this point")
```

## Customize this template

- **Adjust compliance thresholds**: Change `POSITION_LIMIT` (default 0.15) and `SECTOR_LIMIT` (default 0.30) at the top of the script to tighten or relax concentration rules for both the rules compliance stage and the optimization constraints.
- **Add more stocks**: Extend `returns.csv` and `covar.csv` with additional assets and their covariance entries.
- **Add compliance rules**: Define additional Relationships in the rules stage (e.g., minimum holding period, transaction velocity limits).
- **Allow short selling**: Remove the non-negativity constraint to allow negative holdings.
- **Adjust frontier resolution**: Increase `n_interior` for a finer-grained efficient frontier.
- **Maximize return for given risk**: Flip the formulation to maximize expected return subject to a risk budget.
- **Transaction costs**: Add a linear or quadratic penalty term for rebalancing from an existing portfolio.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The return rate target may be too high for the available stocks and budget. Reduce `n_interior` to use fewer sweep points, or increase the budget values in the scenario data.
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

Ensure the covariance matrix is symmetric and positive semi-definite. Check that `covar.csv` contains entries for all (i, j) pairs and that covar(i,j) == covar(j,i). The Ipopt solver finds locally optimal solutions for convex QP problems.
</details>
