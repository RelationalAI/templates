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

## What this template is for

Manufacturing operations must decide how much of each product to make at each factory to maximize profit, given limited resources and bounded demand. Answering "what is the most profitable plan?" is only half the job. The planner's next questions are marginal ones: which factory's capacity is the bottleneck worth expanding, and which products are held back by demand rather than by the plant. This template answers both from a single solve, on a small, fully hand-checkable product-mix problem that makes shadow prices and reduced costs concrete.

**It uses Prescriptive reasoning to solve a product-mix linear program and, with one `sensitivity=True` flag on the same solve, reads the capacity shadow prices and product reduced costs straight off the constraint and variable objects.**

> **Production-planning learning ladder**
> 1. **Factory Production** *(this template)* -- single-period product-mix LP with sensitivity analysis.
> 2. [`production_planning`](../production_planning/) -- multi-machine assignment with integer decisions and demand multipliers.
> 3. [`demand_planning_temporal`](../demand_planning_temporal/) -- multi-period production + inventory across sites with date-filtered planning horizon.

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
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself
- `data/factories.csv` -- Factory names and available resource-hours
- `data/products.csv` -- Products with factory assignment, production rate, profit, and demand cap
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.11.0

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

   Reading the result: `steel_factory` fills all 40 hours (it is the binding factory, so its capacity prices at **+4200/hour** -- the per-hour profit of the swing product `coils`, i.e. its 30/unit profit times its 140 units/hour rate). `amazing_brewery` meets all demand in 25 of its 30 hours, so its capacity is **slack** and prices at **0** -- its bottleneck is demand, not capacity. Each of these demand-capped products (`bands`, `stouts`, `ales`) carries a positive reduced cost here: the profit you would gain per extra unit of demand allowed.

## Template structure

```text
.
├── README.md                 # this file
├── runbook.md                # step-by-step analyst walkthrough
├── pyproject.toml            # dependencies
├── factory_production.py     # main script (LP model + sensitivity read-back)
└── data/
    ├── factories.csv         # factory names and available resource-hours
    └── products.csv          # products with factory, rate, profit, demand cap
```

**Start here**: run `python factory_production.py` for the full solve and sensitivity report end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is a small, hand-checkable product-mix setting -- two factories that share no resources, so the joint optimum is each factory solved independently, but one solve reads every factory's marginals side by side.

- **`data/factories.csv`** (2 rows) -- `steel_factory` (40 available hours) and `amazing_brewery` (30 available hours).
- **`data/products.csv`** (4 rows) -- `bands` and `coils` at `steel_factory`, `stouts` and `ales` at `amazing_brewery`, each with a production `rate` (units per hour), a unit `profit`, and a `demand` cap.

Product names are unique across factories, so the plan can be keyed by product name alone. The script asserts the expected factory and product names on load, so an edit to `data/` fails loudly rather than silently passing the name-gated sensitivity checks on zero rows.

## Model overview

The model has two concepts and one relationship linking them; the decision variable and its marginals hang off `Product`.

- **Key entities**: `Factory` (a plant with an hourly resource budget) and `Product` (an item made at one factory).
- **Primary identifiers**: `Factory` by `name`; `Product` by `name` plus `factory_name` (a composite identity).
- **Important invariants**: production quantities are non-negative and capped at each product's demand; each factory's total resource usage stays within its available hours; profit and rate are positive.

