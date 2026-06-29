# Runbook: Planogram Optimization — Multi-Reasoner Walkthrough

A retailer must decide how many facings (front-row shelf positions) to give each product on each fixed-length shelf. More facings of a fast mover lifts its sales; more facings of a slow mover wastes length a better seller could use. This is a predict-then-optimize problem: a demand model scores how much each product sells at each facing count, and an optimizer then picks the facing counts that maximize total predicted demand under shelf-space and category limits.

## The chain

```
18 SKUs across 4 categories sit on 4 fixed-length shelves. The chain reads predicted
demand at each facing count, then chooses integer facings per SKU to maximize total
predicted weekly demand — OPTIMAL at 1,656 units, 16 of 18 SKUs given shelf space.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Predictive   ──►  PredictedDemand.demand_units        (73)
                              Per-(SKU, facing count) demand from a
                              regression, supplied as a lookup table;
                              concave curves (e.g. Cola: 1→90, 2→148,
                              3→189, 4→212 units/week).
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Prescriptive ──►  Sku.facings / Sku.realized_demand / Sku.active
                              Choose integer facings per SKU to maximize
                              total predicted demand. OPTIMAL, 1,656 units,
                              16 of 18 SKUs active. Bottom shelf full (90/90 cm).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build an ontology from data/skus.csv (each SKU has a category, a width, a max facings, and an assigned shelf), data/shelves.csv (each shelf has a length), data/categories.csv (each category has a min and max number of active SKUs), and data/predicted_demand_table.csv (predicted weekly demand for each SKU at each possible facing count). Model predicted demand as a relationship keyed by SKU and facing count.
```

**Response**

Loads `Sku` (18, across 4 categories: snacks, beverages, candy, household_paper, each with `width_cm`, `max_facings`, assigned shelf), `Shelf` (4, with `length_cm`), `Category` (4, with active-SKU min/max), and `PredictedDemand` (73 rows — one per SKU and facing count, including the 0-facing = 0-demand baseline).

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, and how many rows are in each?
```

**Response**

Four concepts — 18 `Sku`, 4 `Shelf`, 4 `Category`, and 73 `PredictedDemand` rows (the per-SKU demand curve over facing counts). Each SKU's curve is concave: extra facings help, with diminishing returns.

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery We have predicted weekly demand for each product at each facing count, fixed-length shelves, and per-category limits on how many products can be active. How do we choose facings to sell the most?
```

**Response**

Routes to a predict-then-optimize pattern: the predicted-demand curves (predictive) feed a facing-allocation optimization (prescriptive) under shelf-length and category-cardinality constraints.

### 4. Read predicted demand

**Prompt**

```
/rai-predictive-modeling How much is each SKU predicted to sell at each facing count, and what shape do the demand curves take?
```

**Response**

Each SKU has a concave demand curve over facing counts — demand rises with facings but with diminishing returns (e.g. Cola 12oz: 90 units at 1 facing, 148 at 2, 189 at 3, 212 at 4). These predictions come from a demand regression and are supplied as the `PredictedDemand` table so the optimizer can read demand at whatever facing count it chooses.

### 5. Optimize facings

**Prompt**

```
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management Choose an integer number of facings for each SKU (within its max facings) to maximize total predicted weekly demand, where each SKU's realized demand is the predicted demand at its chosen facing count. Respect each shelf's length (sum of facings times width can't exceed shelf length) and each category's min and max number of active SKUs. Persist the chosen facings, realized demand, and active flag.
```

**Response**

OPTIMAL (MiniZinc), total predicted weekly demand **1,656 units**. The decision picks facings per SKU (binding each SKU's realized demand to its predicted-demand row via a table lookup), with shelf-length and category-cardinality constraints; `Sku.facings`, `Sku.realized_demand`, and `Sku.active` are written back.

### 6. Read the planogram

**Prompt**

```
/rai-prescriptive-results-interpretation How many SKUs get shelf space, which shelf is the tightest, and what forces any SKU off the shelf?
```

**Response**

**16 of 18 SKUs are active**; two are squeezed out (a mint roll and a paper-towel pack) because the candy and household-paper categories each cap active SKUs at 3 while holding 4 candidates. The **Bottom shelf is the binding one — full at 90/90 cm** — and the other three shelves sit within a few centimeters of capacity, so shelf length and the category caps together, not demand, decide which SKUs make the set.

## Data

Bundled CSVs in `data/`: 18 SKUs, 4 shelves, 4 categories, 73 predicted-demand rows. The predicted demand is supplied as a table (standing in for a demand regression — see the template's customize section to swap in a trained model). Full chain in `planogram_optimization.py`.
