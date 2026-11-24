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

- **Model**: three source concepts (`Runner`, `Workflow`, `Compatibility`) plus an `Assignment` decision concept, with a binary assignment variable, an assign-one-runner rule, a per-runner concurrency rule, and a cost-minimizing objective, in the `model/` package (`schema.py` declares the concepts, `source.py` loads the sample data and checks it, `reasoning.py` states one decision problem per concurrency scenario and one for the maintenance outage), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs the solves.
- **Query**: `queries/allocation_report.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the model itself.
- **Sample data**: 8 runner types, 20 workflow jobs, and their pre-computed compatibility pairs. See *Sample data* below.
- **Outputs**: per-scenario solver status, total pipeline cost, and the runner-to-workflow assignment table printed to stdout; then the outage diagnosis naming the stranded jobs and the binding concurrency cap.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.CICD_RUNNER_ALLOCATION_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.CICD_RUNNER_ALLOCATION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/cicd_runner_allocation.zip), unzip it, and enter the template directory:

   ```bash
   unzip cicd_runner_allocation.zip
   cd cicd_runner_allocation
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
       name: cicd_runner_allocation_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.CICD_RUNNER_ALLOCATION               # published views and tables
     identity:
       internal_schema: <DB>.CICD_RUNNER_ALLOCATION_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs one solve per concurrency scenario and one for the maintenance outage. Each refresh of the deployed model runs the solves again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.allocation_report
   ```

   ```text
   Running scenario: concurrency_multiplier = 0.5
   --------------------------------------------------

   Solve result:
   • status: OPTIMAL
   • objective: 10.175

     Status: OPTIMAL
     Total pipeline cost: $10.18

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (4 jobs): e2e-tests-chrome, integration-tests, nightly-build, performance-tests
       ubuntu-22.04 (3 jobs): deploy-production, release-notes, unit-tests-frontend
       ubuntu-large (3 jobs): build-mobile-android, docker-build, unit-tests-api
       ubuntu-latest (6 jobs): build-api, build-frontend, dependency-audit, deploy-staging, lint-and-format, security-scan
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.0
   --------------------------------------------------

   Solve result:
   • status: OPTIMAL
   • objective: 9.622

     Status: OPTIMAL
     Total pipeline cost: $9.62

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (8 jobs): build-api, build-mobile-android, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, unit-tests-api
       ubuntu-22.04 (7 jobs): build-frontend, dependency-audit, deploy-production, deploy-staging, lint-and-format, security-scan, unit-tests-frontend
       ubuntu-latest (1 jobs): release-notes
       windows-latest (1 jobs): windows-installer

   Running scenario: concurrency_multiplier = 1.5
   --------------------------------------------------

   Solve result:
   • status: OPTIMAL
   • objective: 9.526

     Status: OPTIMAL
     Total pipeline cost: $9.53

     Assignments:
       macos-large (1 jobs): ios-testflight
       macos-latest (2 jobs): build-mobile-ios, e2e-tests-safari
       self-hosted-linux (12 jobs): build-api, build-frontend, build-mobile-android, dependency-audit, docker-build, e2e-tests-chrome, integration-tests, nightly-build, performance-tests, security-scan, unit-tests-api, unit-tests-frontend
       ubuntu-22.04 (3 jobs): deploy-staging, lint-and-format, release-notes
       ubuntu-latest (1 jobs): deploy-production
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

   Stranded jobs (assign-one rule in conflict):
               workflow
   build-mobile-android
           docker-build
       e2e-tests-chrome
      integration-tests
          nightly-build
      performance-tests
         unit-tests-api

   Binding runner caps (concurrency rule in conflict):
          runner  max_concurrent
   ubuntu-xlarge               5

   To restore feasibility, relax one member of the conflict: bring ubuntu-large or self-hosted-linux back online, or raise ubuntu-xlarge's concurrency cap. All seven high-CPU jobs share the one survivor, so lift the cap (or restore a runner) enough for all of them and re-deploy to confirm -- clearing a single stranded job only resolves that row of the conflict.
   ```

   Equal-cost runners may be swapped between tied optima; the statuses, costs, and conflict are stable. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.CICD_RUNNER_ALLOCATION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
.
├── README.md                  # this file
├── runbook.md                 # step-by-step analyst walkthrough
├── pyproject.toml             # dependencies
├── model/
│   ├── __init__.py            # exports of the deployed model
│   ├── schema.py              # concepts and properties
│   ├── source.py              # sample data and the outage's runner check
│   └── reasoning.py           # one solve per scenario, the outage solve and its conflict
├── queries/
│   └── allocation_report.py   # report from the deployed model
└── data/
    ├── runners.csv            # 8 runner types (specs, cost, concurrency cap)
    ├── workflows.csv          # 20 CI/CD jobs (requirements, duration)
    └── compatibility.csv      # pre-computed (workflow, runner) compatible pairs
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.allocation_report` for the full scenario sweep and outage diagnosis end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

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

