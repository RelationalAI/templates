---
title: "Product Configurator"
description: "Enumerate every feasible build of a configurable product in multi-solution mode: one option per slot subject to feature-model rules, regional regulations, and a price ceiling."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - configuration
  - constraint-programming
  - multi-solution
  - feature-model
  - manufacturing
---

# Product Configurator

## What this template is for

Configurable products -- cars, industrial equipment, enterprise software, network gear -- come with hundreds or thousands of options grouped into slots (engine, transmission, trim, sound, wheels, and so on). Picking a buildable combination by hand is hard: options require or exclude other options, regional regulations remove some choices entirely, and the total price has to stay under a target.

A configurator UI rarely wants a *single* feasible build. A buyer's quote, a sales playbook, and a "show me my options under this ceiling" trade-off slider all need the *population* of feasible configurations -- the cheap-but-basic build, the loaded build at the price-ceiling boundary, the build that drops a low-utility option to free up budget elsewhere. This template formulates the configuration problem as a **constraint satisfaction** model using RelationalAI's **prescriptive** reasoning and runs the solver in multi-solution mode: pass `solution_limit=MAX_CONFIGURATIONS` to `problem.solve(...)`, then enumerate each feasible build via `Variable.values(solution_index, value)`. The output is pivoted to one row per build (one column per slot, plus a total in dollars, sorted ascending by price) -- ready to drop straight into a buyer-facing UI.

For one target region, every returned build picks exactly one option per slot so that all feature-model rules are satisfied (implies / excludes), only region-allowed options appear, and the total price stays within a ceiling. Solver enumeration guarantees each returned build is *distinct* (differs on at least one option). When `solution_limit` is large enough to exhaust the search, the solver returns the full feasible set and reports status `OPTIMAL`; when the limit is tighter than the feasible set, the solver returns the first K it finds (status `SOLUTION_LIMIT`) and the specific subset depends on solver heuristics, so plan accordingly.

The configurator scenario here is automotive trim, drawn from the public Renault feature-model literature. The same pattern -- slots, options, implies, excludes, regional availability, price ceiling -- applies directly to enterprise software license bundling, industrial machinery configuration, and bill-of-materials product variants. Multi-solution enumeration is the right return shape for all of them.

## Who this is for

- Product engineers and configuration specialists in manufacturing or industrial automation
- Software developers building product-configurator UIs that need a constraint engine in the backend
- Operations researchers learning how feature-model configuration translates to constraint programming
- Developers exploring prescriptive reasoning with RelationalAI

## What you'll build

- A constraint model with binary `Option.selected` decisions and four constraint families: per-slot exactly-one, implies, excludes, and price ceiling
- A region-filtered decision domain so options not allowed in the target region simply don't appear as decisions
- A pre-solve catalog validation pass that fails fast on two pathologies the region filter can hide: a slot with zero region-allowed options (the exactly-one IC would not bind), and an implies rule whose tail option is not allowed in the region (the implies IC would not bind)
- **Multi-solution enumeration as the primary code path**: `problem.solve(..., solution_limit=MAX_CONFIGURATIONS)` runs the search in enumeration mode and `Variable.values(solution_index, value)` surfaces every distinct feasible build; the bundled demo's `MAX_CONFIGURATIONS = 100` is set above the feasible-set size so the solver exhausts the search (status `OPTIMAL`), and a post-solve `pandas.pivot` collapses the per-option rows into one row per build (one column per slot, sorted ascending by total price) for buyer-facing display
- Post-solve sanity check via `problem.verify()` confirming every re-evaluable constraint holds against the first returned configuration (`verify` re-evaluates each named IC against the populated property -- the first solution -- not across every enumerated build, but the model itself enforces the constraints across every solution the solver returns)

## What's included

- `product_configurator.py` -- main script with ontology, decisions, constraints, and solver call
- `data/slots.csv` -- 6 slots (Engine, Transmission, Trim, Sound, Wheels, Roof)
- `data/options.csv` -- 16 options across the 6 slots, each with a price in integer cents
- `data/implies.csv` -- option-to-option implies rules (e.g. Premium Audio implies Premium Trim)
- `data/excludes.csv` -- option-to-option excludes rules (e.g. V6 excludes Manual)
- `data/regional_rules.csv` -- which options are allowed in which region (US, EU)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.1.0

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/product_configurator.zip
   unzip product_configurator.zip
   cd product_configurator
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

