---
title: "Cell Tower Coverage"
description: "Select candidate cell tower sites and assign demand zones to maximize covered population under budget, tower-count, and capacity limits."
featured: false
experience_level: beginner
industry: "Energy & Utilities"
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

# Cell Tower Coverage

## What this template is for

Telecommunications and infrastructure teams often need to decide where to build the next set of wireless sites. Candidate locations differ in cost and serving capacity, and each site can cover only a subset of demand zones based on distance, terrain, signal quality, or planning rules. This template chooses tower sites and assigns covered demand zones to selected towers, maximizing covered population while respecting a fixed build budget, a maximum number of new towers, and tower capacity limits.

The model uses RelationalAI's **prescriptive** reasoner to solve a maximum-coverage mixed-integer program with single assignment. Binary variables choose which tower sites to build, mark which demand zones are covered, and assign each covered demand zone to exactly one selected tower that can serve it.

## Why this problem matters

Coverage planning is a common capital allocation problem for wireless network expansion, public safety communications, rural broadband programs, and temporary network deployments. The challenge is that every candidate tower covers a different overlapping set of zones and has finite serving capacity. The best plan is not always the cheapest tower or the tower covering the largest single zone; the selected sites need to work together as a portfolio, and assigned demand cannot overload any selected tower.

### Key design patterns demonstrated

- **Maximum coverage** -- maximize covered population under a limited budget.
- **Linked binary decisions** -- a zone can count as covered only if it is assigned to a selected tower that can serve it.
- **Single assignment** -- every covered demand zone is assigned to exactly one serving tower.
- **Capacity constraints** -- each selected tower can serve assigned population only up to its capacity.
- **Budget-constrained selection** -- tower build costs must stay under a capital limit.
- **Cardinality constraint** -- the plan can select at most a fixed number of towers.
- **Many-to-many coverage relationships** -- tower-zone coverage pairs are represented explicitly in the ontology.
- **Post-solve coverage reporting** -- report selected sites, tower utilization, assigned zones, uncovered zones, and total coverage rate.

## Who this is for

- Network planners evaluating candidate tower sites
- Infrastructure teams prioritizing capital projects
- Public-sector analysts studying emergency communications coverage
- Data scientists learning set-covering and maximum-coverage optimization
- Engineers modeling binary selection decisions with RelationalAI

## What you'll build

- A semantic model for candidate tower sites, demand zones, and feasible coverage pairs
- A mixed-integer optimization model with tower-selection, zone-coverage, and zone-assignment variables
- A budget constraint and a maximum-tower constraint
- A coverage-linking constraint that assigns each covered zone to exactly one selected tower
- A tower-capacity constraint that prevents overloaded serving plans
- A covered-population objective
- A coverage summary and CSV output for downstream mapping or reporting

## What's included

- `cell_tower_coverage.py` -- Main script with the semantic model, optimization model, solve, and reporting
- `data/tower_sites.csv` -- Candidate tower sites with build costs, capacities, and site metadata
- `data/demand_zones.csv` -- Demand zones with region and population
- `data/coverage_pairs.csv` -- Feasible tower-zone service pairs with distance and signal score
- `pyproject.toml` -- Python package configuration with dependencies

## Template structure

```text
.
├─ README.md                       # this file
├─ pyproject.toml                  # dependencies
├─ cell_tower_coverage.py          # main entrypoint: model, solve, report
└─ data/
   ├─ tower_sites.csv              # candidate build sites
   ├─ demand_zones.csv             # population demand zones
   ├─ coverage_pairs.csv           # feasible tower-zone coverage pairs
   └─ coverage_solution.csv        # written by the script after solving
```

**Start here**: run `python cell_tower_coverage.py`.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/cell_tower_coverage.zip
   unzip cell_tower_coverage.zip
   cd cell_tower_coverage
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
   python cell_tower_coverage.py
   ```

6. Expected output:
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
   Objective: covered population = ...

   === Selected Tower Sites ===
   site_id                    name site_type  region build_cost capacity assigned_population utilization
      ...                     ...       ...     ...        ...

   === Assigned Demand Zones ===
   zone_id                 name  region population              assigned_site
      ...                  ...     ...        ...                         ...

   === Uncovered Demand Zones ===
   zone_id                 name  region population
      ...                  ...     ...        ...

   === Coverage Summary ===
   Selected build cost: ...
   Covered population: ...
   Coverage rate: ...
   Uncovered population: ...

   Wrote coverage solution to: data/coverage_solution.csv
   ```

## How It Works

### 1. Load the planning data

The template loads a compact synthetic dataset:

- `tower_sites.csv`: candidate tower sites, regions, site types, build costs, and serving capacities
- `demand_zones.csv`: demand zones with population counts
- `coverage_pairs.csv`: feasible service pairs from tower sites to demand zones

The data is synthetic but shaped like a real network expansion screen. The coverage pairs could come from a radio-frequency planning tool, a distance threshold, a terrain model, or engineering judgment.

### 2. Define selection, coverage, and assignment variables

The model has three binary decision variables:

```python
TowerSite.x_selected = model.Property(f"{TowerSite} selected if {Float:selected}")
DemandZone.y_covered = model.Property(f"{DemandZone} covered if {Float:covered}")
CoveragePair.z_assigned = model.Property(f"{CoveragePair} assigned if {Float:assigned}")
```

`x_selected` chooses candidate tower sites. `y_covered` records whether each demand zone is covered by the selected plan. `z_assigned` chooses the specific selected tower that serves a covered demand zone.

### 3. Link coverage to serving assignments

A demand zone can only count as covered if it is assigned to exactly one feasible tower-zone coverage pair:

```text
sum_j assigned[i,j] = covered[i]
```

This prevents the objective from marking a zone as covered unless the physical network plan gives it a serving tower. Assignment variables exist only for rows in `coverage_pairs.csv`, so a zone can only be assigned to a tower that can physically cover it.

### 4. Assign zones only to selected towers

Each assignment must use a selected tower:

```text
assigned[i,j] <= selected[j]
```

### 5. Respect tower capacity

Each selected tower can serve assigned population only up to its capacity:

```text
sum_i population[i] * assigned[i,j] <= capacity[j] * selected[j]
```

If a tower is not selected, the right side is zero, so no demand zone can be assigned to it.

### 6. Respect capital and rollout limits

The formulation limits both total build cost and the number of tower sites selected:

```text
sum_j build_cost[j] * selected[j] <= BUILD_BUDGET
sum_j selected[j] <= MAX_NEW_TOWERS
```

### 7. Maximize covered population

The objective rewards covering high-population zones:

```text
maximize sum_i population[i] * covered[i]
```

Because every demand zone has a binary covered variable and each covered zone has exactly one assignment, the model naturally handles overlapping tower coverage without double-counting population or overloading selected towers.

## Customize this template

- **Change the rollout budget** by editing `BUILD_BUDGET` in `cell_tower_coverage.py`.
- **Limit or expand the build plan** by changing `MAX_NEW_TOWERS`.
- **Add more candidate tower sites** in `tower_sites.csv`.
- **Add more demand zones** in `demand_zones.csv`.
- **Regenerate coverage pairs** using your preferred distance, signal-strength, or engineering threshold.
- **Adjust capacity assumptions** by editing the `capacity` column in `tower_sites.csv`.
- **Add regional fairness** by requiring a minimum number of covered zones or covered population per region.
- **Allow fractional assignment** by replacing binary assignment with continuous fractions if zones can split demand across multiple serving towers.

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

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>
