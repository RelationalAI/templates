---
title: "Product Configurator"
description: "Pick options per slot to assemble a buildable product subject to feature-model rules, regional regulations, and a price ceiling."
featured: false
experience_level: intermediate
industry: "Manufacturing"
reasoning_types:
  - Prescriptive
tags:
  - configuration
  - constraint-programming
  - feature-model
  - manufacturing
---

# Product Configurator

## What this template is for

Configurable products -- cars, industrial equipment, enterprise software, network gear -- come with hundreds or thousands of options grouped into slots (engine, transmission, trim, sound, wheels, and so on). Picking a buildable combination by hand is hard: options require or exclude other options, regional regulations remove some choices entirely, and the total price has to stay under a target.

This template formulates the configuration problem as a constraint satisfaction model using RelationalAI's prescriptive reasoning. For one target region, the solver picks exactly one option per slot so that all feature-model rules are satisfied (requires / excludes), only region-allowed options appear, and the total price stays within a ceiling. The solver (MiniZinc) returns a feasible build that respects every constraint at once.

The configurator scenario here is automotive trim, drawn from the public Renault feature-model literature. The same pattern -- slots, options, requires, excludes, regional availability, price ceiling -- applies directly to enterprise software licence bundling, industrial machinery configuration, and bill-of-materials product variants.

## Who this is for

- Product engineers and configuration specialists in manufacturing or industrial automation
- Software developers building product-configurator UIs that need a constraint engine in the backend
- Operations researchers learning how feature-model configuration translates to constraint programming
- Developers exploring prescriptive reasoning with RelationalAI

## What you'll build

- A constraint model with binary `Option.selected` decisions and four constraint families: per-slot exactly-one, requires, excludes, and price ceiling
- A region-filtered decision domain so options not allowed in the target region simply don't appear as decisions
- Post-solve verification via `problem.verify()` confirming every named constraint holds in the returned configuration

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

6. Expected output (the solver returns one feasible build; the exact options chosen may vary):
   ```text
   Selected configuration for region 'EU' (ceiling $20,000):
              slot              option  price_cents
            Engine          1.6L Inline-4       150000
      Transmission                Manual            0
              Trim             Base Trim            0
             Sound        Standard Sound            0
            Wheels         16-inch Alloy            0
              Roof            Steel Roof            0

   Total price (cents):
    total_cents
         150000
   ```

   With `TARGET_REGION = "EU"`, the V6 engine is unavailable. Constraints rule out combinations like 1.6L + 19-inch Performance wheels, V6 + Manual transmission, DCT + non-2.0L engine, Premium Audio without Premium Trim, and Panoramic Glass with Sport Trim.

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

**5. Solve and verify.** A single solve returns a feasible build. After solving, `problem.verify()` fires the named constraints to confirm the configuration satisfies every rule:

```python
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()
problem.verify(exactly_one_ic, requires_ic, excludes_ic, price_ic)
```

## Customize this template

- **Use your own product** by replacing the five CSV files with your slots, options, requires, excludes, and regional_rules tables. The constraint structure does not change.
- **Add a new region** by adding rows to `regional_rules.csv` for the new region and changing `TARGET_REGION` in the runner.
- **Tighten the price ceiling** by lowering `PRICE_CEILING_CENTS` to force the solver toward cheaper builds. If the ceiling drops below the cheapest feasible build, the solver returns INFEASIBLE.
- **Switch from satisfaction to optimization** by adding `problem.minimize(sum(Option.price_cents * Option.selected))` to find the cheapest feasible build, or `problem.maximize(...)` over a desirability score.
- **Add cardinality rules** like "at least one of {A, B, C} must be selected" with `count` over a filter on `Option.id`.
- **Apply this to enterprise software bundling** by mapping slots to product modules, options to feature tiers, requires/excludes to module dependencies, and price_cents to seat-licence cost. The constraint families carry over unchanged.

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
  <summary>The chosen configuration changes between runs</summary>

- This is constraint satisfaction, not optimization. Any feasible build is a valid answer; the solver is free to return different ones across runs.
- To pin a single answer, switch to optimization (e.g. `problem.minimize(sum(Option.price_cents * Option.selected))`) so the solver always returns the cheapest feasible build.

</details>
