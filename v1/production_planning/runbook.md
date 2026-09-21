# Production Planning — Analyst Runbook

A manufacturer wants the production plan that maximizes profit across three products and three machines, and wants to stress it against demand uncertainty by evaluating three demand levels at once. The dataset is 3 products (each with a demand floor and a per-unit profit), 3 machines (each with available hours), and the 9 machine-product production rates. The analysis solves an integer program that decides how many units to make on each machine for each product under every demand scenario in a single solve.

```text
3 products (demand floor, profit) · 3 machines (hours) · 9 machine-product rates
      │
      ▼
/rai-prescriptive-problem
   • decision: integer quantity per (machine, product, scenario), ≥ 0
   • constraints: per machine, sum(qty x hours/unit) ≤ machine hours;
     per product, total qty ≥ demand x scenario multiplier
   • objective: maximize sum(qty x product profit) across all scenarios
   • demand scenarios 0.8 / 1.0 / 1.1 in one solve · HiGHS  -> OPTIMAL, $44,735 total
      │
      ▼
/rai-prescriptive-results
   • per-scenario profit: $15,020 (0.8) > $14,945 (1.0) > $14,770 (1.1)
   • looser demand floors leave more capacity for the most profitable mix
   • Machine_2 runs Widget_B at full capacity (70 units, 35 hrs) in every scenario
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Product`/`Machine`/`ProductionRate` concepts the build step created, and the interpret step reads the `Production.x_quantity` decisions the solve wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/products.csv` (each product has a demand and a per-unit profit), `data/machines.csv` (each machine has available hours), and `data/production_rates.csv` (the hours per unit for each machine-product pair). Model the production rate as a relationship linking a machine and a product to its hours-per-unit.

**Response:** Loads `Product` (3: Widget_A demand 100 / profit 50, Widget_B 80 / 70, Widget_C 60 / 45), `Machine` (3: Machine_1 40 hrs, Machine_2 35 hrs, Machine_3 45 hrs), and `ProductionRate` (9, every machine-product pair, with `hours_per_unit` 0.4–0.8).

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 3 `Product` (demand, profit), 3 `Machine` (hours_available), and 9 `ProductionRate` (one per machine-product pair, with `hours_per_unit`).

## 3. Maximize profit across demand scenarios

**Prompt:** /rai-prescriptive-problem How many units of each product should each machine make to maximize total profit, given each machine's limited hours and a floor on each product's total output? Use a non-negative integer quantity per machine-product pair. Each machine's total time — quantity times hours-per-unit, summed over its products — must stay within its hours; each product's total output across machines must meet its demand floor. Solve three demand scenarios in one solve — demand floors scaled to 80%, 100%, and 110% — with the scenario as a first-class concept and the quantity indexed by (machine, product, scenario). Persist the quantities to the ontology.

**Response:** OPTIMAL (HiGHS), combined profit **$44,735** across the three scenarios (relative gap 0.0). 27 integer variables (9 machine-product pairs x 3 scenarios), 18 constraints. Quantities are written back as `Production.x_quantity(Scenario)`.

## 4. Read the plan across scenarios

**Prompt:** /rai-prescriptive-results What's the per-scenario profit and production plan, and why does profit move the way it does as the demand floor rises?

**Response:** Per-scenario profit is **$15,020 at 0.8x, $14,945 at baseline, and $14,770 at 1.1x** — profit *falls* as the demand floor rises. With capacity fixed, a looser demand floor leaves more machine time free to chase the highest-margin mix, while a higher floor forces lower-margin units to be made just to satisfy it. Across all scenarios **Machine_2 runs Widget_B at full capacity** (70 units, its entire 35 hours), and Widget_A is made mostly on Machine_3 (its fastest 0.4 hours/unit line).

## Data

Bundled CSVs in `data/`: 3 products with demand and profit, 3 machines with hours, 9 machine-product rates. The three demand scenarios (0.8, 1.0, 1.1) are defined in the script. Full model in `production_planning.py`.
