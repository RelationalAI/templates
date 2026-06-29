# Retail Markdown — Analyst Runbook

A merchandiser needs to clear seasonal inventory before it loses value, setting a discount schedule across a multi-week season. Deeper discounts lift demand but cut per-unit revenue, and whatever doesn't sell is only worth its salvage value — so the plan has to balance aggressive markdowns against margin. The dataset is 4 products (each with price, cost, inventory, base demand, and salvage rate), 5 discount levels (each with a demand lift), and a 4-week horizon with seasonal demand decay. The analysis solves a mixed-integer program that picks each product's weekly discount.

```text
4 products (price, inventory, base demand, salvage) · 5 discount levels (lift) · 4 weeks (seasonal decay)
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decisions: one discount level per product-week (binary) + units sold + cumulative sold
   • constraints: exactly one discount per product-week; discounts only deepen over time;
     sales ≤ demand at the chosen discount; cumulative sales ≤ inventory
   • objective: maximize discounted sales revenue + salvage value of leftover stock
   • HiGHS mixed-integer program                 -> OPTIMAL, $23,374.65
      │
      ▼
/rai-prescriptive-results-interpretation
   • discounts start shallow (20%) and deepen to 30% late; no product needs the 50% tier
   • Pants, Shirt, Sweater nearly clear inventory by the final week
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Product`/`Discount`/`Week` concepts the build step created, and the interpret step reads the discount and sales decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/products.csv` (each product has an initial price, a cost, an initial inventory, a base demand, and a salvage rate), `data/discounts.csv` (each discount level has a percentage and a demand lift), and `data/weeks.csv` (each week has a seasonal demand multiplier).

**Response:** Loads `Product` (4: Sweater, Jacket, Pants, Shirt, each with price, cost, inventory, base demand, salvage rate), `Discount` (5 levels: 0/10/20/30/50%, each with a demand lift from 1.0 to 2.0), and `Week` (4, with seasonal multipliers 1.0/0.9/0.8/0.7).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Three concepts — 4 `Product` (price, cost, inventory, base demand, salvage rate), 5 `Discount` (percentage and demand lift), and 4 `Week` (seasonal demand multiplier, declining 1.0 → 0.7 across the season).

## 3. Set the markdown schedule

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management What discount should each product carry each week to maximize total revenue plus the salvage value of leftover stock? Pick exactly one discount level per product-week (binary), and only let discounts deepen over the season, never reverse. Units sold can't exceed demand at the chosen discount (base demand times the discount's lift times the week's seasonal multiplier), and a product's cumulative sales can't exceed its inventory. Maximize discounted sales revenue plus salvage value of any unsold stock, and persist the schedule to the ontology.

**Response:** OPTIMAL (HiGHS), total revenue plus salvage **$23,374.65** (relative gap 0.0). 176 variables (binary discount selections plus continuous sales and cumulative-sales) and 248 constraints; the discount selection, sales, and cumulative sales are written back as `Product.x_select`, `Product.x_sales`, and `Product.x_cuml_sales`.

## 4. Read the markdown plan

**Prompt:** /rai-prescriptive-results-interpretation How does the discount schedule evolve over the season, and how much inventory clears?

**Response:** Discounts start shallow — **20% across the board early** — and **deepen to 30% in the later weeks** for the slower movers (Shirt and Sweater move to 30% by week 3, Pants by week 4; Jacket holds at 20% throughout). **No product ever needs the deepest 50% tier.** By the final week Pants, Shirt, and Sweater have nearly cleared their inventory (roughly 99%, 99%, and 99% sold), while the higher-margin Jacket sells through about two-thirds — the plan protects Jacket's margin rather than discounting hard to clear it.

## Data

Bundled CSVs in `data/`: 4 products, 5 discount levels, 4 weeks. Full model in `retail_markdown.py`.
