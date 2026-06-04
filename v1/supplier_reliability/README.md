---
title: "Supplier Reliability"
description: "Select suppliers to meet product demand at minimum cost, with sensitivity marginals and supplier-disruption scenario analysis."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Supplier Selection
  - Scenario Analysis
  - Sensitivity Analysis
  - Cost Optimization
---

# Supplier Reliability

## What this template is for

Procurement teams must choose which suppliers to source from when multiple options exist for each product. Each supplier has different pricing and capacity limits (plus a reliability score, carried as extension data -- not priced into the objective, and not what drives the disruption scenarios below). The challenge is to meet all product demand at minimum cost without exceeding any supplier's capacity.

This template uses **Prescriptive** reasoning to formulate the supplier selection problem as a linear program. It determines the optimal order quantities across supply options, ensuring that every product's demand is met and no supplier is overloaded. The solver finds the cost-minimizing allocation automatically.

A plain solve answers *"what is the cheapest sourcing plan?"*. This template also requests **sensitivity analysis** (`solve(sensitivity=True)`) on the baseline, which answers the *marginal* questions a planner asks next -- in the same solve:

- **Which supplier capacity is the bottleneck?** The *shadow price* of each capacity constraint (`cap.shadow_price`) is how much total cost moves per unit of that supplier's capacity. A capacity with room to spare prices at zero; a nonzero price marks a binding bottleneck.
- **What does one more unit of demand cost?** The shadow price of each demand constraint (`meet.shadow_price`) is the marginal cost to serve one more unit of that product.
- **Which supply lanes are priced out?** A lane's *reduced cost* (`qty_var.reduced_cost`) and *basis status* (`qty_var.basis_status`) show which options are unused and how far their cost must fall before they enter the plan.

Finally, the template demonstrates **scenario analysis** by re-solving the problem with specific suppliers fully excluded. This is a *finite, structural* change -- what happens to cost and feasibility if a key supplier becomes unavailable? -- that the local marginals contextualize but do not by themselves predict.

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

- `supplier_reliability.py` -- Main script defining the model, constraints, and scenario analysis
- `data/suppliers.csv` -- Supplier capacity and reliability scores
- `data/products.csv` -- Product demand requirements
- `data/supply_options.csv` -- Cost per unit for each supplier-product pair
- `pyproject.toml` -- Python package configuration

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
   SupplierB    Widget     150.0
   SupplierC Component     200.0
   SupplierC    Gadget     250.0
   SupplierC    Widget     150.0

   Lane reduced costs and basis status:
    supplier   product  reduced_cost      basis_status
   SupplierA    Gadget           3.0 NONBASIC_AT_LOWER
   SupplierA    Widget           2.0 NONBASIC_AT_LOWER
   SupplierB Component           0.0 NONBASIC_AT_LOWER
   SupplierB    Gadget           0.0 NONBASIC_AT_LOWER
   SupplierB    Widget           0.0             BASIC
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
    SupplierB Component     150.0
    SupplierB    Gadget     250.0
    SupplierD Component      50.0

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
   $6,750) as demand shifts to more expensive SupplierB and SupplierD -- consistent
   with SupplierC's high marginal value, though the duals (local marginals) do not by
   themselves predict the full impact of removing all 600 units. Removing SupplierB has
   less impact (+6%) since SupplierC absorbs most of the displaced volume.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── supplier_reliability.py
└── data/
    ├── products.csv
    ├── suppliers.csv
    └── supply_options.csv
