# Factory Production — Analyst Runbook

A manufacturing planner wants the most profitable production plan across two factories making four products, and — just as important — the marginals that tell them what to do next: which factory to expand first, and which products are capped by demand rather than capacity. The dataset is 2 factories (each with a pool of resource-hours) and 4 products (each with a production rate, a per-unit profit, and a demand cap). The analysis solves a product-mix linear program with sensitivity analysis enabled, so the shadow prices and reduced costs come back in the same solve.

```text
2 factories (resource-hours) x 4 products (rate units/hr, profit, demand cap)
      │
      ▼
/rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management
   • decision: continuous quantity per product, 0 ≤ qty ≤ demand cap
   • constraint: per factory, sum(qty / rate) ≤ available resource-hours
   • objective: maximize sum(profit x qty); solve with sensitivity marginals on
   • HiGHS linear program                        -> OPTIMAL, $200,000 total profit
      │
      ▼
/rai-prescriptive-results-interpretation
   • plan: bands 6000, coils 1400, stouts 1000, ales 2000
   • steel_factory capacity is binding (shadow price $4,200/hr, 0 idle hours)
   • amazing_brewery is demand-bound (5 idle hours); coils is the swing product
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Factory`/`Product` concepts the build step created, and the interpret step reads the solved quantities and the sensitivity marginals the solve produced.

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/factories.csv` (each factory has available resource-hours) and `data/products.csv` (each product belongs to a factory and has a production rate in units per hour, a per-unit profit, and a demand cap). Link each product to its factory.

**Response:** Loads `Factory` (2: steel_factory 40 hrs, amazing_brewery 30 hrs) and `Product` (4, each with `rate`, `profit`, `demand`, linked to its factory) — steel_factory makes bands and coils, amazing_brewery makes stouts and ales.

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many of each?

**Response:** Two concepts — 2 `Factory` (with `avail` resource-hours) and 4 `Product` (with `rate`, `profit`, `demand`, each linked to its factory). Each factory makes two products.

## 3. Find the most profitable production plan

**Prompt:** /rai-prescriptive-problem-formulation + /rai-prescriptive-solver-management How many units of each product should we make to maximize total profit, given each factory's limited resource-hours and each product's demand cap? Model the demand cap as the upper bound on each product's quantity (so its marginal reads back as a reduced cost), require each factory's total resource usage — the sum of quantity divided by rate — to stay within its available hours, and solve with sensitivity analysis on so capacity shadow prices and product reduced costs come back too.

**Response:** OPTIMAL (HiGHS), total profit **$200,000** (relative gap 0.0). 4 continuous quantity variables, 2 capacity constraints. The plan, capacity shadow prices (keyed by factory), and per-product reduced costs and basis status are all available from the solve handles.

## 4. Read the plan and the marginals

**Prompt:** /rai-prescriptive-results-interpretation What's the optimal quantity per product, which factory's capacity should we expand first, and which products are limited by demand rather than capacity?

**Response:** Plan: bands 6000, coils 1400 (steel_factory); stouts 1000, ales 2000 (amazing_brewery). **steel_factory** is the binding capacity — 0 idle hours and a shadow price of **$4,200 per added hour** (the profit-per-hour of coils, its swing product), so it's the one to expand first. **amazing_brewery** has 5 idle hours and is demand-bound, not capacity-bound. Bands, stouts, and ales sit at their demand caps (nonbasic-at-upper, positive reduced cost); **coils** is the single swing product (basic, reduced cost 0) absorbing steel_factory's remaining capacity.

## Data

Bundled CSVs in `data/`: 2 factories with resource-hours, 4 products with rate / profit / demand. Full model in `factory_production.py`.
