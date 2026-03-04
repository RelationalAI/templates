---
title: "Factory Production"
description: "Maximize profit from production with limited resource availability per factory."
featured: false
experience_level: beginner
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Profit Maximization
  - Resource Allocation
  - Scenario Analysis
---

# Factory Production

## What this template is for

Manufacturing operations must decide how much of each product to produce at each factory to maximize profit, given limited resources and bounded demand. Each product has a production rate (units per hour of resource), a profit per unit, and a maximum demand. Each factory has a fixed number of available resource-hours.

This template formulates the problem as a linear program. Decision variables represent the quantity of each product to produce. Constraints ensure that total resource usage at each factory does not exceed availability and that production does not exceed demand. The objective maximizes total profit.

The template solves the problem independently per factory, demonstrating a scenario-based approach where each factory is treated as a separate optimization. This pattern is useful when factories operate autonomously or when you want to analyze each facility's optimal production mix in isolation.

## Who this is for

- Manufacturing planners optimizing production schedules
- Operations researchers learning resource-constrained profit maximization
- Data scientists exploring factory-level scenario analysis
- Beginners looking for a clean LP example with real-world context

## What you'll build

- A linear programming model that determines optimal production quantities per product
- Resource capacity constraints tied to factory availability
- Demand upper bounds on each product
- Per-factory scenario analysis with independent optimization

## What's included

- `factory_production.py` -- Main script defining the optimization model, constraints, and per-factory scenarios
- `data/factories.csv` -- Factory names and available resource-hours
- `data/products.csv` -- Products with factory assignment, production rate, profit, and demand cap
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
   curl -O https://docs.relational.ai/templates/zips/v1/factory_production.zip
   unzip factory_production.zip
   cd factory_production
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
   python factory_production.py
   ```

6. Expected output:
   ```text
   For factory: steel_factory
     Status: OPTIMAL, Profit: $192000.00
     Production plan:
      name     value
     bands    6000.0
     coils    1400.0

   For factory: amazing_brewery
     Status: OPTIMAL, Profit: $6000.00
     Production plan:
      name     value
    stouts    1000.0
      ales    1000.0

   ==================================================
   Factory Production Summary
   ==================================================
     steel_factory: OPTIMAL, profit=$192000.00
     amazing_brewery: OPTIMAL, profit=$6000.00
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── factory_production.py
└── data/
    ├── factories.csv
    └── products.csv
```

## How it works

### 1. Define concepts and load data

The model defines `Factory` (with available resource-hours) and `Product` (with factory assignment, production rate, profit, and demand). A relationship links products to their factory:

```python
Factory = Concept("Factory", identify_by={"name": String})
Factory.avail = Property(f"{Factory} has {Float:avail}")

Product = Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = Property(f"{Product} is produced by {Factory}")
Product.rate = Property(f"{Product} has {Float:rate}")
Product.profit = Property(f"{Product} has {Float:profit}")
Product.demand = Property(f"{Product} has {Integer:demand}")
```

### 2. Decision variables

Each product gets a continuous variable bounded between 0 and its demand cap:

```python
s.solve_for(
    Product.x_quantity,
    lower=0,
    upper=Product.demand,
    name=Product.name,
    where=[this_product],
    populate=False,
)
```

### 3. Constraints and objective

Resource usage at each factory must not exceed availability. The objective maximizes total profit:

```python
profit = sum(Product.profit * Product.x_quantity).where(this_product)
s.maximize(profit)

s.satisfy(model.require(
    sum(Product.x_quantity / Product.rate) <= Factory.avail
).where(this_product, Factory.name(factory_name)))
```

### 4. Per-factory scenario analysis

The template iterates over factories and solves an independent optimization for each, filtering products by their factory assignment. This allows comparison of optimal production plans across facilities.

## Customize this template

- **Add more factories and products**: Extend the CSV files. The model automatically picks up new data and creates scenarios per factory.
- **Shared resources across factories**: Remove the per-factory loop and solve a single global problem with cross-factory resource constraints.
- **Multi-period planning**: Add a time dimension to model production across multiple periods with inventory carryover.
- **Integer production**: Change the variable type from continuous to integer if products must be produced in whole units.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

Check that factory availability is sufficient to produce at least some quantity of each product. If demand is high but resource-hours are too low, the bounded problem may still be feasible but produce small quantities.
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
<summary>Products missing from solution</summary>

Products with zero quantity in the solution are not profitable enough to justify their resource usage. This is expected when resource availability is tight. Increase factory `avail` or reduce the production rate to see more products in the plan.
</details>
