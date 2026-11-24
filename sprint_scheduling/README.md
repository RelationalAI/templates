---
title: "Sprint Scheduling"
description: "Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. Uses mixed-integer programming (MIP)."
featured: false
experience_level: intermediate
industry: "Technology & Telecom"
reasoning_types:
  - Prescriptive
tags:
  - Assignment
  - Scheduling
  - Mixed-Integer Programming (MIP)
  - Temporal Filtering
---

## What this template is for

Software development teams need to decide which developer works on which issue in which sprint. Manually balancing priorities, story points, skill requirements, and capacity across multiple sprints is error-prone and time-consuming, especially as the backlog grows. An optimization model can produce an assignment plan that minimizes delay on high-priority work while keeping every developer within their capacity.

This template assigns 30 backlog issues to 8 developers across 4 two-week sprints. It demonstrates how to filter issues by epoch timestamp to scope the backlog to a planning horizon, map epoch-based creation dates to categorical sprint periods, and build a binary assignment optimization that respects developer capacity and team skill constraints.

**Prescriptive** reasoning is well suited here because the problem has combinatorial structure -- each issue must go to exactly one developer in one sprint, developers have capacity limits, and only developers with matching team skills can take on an issue. The solver explores the full space of valid assignments to find the schedule that minimizes weighted completion time, prioritizing high-urgency issues into earlier sprints.

## Who this is for

- **Intermediate users** familiar with mixed-integer programming concepts (binary variables, assignment constraints)
- **Engineering managers** looking to automate sprint planning
- **Project managers** balancing team workloads across multiple sprints
- **Data scientists** working with epoch-timestamped event data who need temporal filtering patterns

## What you'll build

- A sprint assignment plan that places each in-scope issue with exactly one developer in one sprint, minimizing weighted completion time within capacity and skill limits, produced by **prescriptive reasoning** (a mixed-integer program).
- An `Assignment` decision concept whose binary variables span only the valid (developer, issue, sprint) combinations, pruned by an epoch-based temporal filter and skill-matching `.where()` clauses.
- A scenario comparison across capacity-multiplier levels (0.35, 0.5, 1.0), showing how reduced team capacity moves the objective and tips the problem into infeasibility.
- Per-scenario stdout: solve status, objective value, planning-horizon summary, and the assignment table.

Built using **prescriptive reasoning** (mixed-integer programming solved with HiGHS), with epoch-based temporal filtering to scope the backlog.

## What's included

