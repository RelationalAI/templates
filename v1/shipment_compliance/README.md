---
title: "Shipment Compliance"
description: "Define derived business rules for shipment compliance, sourcing risk, and demand escalation."
featured: false
experience_level: beginner
industry: "Supply Chain & Logistics"
reasoning_types:
   - Rules-based
tags:
  - Derived Properties
  - Business Logic
  - Compliance
  - Aggregation
---

# Shipment Compliance

## What this template is for

This template uses **rules-based reasoning** to define derived business rules for shipment compliance, sourcing risk, and demand escalation.

Supply chain operations generate large volumes of shipment, procurement, and demand data. Business rules help surface exceptions and risks automatically: which shipments are late, which inputs depend on a single supplier, which demands need urgent attention.

This template uses RelationalAI's logic reasoner to define four derived rules as boolean flags on existing concepts. No optimization solver is involved -- rules are pure declarative logic evaluated over the data model.

The four rules demonstrate different rule patterns:
1. **Simple threshold** -- flag shipments where delay exceeds zero
2. **Cross-entity check** -- flag undelivered shipments from unreliable suppliers
3. **Aggregation-based** -- flag BOM inputs sourced by exactly one operation route
4. **OR semantics** -- flag demands with HIGH or URGENT priority using multiple define() calls

## Who this is for

- Data scientists and analysts learning rule-based reasoning with RelationalAI
- Supply chain teams wanting to automate compliance and risk detection
- Beginners who want to understand derived properties and aggregation patterns

## What you'll build

- A data model with suppliers, SKUs, shipments, operations, BOMs, and demand
- Four derived rules using `model.where(...).define(...)` pattern
- Queries that surface which entities match each rule

## What's included

- `shipment_compliance.py` -- Main script defining the data model and four rules
- `data/suppliers.csv` -- Supplier names and reliability scores
- `data/skus.csv` -- Product and component catalog
- `data/shipments.csv` -- Shipment records with status and delay
- `data/operations.csv` -- Production/shipping routes linking SKUs
- `data/bill_of_materials.csv` -- BOM requirements per site
- `data/demands.csv` -- Demand orders with priority levels
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
   curl -O https://docs.relational.ai/templates/zips/v1/shipment_compliance.zip
   unzip shipment_compliance.zip
   cd shipment_compliance
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
   python shipment_compliance.py
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── shipment_compliance.py
└── data/
    ├── suppliers.csv
    ├── skus.csv
    ├── shipments.csv
    ├── operations.csv
    ├── bill_of_materials.csv
    └── demands.csv
```

## How it works

### 1. Define concepts and load data

The model defines six concepts (Supplier, SKU, Shipment, Operation, BillOfMaterials, Demand) and loads each from CSV. Relationships link shipments to suppliers and SKUs, operations to input/output SKUs, etc.

### 2. Define rules as derived Relationships

Each rule uses the `model.where(...).define(...)` pattern to create a boolean flag:

```python
# Simple threshold rule
Shipment.is_late = Relationship(f"{Shipment} is late")
model.where(Shipment.delay_days > 0).define(Shipment.is_late())

# Cross-entity rule (joins Shipment -> Supplier)
Shipment.is_at_risk = Relationship(f"{Shipment} is at risk")
model.where(
    Shipment.status != "DELIVERED",
    Shipment.supplier(SupplierRef),
    SupplierRef.reliability_score < 0.8,
).define(Shipment.is_at_risk())

# Aggregation rule (count operations per BOM)
route_count = aggregates.count(Operation).per(BOM).where(...)
model.where(route_count == 1).define(BOM.is_single_sourced())

# OR semantics (multiple define calls on same Relationship)
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())
model.where(Demand.priority == "URGENT").define(Demand.is_escalated())
```

### 3. Query flagged entities

Each rule is queried with `model.select(...).where(Concept.rule_flag())` to display matching entities.

## Customize this template

- **Add more rules**: Define additional Relationships for new business conditions (e.g., `Supplier.is_high_risk` based on reliability thresholds).
- **Chain rules**: Reference one rule's output in another rule's definition (e.g., flag demands as critical if they are escalated AND depend on a single-sourced BOM input).
- **Connect to optimization**: Use rule flags as constraint filters in a prescriptive formulation (e.g., exclude at-risk shipments from allocation).

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>
