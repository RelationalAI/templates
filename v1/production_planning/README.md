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

## What this template is for

Manufacturers must decide how many units of each product to produce on each machine to maximize profit while meeting customer demand and respecting machine capacity. When market conditions are uncertain, planners need to evaluate how production plans change under different demand scenarios.

This template finds the profit-maximizing production plan across a set of machines and products. Each machine has limited available hours, and each machine-product combination has a specific production rate. Three demand scenarios (80%, 100%, and 110% of base demand) are modeled together so decision-makers can see how the optimal plan shifts as demand changes and understand how sensitive their production strategy is to demand fluctuations.

**The reasoning approach uses prescriptive optimization: a single mixed-integer program that solves all demand scenarios simultaneously, with scenario-scoped capacity and demand constraints.**

## Who this is for

- Production planners optimizing machine utilization and product mix
- Operations managers evaluating plans under demand uncertainty
- Developers learning integer programming and scenario analysis with RelationalAI
- **Assumed knowledge**: comfortable reading Python; the optimization and manufacturing terms are explained as they come up

## What you'll build

- A profit-maximizing production plan across machines and products, produced by **prescriptive reasoning** (mixed-integer program)
- Machine-capacity limits enforced as per-machine, per-scenario constraints
- Demand-satisfaction requirements scaled by a per-scenario demand multiplier
- A three-scenario comparison (80% / 100% / 110% of base demand) solved in a single call over a first-class `Scenario` concept

## What's included

- `production_planning.py` -- Main script with the scenario model, constraints, objective, and result summary
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
   curl -O https://docs.relational.ai/templates/zips/v1/production_planning.zip
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

6. Expected output (all scenarios solved together in a single call):
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 44735.0
   • solver: HiGHS
   • relative gap: 0.0

   Production plan per scenario:
          scenario    machine   product  quantity
   0      baseline  Machine_1  Widget_A       4.0
   1      baseline  Machine_1  Widget_C      95.0
   2      baseline  Machine_2  Widget_B      70.0
   3      baseline  Machine_3  Widget_A      96.0
   4      baseline  Machine_3  Widget_B      11.0
   5   high_demand  Machine_1  Widget_A      24.0
   6   high_demand  Machine_1  Widget_B       1.0
   7   high_demand  Machine_1  Widget_C      68.0
   8   high_demand  Machine_2  Widget_B      70.0
   9   high_demand  Machine_3  Widget_A      87.0
   10  high_demand  Machine_3  Widget_B      17.0
   11   low_demand  Machine_1  Widget_C     100.0
   12   low_demand  Machine_2  Widget_B      70.0
   13   low_demand  Machine_3  Widget_A     111.0
   14   low_demand  Machine_3  Widget_B       1.0
   ```

   The single objective (`44735.0`) is the combined profit across all three scenarios. Per-scenario profit is $15,020 (0.8x), $14,945 (1.0x), and $14,770 (1.1x) — profit *falls* as the demand floor rises, because a looser floor leaves more capacity for the highest-margin mix.

## Template structure

```text
production_planning/
├── README.md               # this file
├── pyproject.toml          # dependencies
├── production_planning.py   # main script (single solve over all scenarios)
├── runbook.md              # analyst-facing walkthrough
└── data/
    ├── products.csv        # products with base demand and per-unit profit
    ├── machines.csv        # machines with available hours per period
    └── production_rates.csv # hours per unit for each machine-product pair
```

**Start here**: run `python production_planning.py` for the end-to-end solve, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is small and illustrative — three CSVs describing a plant with a handful of products and machines, sized so the model solves instantly while showing the full workflow.

- **`products.csv`** — one row per product, with `demand` (base units required) and `profit` (per-unit margin).
- **`machines.csv`** — one row per machine, with `hours_available` per planning period.
- **`production_rates.csv`** — one row per machine-product pair, with `hours_per_unit` (machine time to make one unit). A missing pair means that machine cannot make that product.

The three demand scenarios (`low_demand` 0.8, `baseline` 1.0, `high_demand` 1.1) are defined inline in the script, not loaded from a CSV.

## Model overview

- **Key entities**: `Product`, `Machine`, `ProductionRate`, `Scenario`, and the decision concept `Production`.
- **Primary identifiers**: integer `id` on `Product` and `Machine`; string `name` on `Scenario`. `ProductionRate` and `Production` are identified structurally by the entities they link.
- **Important invariants**: `demand`, `profit`, `hours_available`, and `hours_per_unit` are non-negative; the decision variable `x_quantity` is a non-negative integer; total machine hours used cannot exceed `hours_available`; total units produced must meet demand scaled by the scenario multiplier.

**`Product`** — a product to manufacture, with its base demand and profit margin.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/products.csv` |
| `name` | String | No | Human-readable product name |
| `demand` | Integer | No | Base units required (scaled per scenario) |
| `profit` | Float | No | Per-unit profit margin |

