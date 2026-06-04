---
title: "Factory Production"
description: "Maximize production profit under per-factory resource limits, then read the sensitivity marginals (capacity shadow prices and product reduced costs) from one solve."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Profit Maximization
  - Resource Allocation
  - Sensitivity Analysis
  - Shadow Prices
---

# Factory Production

## What this template is for

This template uses **Prescriptive** reasoning to maximize factory production profit under resource constraints, and then to read back the **sensitivity marginals** a planner asks next — all from a single solve. It is a compact, textbook **product-mix linear program**: the cleanest setting in this portfolio for learning what shadow prices and reduced costs mean.

Manufacturing operations must decide how much of each product to produce at each factory to maximize profit, given limited resources and bounded demand. Each product has a production rate (units per hour of resource), a profit per unit, and a maximum demand. Each factory has a fixed number of available resource-hours.

This template formulates the problem as a linear program. Decision variables represent the quantity of each product to produce, bounded above by demand. A per-factory constraint keeps total resource usage within availability, and the objective maximizes total profit.

A plain solve answers *"what is the most profitable production plan?"*. Adding `sensitivity=True` to the solve ALSO answers the marginal questions — in the same solve, with the answers read straight off the variable and constraint objects:

- **Capacity shadow price** (`cap.shadow_price`): how much total profit moves per extra hour at a factory. A capacity with idle hours prices at **zero** (it is not the bottleneck); a positive price flags a binding capacity worth expanding — so this ranks which factory to expand first. (The rule is one-way: slack ⇒ zero price, and a positive price ⇒ binding.)
- **Product reduced cost** and **basis status** (`quantity_var.reduced_cost` / `quantity_var.basis_status`): a product held at its demand cap shows a positive reduced cost here (the extra profit per unit of demand allowed); the swing product that sets the binding factory's marginal price is `BASIC` at ~0.

Because the objective is a **maximization**, the *capacity shadow price* is the mirror image of a minimize-cost model — a binding `<=` capacity prices `>= 0` here, versus `<= 0` in the cost-minimizing [`supplier_reliability`](../supplier_reliability/) template. The nonbasic bound marginals shown in *both* tables are non-negative; what flips for the *product* marginal is the active bound — the binding product is `NONBASIC_AT_UPPER` (its demand cap) here, versus `NONBASIC_AT_LOWER` (zero) there. Laying the two reduced-cost tables side by side is the fastest way to internalize the conventions.

> **Production-planning learning ladder**
> 1. **Factory Production** *(this template)* — single-period product-mix LP with sensitivity analysis.
> 2. [`production_planning`](../production_planning/) — multi-machine assignment with integer decisions and demand multipliers.
> 3. [`demand_planning_temporal`](../demand_planning_temporal/) — multi-period production + inventory across sites with date-filtered planning horizon.

## Who this is for

- Manufacturing planners optimizing production schedules and ranking capacity investments
- Operations researchers learning resource-constrained profit maximization and LP duality
- Data scientists who want shadow prices and reduced costs without leaving the model
- Anyone learning what "sensitivity analysis" means on a small, fully hand-checkable LP

## What you'll build

- A linear programming model that determines optimal production quantities per product
- Per-factory resource capacity constraints, captured as handles for marginal read-back
- Demand upper bounds on each product (whose marginals surface as reduced costs)
- A one-solve sensitivity report: capacity shadow prices, product reduced costs, and basis status, each joined back to its factory/product by entity key

## What's included

- `factory_production.py` -- Main script defining the optimization model, constraints, objective, and sensitivity read-back
- `data/factories.csv` -- Factory names and available resource-hours
- `data/products.csv` -- Products with factory assignment, production rate, profit, and demand cap
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

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

6. Expected output (model and solver display trimmed):
   ```text
   Baseline status: OPTIMAL, total profit: 200000.00

   Production plan:
           factory product  quantity
   amazing_brewery    ales    2000.0
   amazing_brewery  stouts    1000.0
     steel_factory   bands    6000.0
     steel_factory   coils    1400.0

   Factory capacity shadow prices (d profit / d hour):
           factory  avail  shadow_price
   amazing_brewery   30.0          -0.0
     steel_factory   40.0        4200.0

   Product reduced costs and basis status:
           factory product  reduced_cost      basis_status
   amazing_brewery    ales           2.0 NONBASIC_AT_UPPER
   amazing_brewery  stouts           4.0 NONBASIC_AT_UPPER
     steel_factory   bands           4.0 NONBASIC_AT_UPPER
     steel_factory   coils          -0.0             BASIC

   Most profit-sensitive capacity: steel_factory (d profit / d hour = +4200.00)

   ==================================================
   Factory Capacity Summary
   ==================================================
           factory  avail  hours_used  idle
   amazing_brewery   30.0        25.0   5.0
     steel_factory   40.0        40.0   0.0
   ```

   Reading the result: `steel_factory` fills all 40 hours (it is the binding factory, so its capacity prices at **+4200/hour** — the per-hour profit of the swing product `coils`, i.e. its 30/unit profit × 140 units/hour rate). `amazing_brewery` meets all demand in 25 of its 30 hours, so its capacity is **slack** and prices at **0** — its bottleneck is demand, not capacity. Each of these demand-capped products (`bands`, `stouts`, `ales`) carries a positive reduced cost here: the profit you would gain per extra unit of demand allowed.

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