For the full concept and property definitions, see `factory_production.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The template loads two source tables, sets up one product-mix LP, and reads the marginals off the same solve:

```text
factories.csv + products.csv → decision variables → capacity constraint + profit objective → sensitivity solve → shadow prices + reduced costs
```

1. **Define concepts and load data.** `Factory` carries its available resource-hours; `Product` carries a per-hour production rate, unit profit, and demand cap, and links to the factory that produces it (a composite `(name, factory_name)` identity).

2. **Decision variables.** Each product gets a continuous quantity variable bounded between 0 and its demand cap. The demand cap is the variable's *upper bound* (not a separate constraint), so its marginal surfaces as the variable's reduced cost.

3. **Capacity constraint and objective.** Each factory's total resource usage (quantity over rate, summed) must stay within its available hours. The constraint is captured as a handle keyed by `Factory`, so each instance's shadow price reads back through the entity key rather than by parsing a name string. The objective maximizes total profit, and the solve runs with `sensitivity=True`.

4. **Read the sensitivity marginals.** After the solve, marginals are attributes on the captured handles: each constraint carries an entity back-pointer to its factory and each variable an automatic one to its product, so every marginal joins to that entity's own data by key — no pandas, no name parsing.

### Reading the marginals: two objects, one sign convention

The two sensitivity objects come from two different modeling choices. Capacity is a *constraint*, so its marginal is a shadow price; the demand cap is a variable *upper bound*, so its marginal is a reduced cost. A capacity shadow price answers "how much profit per extra hour at this factory", and a positive value flags the binding capacity to expand first. A product reduced cost answers "how much profit per extra unit of demand allowed" for a product pinned at its cap; the swing product that sets the binding factory's marginal price is `BASIC` at about zero.

Because the objective is a maximization, the signs mirror a minimize-cost model: a binding capacity prices at zero or above here, versus zero or below in the cost-minimizing [`supplier_reliability`](../supplier_reliability/) template, and a demand-capped product sits at its upper bound (`NONBASIC_AT_UPPER`) here while a priced-out supply lane there sits at its lower bound of zero (`NONBASIC_AT_LOWER`). Laying the two reduced-cost tables side by side is the fastest way to internalize the conventions.

Sensitivity marginals are exact for a linear program. They describe the rate of change at the current optimum -- the range over which that rate holds is not reported (there is no RHS/coefficient ranging) -- and a large, discrete change (adding a factory, removing a product) is a structural change best answered by re-solving.

See `factory_production.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace `data/factories.csv` (columns `name`, `avail`) and `data/products.csv` (columns `factory_name`, `name`, `rate`, `profit`, `demand`) with your own rows. The model and the per-factory marginals pick up new factories and products automatically.
- Keep product names unique across factories, or key the plan by the composite `(factory_name, name)` instead of by name alone.
- Update the `EXPECTED_FACTORIES` / `EXPECTED_PRODUCTS` guard sets at the top of the script (or remove them) so the load-time assertions match your data.

### Tune parameters

- **Find the demand bottleneck**: raise `amazing_brewery`'s demand caps in `products.csv`. Once its 30 hours bind, its capacity shadow price jumps from zero to positive -- capacity becomes the bottleneck.
- **Shift the swing product**: lower `steel_factory`'s `avail` in `factories.csv`. `coils` (the basic, swing product) shrinks but stays the swing down to just above 30 hours, so the shadow price holds at 4200. At exactly 30 hours `coils` hits zero -- a degenerate breakpoint where the marginal is one-sided -- and below 30 hours `bands` becomes the swing and the price rises to 5000.

### Extend the model

- **Add more factories and products**: extend the CSV files. The model and the per-factory marginals pick up new rows automatically.
- **Add shared resources**: today the factories share no resources. Add a constraint over a resource used across factories to couple their plans and make the joint solve more than the sum of independent ones.

### Scale up / productionize

- **Integer production**: change the variable type from continuous to integer if products must be produced in whole units. Sensitivity marginals are an LP concept -- they are reported only for continuous (LP/QP) problems, and are empty for integer models.
- Point the `read_csv` calls at Snowflake tables via `model.data(...)` to run the same model over warehouse-scale reference data.

## Troubleshooting

<details>
<summary>Shadow prices or reduced costs are all empty</summary>

Sensitivity marginals are an LP/QP concept. They are populated only when the problem is continuous and solved with `sensitivity=True`. An integer (MIP) model returns no marginals -- keep the production variables continuous to see them.
</details>

<details>
<summary>A factory's capacity shadow price is zero</summary>

Usually that factory has idle resource-hours -- slack capacity, so an extra hour buys nothing, and its bottleneck is elsewhere (typically product demand). Confirm with the `idle` column in the capacity summary: a positive `idle` is genuine slack. (Less commonly, a *binding* capacity can also price at zero under degeneracy -- zero idle hours yet a zero price -- so read the `idle` column, not the price alone.)
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

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used throughout this template.
- [Sensitivity analysis](https://docs.relational.ai/) — shadow prices, reduced costs, and basis status on a solved linear program.

### Language / modeling reference

- [PyRel v1 language](https://docs.relational.ai/) — concepts, properties, and relationships as used in the model definition.

### Deeper dives

- [`supplier_reliability`](../supplier_reliability/) — a cost-minimizing companion whose sign conventions mirror this one; reading the two side by side clarifies the marginals.
- [`production_planning`](../production_planning/) and [`demand_planning_temporal`](../demand_planning_temporal/) — the next rungs of the production-planning learning ladder.

## Support

- File issues at the RelationalAI templates repository.
