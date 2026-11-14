---
title: "Cell Tower Coverage"
description: "Choose which candidate cell tower sites to build and assign demand zones to them, maximizing covered population under budget, tower-count, and capacity limits."
featured: false
experience_level: beginner
industry: "Technology & Telecom"
reasoning_types:
    - Prescriptive
tags:
  - Mixed-Integer Programming
  - Set Covering
  - Maximum Coverage
  - Facility Location
  - Wireless Network Planning
  - Infrastructure Planning
  - HiGHS
---

## What this template is for

Telecommunications and infrastructure teams routinely have to decide where to build the next set of wireless sites. Candidate locations differ in build cost and serving capacity, and each site can cover only a subset of demand zones based on distance, terrain, signal quality, or planning rules. Picking the cheapest tower or the one covering the single largest zone rarely gives the best plan — the selected sites have to work together as a portfolio, and the demand assigned to a tower cannot exceed its capacity. This template chooses tower sites and assigns each covered demand zone to a serving tower so that covered population is as large as possible within a fixed build budget and a cap on the number of new towers.

**The model uses RelationalAI's prescriptive reasoner to solve a maximum-coverage mixed-integer program in which binary variables select tower sites, mark demand zones as covered, and assign each covered zone to exactly one selected tower that can serve it.** The result is a defensible capital plan: which sites to build, which zones they serve, how loaded each tower is, and which population remains uncovered.

## Who this is for

- Network planners evaluating candidate tower sites and infrastructure teams prioritizing capital projects.
- Public-sector analysts studying emergency-communications or rural-broadband coverage.
- Data scientists and engineers learning set-covering and maximum-coverage optimization with RelationalAI.
- **Assumed knowledge**: comfortable reading Python; the optimization terms (decision variables, constraints, objective) are explained as they come up. As a beginner-level single-reasoner template, no prior RelationalAI experience is required to run it.

## What you'll build

- A funded tower-build plan that maximizes covered population within a fixed capital budget and a cap on new towers, produced by **prescriptive reasoning** (a mixed-integer program).
- A semantic model of candidate tower sites, demand zones, and feasible tower-zone coverage pairs, expressed as RelationalAI concepts and relationships.
- A coverage-linking rule that counts a zone as covered only when it is assigned to exactly one selected, serving tower, plus a capacity rule that prevents any tower from being overloaded.
- A coverage report — selected sites with utilization, assigned zones, uncovered zones, and total coverage rate — written to `data/coverage_solution.csv` for downstream mapping or reporting.

## What's included

