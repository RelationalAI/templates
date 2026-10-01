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
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
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
- RelationalAI Python SDK (`relationalai == 1.13.0`)

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

**Start here**: run `python shipment_compliance.py` for the full run end to end — authoring all four rules and printing the flagged records — or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

- **Key entities**: `Supplier` — a company that supplies parts; `SKU` — a stock-keeping unit tracked in the supply chain; `Shipment` — a delivery of a SKU from a supplier; `Operation` — a production or shipping route that transforms SKUs; `BillOfMaterials` — an input-SKU requirement for production; `Demand` — a quantity requirement for a specific SKU.
- **Primary identifiers**: an integer `id` on every concept.
- **Important invariants**: `Supplier.reliability_score` is a fraction in `[0, 1]`; `Shipment.status` is a `ShipmentStatus` member (`PENDING` / `IN_TRANSIT` / `DELIVERED`); `Demand.priority` is a `Priority` member (`LOW` / `STANDARD` / `HIGH` / `URGENT`); `delay_days`, `quantity`, and `input_quantity` are non-negative. Each rule adds a derived boolean flag back onto its concept: `Shipment.is_late` (Rule 1), `Shipment.is_at_risk` (Rule 2), `BillOfMaterials.is_single_sourced` (Rule 3), and `Demand.is_escalated` (Rule 4).

For the full concept and property definitions, see `shipment_compliance.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline loads six concepts from CSV, maps the closed-vocabulary columns to enums, then declares four derived rules as boolean flags and queries the entities each one catches. No solver is involved — the rules are pure declarative logic that re-evaluates as the data changes.

```text
CSV inputs → load Supplier / SKU / Shipment / Operation / BOM / Demand
  → map status & priority strings to enum members → define four rule flags → query flagged entities
```

1. **Load the data and map enums.** Six concepts load from CSV, with relationships linking shipments to their SKU and supplier, operations to their input/output SKUs, and so on. The `status` and `priority` columns are closed vocabularies declared as `model.Enum` types (`ShipmentStatus`, `Priority`) and populated by name — so `"DELIVERED"` in the CSV becomes the `ShipmentStatus.DELIVERED` member. Rules then compare against members rather than raw strings, which is typo-proof and discoverable, and queries read the label back with `.name`. One caveat when bringing your own data: `lookup()` cannot validate values arriving from data columns — a CSV value matching no member name silently maps to a nonexistent entity and drops out of every member-comparison rule, so keep the enum declarations in sync with your data's vocabulary.
2. **Define four rule patterns.** Each rule uses the `model.where(...).define(...)` pattern to set a boolean flag, and together they show four shapes: a simple threshold (Rule 1: `delay_days > 0`), a cross-entity join (Rule 2: undelivered shipments from suppliers scoring below `0.8`), an aggregation (Rule 3: BOM inputs produced by exactly one operation route), and OR semantics via multiple `define()` calls on the same relationship (Rule 4: `HIGH` or `URGENT` priority).
3. **Query the flags.** Each rule is queried with `model.select(...).where(Concept.rule_flag())` to display the matching entities.

See `shipment_compliance.py` for the implementation and `runbook.md` for the skill-driven reproduction.

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
