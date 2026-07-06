---
title: "Supplier Reliability"
description: "Select suppliers to meet product demand at minimum cost, with sensitivity marginals and supplier-disruption scenario analysis."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - Supplier Selection
  - Scenario Analysis
  - Sensitivity Analysis
  - Cost Optimization
---

## What this template is for

Procurement teams must choose which suppliers to source from when multiple options exist for each product. Each supplier has different pricing and capacity limits, and the challenge is to meet all product demand at minimum cost without overloading any supplier. Beyond the cheapest plan, a planner wants to know which supplier is the real bottleneck, what one more unit of demand would cost, and how badly the plan breaks if a key supplier goes offline.

This template answers all of those in one place: it finds the cost-minimizing sourcing plan, reads off the marginal values that rank where to invest next, and re-solves under supplier-disruption scenarios to test resilience.

**Prescriptive reasoning formulates supplier selection as a linear program**, solved once with sensitivity analysis for the marginals and re-solved per scenario for the disruption tests.

## Who this is for

- Supply chain and procurement analysts evaluating supplier portfolios
- Operations researchers modeling multi-supplier sourcing decisions
- Developers learning how to build scenario analysis into optimization models with RelationalAI

## What you'll build

- A linear programming model that allocates order quantities across suppliers and products
- Capacity and demand satisfaction constraints
- A baseline solve with sensitivity analysis: capacity and demand shadow prices, plus lane reduced costs and basis status, read back by entity key
- A scenario loop that excludes suppliers one at a time to assess supply chain risk
- A summary comparing cost and feasibility across scenarios

## What's included

- **Model**: `Supplier`, `Product`, and `SupplyOption` concepts, a `SupplyOrder` decision concept holding the order-quantity variable, capacity and demand constraints, and a cost-minimizing objective.
- **Runner**: `supplier_reliability.py` -- a single Python script that loads data, runs the baseline solve with sensitivity analysis, reads the marginals, and runs the disruption scenarios end to end.
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: three CSVs under `data/` describing suppliers, products, and per-supplier-product supply options. See *Sample data* below.
- **Outputs**: the baseline plan with capacity and demand shadow prices, lane reduced costs and basis status, a per-scenario order plan, and a scenario-analysis summary printed to stdout.

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
   curl -O https://docs.relational.ai/templates/zips/v1/supplier_reliability.zip
   unzip supplier_reliability.zip
   cd supplier_reliability
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
   python supplier_reliability.py
   ```

6. Expected output (model and solver display trimmed; marginal tables are read back by entity key):
   ```text
   Baseline status: OPTIMAL, objective: 4850.00

   Baseline orders:
    supplier   product  quantity
   SupplierB Component     150.0
   SupplierC Component      50.0
   SupplierC    Gadget     250.0
   SupplierC    Widget     300.0

   Lane reduced costs and basis status:
    supplier   product  reduced_cost      basis_status
   SupplierA    Gadget           3.0 NONBASIC_AT_LOWER
   SupplierA    Widget           2.0 NONBASIC_AT_LOWER
   SupplierB Component           0.0             BASIC
   SupplierB    Gadget           0.0 NONBASIC_AT_LOWER
   SupplierB    Widget           0.0 NONBASIC_AT_LOWER
   SupplierC Component           0.0             BASIC
   SupplierC    Gadget           0.0             BASIC
   SupplierC    Widget           0.0             BASIC
   SupplierD Component           2.0 NONBASIC_AT_LOWER
   SupplierD    Gadget           2.0 NONBASIC_AT_LOWER

   Supplier capacity shadow prices (d cost / d capacity):
    supplier capacity  shadow_price
   SupplierA      500           0.0
   SupplierB      400           0.0
   SupplierC      600          -2.0
   SupplierD      350           0.0

   Product demand shadow prices (d cost / d demand):
     product demand  shadow_price
   Component    200           7.0
      Gadget    250           9.0
      Widget    300           8.0

   Most cost-sensitive capacity: SupplierC (d cost / d capacity = -2.00)

   Running scenario: without_SupplierC
     Status: OPTIMAL, Objective: 6750.0

     Orders:
     supplier   product  quantity
    SupplierA    Widget     300.0
    SupplierB Component     200.0
    SupplierB    Gadget     200.0
    SupplierD    Gadget      50.0

   Running scenario: without_SupplierB
     Status: OPTIMAL, Objective: 5150.0

     Orders:
     supplier   product  quantity
    SupplierC Component     200.0
    SupplierC    Gadget     100.0
    SupplierC    Widget     300.0
    SupplierD    Gadget     150.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
     baseline: OPTIMAL, obj=4850.00
     without_SupplierC: OPTIMAL, obj=6750.00
     without_SupplierB: OPTIMAL, obj=5150.00
   ```

   **Reading the marginals.** SupplierC is the cheapest source for every product, so
   it fills its 600-unit capacity and is the only **binding** capacity -- its shadow
   price of `-2.0` means each extra unit of SupplierC capacity would lower total cost
   by $2. Every other capacity has room to spare and prices at `0`. The demand shadow
   prices (`7`, `9`, `8` for Component, Gadget, Widget) are the marginal cost of one
   more unit of each product.
   SupplierA's and SupplierD's lanes are **priced out** (positive reduced cost); note
   SupplierB's unused lanes price at `~0` because each is exactly $2 above SupplierC --
   an alternate-optimum tie, which is why the script asserts only that *used* lanes
   have ~0 reduced cost, never that *every* unused lane is strictly positive. The
   exact order quantities (and the matching basis statuses) above are one of several
   cost-equal optima -- a different HiGHS build may land on another vertex with the
   same $4,850 objective and the same shadow prices.

   **Scenario analysis.** Removing SupplierC entirely increases cost by 39% ($4,850 to
   $6,750) as demand shifts to the more expensive SupplierA, SupplierB, and SupplierD -- consistent
   with SupplierC's high marginal value, though the duals (local marginals) do not by
   themselves predict the full impact of removing all 600 units. Removing SupplierB has
   less impact (+6%) since SupplierC absorbs most of the displaced volume.

## Template structure

```text
.
├── README.md                # this file
├── pyproject.toml           # dependencies
├── supplier_reliability.py  # main script (load, baseline solve, marginals, scenarios)
└── data/
    ├── products.csv         # products with demand requirements
    ├── suppliers.csv        # suppliers with capacity and reliability scores
    └── supply_options.csv   # per-unit cost for each supplier-product pair
