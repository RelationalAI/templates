# Supplier Reliability — Analyst Runbook

A procurement team wants the cheapest way to source every product across suppliers with different prices and hard capacity limits — and, just as important, the marginals behind the plan: which supplier capacity is the binding bottleneck, what an extra unit of each product's demand costs, and which supply lanes are priced out. It then stress-tests resilience by removing a key supplier and re-solving. The dataset is 4 suppliers, 3 products (750 units of total demand), and 10 supplier-product supply lanes. The analysis solves a min-cost sourcing LP with sensitivity analysis, then runs supplier-disruption scenarios.

```text
4 suppliers (price, capacity) · 3 products (demand, 750 total) · 10 supplier-product lanes
      │
      ▼
/rai-prescriptive-problem
   • decision: continuous order quantity per supply lane, ≥ 0
   • constraints: per-supplier total ≤ capacity; per-product total ≥ demand
   • objective: minimize sum(quantity x lane cost); solve with sensitivity marginals
   • HiGHS linear program                        -> OPTIMAL, $4,850
      │
      ▼
/rai-prescriptive-results
   • SupplierC capacity is the bottleneck (cheapest on every product; shadow price −2)
   • disruption: remove SupplierC → $6,750 (+39%); remove SupplierB → $5,150 (+6%)
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — later steps read the `Supplier`/`Product`/`SupplyOption` concepts the build step created and the solve handles the formulation produced.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/suppliers.csv` (each supplier has a capacity and a reliability score), `data/products.csv` (each product has a demand), and `data/supply_options.csv` (each supplier-product lane has a per-unit cost). Model the supply option as a relationship linking a supplier and a product to its cost.

**Response:** Loads `Supplier` (4: SupplierA–D, capacities 500/400/600/350, with a `reliability` score), `Product` (3: Widget 300, Gadget 250, Component 200 — 750 total), and `SupplyOption` (10 supplier-product lanes, each with `cost_per_unit`; SupplierC is cheapest on every product). Note that 10 of the 12 possible pairs exist.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 4 `Supplier` (capacity, reliability), 3 `Product` (demand, 750 total), and 10 `SupplyOption` (the available supplier-product lanes with per-unit cost). The reliability score is carried as context; the sourcing optimization is cost-driven.

## 3. Source at minimum cost

**Prompt:** /rai-prescriptive-problem What order quantity on each supply lane meets every product's demand at minimum total cost, with no supplier shipping beyond its capacity? Use a continuous, non-negative quantity per lane, require each supplier's total to stay within capacity and each product's total to cover its demand, and solve with sensitivity analysis on so the capacity shadow prices, demand shadow prices, and lane reduced costs come back too.

**Response:** OPTIMAL (HiGHS), total sourcing cost **$4,850** (relative gap 0.0). 10 continuous quantity variables, 7 constraints (4 capacity, 3 demand); the capacity and demand constraints are keyed by supplier and product so their shadow prices read back per entity, and each lane's reduced cost and basis status are available from the solve. (Several cost-equal optima exist, so the exact lane quantities can vary; the cost and marginals are stable.)

## 4. Read the marginals

**Prompt:** /rai-prescriptive-results Which supplier's capacity is the bottleneck to expand first, what does an extra unit of each product's demand cost, and which lanes are priced out?

**Response:** **SupplierC is the bottleneck** — the only supplier whose capacity binds (shadow price −2, i.e. one more unit of its capacity saves $2), because it's cheapest on every product. Each product's demand shadow price is the marginal cost of one more unit: **Component $7, Widget $8, Gadget $9**. The priced-out lanes (positive reduced cost, unused) are the SupplierA and SupplierD lanes — they'd only enter the plan if their cost dropped or SupplierC capacity ran out.

## 5. Stress-test supplier disruption

**Prompt:** /rai-prescriptive-results How much does total cost rise if we lose a supplier entirely — first SupplierC, then SupplierB — re-solving sourcing without them?

**Response:** Removing **SupplierC** (the cheapest, capacity-binding supplier) pushes cost to **$6,750 — a 39% increase** — confirming it as the critical dependency. Removing **SupplierB** raises cost only to **$5,150 (+6%)**, since its volume re-sources cheaply. Both remain OPTIMAL (demand is still satisfiable), so the risk is cost, not feasibility — the reliability exposure concentrates on SupplierC.

## Data

Bundled CSVs in `data/`: 4 suppliers, 3 products, 10 supply options. The disruption scenarios (remove SupplierC, SupplierB) are defined in the script. Full model in `supplier_reliability.py`.
