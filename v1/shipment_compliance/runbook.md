# Shipment Compliance — Analyst Runbook

Supply-chain operations generate more shipment, sourcing, and demand data than anyone can hand-check, so exceptions need to surface automatically. This template uses the logic reasoner to author four business rules as boolean flags across the data model — which shipments are late, which undelivered shipments come from unreliable suppliers, which inputs depend on a single sourcing route, and which demand orders are urgent. Each rule demonstrates a different pattern (threshold, cross-entity join, aggregation, OR-semantics). The dataset is 6 concepts spanning suppliers, SKUs, shipments, operations, bills of materials, and demand.

```text
6 concepts: 5 suppliers · 6 SKUs · 12 shipments · 7 operations · 6 BOM lines · 8 demand orders
      │
      ▼
/rai-pyrel  (four derived flags, then the exception worklist)
   • Shipment.is_late              (delay_days > 0)                              -> 2
   • Shipment.is_at_risk           (undelivered AND supplier reliability < 0.8) -> 6
   • BillOfMaterials.is_single_sourced (only one operation makes the input)     -> 2
   • Demand.is_escalated           (priority HIGH or URGENT)                     -> 4
   • list the flagged shipments, BOM inputs, and demand orders
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the rules step writes the flags back onto the concepts the build step created, then reads the exception worklist out of them.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/suppliers.csv` (each supplier has a reliability score), `data/skus.csv` (each SKU has a product type), `data/shipments.csv` (each shipment has a status and a delay in days, and links to a SKU and a supplier), `data/operations.csv` (each operation consumes an input SKU and produces an output SKU), `data/bill_of_materials.csv` (each BOM line requires an input SKU), and `data/demands.csv` (each demand order has a quantity and a priority, and links to a SKU).

**Response:** Loads `Supplier` (5, with `reliability_score`), `SKU` (6, with `product_type`), `Shipment` (12, with `status` and `delay_days`, linked to SKU and supplier), `Operation` (7, with input/output SKU), `BillOfMaterials` (6, requiring an input SKU), and `Demand` (8, with `quantity` and `priority`). Status and priority are closed enumerations.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Six concepts — 5 `Supplier`, 6 `SKU`, 12 `Shipment`, 7 `Operation`, 6 `BillOfMaterials`, 8 `Demand` — linked by SKU/supplier references, forming a small sourcing-and-fulfillment model.

## 3. Author the compliance rules and list the flagged records

**Prompt:** /rai-pyrel Define four derived flags. (1) A shipment is **late** if its delay in days is greater than zero. (2) A shipment is **at risk** if it isn't delivered yet and its supplier's reliability score is below 0.8. (3) A bill-of-materials input is **single-sourced** if exactly one operation produces that input SKU. (4) A demand order is **escalated** if its priority is HIGH or URGENT. Write each as a boolean property on its concept. Then: how many records does each flag catch, and which ones?

**Response:** Authors `Shipment.is_late` (threshold rule), `Shipment.is_at_risk` (cross-entity join to the supplier), `BillOfMaterials.is_single_sourced` (aggregation over producing operations), and `Demand.is_escalated` (OR over two priority tiers) — four boolean derived properties, one per rule pattern. Reading them back: **2 late shipments** (Widget-B from GlobalChip, 3 days; Frame-Z from Acme Parts, 1 day). **6 at-risk shipments** — all from the two low-reliability suppliers, GlobalChip (0.65) and BudgetSupply (0.72). **2 single-sourced BOM inputs**, both Chip-Y, which only one operation produces — a concentration risk. **4 escalated demand orders** (the HIGH and URGENT ones, all Widget-A or Widget-B). The flags turn raw rows into an exception worklist without anyone scanning the tables.

## Data

Bundled CSVs in `data/`: 5 suppliers, 6 SKUs, 12 shipments, 7 operations, 6 BOM lines, 8 demand orders. Full model in `shipment_compliance.py`.
