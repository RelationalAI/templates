---
title: "Portfolio Balancing"
description: "Explore the risk-return tradeoff using bi-objective Markowitz optimization with epsilon constraint."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
  - Prescriptive
tags:
  - Quadratic Programming
  - Risk Minimization
  - Portfolio Optimization
  - Multi-Objective
  - Scenario Analysis
  - Ipopt
---

# Portfolio Balancing

## What this template is for

This template uses **prescriptive reasoning (optimization)** to trace the efficient frontier between portfolio risk and expected return using bi-objective Markowitz mean-variance optimization.

Portfolio optimization involves two competing objectives: minimizing risk (variance) and maximizing return. Rather than fixing a single return target, this template uses the **epsilon constraint method** to sweep return targets across the feasible range, producing the full tradeoff curve. Each point on the frontier is a valid portfolio — no point is strictly better than another.

The template also demonstrates **Scenario Concept inside the epsilon loop**: budget levels are modeled as scenarios, so each epsilon solve handles all budget scenarios simultaneously. This reveals how the risk-return frontier shifts with available capital.

## Who this is for

- Quantitative analysts and portfolio managers exploring mean-variance optimization
- Data scientists learning quadratic programming with RelationalAI
- Finance students studying the Markowitz efficient frontier
- Anyone interested in risk-return trade-off analysis with scenario comparisons

## What you'll build

- A quadratic programming model that minimizes portfolio variance (primary objective)
- Budget and no-short-selling constraints across multiple budget scenarios
- Epsilon constraint method sweeping return targets to trace the efficient frontier
- Anchor solves to establish the feasible return range
- Pareto analysis with marginal cost and knee detection

## What's included

- `portfolio_balancing.py` -- Main script defining the QP model, epsilon constraint sweep, and Pareto analysis
- `data/returns.csv` -- Expected returns for each stock
- `data/covar.csv` -- Covariance matrix entries (i, j, covariance value)
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

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
   ANCHOR SOLVE 1: Minimize risk (no return constraint)
   ======================================================================
   Status: LOCALLY_SOLVED, total risk: ...
     budget_500: return = ...
     budget_1000: return = ...
     budget_2000: return = ...

   ======================================================================
   EPSILON SWEEP: 5 interior points
   ======================================================================
     Point 1 (rate=...): LOCALLY_SOLVED, risk=...
     Point 2 (rate=...): LOCALLY_SOLVED, risk=...
     ...

   ======================================================================
   EFFICIENT FRONTIER: Risk vs Return (per budget scenario)
   ======================================================================

     budget_500 (budget=500):
       #      Label     Return         Risk
       ----------------------------------------
       1   min_risk      ...         ...
       2      eps_1      ...         ...
       ...

     Marginal analysis:
       ...
       Knee: Point N (...) -- marginal cost jumps Nx beyond this point
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── portfolio_balancing.py
└── data/
    ├── returns.csv
    └── covar.csv
```

## How it works

This section walks through the highlights in `portfolio_balancing.py`.

### Define concepts and load CSV data

The model defines a `Stock` concept with expected returns. The covariance matrix is loaded as a binary property relating pairs of stocks.

```python
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
returns_csv = read_csv(data_dir / "returns.csv")
model.define(Stock.new(model.data(returns_csv).to_schema()))

Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
PairedStock = Stock.ref()
covar_data = model.data(read_csv(data_dir / "covar.csv"))
model.where(Stock.index(covar_data.i), PairedStock.index(covar_data.j)).define(
    Stock.covar(Stock, PairedStock, covar_data.covar)
)
```

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

### Define decision variables, constraints, and objective

Each stock gets a continuous quantity variable indexed by Scenario (multi-argument Property).

```python
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
```

The `solve_epsilon` helper defines the shared constraints and objective, with an optional return lower bound parameterized by `eps_value`. This is the core of the bi-objective transformation: in the original single-objective template, the return target was a fixed Scenario property (`Scenario.min_return`). In the bi-objective version, the return target becomes a parameter swept by the epsilon loop.

```python
def solve_epsilon(eps_value=None):
    p = Problem(model, Float)

    p.solve_for(
        Stock.x_quantity(Scenario, x_qty),
        name=["qty", Scenario.name, Stock.index],
        populate=False,
    )

    # Non-negative
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(x_qty >= 0))

    # Budget per scenario
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) <= Scenario.budget))

    # Fully invested per scenario
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(sum(x_qty).per(Scenario) >= Scenario.budget))

    # EPSILON CONSTRAINT: return >= target per scenario
    if eps_value is not None:
        p.satisfy(model.where(
            Stock.x_quantity(Scenario, x_qty),
        ).require(
            sum(Stock.returns * x_qty).per(Scenario) >= eps_value
        ))

    # Primary objective: minimize risk (quadratic via covariance matrix)
    p.minimize(
        sum(covar_value * x_qty * x_qty_paired)
        .where(Stock.covar(PairedStock, covar_value),
               Stock.x_quantity(Scenario, x_qty),
               PairedStock.x_quantity(Scenario, x_qty_paired))
    )

    p.solve("ipopt", time_limit_sec=60)
```

### Solve anchor points and run the epsilon sweep

Two anchor solves establish the feasible return range. Anchor 1 minimizes risk with no return constraint (finding the minimum-risk portfolio). Anchor 2 maximizes return (finding the maximum achievable return).

```python
result1 = solve_epsilon(eps_value=None)
```

The epsilon sweep then traces interior points between the anchors. Each solve minimizes risk subject to a return-rate floor that scales with budget, so all budget scenarios are handled in a single solve call per epsilon value.

```python
n_interior = 5
epsilon_rates = [
    return_rate_min + i * (return_rate_max - return_rate_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]

for i, rate in enumerate(epsilon_rates):
    p = Problem(model, Float)
    # ... same constraints as solve_epsilon ...
    # Epsilon constraint: return rate >= target rate (scaled by budget)
    p.satisfy(model.where(
        Stock.x_quantity(Scenario, x_qty),
    ).require(
        sum(Stock.returns * x_qty).per(Scenario) >= rate * Scenario.budget
    ))
    p.minimize(
        sum(covar_value * x_qty * x_qty_paired)
        .where(Stock.covar(PairedStock, covar_value),
               Stock.x_quantity(Scenario, x_qty),
               PairedStock.x_quantity(Scenario, x_qty_paired))
    )
    p.solve("ipopt", time_limit_sec=60)
```

### Pareto analysis output

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
              f"— marginal cost jumps {max_jump:.1f}x beyond this point")
```

## Customize this template

- **Add more stocks**: Extend `returns.csv` and `covar.csv` with additional assets and their covariance entries.
- **Allow short selling**: Remove the non-negativity constraint to allow negative holdings.
- **Add sector constraints**: Group stocks by sector and limit total allocation per sector.
- **Adjust frontier resolution**: Increase `n_interior` for a finer-grained efficient frontier.
- **Maximize return for given risk**: Flip the formulation to maximize expected return subject to a risk budget.
- **Transaction costs**: Add a linear or quadratic penalty term for rebalancing from an existing portfolio.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The minimum return target may be too high for the available stocks and budget. Lower the `min_return` scenario values or increase the `budget` parameter.
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