- **Model**: developers, sprints, issues, and skill mappings as concepts, plus a cross-product `Assignment` decision concept with binary assignment variables, capacity and once-per-issue constraints, and a weighted-completion-time objective, in the `model/` package (`schema.py` declares the concepts, `source.py` loads the sample data and applies the planning horizon, `reasoning.py` states one decision problem per capacity scenario), which `rai models deploy --path model` deploys to your Snowflake account, where each refresh runs the solves.
- **Query**: `queries/sprint_plan.py`, which prints the report from the deployed model.
- **Runbook**: `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: four CSVs under `data/` describing 8 developers, 4 sprints, 30 backlog issues, and developer-team skills. See *Sample data* below.
- **Outputs**: per-scenario solve result (status and objective), planning-horizon summary, and assignment table printed to stdout, plus a scenario-analysis summary.

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
CREATE SCHEMA IF NOT EXISTS <DB>.SPRINT_SCHEDULING_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.SPRINT_SCHEDULING_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/sprint_scheduling.zip), unzip it, and enter the template directory:

   ```bash
   unzip sprint_scheduling.zip
   cd sprint_scheduling
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
       name: sprint_scheduling_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SPRINT_SCHEDULING               # published views and tables
     identity:
       internal_schema: <DB>.SPRINT_SCHEDULING_META      # solver inputs, results, refresh procedures
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

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs one solve per capacity scenario. Each refresh of the deployed model runs the solves again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.sprint_plan
   ```

   ```text
   Running scenario: capacity_multiplier = 0.35

   Solve result:
   • status: INFEASIBLE
     Status: INFEASIBLE — skipping results

   Running scenario: capacity_multiplier = 0.5

   Solve result:
   • status: OPTIMAL
   • objective: 112.0

     Status: OPTIMAL, Objective: 112.0
     Planning horizon: 2024-10-01 to 2024-11-26
     Issues in scope: 25 (of 30 total)

     Assignments:
      issue developer   sprint
   PROJ-106     Alice Sprint 1
   PROJ-107     Carol Sprint 1
   PROJ-108     Frank Sprint 1
   PROJ-109       Bob Sprint 1
   PROJ-110      Dave Sprint 1
   PROJ-111      Hank Sprint 1
   ...

   Running scenario: capacity_multiplier = 1.0

   Solve result:
   • status: OPTIMAL
   • objective: 112.0

     Status: OPTIMAL, Objective: 112.0
     Planning horizon: 2024-10-01 to 2024-11-26
     Issues in scope: 25 (of 30 total)

     Assignments:
      issue developer   sprint
   PROJ-106       Bob Sprint 1
   PROJ-107      Dave Sprint 1
   PROJ-108     Frank Sprint 1
   PROJ-109       Bob Sprint 1
   PROJ-110      Dave Sprint 1
   PROJ-111     Frank Sprint 1
   ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     capacity_multiplier=0.35: INFEASIBLE, obj=N/A
     capacity_multiplier=0.5: OPTIMAL, obj=112.0
     capacity_multiplier=1.0: OPTIMAL, obj=112.0
   ```

   At 35% capacity the problem is infeasible -- not enough hours to schedule
   all in-scope issues. At 50% and 100% capacity the solver finds the same
   optimal objective (112.0), meaning half capacity is sufficient to schedule
   all 25 issues within the 4-sprint horizon. See `runbook.md` for the step-by-step walkthrough.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.SPRINT_SCHEDULING_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
├── README.md              # this file
├── runbook.md             # step-by-step analyst walkthrough
├── pyproject.toml         # dependencies
├── model/
│   ├── __init__.py        # exports of the deployed model
│   ├── schema.py          # concepts and properties
│   ├── source.py          # sample data, planning horizon, epoch filter
│   └── reasoning.py       # assignment domain, constraints, objective, one solve per scenario
├── queries/
│   └── sprint_plan.py     # report from the deployed model
└── data/
    ├── developers.csv     # 8 developers with team and per-sprint capacity
    ├── sprints.csv        # 4 two-week sprints with epoch start/end dates
    ├── issues.csv         # 30 backlog issues with epoch created_at, priority, team
    └── skills.csv         # developer-team skill mappings
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.sprint_plan` for the full load, model, and capacity-scenario sweep end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative -- a small backlog sized to teach the assignment and temporal-filtering patterns, not to mirror a specific team's tracker.

- **`developers.csv`** (8 rows) -- developers with a `team` and `capacity_points_per_sprint` (14-20 points each).
- **`sprints.csv`** (4 rows) -- two-week sprints, each with a `number` and Unix-epoch `startdate` / `enddate`.
- **`issues.csv`** (30 rows) -- backlog issues with `story_points`, `priority` (1 = most urgent), `team`, and a Unix-epoch `created_at`. Raw data spans September-November 2024; the planning-horizon filter keeps the 25 issues created within the window.
- **`skills.csv`** -- which teams each developer can work on. Most developers cover one team; Grace and Hank carry cross-team skills.

## Model overview

The model has four source concepts loaded from CSV, plus a derived `Assignment` decision concept that forms the optimizer's search space. All identifiers are integer keys except the composite `Assignment`, which is identified by its three linked entities.

- **Key entities**: `Developer` — an engineer with a team affiliation and a per-sprint story-point capacity; `Sprint` — a two-week planning period with epoch boundaries; `Issue` — a backlog item to schedule; `Skill` — a developer-team capability row; and the decision concept `Assignment` — a valid (developer, issue, sprint) placement.
- **Primary identifiers**: integer `id` on `Developer`, `Sprint`, `Issue`, and `Skill`; `Assignment` is identified by its `(developer, issue, sprint)` triple.
- **Important invariants**: `story_points`, `priority`, and `capacity_points_per_sprint` are positive integers; each issue is assigned exactly once; a developer's assigned story points per sprint stay within capacity (scaled by the scenario's `capacity_multiplier`); a sprint can only host issues whose target sprint is at or before it.

For the full concept and property definitions, see `model/schema.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV inputs → epoch filter → target-sprint mapping → assignment domain → constraints + objective → solve → results
```

