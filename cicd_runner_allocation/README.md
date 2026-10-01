---
title: "CI/CD Runner Allocation"
description: "Assign continuous-integration and continuous-delivery (CI/CD) workflow jobs to the cheapest compatible runner within concurrency limits. Sweep capacity scenarios and diagnose an infeasible maintenance outage with conflict analysis."
featured: false
experience_level: intermediate
industry: "Technology & Telecom"
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

## What this template is for

Every merge kicks off a pipeline of build, test, and deploy jobs, and each job can run on several kinds of runner — hosted Linux, Windows, or macOS machines, or self-hosted hardware — that differ in cost, capacity, and what they can execute. Picking the cheapest runner for each job while staying inside each runner's concurrency limit is a real budgeting problem for any platform team, and it gets harder the moment a runner goes offline for maintenance. This template answers two questions an operator actually asks: what is the least-cost way to schedule this pipeline, and when a runner outage makes the pipeline unschedulable, exactly which cap or runner is to blame.

**It uses RelationalAI's prescriptive reasoner to solve the assignment as a cost-minimizing optimization, then reruns it across capacity scenarios and, on an infeasible outage, reads back the minimal set of rules that cannot all hold at once — so the answer is not just "infeasible" but a named list of stranded jobs and the one binding runner cap.**

## Who this is for

- DevOps and platform engineers optimizing CI/CD runner costs or sizing a runner fleet for GitHub Actions or a similar CI system.
- Operations researchers exploring resource-assignment optimization and infeasibility diagnosis in RelationalAI.
- **Assumed knowledge**: comfortable reading Python; the CI/CD, optimization, and conflict-analysis terms are explained as they come up. No prior RelationalAI experience is required to run it.

## What you'll build

- A least-cost assignment plan mapping each workflow job to a compatible runner, built with the **prescriptive reasoner** as binary decision variables under an exactly-one-runner-per-job rule.
- Per-runner concurrency constraints scaled by a scenario parameter, so the same model answers "what does half capacity cost?" or "what does burst capacity save?"
- A scenario comparison across concurrency multipliers (half, full, and burst capacity) showing how pipeline cost moves with runner capacity.
- A maintenance-outage diagnosis that requests an **irreducible infeasible subsystem (IIS)** and reads it back by entity key — the stranded jobs and the binding runner cap — so an operator knows precisely which cap to raise or which runner to restore.

## What's included

- **Model**: three source concepts (`Runner`, `Workflow`, `Compatibility`) plus an `Assignment` decision concept, with a binary assignment variable, an assign-one-runner rule, a per-runner concurrency rule, and a cost-minimizing objective.
- **Runner**: `cicd_runner_allocation.py` — a single Python script that runs the scenario sweep and the outage diagnosis end to end against a Snowflake-connected RAI account.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: 8 runner types, 20 workflow jobs, and their pre-computed compatibility pairs. See *Sample data* below.
- **Outputs**: per-scenario solver status, total pipeline cost, and the runner-to-workflow assignment table printed to stdout; then the outage diagnosis naming the stranded jobs and the binding concurrency cap.

## Prerequisites

### Access

- A Snowflake account with the RelationalAI Native App installed.
- A Snowflake user with permissions to access the RelationalAI Native App.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.11.0`).

## Quickstart

1. Download the template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/cicd_runner_allocation.zip
   unzip cicd_runner_allocation.zip
   cd cicd_runner_allocation
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create a virtual environment and activate it:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure credentials:

   ```bash
   rai init
   ```

5. Run the template end to end:

   ```bash
   python cicd_runner_allocation.py
   ```

6. Expected output (a few representative lines confirm a successful run):

   ```text
   Running scenario: concurrency_multiplier = 1.0
   --------------------------------------------------
     Status: OPTIMAL
     Total pipeline cost: $9.62

   ==================================================
   Scenario Analysis Summary
   ==================================================
     concurrency_multiplier=0.5: OPTIMAL, cost=$10.18
     concurrency_multiplier=1.0: OPTIMAL, cost=$9.62
     concurrency_multiplier=1.5: OPTIMAL, cost=$9.53

   ==================================================
   Maintenance outage: ubuntu-large, self-hosted-linux offline
   ==================================================
   • status: INFEASIBLE
   • conflict status: CONFLICT_FOUND

   Binding runner caps (concurrency rule in conflict):
          runner max_concurrent
   ubuntu-xlarge              5
   ```

   Equal-cost runners may be swapped between tied optima, and the IIS may name a different six of the seven stranded jobs; the statuses, costs, and the binding runner cap are stable. The full printout and a step-by-step walkthrough are in `runbook.md`.

## Template structure

```text
cicd_runner_allocation/
  cicd_runner_allocation.py       # Main script (scenario sweep + outage diagnosis)
  data/
    runners.csv                   # 8 runner types (specs, cost, concurrency cap)
    workflows.csv                 # 20 CI/CD jobs (requirements, duration)
    compatibility.csv             # pre-computed (workflow, runner) compatible pairs
  README.md                       # this file
  runbook.md                      # analyst-facing paste-testable walkthrough
  pyproject.toml                  # dependencies
