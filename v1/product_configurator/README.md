---
title: "Product Configurator"
description: "Enumerate every feasible build of a configurable product with a constraint solver in multi-solution mode. Each build picks one option per slot subject to feature-model rules, regional regulations, and a price ceiling."
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
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
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

6. Expected output. With `MAX_CONFIGURATIONS = 100` and `TARGET_REGION = "EU"`, the solver exhausts the search and returns every distinct feasible build (status `OPTIMAL`, 63 builds), pivoted to one row per configuration and sorted ascending by total dollars. A few representative lines (the script prints all 63):

   ```text
   Solve result:
   • status: OPTIMAL
   • num_points: 63

   Feasible builds for region 'EU' (ceiling $20,000, up to 100 per run):
    solution        Engine            Roof          Sound Transmission         Trim              Wheels  total_$
          60 1.6L Inline-4      Steel Roof Standard Sound       Manual    Base Trim       16-inch Alloy     1500
          59 1.6L Inline-4      Steel Roof Standard Sound       Manual    Base Trim       18-inch Sport     2700
           ... 60 more builds omitted (script prints all 63) ...
           2    2.0L Turbo Panoramic Glass  Premium Audio          DCT Premium Trim       18-inch Sport    18200
   ```

   With `TARGET_REGION = "EU"` the V6 engine is unavailable, and the 63 returned builds span $1,500-$18,200 -- every legal combination across the six slots, satisfying every implies/excludes rule. Lower `MAX_CONFIGURATIONS` to cap how many the solver returns (status flips to `SOLUTION_LIMIT` once hit). The full 63-row printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
product_configurator/
  product_configurator.py    # Main script (ontology, decisions, constraints, solve, inspection)
  data/
    slots.csv                # 6 slots (Engine, Transmission, Trim, Sound, Wheels, Roof)
    options.csv              # 16 options across the 6 slots, each priced in integer cents
    implies.csv              # option-to-option implies rules (head -> tail)
    excludes.csv             # option-to-option excludes rules (symmetric)
    regional_rules.csv       # which options are allowed in which region (US, EU)
  README.md                  # this file
  runbook.md                 # analyst-facing paste-testable walkthrough
  pyproject.toml             # dependencies
```

**Start here**: run `python product_configurator.py` to enumerate every feasible build end to end, or follow `runbook.md` to rebuild it step by step.

## Sample data

The bundled CSVs are illustrative demo data for an automotive trim configurator, drawn from the public Renault feature-model literature. Swap in your own slots, options, and rules to configure a different product.

- **`slots.csv`** (6 rows) — the configurable slots (Engine, Transmission, Trim, Sound, Wheels, Roof).
- **`options.csv`** (16 rows) — the options across the six slots, each with a `slot_id`, `name`, and `price_cents`.
- **`implies.csv`** — directional option-to-option rules (`head_id` -> `tail_id`); selecting the head requires the tail.
- **`excludes.csv`** — symmetric option-to-option rules (`left_id`, `right_id`); at most one of the pair may be selected.
- **`regional_rules.csv`** — one row per `(option_id, region)` allowed pairing; an option missing for a region is banned there.

## Model overview

The script builds a small ontology from the CSVs, then layers the binary decision and the four constraint families on top.

- **Key entities**: `Slot`, `Option`; plus the `Implies` and `Excludes` rule tables.
- **Primary identifiers**: integer `id` on `Slot` and `Option`; composite key on each rule table (`head_id` + `tail_id` on `Implies`, `left_id` + `right_id` on `Excludes`).
- **Important invariants**: every option belongs to exactly one slot; prices are non-negative integer cents; a build picks exactly one option per slot; only options allowed in the target region get a decision variable.

The two rule tables — `Implies(head_id, tail_id)` (selecting the head requires the tail) and `Excludes(left_id, right_id)` (at most one of the pair) — are concepts identified by the pair of option ids they link, and the constraint families read them directly.

For the full concept and property definitions, see `product_configurator.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model declares a binary "selected" decision per region-allowed option, applies four constraint families, then enumerates every feasible build in one multi-solution solve.

```text
slots + options + implies + excludes + regional rules → region-filtered selected decisions → exactly-one + implies + excludes + price constraints → multi-solution solve → pivot to one row per build
```

