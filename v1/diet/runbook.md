# Diet Optimization — Analyst Runbook

A nutritionist wants the cheapest daily food basket that still meets every nutrient requirement, and wants to see how that cost moves as the requirements tighten or loosen. The dataset is 9 foods (each with a cost and its calorie, protein, fat, and sodium content) and 4 nutrients (each with a minimum and maximum daily bound). The analysis formulates a linear program that picks a continuous amount of each food, then solves three requirement scenarios — 80%, 100%, and 120% of the bounds — in a single solve.

```text
9 foods x 4 nutrients (calories, protein, fat, sodium), each nutrient has a [min, max] bound
      │
      ▼
/rai-prescriptive-problem
   • decision: a continuous amount per (food, scenario), at least 0
   • constraint: each nutrient's total intake within [min, max] scaled by the scenario
   • objective: minimize total cost summed across all three scenarios
   • single solve over scenarios 0.8 / 1.0 / 1.2          -> OPTIMAL, $35.49 total (HiGHS)
      │
      ▼
/rai-prescriptive-results
   • basket = hamburger + icecream + milk in every scenario
   • per-scenario cost: $9.46 (0.8) / $11.83 (1.0) / $14.19 (1.2) — scales linearly
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the concepts the build step created, and the interpret step reads the `Food.x_amount` decisions the solve wrote back to the ontology.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/nutrients.csv` (each nutrient has min/max bounds) and `data/foods.csv` (each food has a cost plus one column per nutrient). Model food-to-nutrient content as a ternary relationship — a food contains a nutrient in some quantity.

**Response:** Loads `Nutrient` (properties `min`, `max`) and `Food` (property `cost`), plus a ternary `Food.contains(Nutrient) -> qty` relationship populated from the per-nutrient columns. 4 nutrients (calories, protein, fat, sodium) and 9 foods.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Two concepts — 4 `Nutrient` (calories 1800–2200, protein 91–200, fat 0–65, sodium 0–1779) and 9 `Food` (hamburger, chicken, hotdog, fries, macaroni, pizza, salad, milk, icecream) — linked by the `contains` ternary with 36 food-nutrient quantity rows (9 foods x 4 nutrients).

## 3. Minimize cost across requirement scenarios

**Prompt:** /rai-prescriptive-problem What's the minimum-cost amount of each food (continuous, non-negative) that keeps every nutrient's total intake within its [min, max] bounds? Solve three requirement scenarios in one solve — bounds scaled to 80%, 100%, and 120% — with the scenario as a first-class concept and the amount decision indexed by (food, scenario). Minimize total cost across all three, and persist the amounts to the ontology.

**Response:** OPTIMAL (HiGHS), total objective $35.49 across the three scenarios. The amount decision is written back as `Food.x_amount(Scenario) -> amount` so the next step can read it; the solve is sub-second (18 simplex iterations).

## 4. Read the per-scenario diet plan

**Prompt:** /rai-prescriptive-results For each scenario, which foods are selected and in what amount, and what is each scenario's total cost? How does cost respond as the requirements scale up and down?

**Response:** The optimal basket is the same three foods in every scenario — hamburger, icecream, and milk — scaled proportionally. Per-scenario cost is $9.46 at 0.8x, $11.83 at baseline, and $14.19 at 1.2x. Because every bound scales by the same factor and the model is a pure linear program, both the amounts and the cost scale linearly with the requirement multiplier (the 0.8x and 1.2x baskets are exactly 0.8 and 1.2 times the baseline).

## Data

Bundled CSVs in `data/`: 9 foods with cost and nutrient content, 4 nutrients with min/max bounds. Full model in `diet.py`.