```

## How it works

### 1. Define the ontology and load data

The model defines three concepts -- Supplier, Product, and SupplyOption -- and loads them from CSV files:

```python
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.reliability = Property(f"{Supplier} has {Float:reliability}")
Supplier.capacity = Property(f"{Supplier} has {Integer:capacity}")
supplier_csv = read_csv(DATA_DIR / "suppliers.csv")
model.define(Supplier.new(model.data(supplier_csv).to_schema()))
```

SupplyOption links suppliers to products with a cost per unit, establishing the many-to-many relationship:

```python
SupplyOption = Concept("SupplyOption", identify_by={"id": Integer})
SupplyOption.supplier = Property(f"{SupplyOption} from {Supplier}", short_name="supplier")
SupplyOption.product = Property(f"{SupplyOption} for {Product}", short_name="product")
SupplyOption.cost_per_unit = Property(f"{SupplyOption} has {Float:cost_per_unit}")
```

### 2. Create decision variables

A SupplyOrder concept holds the decision variable -- the quantity to order through each supply option:

```python
SupplyOrder = Concept("SupplyOrder")
SupplyOrder.option = Property(f"{SupplyOrder} uses {SupplyOption}", short_name="option")
SupplyOrder.x_quantity = Property(f"{SupplyOrder} has {Float:quantity}")
model.define(SupplyOrder.new(option=SupplyOption))
```

### 3. Add constraints and objective

Capacity and demand constraints ensure feasibility, while the objective minimizes total procurement cost. Each constraint is **captured as a handle**, **named per entity** (a readable label), and declared with **`keyed_by`** -- the entity key its marginal reads back through after the solve:

```python
cap = baseline.satisfy(
    model.require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.supplier == Supplier).per(Supplier) <= Supplier.capacity
    ),
    name=["cap", Supplier.name],
    keyed_by={"supplier": Supplier},
)
meet = baseline.satisfy(
    model.require(
        sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product) >= Product.demand
    ),
    name=["demand", Product.name],
    keyed_by={"product": Product},
)
baseline.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))
```

### 4. Request sensitivity and read the marginals

Solve the baseline with `sensitivity=True`, then read each marginal straight off the variable or constraint object -- the same attribute style as `.name`. A constraint declared with `keyed_by` carries an **entity back-pointer** (`cap.supplier`, `meet.product`), mirroring the variable's automatic back-pointer (`qty_var.supplyorder`), so a marginal joins to that entity's own data by KEY -- no name parsing, no pandas:

```python
baseline.solve("highs", time_limit_sec=60, sensitivity=True)

# Capacity shadow prices, joined to each supplier's capacity by key:
model.select(cap.supplier.name, cap.supplier.capacity, cap.shadow_price).inspect()
# Demand shadow prices, joined to each product's demand by key:
model.select(meet.product.name, meet.product.demand, meet.shadow_price).inspect()
# Lane reduced costs and basis status, joined to supplier / product by key:
model.select(
    qty_var.supplyorder.supplier.name, qty_var.supplyorder.product.name,
    qty_var.reduced_cost, qty_var.basis_status,
).inspect()
```

The economics are also stated as integrity constraints joined by the same keys -- but only the always-true directions of complementary slackness (a lane in use prices at ~0; SupplierA's lanes are priced out). The converse "every unused lane has a positive reduced cost" is **not** asserted, because SupplierB's lanes tie SupplierC at the margin (alternate optima).

> [!NOTE]
> Sensitivity analysis returns marginals only for LP/QP models (linear constraints with a linear or quadratic objective). For mixed-integer models the duals are empty -- use scenario analysis instead. The marginal reads must happen on the **baseline** Problem, before the scenario loop rebuilds a fresh Problem.

### 5. Scenario analysis

Each disruption scenario is a separate Problem that excludes one supplier with a `where=` filter on the decision variable -- a finite, structural change the marginals contextualize but do not by themselves predict:

```python
for excluded in ["SupplierC", "SupplierB"]:
    problem = Problem(model, Float)
    qty_scn = problem.solve_for(
        SupplyOrder.x_quantity,
        name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
        lower=0,
        where=[SupplyOrder.supplier.name != excluded],
        populate=False,
    )
    # ... re-add capacity / demand constraints and the objective ...
    problem.solve("highs", time_limit_sec=60)
```

## Customize this template

- **Add a reliability penalty** to the objective function, weighting cost against supplier reliability scores. One weighting yields a single trade-off point; sweep the weight to trace the cost-vs-reliability frontier.
- **Expand the scenario analysis** to exclude combinations of suppliers or simulate capacity reductions.
- **Add minimum order quantities** by setting lower bounds on the decision variables for active supply options.
- **Introduce transportation costs** by adding a distance or shipping cost dimension to supply options.

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