Each product gets a continuous variable bounded between 0 and its demand cap. The demand cap is the variable's **upper bound** (not a separate constraint), so its marginal surfaces later as the variable's *reduced cost*:

```python
quantity_var = problem.solve_for(
    Product.x_quantity,
    name=["qty", Product.factory.name, Product.name],
    lower=0,
    upper=Product.demand,
    populate=False,
)
```

### 3. Capacity constraint and objective

Each factory's total resource usage must not exceed its availability. The constraint is captured as a handle (`cap`), named per factory (a readable label), and declared with `keyed_by={"factory": Factory}`, so each instance's shadow price reads back through that **entity key** (`cap.factory`) rather than by parsing a name string. The objective maximizes total profit across all factories:

```python
cap = problem.satisfy(
    model.require(
        sum(Product.x_quantity / Product.rate)
        .where(Product.factory == Factory)
        .per(Factory)
        <= Factory.avail
    ),
    name=["cap", Factory.name],
    keyed_by={"factory": Factory},
)

problem.maximize(sum(Product.profit * Product.x_quantity))
problem.solve("highs", time_limit_sec=60, sensitivity=True)
```

### 4. Read the sensitivity marginals

After a `sensitivity=True` solve, the marginals are attributes on the captured handles. A constraint carries the entity back-pointer declared with `keyed_by` (`cap.factory`) and a variable carries an automatic one to its product (`quantity_var.product`), so each marginal joins to that entity's own data by key — no pandas, no name parsing:

```python
# Which factory's capacity to expand first?
model.select(cap.factory.name, cap.factory.avail, cap.shadow_price).inspect()

# Which products are pinned at their demand cap, and which is the swing product?
model.select(
    quantity_var.product.factory.name,
    quantity_var.product.name,
    quantity_var.reduced_cost,
    quantity_var.basis_status,
).inspect()
```

Sensitivity marginals are exact for a linear program. They describe the rate of change at the current optimum, valid over a range; a large, discrete change (adding a factory, removing a product) is a structural change best answered by re-solving.

## Customize this template

- **Find the demand bottleneck**: Raise `amazing_brewery`'s demand caps in `products.csv`. Once its 30 hours bind, its capacity shadow price jumps from 0 to positive — capacity becomes the bottleneck.
- **Shift the swing product**: Lower `steel_factory`'s `avail` in `factories.csv`. `coils` (the basic, swing product) shrinks but stays the swing down to just above 30 hours, so the shadow price holds at 4200. At exactly 30 hours `coils` hits zero — a degenerate breakpoint where the marginal is one-sided — and below 30 hours `bands` becomes the swing and the price rises to 5000.
- **Add more factories and products**: Extend the CSV files. The model and the per-factory marginals pick up new rows automatically.
- **Integer production**: Change the variable type from continuous to integer if products must be produced in whole units. Note that sensitivity marginals are an LP concept — they are reported only for continuous (LP/QP) problems, and are empty for integer models.

## Troubleshooting

<details>
<summary>Shadow prices or reduced costs are all empty</summary>

Sensitivity marginals are an LP/QP concept. They are populated only when the problem is continuous and solved with `sensitivity=True`. An integer (MIP) model returns no marginals — keep the production variables continuous to see them.
</details>

<details>
<summary>A factory's capacity shadow price is zero</summary>

Usually that factory has idle resource-hours — slack capacity, so an extra hour buys nothing, and its bottleneck is elsewhere (typically product demand). Confirm with the `idle` column in the capacity summary: a positive `idle` is genuine slack. (Less commonly, a *binding* capacity can also price at zero under degeneracy — zero idle hours yet a zero price — so read the `idle` column, not the price alone.)
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
<summary>Products missing from the plan</summary>

A product with zero quantity is not profitable enough to justify its resource usage given tighter, more profitable competitors. Its reduced cost tells you how far its economics are from being worth producing. Increase factory `avail`, raise the product's profit, or lower its production rate to bring it into the plan.
</details>
