---
title: "Shipment Compliance"
description: "Derived classifications for shipment compliance, sourcing risk, and demand escalation."
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
- `model.Enum` vocabularies for the closed-value fields (`ShipmentStatus`, `Priority`), mapped from CSV strings on load
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
- RelationalAI Python SDK (`relationalai == 1.12.0`)

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

6. Expected output (a few lines confirm a successful run):

   The script prints the entities each rule flags. On the bundled data the four
   rules catch **2 late shipments**, **6 at-risk shipments**, **2 single-sourced
   BOM inputs**, and **4 escalated demands**:

   ```text
   === Rule 1: Late Shipments (delay_days > 0) ===
   (2 rows)

   === Rule 2: At-Risk Shipments (undelivered + unreliable supplier) ===
   (6 rows)

   === Rule 3: Single-Sourced BOM Inputs (only 1 operation route) ===
   (2 rows)

   === Rule 4: Escalated Demands (HIGH or URGENT priority) ===
   (4 rows)
   ```

   See `runbook.md` for the full record-by-record walkthrough of each flag.

## Template structure

```text
.
├── README.md               # this file
├── pyproject.toml          # dependencies
├── shipment_compliance.py  # main script: data model + four derived rules
├── runbook.md              # analyst-facing paste-testable walkthrough
└── data/
    ├── suppliers.csv          # 5 suppliers (id, name, reliability_score)
    ├── skus.csv               # 6 SKUs (id, name, product_type)
    ├── shipments.csv          # 12 shipments (id, sku_id, supplier_id, status, delay_days)
    ├── operations.csv         # 7 operations (input/output SKU, cost, capacity)
    ├── bill_of_materials.csv  # 6 BOM lines (input SKU, site, quantity)
    └── demands.csv            # 8 demand orders (SKU, quantity, priority)
```

**Start here**: run `python shipment_compliance.py` to author all four rules and print the flagged records, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled data is a small, illustrative sourcing-and-fulfillment model — 6 concepts sized so each rule pattern is easy to trace by hand.

- **`suppliers.csv`** (5 rows) — supplier `name` and `reliability_score` (a fraction in `[0, 1]`); two suppliers score below the `0.8` at-risk threshold.
- **`skus.csv`** (6 rows) — the product and component catalog (`name`, `product_type`).
- **`shipments.csv`** (12 rows) — each shipment links to a SKU and a supplier, and carries a `status` and `delay_days`.
- **`operations.csv`** (7 rows) — production/shipping routes, each consuming an input SKU and producing an output SKU.
- **`bill_of_materials.csv`** (6 rows) — input-SKU requirements per site.
- **`demands.csv`** (8 rows) — demand orders for SKUs, each with a `quantity` and a `priority`.

`status` and `priority` are closed vocabularies (`ShipmentStatus`, `Priority`) loaded from the raw CSV strings by member name.

## Model overview

Six concepts model a small supply chain, linked by SKU and supplier references. The four business rules are derived boolean flags added back onto the concepts.

- **Key entities**: `Supplier`, `SKU`, `Shipment`, `Operation`, `BillOfMaterials`, `Demand`.
- **Primary identifiers**: an integer `id` on every concept.
- **Important invariants**: `Supplier.reliability_score` is a fraction in `[0, 1]`; `Shipment.status` is a `ShipmentStatus` member (`PENDING` / `IN_TRANSIT` / `DELIVERED`); `Demand.priority` is a `Priority` member (`LOW` / `STANDARD` / `HIGH` / `URGENT`); `delay_days`, `quantity`, and `input_quantity` are non-negative.

### Concepts

**`Supplier`** — a company that supplies parts.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/suppliers.csv` |
| `name` | String | No | Supplier name |
| `reliability_score` | Float | No | `[0, 1]`; below `0.8` flags shipments as at-risk (Rule 2) |

**`SKU`** — a stock-keeping unit tracked in the supply chain.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/skus.csv` |
| `name` | String | No | Human-readable name |
| `product_type` | String | No | e.g. `FINISHED_GOOD` |

**`Shipment`** — a delivery of a SKU from a supplier.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/shipments.csv` |
| `sku` | Relationship | — | Links to the `SKU` carried |
| `supplier` | Relationship | — | Links to the `Supplier` |
| `status` | `ShipmentStatus` enum | No | `PENDING` / `IN_TRANSIT` / `DELIVERED`, mapped from the CSV string |
| `delay_days` | Integer | No | Days late; `> 0` flags the shipment as late (Rule 1) |
| `is_late` | Relationship | — | **Rule 1** derived flag |
| `is_at_risk` | Relationship | — | **Rule 2** derived flag |

**`Operation`** — a production or shipping route that transforms SKUs.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/operations.csv` |
| `type` | String | No | Route type (e.g. `SHIP`) |
| `input_sku` | Relationship | — | The SKU consumed |
| `output_sku` | Relationship | — | The SKU produced |
| `cost_per_unit` | Float | No | Route cost per unit |
| `capacity_per_day` | Integer | No | Daily throughput limit |

**`BillOfMaterials`** — an input-SKU requirement for production.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/bill_of_materials.csv` |
| `input_sku` | Relationship | — | The required input `SKU` |
| `site_id` | Integer | No | Production site |
| `input_quantity` | Integer | No | Quantity required |
| `is_single_sourced` | Relationship | — | **Rule 3** derived flag (only one operation produces the input) |

**`Demand`** — a quantity requirement for a specific SKU.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/demands.csv` |
| `sku` | Relationship | — | The `SKU` demanded |
| `quantity` | Integer | No | Units required |
| `priority` | `Priority` enum | No | `LOW` / `STANDARD` / `HIGH` / `URGENT`, mapped from the CSV string |
| `is_escalated` | Relationship | — | **Rule 4** derived flag (`HIGH` or `URGENT`) |

