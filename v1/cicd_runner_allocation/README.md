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
  - Conflict Analysis
  - CI/CD
  - HiGHS
---

# CI/CD Runner Allocation

## What this template is for

This template uses **prescriptive reasoning (optimization)** to assign CI/CD workflow jobs to runner types at minimum cost. Given a set of runners (GitHub Actions runner types with CPU, memory, OS, and per-minute cost) and workflow jobs (with resource requirements and estimated durations), the optimizer assigns each job to the cheapest compatible runner while respecting per-runner concurrency limits.

The template also demonstrates **scenario analysis** by sweeping concurrency multipliers (0.5x, 1.0x, 1.5x) to show how pipeline cost changes under capacity constraints -- useful for evaluating maintenance windows, cost reduction, or burst provisioning.

Finally, it shows **conflict analysis (infeasibility diagnosis)**. A maintenance outage takes two well-connected Linux runners offline, which funnels every high-CPU Linux job onto the one surviving large runner -- whose concurrency cap cannot hold them all, so the schedule is impossible. Rather than just reporting "infeasible," the outage solve requests `solve(conflict=True)`, which returns an **irreducible infeasible subsystem (IIS)**: the minimal set of rules that cannot all hold at once. The diagnosis names the *stranded jobs* and the *binding runner cap*, so an operator knows exactly which cap to raise or which runner to restore.

## Who this is for

- DevOps engineers optimizing CI/CD runner costs
- Platform teams sizing runner fleets for GitHub Actions or similar CI systems
- Anyone learning resource assignment optimization with RelationalAI

## What you'll build

- A binary assignment model that maps each workflow job to a compatible runner type
- Per-runner concurrency constraints scaled by a scenario parameter
- Cost minimization objective (runner cost_per_minute * job estimated_minutes)
- Scenario comparison showing cost impact of halving or increasing runner capacity
- A maintenance-outage diagnosis that reads the IIS (stranded jobs + binding cap) back by entity key

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
   curl -O https://docs.relational.ai/templates/zips/v1/cicd_runner_allocation.zip
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