4. Configure (prompts for Snowflake account, role, and profile name):
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python product_configurator.py
   ```

6. Expected output. With `MAX_CONFIGURATIONS = 100` and `TARGET_REGION = "EU"`, the solver exhausts the search and returns every distinct feasible build (status `OPTIMAL`, 63 builds). The script prints all 63 rows, pivoted to one row per configuration, sorted ascending by total dollars; the block below is **abridged** to the 8 cheapest and 8 most-expensive. The `solution` column is the solver's internal index, not a sequential ranking, and `objective: 0` is reported by convention because this is pure constraint satisfaction with no minimize/maximize call. Exact wall times and the solver build string vary across RAI Native App versions:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 0
   • solve time: 0.95s
   • num_points: 63
   • solver: MiniZinc_unknown

   Feasible builds for region 'EU' (ceiling $20,000, up to 100 per run):
    solution        Engine            Roof          Sound Transmission         Trim              Wheels  total_$
          60 1.6L Inline-4      Steel Roof Standard Sound       Manual    Base Trim       16-inch Alloy     1500
          59 1.6L Inline-4      Steel Roof Standard Sound       Manual    Base Trim       18-inch Sport     2700
          39 1.6L Inline-4      Steel Roof Standard Sound    Automatic    Base Trim       16-inch Alloy     3500
          50    2.0L Turbo      Steel Roof Standard Sound       Manual    Base Trim       16-inch Alloy     3500
          56 1.6L Inline-4      Steel Roof Standard Sound       Manual   Sport Trim       16-inch Alloy     4000
          51    2.0L Turbo      Steel Roof Standard Sound       Manual    Base Trim       18-inch Sport     4700
          38 1.6L Inline-4      Steel Roof Standard Sound    Automatic    Base Trim       18-inch Sport     4700
          57 1.6L Inline-4      Steel Roof Standard Sound       Manual   Sport Trim       18-inch Sport     5200
           ... 47 more builds omitted (script prints all 63) ...
           5    2.0L Turbo Panoramic Glass Standard Sound    Automatic Premium Trim       18-inch Sport    14700
           7    2.0L Turbo Panoramic Glass  Premium Audio    Automatic Premium Trim       16-inch Alloy    15000
          27    2.0L Turbo      Steel Roof  Premium Audio          DCT Premium Trim       18-inch Sport    15200
          10    2.0L Turbo Panoramic Glass Standard Sound          DCT Premium Trim       16-inch Alloy    15500
           1    2.0L Turbo Panoramic Glass  Premium Audio    Automatic Premium Trim       18-inch Sport    16200
           4    2.0L Turbo Panoramic Glass Standard Sound          DCT Premium Trim       18-inch Sport    16700
          11    2.0L Turbo Panoramic Glass  Premium Audio          DCT Premium Trim       16-inch Alloy    17000
           2    2.0L Turbo Panoramic Glass  Premium Audio          DCT Premium Trim       18-inch Sport    18200
   ```

   With `TARGET_REGION = "EU"` the V6 engine is unavailable, and the 63 returned builds span $1,500-$18,200 -- every legal combination across the six slots, satisfying every implies/excludes rule. Lower `MAX_CONFIGURATIONS` to cap how many the solver returns (status flips to `SOLUTION_LIMIT` once hit).

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── product_configurator.py
└── data/
    ├── slots.csv
    ├── options.csv
    ├── implies.csv
    ├── excludes.csv
    └── regional_rules.csv
```

## How it works

**1. Define slots, options, and load CSVs.** Slots and options are concepts; each option points to its slot, has a price in integer cents, and lists the regions it is allowed in:

```python
Slot = model.Concept("Slot", identify_by={"id": Integer})
Slot.name = model.Property(f"{Slot} has {String:name}")