**`Machine`** — a machine with a fixed number of available hours per planning period.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/machines.csv` |
| `name` | String | No | Human-readable machine name |
| `hours_available` | Float | No | Capacity per planning period |

**`ProductionRate`** — how long a given machine takes to make one unit of a given product.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `machine` | Relationship | — | Link to `Machine` |
| `product` | Relationship | — | Link to `Product` |
| `hours_per_unit` | Float | No | Machine hours per unit, from `data/production_rates.csv` |

**`Scenario`** — a demand scenario applied uniformly to all products.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | `low_demand` / `baseline` / `high_demand` |
| `demand_multiplier` | Float | No | Scales each product's demand (0.8 / 1.0 / 1.1) |

**`Production`** — the decision concept, one per production rate; carries the solved quantity per scenario.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `rate` | Relationship | — | Link to the `ProductionRate` being decided |
| `x_quantity` | Float (integer decision) | No | Units to produce, indexed by `Scenario`; the solver's decision variable |

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

### 2. Define decision variables and scenarios

Scenarios are modeled as a `Scenario` concept with a `demand_multiplier` property — all scenarios are solved in a single call, not a loop.

```python
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.demand_multiplier = Property(f"{Scenario} has {Float:demand_multiplier}")

problem = Problem(model, Float)

# Variable indexed by Scenario — one quantity per production rate per scenario
Production.x_quantity = Property(f"{Production} in {Scenario} has {Float:quantity}")
problem.solve_for(
    Production.x_quantity(Scenario, x_qty),
    name=["qty", Scenario.name, Production.rate.machine.name, Production.rate.product.name],
    lower=0, type="int",
)
```

### 3. Add constraints

Machine capacity and demand satisfaction constraints are defined per scenario.

```python
# Machine capacity: total production hours <= available hours (per machine, per scenario)
problem.satisfy(model.where(...).require(
    sum(x_qty * Production.rate.hours_per_unit)
    .where(Production.rate.machine == Machine)
    .per(Machine, Scenario)
    <= Machine.hours_available
))

# Meet scaled demand (per product, per scenario)
problem.satisfy(model.where(...).require(
    sum(x_qty).where(Production.rate.product == Product).per(Product, Scenario)
    >= Product.demand * Scenario.demand_multiplier
))
```

### 4. Maximize profit

The objective maximizes total profit across all production assignments.

```python
total_profit = sum(Production.x_quantity * Production.rate.product.profit)
problem.maximize(total_profit)
```

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the column names listed in *Sample data* above.
- Add a `production_rates.csv` row for every machine-product pair a machine can actually make; omit pairs it cannot make.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)`.

### Tune parameters

- **Demand scenarios** — edit the `scenario_data` list at the top of the script to change the multipliers or add scenarios.
- **Solver time limit** — `time_limit_sec` (default `60`) on the `problem.solve(...)` call.
- **Extend scenario analysis** to vary other parameters, such as machine availability or profit margins.

### Extend the model

- **Add raw material constraints** by introducing material requirements per product and inventory limits.
- **Model setup times** between product changeovers on the same machine.
- **Add minimum lot sizes** by setting lower bounds on production quantities when a product is produced.

### Scale up / productionize

- Replace the CSV bundle with ingestion from your ERP or MES tables.
- Integer programs grow harder with more products, machines, and scenarios; give the solver more time via `time_limit_sec`, or relax integrality during exploratory runs (see Troubleshooting).

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

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, `.per(...)`, aggregations, and `model.select(...)`.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.

### Deeper dives

- [Scenario modeling with a `Scenario` concept](https://docs.relational.ai/) — how a single solve covers multiple parameter settings via a scenario-indexed decision variable.

## Support

- File issues at the RelationalAI templates repository.