**1. Slots, options, and rule tables.** Slots and options are concepts; each option points to its slot, has a price in integer cents, and lists the regions it is allowed in. Each rule is a concept identified by the pair of option ids it links — `Implies` is directional (head -> tail), `Excludes` is symmetric. The compound-key field names are deliberately dissimilar (`head_id`/`tail_id`, `left_id`/`right_id`) because PyRel emits a "potential relationship typo" warning when two compound-key names differ by a single character.

**2. The binary decision.** `Option.selected` is 0/1 and is scoped, via a `where` on region availability, to options allowed in the target region — options banned in the region simply never get a decision variable. The `solve_for` call returns a variable handle that step 4 uses to read per-solution outputs.

**3. The four constraint families.** Each is stored in a named variable so it can be re-checked by `problem.verify(...)`, and pushed to the solver with `problem.satisfy(...)`:

- **Exactly-one** — the selected options per slot sum to 1, so every build fills each slot exactly once.
- **Implies** — for each region-allowed rule, `selected[head] <= selected[tail]`: picking the head forces the tail.
- **Excludes** — for each region-allowed pair, `selected[left] + selected[right] <= 1`: at most one of the pair.
- **Price ceiling** — the price-weighted sum of selected options stays within `PRICE_CEILING_CENTS`.

**4. Solve in multi-solution mode, verify, and pivot.** Passing `solution_limit=MAX_CONFIGURATIONS` runs the search in enumeration mode, returning up to that many distinct feasible builds. `problem.verify()` re-checks the named constraints against the first returned solution (the constraint structure is shared across every solution the solver returns). The variable handle exposes a `.values(solution_index, value)` relationship over the per-solution outputs; binding the value slot to `1` surfaces just the picked options, and a `pandas.pivot` collapses the per-option rows into one row per build (one column per slot, plus a dollar total, sorted ascending by price) for buyer-facing display.

For the exact PyRel formulation, see `product_configurator.py`; `runbook.md` reproduces the model step by step with the RAI skills.

## Customize this template

### Use your own data

- Replace the five CSV files with your slots, options, implies, excludes, and regional_rules tables. The constraint structure does not change.
- **Add a new region** by adding rows to `regional_rules.csv` for the new region and changing `TARGET_REGION` in the runner.

### Tune parameters

- **Cap the solution limit on a large catalog.** The bundled `MAX_CONFIGURATIONS = 100` is above the demo's feasible-set size so every build is enumerated (status `OPTIMAL`). On a production catalog the feasible set can be enormous; lower `MAX_CONFIGURATIONS` to the K builds your buyer-facing UI wants to surface -- the solver returns once the cap is hit (status `SOLUTION_LIMIT`) and `time_limit_sec` is your safety net for runaway enumeration.
- **Tighten the price ceiling** by lowering `PRICE_CEILING_CENTS` to force the solver toward cheaper builds. If the ceiling drops below the cheapest feasible build, the solver returns INFEASIBLE.

### Extend the model

- **Switch from "all feasible" to "the cheapest build"** by adding `problem.minimize(sum(Option.price_cents * Option.selected))` and setting `MAX_CONFIGURATIONS = 1`. The solver returns one optimum. Top-K *optimal* enumeration (the K cheapest distinct builds, ranked) is not a single solver call; for that, run an iterative exclusion-cut loop -- after each optimal solve, add a constraint forbidding the just-returned build's exact option set, then re-solve -- or sort the enumerated multi-solution set in post-processing if the feasible set is small enough to fit in memory (the bundled demo already does this: 63 builds sorted ascending by total dollars).
- **Add cardinality rules** like "at least one of {A, B, C} must be selected" with `count` over a filter on `Option.id`.

### Scale up / productionize

- **Apply this to enterprise software bundling** by mapping slots to product modules, options to feature tiers, implies/excludes to module dependencies, and price_cents to seat-license cost. The constraint families and multi-solution shape carry over unchanged.
- Swap the `data/` CSV bundle for `model.data(snowflake_table)` calls to configure against a live Snowflake-hosted catalog; `time_limit_sec` and `MAX_CONFIGURATIONS` bound enumeration on large catalogs.

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

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — concepts, properties, relationships, and `model.where(...)`.
- [Prescriptive reasoner](https://docs.relational.ai/) — `Problem` API, binary decision variables, integrity constraints.

### Reasoner reference

- [Multi-solution enumeration](https://docs.relational.ai/) — `solution_limit`, `Variable.values(...)`, and reading every returned solution.
- [Constraint satisfaction patterns](https://docs.relational.ai/) — exactly-one, implies, excludes, and budget constraints over binary decisions.

## Support

- File issues at the RelationalAI templates repository.