Option = model.Concept("Option", identify_by={"id": Integer})
Option.name = model.Property(f"{Option} has {String:name}")
Option.price_cents = model.Property(f"{Option} has {Integer:price_cents}")
Option.slot = model.Property(f"{Option} is in {Slot:slot}")
Option.allowed_in = model.Relationship(f"{Option} is allowed in {String:region}")
```

**2. Define the implies and excludes rule tables.** Each rule is a concept identified by the pair of option IDs it links. `Implies` is directional (`head_id` -> `tail_id`) -- holding the rule *data*; the constraint *method* `model.require(...)` enforces them. `Excludes` is symmetric (`left_id`, `right_id`). The keys are deliberately dissimilar: PyRel emits a "potential relationship typo" warning when two compound-key names differ in a single character (e.g. `option_a_id` / `option_b_id`):

```python
Implies = model.Concept(
    "Implies",
    identify_by={"head_id": Integer, "tail_id": Integer},
)
Excludes = model.Concept(
    "Excludes",
    identify_by={"left_id": Integer, "right_id": Integer},
)
```

**3. Define the binary decision variable.** `Option.selected` is 0/1 and only exists for options allowed in the target region. Options banned in the region simply do not get a decision variable. Capture the returned `selected_var` handle -- step 6 indexes per-solution outputs through it via `.values(solution_index, value)`:

```python
Option.selected = model.Property(f"{Option} is selected if {Integer:selected}")
selected_var = problem.solve_for(
    Option.selected,
    type="bin",
    name=["selected", Option.name],
    where=[Option.allowed_in(TARGET_REGION)],
)
```

**4. Add the four constraint families and register each with the problem.** Each constraint is stored in a named variable so it can be re-checked by `problem.verify(...)` after solving; `problem.satisfy(ic)` is what actually pushes each constraint into the solver:

```python
exactly_one_ic = model.where(
    Option.allowed_in(TARGET_REGION),
    Option.slot(Slot),
).require(sum(Option.selected).per(Slot) == 1)
problem.satisfy(exactly_one_ic)

