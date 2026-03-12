---
title: "Portfolio Balancing"
description: "Minimize portfolio risk for a given return target using Markowitz mean-variance optimization."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
  - Prescriptive
tags:
  - Quadratic Programming
  - Risk Minimization
  - Portfolio Optimization
  - Scenario Analysis
---

# Portfolio Balancing

## What this template is for

Portfolio optimization is a cornerstone of quantitative finance. Given a set of stocks with expected returns and a covariance matrix describing how their returns co-move, the Markowitz mean-variance model finds the allocation that minimizes portfolio risk (variance) while achieving a target minimum return.

This template formulates the portfolio balancing problem as a quadratic program. The decision variables are the number of units to hold in each stock. The quadratic objective minimizes portfolio variance using the covariance matrix. Linear constraints enforce a budget limit, non-negative holdings (no short selling), and a minimum expected return.

The template also demonstrates scenario analysis by solving across multiple return targets (10, 20, and 30). As the minimum return requirement increases, the optimizer must accept more risk, producing the efficient frontier trade-off between risk and return.

## Who this is for

- Quantitative analysts and portfolio managers exploring mean-variance optimization
- Data scientists learning quadratic programming with RelationalAI
- Finance students studying the Markowitz efficient frontier
- Anyone interested in risk-return trade-off analysis with scenario comparisons

## What you'll build

- A quadratic programming model that minimizes portfolio variance
- Budget and no-short-selling constraints
- Minimum return constraints parameterized by scenario
- Scenario analysis across multiple return targets showing the risk-return trade-off

## What's included

- `portfolio_balancing.py` -- Main script defining the QP model, constraints, and scenario analysis
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

6. Expected output:
   ```text
   Running scenario: min_return = 10
     Status: OPTIMAL, Risk: 2.820947
     Portfolio allocation:
       name    value
     qty_1   265.38
     qty_2   134.62

   Running scenario: min_return = 20
     Status: OPTIMAL, Risk: 5.198884
     Portfolio allocation:
       name    value
     qty_1   380.77
     qty_2   269.23
     qty_3   350.00

   Running scenario: min_return = 30
     Status: OPTIMAL, Risk: 13.609802
     Portfolio allocation:
       name    value
     qty_1   196.15
     qty_2   403.85
     qty_3   400.00

   ==================================================
   Scenario Analysis Summary
   ==================================================
     min_return=10: OPTIMAL, risk=2.820947
     min_return=20: OPTIMAL, risk=5.198884
     min_return=30: OPTIMAL, risk=13.609802
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

### 1. Define concepts and load data

The model defines a `Stock` concept with expected returns. The covariance matrix is loaded as a binary property relating pairs of stocks:

```python
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
```

### 2. Decision variables

Each stock gets a continuous variable representing the quantity to hold:

```python
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")
s.solve_for(Stock.x_quantity, name=["qty", Stock.index], populate=False)
```

### 3. Quadratic objective

Portfolio risk is minimized using the covariance matrix. The quadratic term sums over all stock pairs:

```python
covar_value = Float.ref()
risk = sum(covar_value * Stock.x_quantity * PairedStock.x_quantity).where(Stock.covar(PairedStock, covar_value))
s.minimize(risk)
```

### 4. Constraints

The model enforces no short selling, a budget limit, and a minimum return target:

```python
s.satisfy(model.require(Stock.x_quantity >= 0))
s.satisfy(model.require(sum(Stock.x_quantity) <= budget))
s.satisfy(model.require(sum(Stock.returns * Stock.x_quantity) >= min_ret))
```

### 5. Scenario analysis

The template solves for three minimum return targets (10, 20, 30), illustrating how increasing return requirements force the optimizer to accept higher risk -- the efficient frontier trade-off.

## Customize this template

- **Add more stocks**: Extend `returns.csv` and `covar.csv` with additional assets and their covariance entries.
- **Allow short selling**: Remove the non-negativity constraint to allow negative holdings.
- **Add sector constraints**: Group stocks by sector and limit total allocation per sector.
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

Ensure the covariance matrix is symmetric and positive semi-definite. Check that `covar.csv` contains entries for all (i, j) pairs and that covar(i,j) == covar(j,i). The HiGHS solver requires convexity for QP problems.
</details>