```

**Start here**: run `python supplier_reliability.py` for the full baseline solve, marginal reads, and disruption scenarios end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative -- a small four-supplier, three-product catalog sized to teach the sourcing and sensitivity patterns, not to mirror a specific procurement portfolio.

- **`suppliers.csv`** (4 rows) -- suppliers `SupplierA` through `SupplierD`, each with a `capacity` (350-600 units) and a `reliability` score. The reliability score is carried as data only: it is not priced into the objective and does not drive the disruption scenarios (it is an extension point; see *Customize this template*).
- **`products.csv`** (3 rows) -- `Widget`, `Gadget`, and `Component`, each with a `demand` requirement.
- **`supply_options.csv`** -- one row per supplier-product pair with a `cost_per_unit`. `SupplierC` is the cheapest source for every product, so it fills its capacity first; the pricing is tuned so `SupplierC`'s capacity is the single binding bottleneck at the optimum.

## Model overview

The model has three source concepts loaded from CSV, plus a derived `SupplyOrder` decision concept that carries the order-quantity variable and back-pointers to its supplier and product.

- **Key entities**: `Supplier`, `Product`, `SupplyOption`, and the decision concept `SupplyOrder`.
- **Primary identifiers**: integer `id` on `Supplier`, `Product`, and `SupplyOption`; `SupplyOrder` is identified by the `SupplyOption` it uses.
- **Important invariants**: `capacity` and `demand` are non-negative integers; `cost_per_unit` is non-negative; order quantities are continuous and non-negative; total ordered per supplier stays within capacity; total ordered per product meets demand.

For the full concept and property definitions, see `supplier_reliability.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV inputs → load Supplier/Product/SupplyOption → SupplyOrder decision variables → capacity + demand constraints + cost objective → baseline solve with sensitivity → read marginals → scenario re-solves
```

**1. Define the ontology and load data.** Three source concepts -- `Supplier`, `Product`, and `SupplyOption` -- load from CSV. `SupplyOption` links each supplier to each product it can supply with a per-unit cost, forming the many-to-many sourcing lanes.

**2. Create decision variables.** A `SupplyOrder` decision concept holds the order-quantity variable -- how many units to order through each supply option -- with back-pointers to its supplier and product for direct access.

**3. Add constraints and objective.** A capacity constraint caps total units ordered per supplier; a demand constraint requires total units per product to meet demand; the objective minimizes total procurement cost. Each constraint is captured as a handle, named per entity for a readable label, and declared with `keyed_by` so its marginal reads back through the entity's key after the solve.

**4. Request sensitivity and read the marginals.** A plain solve answers *"what is the cheapest sourcing plan?"*. Requesting sensitivity analysis on the same solve also answers the marginal questions a planner asks next:

- **Which supplier capacity is the bottleneck?** The *shadow price* of each capacity constraint is how much total cost moves per unit of that supplier's capacity. A capacity with room to spare prices at zero; a nonzero price marks a binding bottleneck.
- **What does one more unit of demand cost?** The shadow price of each demand constraint is the marginal cost to serve one more unit of that product.
- **Which supply lanes are priced out?** A lane's *reduced cost* and *basis status* show which options are unused and how far their cost must fall before they enter the plan.

Because each constraint carries an entity back-pointer, a marginal joins to that entity's own data by key -- no name parsing, no pandas. The economics are also stated as integrity constraints, but only the always-true directions of complementary slackness (a lane in use prices at ~0; SupplierA's lanes are priced out). The converse "every unused lane has a positive reduced cost" is **not** asserted, because SupplierB's lanes tie SupplierC at the margin (alternate optima).

> [!NOTE]
> Sensitivity analysis returns marginals only for LP/QP models (linear constraints with a linear or quadratic objective). For mixed-integer models the duals are empty -- use scenario analysis instead. The marginal reads must happen on the **baseline** Problem, before the scenario loop rebuilds a fresh Problem.

**5. Scenario analysis.** Each disruption scenario is a separate Problem that excludes one supplier via a filter on the decision variable, then re-solves. This is a finite, structural change the marginals contextualize but do not by themselves predict -- removing all of a supplier's capacity can move cost further than the local shadow price suggests.

For the implementation, see `supplier_reliability.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the three CSVs in `data/` with your own, keeping the column names listed in *Sample data* above. `suppliers.csv`, `products.csv`, and `supply_options.csv` each map directly to a concept.
- Every product in `products.csv` needs at least one supply option in `supply_options.csv`, and total capacity across suppliers must cover total demand, or the baseline solve is infeasible.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.

