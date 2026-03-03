---
title: "Supplier Reliability"
description: "Select suppliers to meet product demand while balancing cost and reliability."
featured: false
experience_level: intermediate
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Supplier Selection
  - Scenario Analysis
  - Cost Optimization
---

# Supplier Reliability

## What this template is for

Procurement teams must choose which suppliers to source from when multiple options exist for each product. Each supplier has different pricing, capacity limits, and reliability scores. The challenge is to meet all product demand at minimum cost without exceeding any supplier's capacity.

This template uses prescriptive reasoning to formulate the supplier selection problem as a linear program. It determines the optimal order quantities across supply options, ensuring that every product's demand is met and no supplier is overloaded. The solver finds the cost-minimizing allocation automatically.

The template also demonstrates scenario analysis by re-solving the problem with specific suppliers excluded. This lets you evaluate supply chain resilience -- what happens to cost and feasibility if a key supplier becomes unavailable?

## Who this is for

- Supply chain and procurement analysts evaluating supplier portfolios
- Operations researchers modeling multi-supplier sourcing decisions
- Developers learning how to build scenario analysis into optimization models with RelationalAI

## What you'll build

- A linear programming model that allocates order quantities across suppliers and products
- Capacity and demand satisfaction constraints
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

6. Expected output:
   ```text
   Running scenario: excluded_supplier = None
     Status: OPTIMAL, Objective: 5350.0

     Orders:
          name          name  value
    qty_SupplierA_Gadget  250.0
    qty_SupplierB_Widget  300.0
    qty_SupplierC_Component  200.0

   Running scenario: excluded_supplier = SupplierC
     Status: OPTIMAL, Objective: 6050.0

   Running scenario: excluded_supplier = SupplierB
     Status: OPTIMAL, Objective: 5700.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
     None: OPTIMAL, obj=5350.0
     SupplierC: OPTIMAL, obj=6050.0
     SupplierB: OPTIMAL, obj=5700.0
   ```

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
supplier_csv = read_csv(data_dir / "suppliers.csv")
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

Capacity and demand constraints ensure feasibility, while the objective minimizes total procurement cost:

```python
s.satisfy(model.require(
    sum(SupplyOrder.x_quantity).where(SupplyOrder.supplier == Supplier).per(Supplier) <= Supplier.capacity
))
s.satisfy(model.require(
    sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product) >= Product.demand
))
s.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))
```

### 4. Scenario analysis

The script loops over supplier exclusion scenarios, setting excluded supplier quantities to zero:

```python
for excluded_supplier in SCENARIO_VALUES:
    s = Problem(model, Float)
    # ... define variables and constraints ...
    if excluded_supplier is not None:
        exclude = model.require(SupplyOrder.x_quantity == 0).where(
            SupplyOrder.supplier.name == excluded_supplier
        )
        s.satisfy(exclude)
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
```

## Customize this template

- **Add a reliability penalty** to the objective function, weighting cost against supplier reliability scores to find the Pareto-optimal balance.
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
