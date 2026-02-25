---
title: "Portfolio Optimization"
description: "Allocate investment across stocks to minimize risk while achieving a target return."
featured: false
experience_level: intermediate
industry: "Finance"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - QP
---

# Portfolio Optimization

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13` of the `relationalai` Python package.

## What this template is for

Investors and portfolio managers often need to allocate capital across multiple assets while balancing expected return against risk.
This template implements a classic Markowitz mean-variance model that chooses non-negative allocations to minimize portfolio variance subject to a minimum expected return target.

This template uses RelationalAI's **prescriptive reasoning (optimization)** capabilities to compute an optimal allocation under constraints, and to run a small scenario analysis that illustrates the risk/return trade-off.

Prescriptive reasoning helps you:

- **Quantify trade-offs** between return targets and risk.
- **Enforce constraints** like budgets and no-short-selling.
- **Explore scenarios** by varying the minimum expected return.

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with quadratic objectives.
- You’re comfortable with basic Python and optimization concepts (risk/return, covariance).

## What you’ll build

- A semantic model for stocks, expected returns, and pairwise covariance.
- A quadratic program that chooses non-negative allocations.
- A minimum return constraint and a variance-minimization objective.
- A scenario loop over different minimum return targets with a summary table.

## What’s included

- **Model + solve script**: `portfolio_balancing.py`
- **Sample data**: `data/returns.csv`, `data/covariance.csv`
- **Outputs**: per-scenario solver status/objective, allocation table, and a scenario summary

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://private.relational.ai/templates/zips/v0.13/portfolio_balancing.zip
   unzip portfolio_balancing.zip
   cd portfolio_balancing
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python portfolio_balancing.py
   ```

6. **Expected output**

   The script solves three scenarios for the minimum expected return target.

   ```text
   Running scenario: min_return = 10
     Status: OPTIMAL, Objective: ...

     Portfolio allocation:
     name   value
     ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     10: OPTIMAL, obj=...
     20: OPTIMAL, obj=...
     30: OPTIMAL, obj=...
   ```

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ portfolio_balancing.py    # main runner / entrypoint
└─ data/                     # sample input data
   ├─ returns.csv
   └─ covariance.csv
```

**Start here**: `portfolio_balancing.py`

## Sample data

Data files are in `data/`.

### `returns.csv`

Defines one expected return value per stock.

| Column | Meaning |
| --- | --- |
| `index` | Stock identifier |
| `returns` | Expected return (decimal, e.g., `0.04` = 4%) |

### `covariance.csv`

Defines pairwise covariance values between stock pairs.

| Column | Meaning |
| --- | --- |
| `i` | First stock index |
| `j` | Second stock index |
| `covar` | Covariance between stocks `i` and `j` |

> [!NOTE]
> The covariance matrix is symmetric in the sample data (`covar_ij == covar_ji`).

## Model overview

The semantic model uses a single concept (`Stock`) and a pairwise covariance property (`Stock.covar`). The decision variable is a continuous allocation per stock.

### `Stock`

Represents an investable asset.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `index` | int | Yes | Loaded from `data/returns.csv` |
| `returns` | float | No | Expected return |
| `covar` | float | No | Pairwise covariance with another `Stock` |
| `quantity` | float | No | Decision variable (continuous, non-negative) |

## How it works

This section walks through the highlights in `portfolio_balancing.py`.

### Import libraries and configure inputs

First, the script imports the Semantics and optimization APIs, configures the data directory, and defines the key parameters:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Float, Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# Budget and minimum return parameters.
BUDGET = 1000
MIN_RETURN = 20
```

### Define concepts and load CSV data

Next, it creates a `Model`, defines the `Stock` concept, and loads both CSVs. The covariance values are defined by joining stock indices using `where(...).define(...)`:

```python
# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("portfolio", config=globals().get("config", None), use_lqp=False)

# Stock concept: available investments with expected returns.
Stock = model.Concept("Stock")
Stock.returns = model.Property("{Stock} has {returns:float}")

# Load expected return data from CSV.
data(read_csv(DATA_DIR / "returns.csv")).into(Stock, keys=["index"])

# Stock.covar property: covariance matrix between stock pairs.
Stock.covar = model.Property("{Stock} and {stock2:Stock} have {covar:float}")
Stock2 = Stock.ref()

# Load covariance data from CSV.
covar_csv = read_csv(DATA_DIR / "covariance.csv")
pairs = data(covar_csv)
where(
    Stock.index == pairs.i,
    Stock2.index == pairs.j
).define(
    Stock.covar(Stock, Stock2, pairs.covar)
)
```

### Define decision variables, constraints, and objective

Then it creates a decision variable `Stock.x_quantity` and registers constraints and the quadratic variance objective inside `build_formulation(...)`:

```python
# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Stock.x_quantity decision variable: amount allocated to each stock.
Stock.x_quantity = model.Property("{Stock} quantity is {x:float}")

c = Float.ref()

# Scenario parameter. This is updated inside the scenario loop.
min_return = MIN_RETURN

# Budget is fixed across scenarios.
budget = BUDGET


def build_formulation(s):
    """Register variables, constraints, and objective on the solver model."""
    # Decision variable: quantity of each stock.
    s.solve_for(Stock.x_quantity, name=["qty", Stock.index])

    # Constraint: no short selling.
    bounds = require(Stock.x_quantity >= 0)
    s.satisfy(bounds)

    # Constraint: budget limit.
    budget_constraint = require(sum(Stock.x_quantity) <= budget)
    s.satisfy(budget_constraint)

    # Constraint: minimum return target (scenario parameter).
    return_constraint = require(sum(Stock.returns * Stock.x_quantity) >= min_return)
    s.satisfy(return_constraint)

    # Objective: minimize portfolio risk (variance)
    risk = sum(c * Stock.x_quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
    s.minimize(risk)
```

### Solve and print results

Finally, the script loops over multiple values of `min_return`, creates a fresh `SolverModel` for each scenario, and prints both the allocation and a summary:

```python
# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

SCENARIO_PARAM = "min_return"
SCENARIO_VALUES = [10, 20, 30]

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value.
    min_return = scenario_value

    # Create a fresh SolverModel for each scenario.
    s = SolverModel(model, "cont")
    build_formulation(s)

    solver = Solver("highs")
    s.solve(solver, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "objective": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Objective: {s.objective_value}")

    # Print portfolio allocation from solver results.
    var_df = s.variable_values().to_df()
    qty_df = var_df[
        var_df["name"].str.startswith("qty") & (var_df["float"] > 0.001)
    ].rename(columns={"float": "value"})
    print(f"\n  Portfolio allocation:")
    print(qty_df.to_string(index=False))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

# Print a scenario summary table.
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
```

## Troubleshooting

<details>
  <summary>I get <code>ModuleNotFoundError</code> when running the script</summary>

  - Confirm you created and activated the virtual environment from the Quickstart.
  - Reinstall dependencies with `python -m pip install .`.
  - Verify you are running `python portfolio_balancing.py` from the `portfolio_balancing/` folder.
</details>

<details>
  <summary>The script fails while reading a CSV from <code>data/</code></summary>

  - Confirm `data/returns.csv` and `data/covariance.csv` exist.
  - Verify headers match the expected columns (`index`, `returns`, `i`, `j`, `covar`).
  - Check for missing values and non-numeric entries in return/covariance columns.
</details>

<details>
  <summary>I see an unexpected termination status (not <code>OPTIMAL</code>)</summary>

  - Try re-running; if you hit a time limit, consider increasing `time_limit_sec`.
  - If you changed scenario parameters, confirm the minimum return target is feasible given the budget.
</details>