```

**Start here**: run `python cicd_runner_allocation.py` for the full scenario sweep and outage diagnosis end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative — designed to teach the reasoning flow on a Snowflake-connected RAI account, not to match a specific team's CI fleet. The three CSVs load into the three source concepts described under *Model overview*.

- **`runners.csv`** (8 rows) — CI/CD runner types (hosted Linux, Windows, macOS, and self-hosted), each with CPU count, memory, operating system, per-minute cost, and a concurrency cap. `self-hosted-linux` is the cheapest at `$0.005/min`; `ubuntu-xlarge` is the only surviving high-CPU Linux runner in the outage scenario, with a concurrency cap of 5.
- **`workflows.csv`** (20 rows) — CI/CD jobs (builds, tests, deploys, and packaging) with a triggering event, required operating system, minimum CPU and memory, and an estimated duration in minutes. Seven jobs are high-CPU Linux jobs (`min_cpu` at least 4), the set that funnels onto one runner during the outage.
- **`compatibility.csv`** — pre-computed `(workflow_id, runner_id)` pairs, one per runner that meets a workflow's operating-system and resource requirements. These pairs define the assignment decision space: only compatible pairs can be chosen.

## Model overview

The model has three source concepts loaded from the CSVs plus one decision concept derived from them.

- **Key entities**: `Runner`, `Workflow`, `Compatibility` (the eligible pairings), and `Assignment` (the decision — one binary variable per compatible pair).
- **Primary identifiers**: integer `runner_id` on `Runner` and `workflow_id` on `Workflow`; `Compatibility` and `Assignment` are each identified by the composite `(workflow, runner)` pair.
- **Important invariants**: `cost_per_minute`, CPU, memory, durations, and concurrency caps are non-negative; each workflow is assigned to exactly one runner; each runner's assigned job count stays within its concurrency cap scaled by the scenario multiplier; assignment variables are binary.

`Compatibility` is a standalone relation, not a set of properties on `Runner` or `Workflow`: it enumerates which runners can execute which workflows (operating-system and resource match), and it seeds the `Assignment` decision space — `Assignment` is defined over exactly the `Compatibility` pairs.

For the full concept and property definitions, see `cicd_runner_allocation.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The script defines the source concepts, seeds the decision space, adds the constraints and objective, sweeps the capacity scenarios, and finally diagnoses a maintenance outage.

### Define concepts and load CSV data

The model defines three source concepts — `Runner` (runner types with resource specs and cost), `Workflow` (CI/CD jobs with resource requirements), and `Compatibility` (which runners can execute which workflows). `Assignment` is the decision concept, defined over exactly the compatible `(workflow, runner)` pairs.

### Define decision variables, constraints, and objective

Each assignment is a binary variable — assign this workflow to this runner or not. Two constraints enforce feasibility; each is captured as a handle, named per entity (a readable label), and declared with `keyed_by` — the entity key its conflict membership reads back through if the model turns out infeasible. First, each workflow must be assigned to exactly one runner. Second, the number of workflows assigned to each runner cannot exceed its concurrency limit, scaled by the scenario multiplier. The objective minimizes total pipeline cost — the sum of runner cost per minute times job duration across all assignments.

### Solve with scenario analysis

The script loops over three concurrency multipliers (0.5x, 1.0x, 1.5x), creating a fresh Problem for each. This reveals the cost of operating at reduced capacity (maintenance window) versus full or burst capacity.

At full capacity (1.0x), `self-hosted-linux` absorbs 8 of 20 jobs at `$0.005/min` — the cheapest runner. At half capacity (0.5x), its 4-job cap forces overflow to `ubuntu-large` and `ubuntu-22.04`, raising cost by 6%. Burst mode (1.5x) pushes 12 jobs to self-hosted, saving another `$0.09` by pulling four more low-CPU jobs off the pricier ubuntu runners (the high-CPU jobs already fit on self-hosted at 1.0x). How the cheap, low-CPU jobs split between the two equal-cost ubuntu runners is one of several tied optima — a different HiGHS build may place them differently at the same total cost. A summary table then compares status and cost across the scenarios.