6. Expected output (representative — equal-cost runners may be swapped between tied optima, and the IIS may name a different six of the seven stranded jobs; the statuses, costs, and binding runner cap are stable):
   ```text
   Running scenario: concurrency_multiplier = 0.5
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $10.18

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (4 jobs): e2e-tests-chrome, integration-tests, nightly-build, performance-tests
       ubuntu-22.04 (4 jobs): build-api, build-frontend, lint-and-format, release-notes
       ubuntu-large (3 jobs): build-mobile-android, docker-build, unit-tests-api
       ubuntu-latest (5 jobs): dependency-audit, deploy-production, deploy-staging, security-scan, unit-tests-frontend
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.0
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $9.62

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (8 jobs): build-api, build-mobile-android, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, unit-tests-api
       ubuntu-22.04 (3 jobs): build-frontend, lint-and-format, release-notes
       ubuntu-latest (5 jobs): dependency-audit, deploy-production, deploy-staging, security-scan, unit-tests-frontend
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.5
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $9.53

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (12 jobs): build-api, build-frontend, build-mobile-android, dependency-audit, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, security-scan, unit-tests-api, unit-tests-frontend
       ubuntu-22.04 (3 jobs): deploy-production, lint-and-format, release-notes
       ubuntu-latest (1 jobs): deploy-staging
       windows-latest (1 jobs): windows-installer

   ==================================================
   Scenario Analysis Summary
   ==================================================
     concurrency_multiplier=0.5: OPTIMAL, cost=$10.18
     concurrency_multiplier=1.0: OPTIMAL, cost=$9.62
     concurrency_multiplier=1.5: OPTIMAL, cost=$9.53

   ==================================================
   Maintenance outage: ubuntu-large, self-hosted-linux offline
   ==================================================
   Solve result:
   • status: INFEASIBLE
   • primal status: NO_SOLUTION
   • dual status: INFEASIBILITY_CERTIFICATE
   • conflict status: CONFLICT_FOUND
   ...

   Stranded jobs (assign-one rule in conflict):
               workflow
   build-mobile-android
           docker-build
       e2e-tests-chrome
      integration-tests
      performance-tests
         unit-tests-api

   Binding runner caps (concurrency rule in conflict):
          runner max_concurrent
   ubuntu-xlarge              5

   To restore feasibility, relax one member of the conflict: bring ubuntu-large or
   self-hosted-linux back online, or raise ubuntu-xlarge's concurrency cap. ...
   ```

   At full capacity (1.0x), self-hosted-linux absorbs 8 of 20 jobs at
   $0.005/min -- the cheapest runner. At half capacity (0.5x), its 4-job
   cap forces overflow to ubuntu-large and ubuntu-22.04, raising cost by
   6%. Burst mode (1.5x) pushes 12 jobs to self-hosted, saving another
   $0.09 by keeping the high-CPU jobs off the pricier ubuntu-large and ubuntu-xlarge runners. (How the cheap,
   low-CPU jobs split between the two equal-cost ubuntu runners is one of several
   tied optima -- a different HiGHS build may place them differently at the same
   total cost.)

   **The maintenance outage** is infeasible: with `ubuntu-large` and
   `self-hosted-linux` offline, the seven high-CPU Linux jobs can only run on
   `ubuntu-xlarge` (cap 5). `solve(conflict=True)` returns the IIS -- six of the
   seven stranded jobs plus the `ubuntu-xlarge` concurrency rule (which six is
   solver-dependent, since any six already exceed the cap). The diagnosis points an
   operator straight at the fix: restore a runner or raise that one cap.

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
Runner.memory_gb = model.Property(f"{Runner} has {Integer:memory_gb}")
Runner.cost_per_minute = model.Property(f"{Runner} has {Float:cost_per_minute}")
Runner.max_concurrent = model.Property(f"{Runner} has {Integer:max_concurrent}")
```

`Workflow` represents CI/CD jobs with resource requirements:

```python
Workflow = model.Concept("Workflow", identify_by={"workflow_id": Integer})
Workflow.name = model.Property(f"{Workflow} has {String:workflow_name}")
Workflow.event = model.Property(f"{Workflow} has {String:workflow_event}")
Workflow.required_os = model.Property(f"{Workflow} has {String:required_os}")
Workflow.min_cpu = model.Property(f"{Workflow} has {Integer:min_cpu}")
Workflow.min_memory_gb = model.Property(f"{Workflow} has {Integer:min_memory_gb}")
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

Two constraints enforce feasibility. Each is **captured as a handle**, **named per entity** (a readable label), and declared with **`keyed_by`** -- the entity key its conflict membership reads back through if the model turns out infeasible. First, each workflow must be assigned to exactly one runner:

```python
assign_one = problem.satisfy(
    model.require(
        sum(AssignRef.x_assigned).where(AssignRef.workflow == Workflow).per(Workflow) == 1
    ),
    name=["assign_one", Workflow.name],
    keyed_by={"workflow": Workflow},
)
```

Second, the number of workflows assigned to each runner cannot exceed its concurrency limit, scaled by the scenario multiplier:

```python
conc = problem.satisfy(
    model.require(
        sum(AssignRef.x_assigned).where(AssignRef.runner == Runner).per(Runner)
        <= concurrency_multiplier * Runner.max_concurrent
    ),
    name=["concurrency", Runner.name],
    keyed_by={"runner": Runner},
)
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
    alloc = solve_allocation(multiplier)
```

After all scenarios, a summary table compares status and cost:

```python
for r in scenario_results:
    print(f"  {SCENARIO_PARAM}={r['scenario']}: "
          f"{r['status']}, cost=${r['objective']:.2f}")
```

### Diagnose a maintenance outage with conflict analysis