**1. Epoch filtering -- scope the backlog to the planning horizon.** Issues carry a `created_at` column in Unix epoch seconds. The model converts the planning-horizon boundaries to epochs and keeps only issues created within the window; issues created before or after are excluded from scheduling.

**2. Epoch-to-categorical-period mapping -- assign target sprints.** Each in-scope issue is mapped to its earliest eligible sprint based on when it was created. An issue created during Sprint 2 cannot be scheduled into Sprint 1 -- only Sprint 2 or later.

**3. Assignment domain with skill constraints.** The `Assignment` decision concept is a cross-product of developers, issues, and sprints, pruned to valid placements only: the developer must have the matching team skill, and the sprint must be at or after the issue's target sprint. Pruning up front keeps the search space tractable by creating variables only where a valid assignment could exist.

**4. Binary assignment variables and constraints.** Each valid placement gets a binary variable (1 = assigned). Two constraints govern the solve: each issue is assigned exactly once, and each developer's assigned story points per sprint stay within capacity scaled by the scenario's `capacity_multiplier`.

**5. Weighted completion time objective.** The objective minimizes a weighted sum where higher-priority issues (lower priority number) cost more when placed in later sprints -- a priority-1 issue in Sprint 4 costs `(4-1+1) * 4 = 12`, a priority-3 issue in Sprint 4 costs `(4-3+1) * 4 = 8`. This pushes the most urgent work into the earliest sprints.

For the implementation, see `model/reasoning.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the four CSVs in `data/` with your own, keeping the column names listed in *Sample data* above. `developers.csv`, `sprints.csv`, `issues.csv`, and `skills.csv` each map directly to a concept.
- `sprints.csv` and `issues.csv` use Unix epoch seconds for dates; convert your date strings to epochs before loading, or adapt the epoch-mapping helper.
- Make sure every team present in `issues.csv` has at least one skilled developer in `skills.csv`, or those issues cannot be assigned.

### Tune parameters

- **Planning horizon** -- edit `planning_start` and `planning_end` in `model/source.py` to include more or fewer sprints, and add matching rows to `sprints.csv`.
- **Capacity** -- modify `capacity_points_per_sprint` in `developers.csv`, or edit `SCENARIO_VALUES` in `model/reasoning.py` to sweep different `capacity_multiplier` levels (default `[0.35, 0.5, 1.0]`).
- **Priority scheme** -- adjust `max_priority` and the weight formula in the objective in `model/reasoning.py` to match your team's priority scale.

### Extend the model

- **Add cross-team skills** -- append rows to `skills.csv` to let developers work on issues outside their primary team (Grace and Hank already carry cross-team skills).
- **Add sprint-specific constraints** -- for example, require that certain issues finish by a given sprint using additional `.where()` clauses on the `Assignment` domain.

### Scale up / productionize

- The assignment domain grows with developers x issues x sprints; the skill and target-sprint `.where()` filters keep it tractable by only creating variables where a valid placement exists.
- Pin the `relationalai` SDK version (see *Prerequisites*) for reproducible solves, and swap the CSV loads for `model.data(snowflake_table)` calls to run against live backlog data.

## Troubleshooting

<details>
<summary>ModuleNotFoundError: No module named 'relationalai'</summary>

Make sure you have activated your virtual environment and installed dependencies:

```bash
source .venv/bin/activate
python -m pip install .
```
</details>

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that total developer capacity across all sprints is sufficient to cover the total story points in the backlog. With the default data, 8 developers with 14-20 points each across 4 sprints provide ample capacity for 30 issues. If you have added issues or reduced capacity, try increasing `capacity_multiplier` or adding more sprints.
</details>

<details>
<summary>Some issues are not assigned</summary>

Every issue must have at least one developer with a matching team skill. Verify that `skills.csv` covers all teams present in `issues.csv`. If a team has no skilled developers, the solver cannot assign those issues and will report infeasibility.
</details>

<details>
<summary>Connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) -- concepts, properties, `.where()` filters, and aggregates used to build the assignment domain.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) -- the `Problem` API, `solve_for` decision variables, `satisfy` constraints, and `minimize` objectives used here.

### CLI / SDK guides

- [RelationalAI setup and `rai init`](https://docs.relational.ai/) -- connecting the SDK to your Snowflake account.

## Support

- File issues at the RelationalAI templates repository.
