---
title: "Manufacturing Compliance"
description: "Define derived business rules for machine maintenance scheduling, parts reordering, risk assessment, and qualification expiry tracking."
experience_level: beginner
industry: Manufacturing
reasoning_types:
  - Rules
tags:
  - Derived Properties
  - Business Logic
  - Compliance
  - Maintenance
  - Manufacturing
---

# Manufacturing Compliance

## What this template is for

Manufacturing operations require continuous monitoring of machine health, parts stock, and technician certifications. Business rules help surface exceptions automatically: which machines are overdue for maintenance, which parts need reordering, which machines pose the highest risk, and which technician qualifications are about to expire.

This template uses RelationalAI's logic reasoner to define four derived rules as boolean flags on existing concepts. No optimization solver is involved -- rules are pure declarative logic evaluated over the data model.

The four rules demonstrate different rule patterns:
1. **Simple comparison** -- flag machines where remaining useful life is below maintenance duration
2. **Threshold check** -- flag parts inventory where stock is at or below minimum order quantity
3. **Multi-condition AND** -- flag machines with both high failure probability and HIGH criticality
4. **Certification deadline** -- flag qualifications expiring within 30 days

## Who this is for

- Data scientists and analysts learning rule-based reasoning with RelationalAI
- Manufacturing teams wanting to automate compliance and maintenance alerts
- Beginners who want to understand derived properties and boolean flag patterns

## What you'll build

- A data model with machines, parts inventory, technicians, and qualifications
- Four derived rules using the `model.where(...).define(...)` pattern
- Queries that surface which entities match each rule

## What's included

- `manufacturing_compliance.py` -- Main script defining the data model and four rules
- `data/machines.csv` -- 8 machines across 3 facilities with RUL, failure probability, and criticality
- `data/parts_inventory.csv` -- 6 parts inventory records with stock levels
- `data/technicians.csv` -- 5 technicians with skill levels
- `data/qualifications.csv` -- 10 technician-to-machine-type certifications with expiry tracking
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
   curl -O https://docs.relational.ai/templates/zips/v1/manufacturing_compliance.zip
   unzip manufacturing_compliance.zip
   cd manufacturing_compliance
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
   python manufacturing_compliance.py
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── manufacturing_compliance.py
└── data/
    ├── machines.csv
    ├── parts_inventory.csv
    ├── technicians.csv
    └── qualifications.csv
```

## How it works

### 1. Define concepts and load data

The model defines four concepts (Machine, PartsInventory, Technician, Qualification) and loads each from CSV. Relationships link qualifications to technicians.

### 2. Define rules as derived Relationships

Each rule uses the `model.where(...).define(...)` pattern to create a boolean flag:

```python
# Simple comparison rule
Machine.is_overdue_maintenance = model.Relationship(f"{Machine} is overdue maintenance")
model.where(
    Machine.remaining_useful_life < Machine.maintenance_duration_hours,
).define(Machine.is_overdue_maintenance())

# Multi-condition AND rule
Machine.is_high_risk = model.Relationship(f"{Machine} is high risk")
model.where(
    Machine.failure_probability > 0.3,
    Machine.criticality == "HIGH",
).define(Machine.is_high_risk())

# Certification expiry rule
Qualification.is_expiring = model.Relationship(f"{Qualification} is expiring")
model.where(Qualification.days_remaining < 30).define(Qualification.is_expiring())
```

### 3. Query flagged entities

Each rule is queried with `model.select(...).where(Concept.rule_flag())` to display matching entities.

## Customize this template

- **Add more rules**: Define additional Relationships for new business conditions (e.g., `Technician.is_overloaded` based on qualification count).
- **Chain rules**: Reference one rule's output in another rule's definition (e.g., flag machines as critical if they are both overdue for maintenance AND high risk).
- **Connect to optimization**: Use rule flags as constraint filters in a prescriptive formulation (e.g., prioritize high-risk machines in maintenance scheduling).