The final section models a maintenance outage: `ubuntu-large` and `self-hosted-linux` go offline (their assignments are dropped with a `where=` filter). Every high-CPU Linux job (`min_cpu >= 4`) is compatible only with runners in `{ubuntu-large, ubuntu-xlarge, self-hosted-linux}` (the two heaviest jobs with just the latter two), so with two of those three down, all seven funnel onto `ubuntu-xlarge` -- whose concurrency cap of 5 cannot hold them. The solve requests a conflict diagnosis:

```python
outage = solve_allocation(1.0, offline_runners=["ubuntu-large", "self-hosted-linux"], conflict=True)

assert outage.si.conflict is True
assert outage.si.termination_status in ("INFEASIBLE", "INFEASIBLE_OR_UNBOUNDED")

# conflict_status gates whether an IIS is available -- dispatch on it.
if outage.si.conflict_status == "CONFLICT_FOUND":
    ...  # read the stranded jobs and the binding cap (below)
else:
    # NO_CONFLICT_EXISTS (the model was feasible) or NOT_SUPPORTED / FAILED (this solver
    # build produced no IIS, e.g. needs HiGHS >= 1.13) -- report the status, don't read it.
    print(f"No IIS to inspect: {outage.si.conflict_status}")
```

(The template's own `else` branch raises instead of printing: its outage is infeasible by construction, so a missing IIS there is a regression. The `print` form above is the one to copy when infeasibility is not guaranteed.)

`in_conflict` is a bare predicate on each constraint instance -- true when the solver reports that instance in the conflict (it collapses the solver's `IN_CONFLICT` and `MAYBE_IN_CONFLICT` into one membership). Each constraint's declared key gives it an **entity back-pointer** (`assign_one.workflow`, `conc.runner`), mirroring the variable's automatic back-pointer, so the conflict reads back as the actual stranded jobs and the binding runner cap, joined by KEY -- no rule-name parsing:

```python
# Stranded jobs (their assign-one rule is in the conflict):
model.select(outage.assign_one.workflow.name).where(outage.assign_one.in_conflict).inspect()
# The binding runner cap (its concurrency rule is in the conflict):
model.select(outage.conc.runner.name, outage.conc.runner.max_concurrent).where(
    outage.conc.in_conflict
).inspect()
```

The IIS is minimal: it names **six of the seven** high-CPU jobs (any six already exceed the cap of five, so which six is solver-dependent) plus the `ubuntu-xlarge` concurrency rule. To restore feasibility, relax one member -- bring a runner back online or raise the cap. Because all seven jobs share the one survivor, lift the cap enough for all of them (or restore a runner) and re-solve to confirm; clearing a single job only resolves that one row of the conflict.

> [!NOTE]
> Conflict analysis works for mixed-integer models like this one (unlike sensitivity analysis, which needs an LP/QP). It requires no objective -- it diagnoses feasibility. Request `conflict=True` on the solve whose infeasibility you want to explain.

## Customize this template

- **Add runners**: Extend `runners.csv` with new runner types (e.g., GPU runners for ML workflows).
- **Adjust concurrency**: Change `max_concurrent` in `runners.csv` or modify `SCENARIO_VALUES` to test different capacity levels.
- **Weight by priority**: Add a priority column to `workflows.csv` and incorporate it into the objective to prefer assigning critical jobs to faster runners.
- **Time windows**: Add time slot concepts to model scheduling across discrete time periods, not just assignment.
- **Real data**: Replace CSVs with queries against your CI/CD platform's API or data warehouse.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The concurrency limits are too tight for the number of workflows. Rather than guess, request a conflict diagnosis -- `solve(conflict=True)` returns the irreducible infeasible subsystem (the stranded jobs and the binding runner cap), as shown in the maintenance-outage section. Then increase `max_concurrent` for the named runner in `runners.csv`, reduce the number of workflows competing for it, or raise the concurrency multiplier.
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
