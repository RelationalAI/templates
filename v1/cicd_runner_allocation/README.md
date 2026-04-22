---
title: "CI/CD Runner Allocation"
description: "Assign CI/CD workflow jobs to the cheapest compatible runner type, subject to concurrency limits, with scenario analysis across capacity levels."
featured: false
experience_level: beginner
industry: "Software Engineering"
reasoning_types:
  - Prescriptive
tags:
  - Assignment
  - Resource Allocation
  - Cost Minimization
  - Scenario Analysis
  - CI/CD
  - HiGHS
---

# CI/CD Runner Allocation

## What this template is for

This template uses **prescriptive reasoning (optimization)** to assign CI/CD workflow jobs to runner types at minimum cost. Given a set of runners (GitHub Actions runner types with CPU, memory, OS, and per-minute cost) and workflow jobs (with resource requirements and estimated durations), the optimizer assigns each job to the cheapest compatible runner while respecting per-runner concurrency limits.

The template also demonstrates **scenario analysis** by sweeping concurrency multipliers (0.5x, 1.0x, 1.5x) to show how pipeline cost changes under capacity constraints -- useful for evaluating maintenance windows, cost reduction, or burst provisioning.

## Who this is for

- DevOps engineers optimizing CI/CD runner costs
- Platform teams sizing runner fleets for GitHub Actions or similar CI systems
- Anyone learning resource assignment optimization with RelationalAI

## What you'll build

- A binary assignment model that maps each workflow job to a compatible runner type
- Per-runner concurrency constraints scaled by a scenario parameter
- Cost minimization objective (runner cost_per_minute * job estimated_minutes)
- Scenario comparison showing cost impact of halving or increasing runner capacity

## What's included

- `cicd_runner_allocation.py` -- Main script with optimization and scenario analysis
- `data/runners.csv` -- 8 runner types with CPU, memory, OS, cost, and concurrency limits
- `data/workflows.csv` -- 20 CI/CD workflow jobs with resource requirements and durations
- `data/compatibility.csv` -- Pre-computed runner-workflow compatibility pairs (OS + resource match)
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://private.relational.ai/templates/zips/v1/cicd_runner_allocation.zip
   unzip cicd_runner_allocation.zip
   cd cicd_runner_allocation
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
   python cicd_runner_allocation.py
   ```

6. Expected output:
   ```text
   Running scenario: concurrency_multiplier = 0.5
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $10.18

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (4 jobs): e2e-tests-chrome, integration-tests, nightly-build, performance-tests
       ubuntu-22.04 (4 jobs): build-api, dependency-audit, lint-and-format, release-notes
       ubuntu-large (3 jobs): build-mobile-android, docker-build, unit-tests-api
       ubuntu-latest (5 jobs): build-frontend, deploy-production, deploy-staging, security-scan, unit-tests-frontend
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.0
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $9.62

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (8 jobs): build-api, build-mobile-android, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, unit-tests-api
       ubuntu-22.04 (3 jobs): dependency-audit, lint-and-format, release-notes
       ubuntu-latest (5 jobs): build-frontend, deploy-production, deploy-staging, security-scan, unit-tests-frontend
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.5
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $9.53

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (12 jobs): build-api, build-frontend, build-mobile-android, dependency-audit, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, security-scan, unit-tests-api, unit-tests-frontend
       ubuntu-22.04 (2 jobs): deploy-staging, release-notes
       ubuntu-latest (2 jobs): deploy-production, lint-and-format
       windows-latest (1 jobs): windows-installer

   ==================================================
   Scenario Analysis Summary
   ==================================================
     concurrency_multiplier=0.5: OPTIMAL, cost=$10.18
     concurrency_multiplier=1.0: OPTIMAL, cost=$9.62
     concurrency_multiplier=1.5: OPTIMAL, cost=$9.53
   ```

   At full capacity (1.0x), self-hosted-linux absorbs 8 of 20 jobs at
   $0.005/min -- the cheapest runner. At half capacity (0.5x), its 4-job
   cap forces overflow to ubuntu-large and ubuntu-22.04, raising cost by
   6%. Burst mode (1.5x) pushes 12 jobs to self-hosted, saving another
   $0.09 by avoiding the more expensive ubuntu runners entirely.

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── cicd_runner_allocation.py
└── data/
    ├── runners.csv
    ├── workflows.csv
    └── compatibility.csv
```

## How it works