## How it works

### 1. Define concepts and load data

The model defines six concepts (Supplier, SKU, Shipment, Operation, BillOfMaterials, Demand) and loads each from CSV. Relationships link shipments to suppliers and SKUs, operations to input/output SKUs, etc.

Closed vocabularies are declared as `model.Enum` types and populated by name from the raw CSV strings (so `"DELIVERED"` in `shipments.csv` becomes the `ShipmentStatus.DELIVERED` member):

```python
class ShipmentStatus(model.Enum):
    PENDING = 1
    IN_TRANSIT = 2
    DELIVERED = 3

Shipment.status = Property(f"{Shipment} has {ShipmentStatus:status}")

model.define(
    s := Shipment.new(id=shipment_data.id, ...),
    s.status(ShipmentStatus.lookup(shipment_data.status)),
)
```

Rules then compare against members rather than raw strings -- typo-proof and discoverable -- and queries read the label back with `.name` (e.g. `Shipment.status.name.alias("status")`).

One caveat when bringing your own data: `lookup()` cannot validate values that arrive from data columns. A CSV value that matches no member name silently maps to a nonexistent entity, and those rows simply drop out of every member-comparison rule. Keep the enum declarations in sync with your data's vocabulary. (Literal strings in code are checked at construction and raise a `ValueError` naming the valid members.)

### 2. Define rules as derived Relationships

Each rule uses the `model.where(...).define(...)` pattern to create a boolean flag:

```python
# Simple threshold rule
Shipment.is_late = Relationship(f"{Shipment} is late")
model.where(Shipment.delay_days > 0).define(Shipment.is_late())

# Cross-entity rule (joins Shipment -> Supplier)
Shipment.is_at_risk = Relationship(f"{Shipment} is at risk")
model.where(
    Shipment.status != ShipmentStatus.DELIVERED,
    Shipment.supplier(SupplierRef),
    SupplierRef.reliability_score < 0.8,
).define(Shipment.is_at_risk())

# Aggregation rule (count operations per BOM)
route_count = aggregates.count(Operation).per(BOM).where(...)
model.where(route_count == 1).define(BOM.is_single_sourced())

# OR semantics (multiple define calls on same Relationship)
model.where(Demand.priority == Priority.HIGH).define(Demand.is_escalated())
model.where(Demand.priority == Priority.URGENT).define(Demand.is_escalated())
```

### 3. Query flagged entities

Each rule is queried with `model.select(...).where(Concept.rule_flag())` to display matching entities.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above. Every foreign-key column (`sku_id`, `supplier_id`, `input_sku_id`, `output_sku_id`) must match an `id` in the referenced file, or those rows drop out of the join.
- The `status` and `priority` columns are enum-mapped: values must exactly match the `ShipmentStatus` / `Priority` member names. `lookup()` cannot validate values that arrive from data columns — unrecognized values silently map to a nonexistent member and drop out of every member-comparison rule. Extend the enum if your feed has more values.

### Tune parameters

- **At-risk threshold** — Rule 2 flags suppliers scoring below `0.8`; adjust the `reliability_score < 0.8` comparison to match your risk tolerance.
- **Escalation tiers** — Rule 4 fires on `HIGH` or `URGENT`; add or remove `define()` calls to change which priorities escalate.

### Extend the model

- **Add more rules**: Define additional Relationships for new business conditions (e.g., `Supplier.is_high_risk` based on reliability thresholds).
- **Chain rules**: Reference one rule's output in another rule's definition (e.g., flag demands as critical if they are escalated AND depend on a single-sourced BOM input).
- **Connect to optimization**: Use rule flags as constraint filters in a prescriptive formulation (e.g., exclude at-risk shipments from allocation).

### Scale up / productionize

- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` and load the concepts from your tables.
- Rules are pure declarative logic and re-evaluate as the underlying data changes, so they slot naturally into a change-data-capture pipeline. Pin the `relationalai` version for reproducibility.

## Troubleshooting

<details>
<summary><code>ModuleNotFoundError</code></summary>

Make sure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>A rule catches no records (or too few)</summary>

- Confirm the enum values in `status` / `priority` exactly match the `ShipmentStatus` / `Priority` member names — mismatched strings silently drop rows.
- Sanity-check the input data: Rule 2 needs undelivered shipments from suppliers scoring below `0.8`; Rule 3 needs an input SKU produced by exactly one operation.
- Verify foreign keys line up across CSVs (`sku_id`, `supplier_id`, `input_sku_id` match an `id` in the referenced file).
</details>

## Learn more

### Core concepts

- [Rules-based reasoning](https://docs.relational.ai/) — authoring business logic as derived properties: validation, classification, and alerting.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...).define(...)` and `model.select(...)`, the patterns this template is built on.

### Language / modeling reference

- [Derived relationships and aggregation](https://docs.relational.ai/) — the `define()` pattern and `aggregates.count(...).per(...)` used in Rule 3.
- [Enum vocabularies](https://docs.relational.ai/) — `model.Enum` types and `lookup()` for closed-value fields.

## Support

- File issues at the RelationalAI templates repository.