### Diagnose a maintenance outage with conflict analysis

The final section models a maintenance outage: `ubuntu-large` and `self-hosted-linux` go offline (their assignments are dropped with a filter). Every high-CPU Linux job (`min_cpu` at least 4) is compatible only with runners in `{ubuntu-large, ubuntu-xlarge, self-hosted-linux}` (the two heaviest jobs with just the latter two), so with two of those three down, all seven funnel onto `ubuntu-xlarge` — whose concurrency cap of 5 cannot hold them. The solve requests a conflict diagnosis.

A `conflict_status` field gates whether an irreducible infeasible subsystem (IIS) is available: on `CONFLICT_FOUND` the script reads back the stranded jobs and binding cap; otherwise it reports the status rather than reading an IIS that is not there. (The template's own branch raises in that case, because its outage is infeasible by construction, but code where infeasibility is not guaranteed should report and move on.)

Each constraint's declared key gives it an entity back-pointer (`assign_one.workflow`, `conc.runner`), mirroring the variable's automatic back-pointer, so the conflict reads back as the actual stranded jobs and the binding runner cap, joined by key — no rule-name parsing.

The IIS is minimal: it names six of the seven high-CPU jobs (any six already exceed the cap of five, so which six is solver-dependent) plus the `ubuntu-xlarge` concurrency rule. To restore feasibility, relax one member — bring a runner back online or raise the cap. Because all seven jobs share the one survivor, lift the cap enough for all of them (or restore a runner) and re-solve to confirm; clearing a single job only resolves that one row of the conflict.

See `cicd_runner_allocation.py` for the implementation and `runbook.md` for the skill-driven reproduction.

> [!NOTE]
> Conflict analysis works for mixed-integer models like this one (unlike sensitivity analysis, which needs a linear or quadratic program). It requires no objective — it diagnoses feasibility. Request `conflict=True` on the solve whose infeasibility you want to explain — up front, or on a fresh build: a `Problem` already solved without it cannot add it on a re-solve.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column headers listed in *Sample data* (`runners.csv`, `workflows.csv`, `compatibility.csv`).
- `compatibility.csv` must hold one `(workflow_id, runner_id)` row per runner that can execute a workflow (operating-system and resource match). If a workflow has no compatible runner, it cannot be assigned and the model becomes infeasible — see *Troubleshooting*.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)` calls.

### Tune parameters

- **Concurrency scenarios** — `SCENARIO_VALUES` (default `[0.5, 1.0, 1.5]`) is the list of concurrency multipliers swept; each scales every runner's `max_concurrent`.
- **Per-runner caps** — change `max_concurrent` in `runners.csv` to model a different fleet size or capacity policy.
- **Solve budget** — the solve uses `time_limit_sec=60`; raise it for larger fleets.

### Extend the model

- **Add runners** — extend `runners.csv` with new runner types (for example, GPU runners for machine-learning workflows) and their compatibility rows.
- **Weight by priority** — add a priority column to `workflows.csv` and fold it into the objective to prefer assigning critical jobs to faster runners.
- **Model time windows** — add time-slot concepts to schedule across discrete time periods, not just assignment.

### Scale up / productionize

- Replace the `data/` CSV bundle with queries against your CI/CD platform's API or data warehouse.
- The model scales to whatever fits the prescriptive engine's solve budget; raise `time_limit_sec` and the concurrency caps together as the fleet grows.
- Pin dependencies (the template pins `relationalai == 1.11.0`) for reproducible runs across environments.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The concurrency limits are too tight for the number of workflows, or a workflow has no compatible runner. Rather than guess, request a conflict diagnosis — `solve(conflict=True)` returns the irreducible infeasible subsystem (the stranded jobs and the binding runner cap), as shown in the maintenance-outage section. Then increase `max_concurrent` for the named runner in `runners.csv`, reduce the number of workflows competing for it, or raise the concurrency multiplier.
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RelationalAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

<details>
<summary>All workflows assigned to the same runner</summary>

This is expected if one runner is cheapest and has enough concurrency. Check that `compatibility.csv` correctly restricts which runners can handle each workflow's operating-system and resource requirements.
</details>

## Learn more

### Core concepts

- [RelationalAI documentation](https://docs.relational.ai/) — concepts, properties, and the semantic model that this template builds on.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used here.
- [Conflict analysis (IIS)](https://docs.relational.ai/) — diagnosing infeasibility and reading back an irreducible infeasible subsystem by entity key.

### CLI / SDK guides

- [RelationalAI CLI and setup](https://docs.relational.ai/) — `rai init`, credentials, and connecting to your Snowflake account.

## Support

- File issues at the RelationalAI templates repository.