This section walks through the highlights in `cicd_runner_allocation.py`.

### Define concepts and load CSV data

The model defines three concepts. `Runner` represents CI/CD runner types with resource specs and cost:

```python
Runner = model.Concept("Runner", identify_by={"runner_id": Integer})
Runner.name = model.Property(f"{Runner} has {String:runner_name}")
Runner.os = model.Property(f"{Runner} has {String:runner_os}")
Runner.cpu = model.Property(f"{Runner} has {Integer:cpu}")
Runner.cost_per_minute = model.Property(f"{Runner} has {Float:cost_per_minute}")
Runner.max_concurrent = model.Property(f"{Runner} has {Integer:max_concurrent}")
```

`Workflow` represents CI/CD jobs with resource requirements:

```python
Workflow = model.Concept("Workflow", identify_by={"workflow_id": Integer})
Workflow.required_os = model.Property(f"{Workflow} has {String:required_os}")
Workflow.min_cpu = model.Property(f"{Workflow} has {Integer:min_cpu}")
Workflow.estimated_minutes = model.Property(
    f"{Workflow} has {Integer:estimated_minutes}"
)
```

`Compatibility` links workflows to runners that meet their OS and resource requirements. `Assignment` is the decision concept -- only compatible (workflow, runner) pairs exist:

```python
Compatibility = model.Concept(
    "Compatibility", identify_by={"workflow": Workflow, "runner": Runner}
)

Assignment = model.Concept(
    "Assignment", identify_by={"workflow": Workflow, "runner": Runner}
)
Assignment.x_assigned = model.Property(f"{Assignment} assigned {Float:x_assigned}")
model.define(
    Assignment.new(workflow=Compatibility.workflow, runner=Compatibility.runner)
)
```

### Define decision variables, constraints, and objective

Each assignment is a binary variable -- assign this workflow to this runner or not:

```python
problem.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=["assign", Assignment.workflow.name, Assignment.runner.name],
)
```

Two constraints enforce feasibility. First, each workflow must be assigned to exactly one runner:

```python
problem.satisfy(model.require(
    sum(AssignRef.x_assigned)
    .where(AssignRef.workflow == Workflow)
    .per(Workflow) == 1
))
```

Second, the number of workflows assigned to each runner cannot exceed its concurrency limit, scaled by the scenario multiplier:

```python
problem.satisfy(model.require(
    sum(AssignRef.x_assigned)
    .where(AssignRef.runner == Runner)
    .per(Runner) <= concurrency_multiplier * Runner.max_concurrent
))
```

The objective minimizes total pipeline cost -- the sum of (runner cost per minute * job duration) across all assignments:

```python
problem.minimize(
    sum(
        Assignment.x_assigned
        * Assignment.runner.cost_per_minute
        * Assignment.workflow.estimated_minutes
    )
)
```

### Solve with scenario analysis

The script loops over three concurrency multipliers (0.5x, 1.0x, 1.5x), creating a fresh Problem for each. This reveals the cost of operating at reduced capacity (maintenance window) versus full or burst capacity:

```python
SCENARIO_VALUES = [0.5, 1.0, 1.5]

for multiplier in SCENARIO_VALUES:
    result = solve_allocation(multiplier)
```

After all scenarios, a summary table compares status and cost:

```python
for r in scenario_results:
    print(f"  {SCENARIO_PARAM}={r['scenario']}: "
          f"{r['status']}, cost=${r['objective']:.2f}")
```

## Customize this template

- **Add runners**: Extend `runners.csv` with new runner types (e.g., GPU runners for ML workflows).
- **Adjust concurrency**: Change `max_concurrent` in `runners.csv` or modify `SCENARIO_VALUES` to test different capacity levels.
- **Weight by priority**: Add a priority column to `workflows.csv` and incorporate it into the objective to prefer assigning critical jobs to faster runners.
- **Time windows**: Add time slot concepts to model scheduling across discrete time periods, not just assignment.
- **Real data**: Replace CSVs with queries against your CI/CD platform's API or data warehouse.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The concurrency limits are too tight for the number of workflows. Increase `max_concurrent` in `runners.csv`, reduce the number of workflows, or increase the concurrency multiplier in `SCENARIO_VALUES`.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>All workflows assigned to the same runner</summary>

This is expected if one runner is cheapest and has enough concurrency. Check that `compatibility.csv` correctly restricts which runners can handle each workflow's OS and resource requirements.
</details>
