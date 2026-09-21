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
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
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

**Start here**: run `python production_planning.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is small and illustrative — three CSVs describing a plant with a handful of products and machines, sized so the model solves instantly while showing the full workflow.

- **`products.csv`** — one row per product, with `demand` (base units required) and `profit` (per-unit margin).
- **`machines.csv`** — one row per machine, with `hours_available` per planning period.
- **`production_rates.csv`** — one row per machine-product pair, with `hours_per_unit` (machine time to make one unit). A missing pair means that machine cannot make that product.

The three demand scenarios (`low_demand` 0.8, `baseline` 1.0, `high_demand` 1.1) are defined inline in the script, not loaded from a CSV.

## Model overview

- **Key entities**: `Product` — a product to manufacture, with its base demand and profit margin; `Machine` — a machine with a fixed number of available hours per planning period; `ProductionRate` — how long a given machine takes to make one unit of a given product; `Scenario` — a demand scenario applied uniformly to all products; and the decision concept `Production` — one per production rate, carrying the solved quantity per scenario.
- **Primary identifiers**: integer `id` on `Product` and `Machine`; string `name` on `Scenario`. `ProductionRate` and `Production` are identified structurally by the entities they link.
- **Important invariants**: `demand`, `profit`, `hours_available`, and `hours_per_unit` are non-negative; the decision variable `x_quantity` is a non-negative integer; total machine hours used cannot exceed `hours_available`; total units produced must meet demand scaled by the scenario multiplier.

For the full concept and property definitions, see `production_planning.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline loads the three CSVs into the ontology, layers a `Scenario` concept over them, and hands a single mixed-integer program to the solver that decides production quantities for every scenario at once.

```text
CSV inputs → load Product / Machine / ProductionRate → add Scenario multipliers
  → build the integer production variable (per rate, per scenario)
  → capacity + demand constraints → maximize profit → solve → per-scenario plan
```

1. **Load the data.** Products carry base demand and per-unit profit, machines carry available hours, and each `ProductionRate` links a machine-product pair to the hours it takes to make one unit. A missing pair means that machine cannot make that product.
2. **Add scenarios and the decision variable.** The three demand scenarios become a first-class `Scenario` concept, each with a `demand_multiplier`. The solver decides one non-negative integer quantity per production rate *per scenario*, so all scenarios are solved together in a single call rather than in a loop.
3. **Constrain the plan.** For each machine and scenario, total hours used cannot exceed the machine's available hours. For each product and scenario, total units produced must meet that product's demand scaled by the scenario's multiplier.
4. **Maximize profit.** The objective sums per-unit profit across every production assignment, and the solver returns the profit-maximizing plan for all scenarios at once.

See `production_planning.py` for the implementation and `runbook.md` for the skill-driven reproduction.

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