A = Option.ref()
B = Option.ref()
implies_ic = model.where(
    R := Implies,
    A.id(R.head_id),
    B.id(R.tail_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected <= B.selected)
problem.satisfy(implies_ic)

excludes_ic = model.where(
    E := Excludes,
    A.id(E.left_id),
    B.id(E.right_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected + B.selected <= 1)
problem.satisfy(excludes_ic)

price_ic = model.where(
    Option.allowed_in(TARGET_REGION),
).require(sum(Option.price_cents * Option.selected) <= PRICE_CEILING_CENTS)
problem.satisfy(price_ic)
```

The implies constraint reads as "if A (head) is selected (selected[A] = 1), then B (tail) must be selected too (selected[B] = 1), so selected[A] <= selected[B]". The excludes constraint reads as "at most one of A and B may be selected".

**5. Solve in multi-solution mode and verify.** Pass `solution_limit=MAX_CONFIGURATIONS` to enumerate up to that many distinct feasible builds. After solving, `problem.verify()` fires the named constraints to confirm the configuration satisfies every rule (it inspects only the first solution -- the populated property -- but the constraint structure is shared across every solution the solver returns):

```python
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)
problem.solve_info().display()
problem.verify(exactly_one_ic, implies_ic, excludes_ic, price_ic)
```

**6. Inspect every feasible build with `Variable.values`.** Capturing the variable subconcept from `solve_for(...)` exposes a `.values(solution_index, value)` relationship that indexes the per-solution outputs; binding the value slot directly to the literal `1` surfaces just the options the solver picked into each build. The variable subconcept exposes a back-pointer field named after the entity in its property: `selected_var.option` walks back to the `Option` instance for each row, so `selected_var.option.slot.name` and `selected_var.option.price_cents` resolve naturally. A post-solve `pandas.pivot` collapses the per-option rows into one row per build for buyer-facing display:

```python
sol_idx = Integer.ref()
selections_df = (
    model.select(
        sol_idx.alias("solution"),
        selected_var.option.slot.name.alias("slot"),
        selected_var.option.name.alias("option"),
        selected_var.option.price_cents.alias("price_cents"),
    )
    .where(selected_var.values(sol_idx, 1))
    .to_df()
    .astype({"solution": "int64", "price_cents": "int64"})
)
build_view = selections_df.pivot(index="solution", columns="slot", values="option")
build_view["total_$"] = selections_df.groupby("solution")["price_cents"].sum() // 100
build_view = build_view.sort_values("total_$").reset_index()
print(build_view.to_string(index=False))
```

## Customize this template

- **Use your own product** by replacing the five CSV files with your slots, options, implies, excludes, and regional_rules tables. The constraint structure does not change.
- **Cap the solution limit on a large catalog.** The bundled `MAX_CONFIGURATIONS = 100` is above the demo's feasible-set size so every build is enumerated (status `OPTIMAL`). On a production catalog the feasible set can be enormous; lower `MAX_CONFIGURATIONS` to the K builds your buyer-facing UI wants to surface -- the solver returns once the cap is hit (status `SOLUTION_LIMIT`) and `time_limit_sec` is your safety net for runaway enumeration.
- **Add a new region** by adding rows to `regional_rules.csv` for the new region and changing `TARGET_REGION` in the runner.
- **Tighten the price ceiling** by lowering `PRICE_CEILING_CENTS` to force the solver toward cheaper builds. If the ceiling drops below the cheapest feasible build, the solver returns INFEASIBLE.
- **Switch from "all feasible" to "the cheapest build"** by adding `problem.minimize(sum(Option.price_cents * Option.selected))` and setting `MAX_CONFIGURATIONS = 1`. The solver returns one optimum. Top-K *optimal* enumeration (the K cheapest distinct builds, ranked) is not a single solver call; for that, run an iterative exclusion-cut loop -- after each optimal solve, add a constraint forbidding the just-returned build's exact option set, then re-solve -- or sort the enumerated multi-solution set in post-processing if the feasible set is small enough to fit in memory (the bundled demo already does this: 63 builds sorted ascending by total dollars).
- **Add cardinality rules** like "at least one of {A, B, C} must be selected" with `count` over a filter on `Option.id`.
- **Apply this to enterprise software bundling** by mapping slots to product modules, options to feature tiers, implies/excludes to module dependencies, and price_cents to seat-license cost. The constraint families and multi-solution shape carry over unchanged.

## Troubleshooting

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS is not appropriate here -- the model is integer feature-model configuration, not LP/MILP.

</details>

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Lower the price ceiling far enough and no feasible build exists. Raise `PRICE_CEILING_CENTS` until the solver returns a configuration.
- Conflicting implies / excludes rules can render the model infeasible. For example, "A implies B" together with "A excludes B" makes A unselectable.

</details>

<details>
  <summary>ValueError: No options are allowed in region X for slot(s) [...]</summary>

- The pre-solve catalog check found a slot with zero region-allowed options. The exactly-one IC is scoped via `model.where(Option.allowed_in(TARGET_REGION), Option.slot(Slot))`, so it would not bind on the empty slot and the solver could return a "build" that is missing that slot entirely.
- Allow at least one option per slot for `TARGET_REGION` in `data/regional_rules.csv`, or remove the slot from `data/slots.csv` if the slot really does not exist in this market.

</details>

<details>
  <summary>ValueError: implies rules whose target option is not allowed in the region</summary>

- The pre-solve catalog check found an implies rule (A -> B) where the head option A is allowed in the region but the tail option B is not. The implies IC filters both A and B to `TARGET_REGION`, so the IC would not bind for this rule and A could be selected even though its tail B does not exist in the region.
- Either ban A in this region (drop the row for `(option_id=A, region=TARGET_REGION)` from `data/regional_rules.csv`), or allow B in this region (add `(option_id=B, region=TARGET_REGION)`).

</details>

<details>
  <summary>How many configurations will the solver return?</summary>

- Up to `MAX_CONFIGURATIONS` (100 by default) or however many feasible builds exist in the catalog, whichever is smaller. `solve_info().num_points` reports the actual count; `solve_info().status` reports `OPTIMAL` when the search has been exhausted (every distinct feasible build returned) and `SOLUTION_LIMIT` when the cap was hit before exhaustion (more builds available).
- The bundled demo has 63 feasible builds in `EU` and `MAX_CONFIGURATIONS = 100` is large enough to enumerate them all, so status is `OPTIMAL` and the *set* of returned builds is deterministic (ordering is re-imposed by the post-solve sort by `total_$`).
- When `MAX_CONFIGURATIONS` is tighter than the feasible set, the solver returns the first K it finds and the specific subset depends on MiniZinc's branching heuristics, so the *set* may shift across solver versions. Treat the `solution` column as a label, not a ranking.
- Returned builds are guaranteed to be *distinct* (each differs on at least one option) but not maximally diverse -- two builds may share five of six slots and only differ on the cheapest. For broad spread, layer optimization passes or apply your own diversity filters in post-processing.
- To pin a single answer (e.g. surface the cheapest build first), set `MAX_CONFIGURATIONS = 1` and add `problem.minimize(sum(Option.price_cents * Option.selected))`.

</details>
