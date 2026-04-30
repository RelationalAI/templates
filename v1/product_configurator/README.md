---
title: "Product Configurator"
description: "Enumerate every feasible build of a configurable product using a CSP solver in multi-solution mode: one option per slot subject to feature-model rules, regional regulations, and a price ceiling."
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

A configurator UI rarely wants a *single* feasible build. A buyer's quote, a sales playbook, and a "show me my options under this ceiling" trade-off slider all need the *population* of feasible configurations -- the cheap-but-basic build, the loaded build at the price-ceiling boundary, the build that drops a low-utility option to free up budget elsewhere. This template formulates the configuration problem as a constraint satisfaction model using RelationalAI's prescriptive reasoning and runs the solver in multi-solution mode: pass `solution_limit=MAX_CONFIGURATIONS` to `problem.solve(...)`, then enumerate each feasible build via `Variable.values(solution_index, value)`. The output is one row per selected option per solution, with per-solution totals -- ready to drop straight into a buyer-facing UI.

For one target region, every returned build picks exactly one option per slot so that all feature-model rules are satisfied (requires / excludes), only region-allowed options appear, and the total price stays within a ceiling. Solver enumeration guarantees each returned build is *distinct* (differs on at least one option) but not maximally diverse -- if you need broad spread across the catalogue, layer optimisation passes on top.

The configurator scenario here is automotive trim, drawn from the public Renault feature-model literature. The same pattern -- slots, options, requires, excludes, regional availability, price ceiling -- applies directly to enterprise software licence bundling, industrial machinery configuration, and bill-of-materials product variants. Multi-solution enumeration is the right return shape for all of them.

## Who this is for

- Product engineers and configuration specialists in manufacturing or industrial automation
- Software developers building product-configurator UIs that need a constraint engine in the backend
- Operations researchers learning how feature-model configuration translates to constraint programming
- Developers exploring prescriptive reasoning with RelationalAI

## What you'll build

- A constraint model with binary `Option.selected` decisions and four constraint families: per-slot exactly-one, requires, excludes, and price ceiling
- A region-filtered decision domain so options not allowed in the target region simply don't appear as decisions
- **Multi-solution enumeration as the primary code path**: `problem.solve(..., solution_limit=MAX_CONFIGURATIONS)` runs the search in enumeration mode; `Variable.values(solution_index, value)` then surfaces every distinct feasible build, with per-solution totals computed by `sum(...).per(solution_index)`
- Post-solve verification via `problem.verify()` confirming every named constraint holds in the returned configuration (`verify` inspects only the first solution, but the constraint structure is shared across every solution the solver returns)

## What's included

