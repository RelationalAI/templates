---
title: "Supplier Impact Analysis"
description: "Trace multi-hop supply chain dependencies to identify which suppliers high-value customers depend on and assess the blast radius of a supplier disruption, including affected customers and products at risk."
experience_level: intermediate
industry: Supply Chain
featured: true
reasoning_types:
  - Graph
tags:
  - graph-analytics
  - reachability
  - betweenness-centrality
  - supply-chain
  - impact-analysis
sidebar:
  order: 6
---

## What this template is for

Modern supply chains span multiple tiers -- raw material suppliers ship to component manufacturers, who supply product assemblers, who distribute through warehouses to end customers. When a key supplier goes offline, the impact cascades through all downstream tiers. SQL joins can trace one hop, but mapping the full blast radius requires graph traversal.

This template demonstrates two complementary reachability analyses on a directed business network:

1. **Upstream dependency** (`reachable(to=target)`) -- "Which suppliers do our high-value customers ultimately depend on?" Traces backward through the supply chain to identify all upstream suppliers.
2. **Downstream impact** (`reachable(from_=target)`) -- "If WaferTech Taiwan goes offline, which customers and products are affected?" Traces forward to map the full blast radius with product-level detail.

## Who this is for

- **Intermediate users** who want to learn parameterized reachability on directed graphs
- **Supply chain risk analysts** assessing supplier concentration and disruption exposure
- **Procurement teams** evaluating single-source risks across multi-tier supply chains

## What you'll build

- Load a 31-business, 262-shipment supply chain network from CSV (consumer electronics, 4 tiers: suppliers, component manufacturers, manufacturers, warehouses, customers)
- Derive `ships_to` relationships from shipment data (supplier-to-customer edges)
- Derive `is_high_value_customer` filter and `receives_shipment` relationship for product-level joins
- Construct a directed business graph and run parameterized reachability in both directions
- Display supplier risk analysis (which suppliers serve which high-value customers) with reliability scores
- Display downstream blast radius for a target supplier disruption, including affected entities by tier and products/quantities at risk
- Compute betweenness centrality to identify structural bottlenecks in the business network

## What's included

- **Self-contained script**: `supplier_impact.py` -- Runs Q5 (upstream) and Q6 (downstream) analyses end-to-end
- **Data**: `data/businesses.csv` (31 businesses across 3 regions) and `data/shipments.csv` (262 shipments with SKU and quantity data)

## Prerequisites

- Python >= 3.10
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

## Quickstart

1. Download and extract this template:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/supplier-impact-analysis.zip
   unzip supplier-impact-analysis.zip
   cd supplier-impact-analysis
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. **Install dependencies**

   ```bash
   python -m pip install .
   ```

4. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

5. **Run the template**

   ```bash
   python supplier_impact.py
   ```

## How it works

```text
CSV files --> Define Business + Shipment concepts --> Derive ships_to edges --> Build directed graph --> Upstream reachability (Q5) --> Downstream impact (Q6) --> Betweenness centrality --> Display results
```

### 1. Load Ontology and Derive Relationships

Businesses and Shipments are loaded from CSV. The `ships_to` relationship is derived from shipment data -- not declared directly:

```python
Business.ships_to = model.Relationship(f"{Business:supplier} ships to {Business:customer}")

model.define(Business.ships_to(b_from, b_to)).where(
    Shipment.supplier(b_from),
    Shipment.customer(b_to),
)
```

### 2. Parameterized Upstream Reachability (Q5)

Define a target set (high-value customers), then find all nodes that can reach them:

```python
target_customer = model.Relationship(f"Target Customer: {Business}")
define(target_customer(Business)).where(Business.is_high_value_customer(Business))

reachable_to = graph.reachable(to=target_customer)
```

This answers: "Which suppliers are upstream of our most important customers?"

### 3. Parameterized Downstream Reachability (Q6)

Define a target supplier, then find everything downstream:

```python
target_supplier = model.Relationship(f"Target Supplier: {Business}")
define(target_supplier(Business)).where(Business.name == "WaferTech Taiwan")

reachable_from = graph.reachable(from_=target_supplier)
```

The downstream results are joined to `receives_shipment` for product-level impact:

```python
where(
    reachable_from(target_supplier, customer),
    customer.receives_shipment.sku_id,
).select(distinct(
    customer.name.alias("customer_name"),
    customer.receives_shipment.sku_id.alias("product_at_risk"),
    aggs.sum(customer.receives_shipment.quantity).per(customer, ...).alias("quantity_at_risk"),
))
```

### 4. Interpret Results

- **Q5 output**: Per high-value customer, the list of upstream suppliers with reliability scores. Suppliers appearing for multiple customers represent concentration risk.
- **Q6 output**: Affected entities by tier (component manufacturers, manufacturers, warehouses, customers) plus product-level quantities at risk for end customers.
- **Betweenness centrality**: Businesses with high betweenness are structural bottlenecks in the supply network.

## Customize this template

**Use your own data:**
- Replace CSVs in `data/` with your own business and shipment data, keeping the same column names.
- The `VALUE_TIER` column can have NaN for non-customer businesses -- the template handles this automatically.

**Change the target supplier:**
- Edit `TARGET_SUPPLIER = "WaferTech Taiwan"` to analyze a different supplier's disruption impact.

**Extend the analysis:**
- Add `Shipment.delay_days` to identify suppliers with reliability issues
- Combine with BOM data to trace component-level (not just business-level) dependencies
- Chain with prescriptive optimization: "Given the impact, how should we re-source to minimize cost?"

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>

- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why do I see "No dependencies found" for Q5?</summary>

- Check that the `VALUE_TIER` column in businesses.csv has `HIGH` values for at least one `BUYER`-type business.
- NaN values in optional columns are handled by loading them separately from the core data.

</details>