For the full concept and property definitions, see `model/schema.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The model defines the source concepts, seeds the decision space, adds the constraints and objective, declares one problem per capacity scenario, and finally diagnoses a maintenance outage.

### Define concepts and load CSV data

The model defines three source concepts — `Runner` (runner types with resource specs and cost), `Workflow` (CI/CD jobs with resource requirements), and `Compatibility` (which runners can execute which workflows). `Assignment` is the decision concept, defined over exactly the compatible `(workflow, runner)` pairs.

### Define decision variables, constraints, and objective

Each assignment is a binary variable — assign this workflow to this runner or not. Two constraints enforce feasibility; each is captured as a handle, named per entity (a readable label), and declared with `keyed_by` — the entity key its conflict membership reads back through if the model turns out infeasible. First, each workflow must be assigned to exactly one runner. Second, the number of workflows assigned to each runner cannot exceed its concurrency limit, scaled by the scenario multiplier. The objective minimizes total pipeline cost — the sum of runner cost per minute times job duration across all assignments.

### Solve with scenario analysis

The model declares one Problem per concurrency multiplier (0.5x, 1.0x, 1.5x), each with its own name, so an infeasible scenario leaves the others solved; each refresh of the deployed model runs all of them. This reveals the cost of operating at reduced capacity (maintenance window) versus full or burst capacity.

At full capacity (1.0x), `self-hosted-linux` absorbs 8 of 20 jobs at `$0.005/min` — the cheapest runner. At half capacity (0.5x), its 4-job cap forces overflow to `ubuntu-large` and `ubuntu-22.04`, raising cost by 6%. Burst mode (1.5x) pushes 12 jobs to self-hosted, saving another `$0.09` by pulling four more low-CPU jobs off the pricier ubuntu runners (the high-CPU jobs already fit on self-hosted at 1.0x). How the cheap, low-CPU jobs split between the two equal-cost ubuntu runners is one of several tied optima — a different HiGHS build may place them differently at the same total cost. A summary table then compares status and cost across the scenarios.

### Diagnose a maintenance outage with conflict analysis

The final section models a maintenance outage: `ubuntu-large` and `self-hosted-linux` go offline (their assignments are dropped with a filter). Every high-CPU Linux job (`min_cpu` at least 4) is compatible only with runners in `{ubuntu-large, ubuntu-xlarge, self-hosted-linux}` (the two heaviest jobs with just the latter two), so with two of those three down, all seven funnel onto `ubuntu-xlarge` — whose concurrency cap of 5 cannot hold them. Its Problem is configured with `conflict=True`, so its solve also computes a conflict diagnosis.

The diagnosis is an irreducible infeasible subsystem (IIS). `in_conflict` is a predicate on each constraint instance, true when the solver reports that instance in the IIS, and the model publishes the members as two relationships the report selects: the stranded jobs and the binding runner caps. When the solver finds no IIS (the model is feasible, or the solver build has no conflict support), both tables print empty.

Each constraint's declared key gives it an entity back-pointer (`assign_one.workflow`, `conc.runner`), mirroring the variable's automatic back-pointer, so the conflict reads back as the actual stranded jobs and the binding runner cap, joined by key — no rule-name parsing.

The IIS is minimal: it names six of the seven high-CPU jobs (any six already exceed the cap of five, so which six is solver-dependent) plus the `ubuntu-xlarge` concurrency rule. To restore feasibility, relax one member — bring a runner back online or raise the cap. Because all seven jobs share the one survivor, lift the cap enough for all of them (or restore a runner) and redeploy to confirm; clearing a single job only resolves that one row of the conflict.

See `model/reasoning.py` and `queries/allocation_report.py` for the implementation and `runbook.md` for the skill-driven reproduction.

> [!NOTE]
> Conflict analysis works for mixed-integer models like this one (unlike sensitivity analysis, which needs a linear or quadratic program). It requires no objective — it diagnoses feasibility. Pass `conflict=True` to the `configure(...)` of the Problem whose infeasibility you want to explain.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own; keep the column headers listed in *Sample data* (`runners.csv`, `workflows.csv`, `compatibility.csv`).
- `compatibility.csv` must hold one `(workflow_id, runner_id)` row per runner that can execute a workflow (operating-system and resource match). If a workflow has no compatible runner, it cannot be assigned and the model becomes infeasible — see *Troubleshooting*.
- For Snowflake-backed runs, swap the `read_csv(...)` calls in `model/source.py` for `model.data(snowflake_table)` calls.

### Tune parameters

- **Concurrency scenarios** — `SCENARIO_VALUES` (default `[0.5, 1.0, 1.5]`) is the list of concurrency multipliers swept; each scales every runner's `max_concurrent`.
- **Per-runner caps** — change `max_concurrent` in `runners.csv` to model a different fleet size or capacity policy.
- **Solve budget** — each `problem.configure(...)` in `model/reasoning.py` uses `time_limit_sec=60`; raise it for larger fleets.

### Extend the model

- **Add runners** — extend `runners.csv` with new runner types (for example, GPU runners for machine-learning workflows) and their compatibility rows.
- **Weight by priority** — add a priority column to `workflows.csv` and fold it into the objective to prefer assigning critical jobs to faster runners.
- **Model time windows** — add time-slot concepts to schedule across discrete time periods, not just assignment.

### Scale up / productionize

- Replace the `data/` CSV bundle with queries against your CI/CD platform's API or data warehouse.
- The model scales to whatever fits the prescriptive engine's solve budget; raise `time_limit_sec` and the concurrency caps together as the fleet grows.
- Pin dependencies (the template pins `relationalai == 2.3.0`) for reproducible runs across environments.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

The concurrency limits are too tight for the number of workflows, or a workflow has no compatible runner. Rather than guess, request a conflict diagnosis — `problem.configure(..., conflict=True)` makes the solve return the irreducible infeasible subsystem (the stranded jobs and the binding runner cap), as shown in the maintenance-outage section. Then increase `max_concurrent` for the named runner in `runners.csv`, reduce the number of workflows competing for it, or raise the concurrency multiplier.
</details>

<details>
<summary>Connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
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
