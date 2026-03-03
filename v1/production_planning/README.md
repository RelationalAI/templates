---
title: "Production Planning"
description: "Schedule production across machines to meet demand and maximize profit with scenario analysis."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Production
  - Manufacturing
  - Scenario Analysis
---

# Production Planning

## What this template is for

Manufacturers must decide how many units of each product to produce on each machine to maximize profit while meeting customer demand and respecting machine capacity. When market conditions are uncertain, planners need to evaluate how production plans change under different demand scenarios.

This template uses prescriptive reasoning to find the profit-maximizing production plan across a set of machines and products. Each machine has limited available hours, and each machine-product combination has a specific production rate. The model runs multiple demand scenarios (80%, 100%, and 110% of base demand) to show how the optimal plan shifts as demand changes.

The scenario analysis loop demonstrates a powerful pattern for what-if planning. By solving the same model structure under different parameter values, decision-makers can understand the sensitivity of their production strategy to demand fluctuations.

## Who this is for

- Production planners optimizing machine utilization and product mix
- Operations managers evaluating plans under demand uncertainty
- Developers learning integer programming and scenario analysis with RelationalAI
- Anyone building production scheduling or capacity planning tools

## What you'll build

- A multi-machine, multi-product production planning model with integer variables
- Machine capacity constraints based on production rates
- Demand satisfaction constraints with configurable demand multipliers
- A profit maximization objective
- A scenario analysis loop comparing results across demand levels

## What's included

- `production_planning.py` -- Main script with scenario loop, model definition, and result summaries
- `data/products.csv` -- Products with base demand and per-unit profit margins
- `data/machines.csv` -- Machines with available hours per planning period
- `data/production_rates.csv` -- Hours required per unit for each machine-product combination
- `pyproject.toml` -- Python project configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -L -O https://docs.relational.ai/templates/zips/v1/production_planning.zip
   unzip production_planning.zip
   cd production_planning
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
   python production_planning.py
   ```

6. Expected output:
   ```text
   Running scenario: demand_multiplier = 0.8
     Status: OPTIMAL, Objective: 14650.0

     Production plan:
              name  value
    qty_Machine_1_Widget_A   80.0
    qty_Machine_1_Widget_C   48.0
    qty_Machine_2_Widget_B   64.0
    qty_Machine_3_Widget_A    2.0
    qty_Machine_3_Widget_B    2.0

   Running scenario: demand_multiplier = 1.0
     Status: OPTIMAL, Objective: 15950.0

     Production plan:
              name  value
    qty_Machine_1_Widget_A   80.0
    qty_Machine_1_Widget_C   60.0
    qty_Machine_2_Widget_B   70.0
    qty_Machine_3_Widget_A   20.0
    qty_Machine_3_Widget_B   10.0

   Running scenario: demand_multiplier = 1.1
     Status: OPTIMAL, Objective: 16800.0

     Production plan:
              name  value
    qty_Machine_1_Widget_A   80.0
    qty_Machine_1_Widget_B   10.0
    qty_Machine_1_Widget_C   66.0
    qty_Machine_2_Widget_B   70.0
    qty_Machine_3_Widget_A   30.0
    qty_Machine_3_Widget_B   10.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
     0.8: OPTIMAL, obj=14650.0
     1.0: OPTIMAL, obj=15950.0
     1.1: OPTIMAL, obj=16800.0
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── production_planning.py
└── data/
    ├── products.csv
    ├── machines.csv
    └── production_rates.csv
```

## How it works

### 1. Define the ontology and load data

The model defines products with demand and profit, machines with available hours, and production rates linking each machine-product pair.

```python
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")
Product.profit = Property(f"{Product} has {Float:profit}")

Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.hours_available = Property(f"{Machine} has {Float:hours_available}")

Rate = Concept("ProductionRate")
Rate.machine = Property(f"{Rate} on {Machine}", short_name="machine")
Rate.product = Property(f"{Rate} for {Product}", short_name="product")
Rate.hours_per_unit = Property(f"{Rate} has {Float:hours_per_unit}")
```

### 2. Run scenario analysis

The script loops over demand multipliers, creating a fresh Problem for each scenario. This lets you compare optimal plans under different demand assumptions.

```python
SCENARIO_VALUES = [0.8, 1.0, 1.1]

for demand_multiplier in SCENARIO_VALUES:
    s = Problem(model, Float)

    s.solve_for(Production.x_quantity,
        name=["qty", Production.rate.machine.name, Production.rate.product.name],
        lower=0, type="int", populate=False)
```

### 3. Add constraints

Machine capacity and demand satisfaction constraints are parameterized by the current demand multiplier.

```python
# Machine capacity: total production hours <= available hours
machine_hours = sum(ProductionRef.x_quantity * ProductionRef.rate.hours_per_unit).where(
    ProductionRef.rate.machine == Machine).per(Machine)
s.satisfy(model.require(machine_hours <= Machine.hours_available))

# Meet scaled demand
product_qty = sum(ProductionRef.x_quantity).where(
    ProductionRef.rate.product == Product).per(Product)
s.satisfy(model.require(product_qty >= Product.demand * demand_multiplier))
```

### 4. Maximize profit

The objective maximizes total profit across all production assignments.

```python
total_profit = sum(Production.x_quantity * Production.rate.product.profit)
s.maximize(total_profit)
```

## Customize this template

- **Add more products or machines** by extending the CSV files.
- **Add raw material constraints** by introducing material requirements per product and inventory limits.
- **Model setup times** between product changeovers on the same machine.
- **Extend scenario analysis** to vary other parameters like machine availability or profit margins.
- **Add minimum lot sizes** by setting lower bounds on production quantities when a product is produced.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE for high demand multipliers</summary>

Machine capacity limits how much can be produced. If the demand multiplier is too high, the machines may not have enough hours to meet all demand. Try increasing `hours_available` in `machines.csv` or reducing the demand multiplier.
</details>

<details>
<summary>Integer solutions take longer to solve</summary>

Integer programming is harder than continuous optimization. For large instances, consider relaxing integer constraints during exploratory analysis by changing `type="int"` to `type="cont"`, then switch back for final planning.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>