### Tune parameters

- **Capacity and demand** -- edit `capacity` in `suppliers.csv` and `demand` in `products.csv` to change where the bottleneck lands; the shadow prices track which constraint binds.
- **Costs** -- adjust `cost_per_unit` in `supply_options.csv` to shift the optimal sourcing mix and the reduced costs of unused lanes.
- **Scenarios** -- edit the excluded-supplier list in the scenario loop to test different disruptions.

### Extend the model

- **Add a reliability penalty** to the objective, weighting cost against supplier reliability scores. One weighting yields a single trade-off point; sweep the weight to trace the cost-vs-reliability frontier.
- **Add minimum order quantities** by setting lower bounds on the decision variables for active supply options.
- **Introduce transportation costs** by adding a distance or shipping-cost dimension to supply options.
- **Expand the scenario analysis** to exclude combinations of suppliers or simulate capacity reductions rather than full exclusions.

### Scale up / productionize

- The model is a linear program that solves quickly; it scales to larger supplier-product catalogs within the solver's time budget.
- Pin the `relationalai` SDK version (see *Prerequisites*) for reproducible solves. Note that the optimum has cost-equal alternates, so exact order quantities can vary across HiGHS builds while the objective and shadow prices stay fixed.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE for a scenario</summary>

This means total remaining supplier capacity cannot meet product demand after excluding a supplier. Check that the remaining suppliers have enough combined capacity by reviewing `suppliers.csv` and `products.csv`. You may need to relax demand constraints or add alternative suppliers.
</details>

<details>
<summary>ModuleNotFoundError: No module named 'relationalai'</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that your account has the RAI Native App installed and that your user has the required permissions.
</details>

<details>
<summary>Unexpected zero quantities in the solution</summary>

The solver minimizes cost, so it will avoid expensive supply options when cheaper alternatives exist. Check `supply_options.csv` to see if the cost differences explain the allocation. If you want to enforce minimum diversification, add constraints requiring orders from multiple suppliers.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) -- concepts, properties, `sum(...).per(...)` aggregates, and `select(...)` used to build constraints and read marginals.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) -- the `Problem` API, `solve_for` decision variables, `satisfy` constraints, and `minimize` objectives.
- [Sensitivity analysis](https://docs.relational.ai/) -- shadow prices, reduced costs, and basis status returned by `solve(sensitivity=True)`, and reading them back by entity key.

### CLI / SDK guides

- [RelationalAI setup and `rai init`](https://docs.relational.ai/) -- connecting the SDK to your Snowflake account.

## Support

- File issues at the RelationalAI templates repository.