- **Model**: `model/__init__.py` builds the semantic model (three concepts, two coverage relationships), the mixed-integer optimization problem (three binary variable families, four constraints, one objective), and the solve; `rai models deploy --path model` deploys it to your Snowflake account, where each refresh runs the solve.
- **Query**: `queries/coverage_report.py` prints the report from the deployed model and writes `data/coverage_solution.csv`.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: 6 candidate tower sites, 10 demand zones, and 19 feasible tower-zone coverage pairs. See *Sample data* below.
- **Outputs**: stdout tables (selected sites, assigned zones, uncovered zones, coverage summary) plus `data/coverage_solution.csv`.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 2.1.1`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.CELL_TOWER_COVERAGE_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.CELL_TOWER_COVERAGE_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/cell_tower_coverage.zip), unzip it, and enter the template directory:

   ```bash
   unzip cell_tower_coverage.zip
   cd cell_tower_coverage
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: cell_tower_coverage_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.CELL_TOWER_COVERAGE               # published views and tables
     identity:
       internal_schema: <DB>.CELL_TOWER_COVERAGE_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.coverage_report
   ```

   ```text
   ======================================================================
   CELL TOWER COVERAGE
   ======================================================================
   Candidate tower sites: 6
   Demand zones: 10
   Coverage pairs: 19
   Build budget: $650,000
   Max new towers: 3

   Status: OPTIMAL
   Objective: covered population = 90,000

   ...

   === Coverage Summary ===
   Selected build cost: $610,000 of $650,000
   Covered population: 90,000 of 102,900
   Coverage rate: 87.46%
   Uncovered population: 12,900

   Wrote coverage solution to: /path/to/cell_tower_coverage/data/coverage_solution.csv
   ```

   The selected-sites, assigned-zones, and uncovered-zones tables are trimmed here. Three towers (T04, T02, and T06) cover 90,000 of 102,900 people for $610,000 of the $650,000 budget, and zones Z04 and Z10 stay uncovered. The report also writes the per-zone solution to `data/coverage_solution.csv` in the template directory, and it stops unless the termination status is OPTIMAL or TIME_LIMIT.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.CELL_TOWER_COVERAGE_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure

```text
cell_tower_coverage/
  model/
    __init__.py                   # the deployed model (concepts, constraints, solve)
  queries/
    coverage_report.py            # report from the deployed model
  data/
    tower_sites.csv               # 6 candidate build sites
    demand_zones.csv              # 10 population demand zones
    coverage_pairs.csv            # 19 feasible tower-zone coverage pairs
    coverage_solution.csv         # written by the query
  README.md                       # this file
  runbook.md                      # paste-testable walkthrough (RAI skills)
  pyproject.toml                  # dependencies
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.coverage_report` for the full model, solve, and report end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative — a compact network-expansion screen shaped like a real one, not a specific operator's network. The coverage pairs could come from a radio-frequency planning tool, a distance threshold, a terrain model, or engineering judgment.

- **`tower_sites.csv`** (6 rows) — candidate tower sites across five regions, with site type (macro or small cell), build cost, and serving capacity.
- **`demand_zones.csv`** (10 rows) — demand zones with region and population count.
- **`coverage_pairs.csv`** (19 rows) — feasible tower-zone service pairs, each with a distance and a signal score. Every demand zone appears in at least one pair, so every zone is reachable by some tower.
- **`coverage_solution.csv`** — written after the solve; one row per demand zone with its covered flag and assigned site.

## Model overview

Three concepts describe the planning problem; the optimization adds one binary decision property to each.

- **Key entities**: `TowerSite` — a candidate infrastructure location that may be built (site type, build cost, serving capacity); `DemandZone` — a population area that may be covered by a selected tower; `CoveragePair` — a feasible tower-zone service relationship, where only paired zones can be served and only by their paired towers.
- **Primary identifiers**: `site_id` on `TowerSite`, `zone_id` on `DemandZone`, and a composite `site_id` + `zone_id` key on `CoveragePair`.
- **Important invariants**: build costs, capacities, and populations are non-negative; every demand zone is reachable by at least one coverage pair (the deploy stops with an error otherwise); the decision variables (`selected`, `covered`, `assigned`) are binary; total build cost stays at or under the budget and the number of selected towers stays at or under the cap.

`CoveragePair` links each pair to its `TowerSite` and `DemandZone`, so only zones that appear as a pair can be served, and only by the towers they are paired with.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline runs from CSV inputs to a solved plan and an exported solution:

```text
CSV inputs -> load and validate -> concepts and coverage pairs -> decision variables -> constraints and objective -> solve (HiGHS) -> report and export
```

### 1. Load and validate the planning data

The model reads the three CSVs and runs feasibility checks before building it: each file is non-empty, the parameters are positive, coverage pairs reference known site and zone IDs, and every demand zone is reachable by at least one pair. Any violation raises a clear error rather than producing a silently wrong plan.

### 2. Define selection, coverage, and assignment variables

The model has three families of binary decision variables. `x_selected` chooses which candidate sites to build. `y_covered` records whether each demand zone ends up covered. `z_assigned` chooses the specific selected tower that serves a covered zone; assignment variables exist only on rows of `coverage_pairs.csv`, so a zone can only be assigned to a tower that can physically cover it.

### 3. Link coverage to serving assignments

A zone counts as covered only when it is assigned to exactly one feasible coverage pair. This per-zone rule prevents the objective from marking a zone as covered without a physical serving tower.

### 4. Assign zones only to selected towers

Each assignment must use a selected tower, so `assigned` cannot exceed `selected` for the pair's tower. If a tower is not selected, none of its pairs can be assigned.

### 5. Respect tower capacity

Each selected tower can serve assigned population only up to its capacity, summed per tower over its assigned zones. If a tower is not built, its capacity term is zero and no zone can be assigned to it.

### 6. Respect capital and rollout limits

Two portfolio constraints bound the plan: total build cost stays at or under `BUILD_BUDGET`, and the number of selected towers stays at or under `MAX_NEW_TOWERS`.

### 7. Maximize covered population

The objective rewards covering high-population zones, weighting each covered zone by its population. Because each zone has a single binary covered variable and each covered zone has exactly one assignment, the model handles overlapping tower coverage without double-counting population or overloading selected towers. After the solve, the query builds report tables (selected sites with utilization, assigned zones, uncovered zones, coverage summary) and writes `data/coverage_solution.csv`.

See `model/__init__.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column names listed in *Sample data* above.
- Regenerate coverage pairs with your preferred distance, signal-strength, or engineering threshold, and make sure every demand zone appears in at least one pair (the model requires it).
- Adjust the `capacity` column in `tower_sites.csv` to reflect real serving capacity, and the `build_cost` column to reflect real capital cost.

### Tune parameters

- **Build budget** — `BUILD_BUDGET` (default `650,000`) caps total capital spend.
- **Rollout size** — `MAX_NEW_TOWERS` (default `3`) caps how many sites the plan may select.
- **Solve budget** — `time_limit_sec` on the `problem.configure("highs", ...)` call (default `60` seconds).

### Extend the model

- **Add regional fairness** — require a minimum number of covered zones or a minimum covered population per region.
- **Allow fractional assignment** — replace the binary assignment variable with a continuous fraction if a zone's demand can split across multiple serving towers.
- **Add more candidates or zones** — grow `tower_sites.csv` and `demand_zones.csv`, then extend `coverage_pairs.csv` accordingly.

### Scale up / productionize

- For Snowflake-backed runs, swap the `pd.read_csv(...)` calls for `model.data(snowflake_table)` calls so inputs arrive from live tables rather than the bundled CSVs.
- The model scales to whatever fits the prescriptive engine's solve budget; the default HiGHS solve carries a 60-second time limit that you can raise for larger networks.
- Pin dependencies (see `pyproject.toml`) for reproducible runs.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Check that `BUILD_BUDGET` is positive and large enough to select at least one candidate tower.
- Verify that every demand zone appears in `coverage_pairs.csv` at least once.
- Confirm that coverage pairs reference valid `site_id` and `zone_id` values.
- Check that at least one feasible set of selected towers has enough capacity to serve at least one zone.

</details>

<details>
  <summary>Solver selects no towers</summary>

- The budget may be lower than the cheapest candidate tower site.
- Increase `BUILD_BUDGET` or lower one or more `build_cost` values.

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

## Learn more

### Core concepts

- [RelationalAI documentation](https://docs.relational.ai/) — concepts, relationships, and the semantic model used throughout this template.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives that drive the maximum-coverage program.

### CLI / SDK guides

- [RelationalAI setup and `rai init`](https://docs.relational.ai/) — connecting the SDK to a Snowflake-backed RAI account.

## Support

- File issues at the RelationalAI templates repository.