- `product_configurator.py` -- main script with ontology, decisions, constraints, and solver call
- `data/slots.csv` -- 6 slots (Engine, Transmission, Trim, Sound, Wheels, Roof)
- `data/options.csv` -- 16 options across the 6 slots, each with a price in integer cents
- `data/requires.csv` -- option-to-option requires rules (e.g. Premium Audio requires Premium Trim)
- `data/excludes.csv` -- option-to-option excludes rules (e.g. V6 excludes Manual)
- `data/regional_rules.csv` -- which options are allowed in which region (US, EU)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

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

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python product_configurator.py
   ```

6. Expected output. With `MAX_CONFIGURATIONS = 5` and `TARGET_REGION = "EU"` the solver enumerates 5 distinct feasible builds and stops because it has hit the limit (status `SOLUTION_LIMIT`); the bundled catalogue admits more builds than that, so raising `MAX_CONFIGURATIONS` will surface them. Solver build strings, exact wall times, and per-solution ordering will vary; the structure of the output and the *set* of returned builds is stable:
   ```text
   Solve result:
   • status: SOLUTION_LIMIT
   • objective: 0
   • solve time: 0.08s
   • num_points: 5
   • solver: MiniZinc_nothing

   Feasible configurations for region 'EU' (ceiling $20,000, up to 5 per run):
       solution          slot           option  price_cents
   0          0        Engine       2.0L Turbo       350000
   1          0          Roof       Steel Roof            0
   2          0         Sound   Standard Sound            0
   3          0  Transmission        Automatic       200000
   4          0          Trim       Sport Trim       250000
   5          0        Wheels    18-inch Sport       120000
   6          1        Engine    1.6L Inline-4       150000
   7          1          Roof       Steel Roof            0
   8          1         Sound   Standard Sound            0
   9          1  Transmission        Automatic       200000
   10         1          Trim       Sport Trim       250000
   11         1        Wheels    18-inch Sport       120000
   12         2        Engine       2.0L Turbo       350000
   13         2          Roof       Steel Roof            0
   14         2         Sound   Standard Sound            0
   15         2  Transmission        Automatic       200000
   16         2          Trim        Base Trim            0
   17         2        Wheels    18-inch Sport       120000
   18         3        Engine       2.0L Turbo       350000
   19         3          Roof  Panoramic Glass       300000
   20         3         Sound   Standard Sound            0
   21         3  Transmission        Automatic       200000
   22         3          Trim     Premium Trim       500000
   23         3        Wheels    18-inch Sport       120000
   24         4        Engine       2.0L Turbo       350000
   25         4          Roof  Panoramic Glass       300000
   26         4         Sound    Premium Audio       150000
   27         4  Transmission        Automatic       200000
   28         4          Trim     Premium Trim       500000
   29         4        Wheels    18-inch Sport       120000

   Total price per configuration (cents):
      solution  total_cents
   0         0       920000
   1         1       720000
   2         2       670000
   3         3      1470000
   4         4      1620000
   ```

   With `TARGET_REGION = "EU"`, the V6 engine is unavailable. Constraints rule out combinations like 1.6L + 19-inch Performance wheels, V6 + Manual transmission, DCT + non-2.0L engine, Premium Audio without Premium Trim, and Panoramic Glass with Sport Trim. The five returned builds span an $8k spread (cheapest $6,700 / most-loaded $16,200) and trade off across the Engine, Trim, Roof, and Sound slots -- exactly the kind of "show me my options" surface a buyer-facing UI wants.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── product_configurator.py
└── data/
    ├── slots.csv
    ├── options.csv
    ├── requires.csv
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
Option.slot = model.Relationship(f"{Option} is in {Slot}")
Option.allowed_in = model.Relationship(f"{Option} is allowed in {String:region}")
```

**2. Define the requires and excludes rule tables.** Each rule is a concept identified by the pair of option IDs it links:

```python
Requires = model.Concept(
    "Requires",
    identify_by={"option_a_id": Integer, "option_b_id": Integer},
)
Excludes = model.Concept(
    "Excludes",
    identify_by={"option_a_id": Integer, "option_b_id": Integer},
)
```

**3. Define the binary decision variable.** `Option.selected` is 0/1 and only exists for options allowed in the target region. Options banned in the region simply do not get a decision variable:

```python
Option.selected = model.Property(f"{Option} is selected if {Integer:selected}")
problem.solve_for(
    Option.selected,
    type="bin",
    name=["selected", Option.name],
    where=[Option.allowed_in(TARGET_REGION)],
)
```

**4. Add the four constraint families.** Each constraint is stored in a named variable so it can be verified after solving:

```python
exactly_one_ic = model.where(
    Option.allowed_in(TARGET_REGION),
    Option.slot(Slot),
).require(sum(Option.selected).per(Slot) == 1)

A = Option.ref()
B = Option.ref()
requires_ic = model.where(
    R := Requires,
    A.id(R.option_a_id),
    B.id(R.option_b_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected <= B.selected)

excludes_ic = model.where(
    E := Excludes,
    A.id(E.option_a_id),
    B.id(E.option_b_id),
    A.allowed_in(TARGET_REGION),
    B.allowed_in(TARGET_REGION),
).require(A.selected + B.selected <= 1)

price_ic = model.where(
    Option.allowed_in(TARGET_REGION),
).require(sum(Option.price_cents * Option.selected) <= PRICE_CEILING_CENTS)
```

The requires constraint reads as "if A is selected (selected[A] = 1), then B must be selected too (selected[B] = 1), so selected[A] <= selected[B]". The excludes constraint reads as "at most one of A and B may be selected".

**5. Solve in multi-solution mode and verify.** Pass `solution_limit=MAX_CONFIGURATIONS` to enumerate up to that many distinct feasible builds. After solving, `problem.verify()` fires the named constraints to confirm the configuration satisfies every rule (it inspects only the first solution -- the populated property -- but the constraint structure is shared across every solution the solver returns):

```python
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)
problem.solve_info().display()
problem.verify(exactly_one_ic, requires_ic, excludes_ic, price_ic)
```

**6. Inspect every feasible build with `Variable.values`.** Capturing the variable subconcept from `solve_for(...)` exposes a `.values(solution_index, value)` relationship that indexes the per-solution outputs; filtering on `value == 1` surfaces just the options the solver picked into each build. The variable subconcept exposes a back-pointer field named after the entity in its property: `selected_var.option` walks back to the `Option` instance for each row, so `selected_var.option.slot.name` and `selected_var.option.price_cents` resolve naturally:

```python
selected_var = problem.solve_for(
    Option.selected, type="bin", name=["selected", Option.name],
    where=[Option.allowed_in(TARGET_REGION)],
)
# ... constraints ...
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_CONFIGURATIONS)

sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    selected_var.option.slot.name.alias("slot"),
    selected_var.option.name.alias("option"),
    selected_var.option.price_cents.alias("price_cents"),
).where(selected_var.values(sol_idx, val), val == 1).inspect()
```

Per-solution aggregates use `.per(solution_index_ref)` to group across `Variable.values` rows -- this is how `Total price per configuration` is computed:

```python
sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    sum(selected_var.option.price_cents * val).per(sol_idx).alias("total_cents"),
).where(selected_var.values(sol_idx, val)).inspect()
```

## Customize this template

- **Use your own product** by replacing the five CSV files with your slots, options, requires, excludes, and regional_rules tables. The constraint structure does not change.
- **Raise the solution limit on a real catalogue.** The bundled `MAX_CONFIGURATIONS = 5` is sized for the demo. On a production catalogue you may want `MAX_CONFIGURATIONS = 50` or higher so the buyer-facing UI surfaces a meaningful spread; `time_limit_sec` is your safety net -- enumeration stops when either the limit or the budget is reached.
- **Add a new region** by adding rows to `regional_rules.csv` for the new region and changing `TARGET_REGION` in the runner.
- **Tighten the price ceiling** by lowering `PRICE_CEILING_CENTS` to force the solver toward cheaper builds. If the ceiling drops below the cheapest feasible build, the solver returns INFEASIBLE.
- **Switch from "all feasible" to "best K"** by adding `problem.minimize(sum(Option.price_cents * Option.selected))`. Under multi-solution mode this returns the K *cheapest* feasible builds in lex order rather than an arbitrary 5; pair with `MAX_CONFIGURATIONS = 5` to surface a top-of-funnel "cheapest options" view, or with `maximize(...)` over a desirability score for a "best-value" view.
- **Add cardinality rules** like "at least one of {A, B, C} must be selected" with `count` over a filter on `Option.id`.
- **Apply this to enterprise software bundling** by mapping slots to product modules, options to feature tiers, requires/excludes to module dependencies, and price_cents to seat-licence cost. The constraint families and multi-solution shape carry over unchanged.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Lower the price ceiling far enough and no feasible build exists. Raise `PRICE_CEILING_CENTS` until the solver returns a configuration.
- A regional rule may have stripped every option from a slot, leaving the per-slot exactly-one constraint unsatisfiable. Check `data/regional_rules.csv` to confirm at least one option per slot is allowed in `TARGET_REGION`.
- Conflicting requires / excludes rules can render the model infeasible. For example, "A requires B" together with "A excludes B" makes A unselectable.

</details>

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
  <summary>How many configurations will the solver return?</summary>

- Up to `MAX_CONFIGURATIONS` (5 by default) or however many feasible builds exist in the catalogue, whichever is smaller. `problem.num_points()` reports the actual count; `solve_info()` reports `status: SOLUTION_LIMIT` when the limit was hit (more builds available) and `status: OPTIMAL` when the search has been exhausted.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of returned builds for a given limit may also shift if MiniZinc's branching heuristics see new ties. Treat the `solution` column as a label, not a ranking.
- The K returned builds are guaranteed to be *distinct* (each differs on at least one option) but not maximally diverse -- you may see two builds that share five of six slots and only differ on the cheapest. For broad spread, layer optimisation passes or apply your own diversity filters in post-processing.
- To pin a single answer (e.g. surface the cheapest build first), set `MAX_CONFIGURATIONS = 1` and add `problem.minimize(sum(Option.price_cents * Option.selected))`.

</details>
