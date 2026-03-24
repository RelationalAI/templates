---
title: "Sprint Scheduling"
description: "Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints."
featured: false
experience_level: intermediate
industry: "Technology"
reasoning_types:
  - Prescriptive
tags:
  - Assignment
  - Scheduling
  - MIP
  - Temporal-Filtering
---

# Sprint Scheduling

## What this template is for

Software development teams need to decide which developer works on which issue in which sprint. Manually balancing priorities, story points, skill requirements, and capacity across multiple sprints is error-prone and time-consuming, especially as the backlog grows. An optimization model can produce an assignment plan that minimizes delay on high-priority work while keeping every developer within their capacity.

This template assigns 30 backlog issues to 8 developers across 4 two-week sprints. It demonstrates how to filter issues by epoch timestamp to scope the backlog to a planning horizon, map epoch-based creation dates to categorical sprint periods, and build a binary assignment optimization that respects developer capacity and team skill constraints.

Prescriptive reasoning is well suited here because the problem has combinatorial structure -- each issue must go to exactly one developer in one sprint, developers have capacity limits, and only developers with matching team skills can take on an issue. The solver explores the full space of valid assignments to find the schedule that minimizes weighted completion time, prioritizing high-urgency issues into earlier sprints.

## Who this is for

- **Intermediate users** familiar with mixed-integer programming concepts (binary variables, assignment constraints)
- **Engineering managers** looking to automate sprint planning
- **Project managers** balancing team workloads across multiple sprints
- **Data scientists** working with epoch-timestamped event data who need temporal filtering patterns

## What you'll build

- Load developers, sprints, issues, and skill mappings from CSV files
- Filter issues by epoch timestamp to scope the backlog to a planning horizon
- Map each issue's `created_at` epoch to a target sprint (earliest eligible sprint)
- Build a cross-product `Assignment` concept linking developers, issues, and sprints where skill constraints hold
- Define binary decision variables for each valid (developer, issue, sprint) assignment
- Enforce that each issue is assigned exactly once and developer capacity is not exceeded per sprint
- Minimize weighted completion time so high-priority issues land in earlier sprints
- Run scenario analysis across capacity multiplier levels (0.5, 0.75, 1.0) to see the impact of reduced team capacity
- Solve with HiGHS and display the assignment plan per scenario

## What's included

- **Script**: `sprint_scheduling.py` -- end-to-end model, solve, and results
- **Data**: `data/developers.csv`, `data/sprints.csv`, `data/issues.csv`, `data/skills.csv`
- **Config**: `pyproject.toml`

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/sprint_scheduling.zip
   unzip sprint_scheduling.zip
   cd sprint_scheduling
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
   python sprint_scheduling.py
   ```

6. Expected output:
   ```text
   Running scenario: capacity_multiplier = 0.5
     Status: OPTIMAL, Objective: ...
     ...

   Running scenario: capacity_multiplier = 0.75
     Status: OPTIMAL, Objective: ...
     ...

   Running scenario: capacity_multiplier = 1.0
     Status: OPTIMAL, Objective: ...
     Planning horizon: 2024-10-01 to 2024-11-26
     Issues in scope: 30 (of 30 total)

     Assignments:
                          name  value
     assign_PROJ-101_Alice_Sprint 1    1.0
     assign_PROJ-103_Eve_Sprint 1      1.0
     ...

   ==================================================
   Scenario Analysis Summary
   ==================================================
     capacity_multiplier=0.5: OPTIMAL, obj=...
     capacity_multiplier=0.75: OPTIMAL, obj=...
     capacity_multiplier=1.0: OPTIMAL, obj=...
   ```

## Template structure

```text
.
├── README.md
├── pyproject.toml
├── sprint_scheduling.py
└── data/
    ├── developers.csv
    ├── sprints.csv
    ├── issues.csv
    └── skills.csv
```

## How it works

### 1. Epoch filtering -- scope the backlog to the planning horizon

Issues have a `created_at` column storing Unix epoch seconds. The script converts the planning horizon boundaries to epochs and filters:

```python
planning_start = "2024-10-01"
planning_end = "2024-11-26"

start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp())

filtered_issues = issues_df[
    (issues_df["created_at"] >= start_epoch) & (issues_df["created_at"] <= end_epoch)
].copy()
```

This keeps only issues created within the planning horizon. Issues created before or after are excluded from scheduling.

### 2. Epoch-to-categorical-period mapping -- assign target sprints

Unlike the date-to-integer mapping in the demand planning template, this template maps epochs to categorical sprint periods. Each issue is assigned to its earliest eligible sprint based on when it was created:

```python
def map_to_sprint(created_at_epoch):
    for _, sprint in sprints_df.iterrows():
        if created_at_epoch < sprint["startdate"]:
            return int(sprint["number"])
        if sprint["startdate"] <= created_at_epoch < sprint["enddate"]:
            return int(sprint["number"])
    return int(sprints_df["number"].max())

filtered_issues["target_sprint_number"] = filtered_issues["created_at"].apply(map_to_sprint)
```

Issues created before Sprint 1 starts are backlog items eligible from Sprint 1. Issues created during Sprint 2 cannot be assigned to Sprint 1 (only Sprint 2 or later).

### 3. Assignment domain with skill constraints

The `Assignment` concept is a cross-product of developers, issues, and sprints, filtered by two conditions: the developer must have the matching team skill, and the sprint must be at or after the issue's target sprint:

```python
Assignment = Concept("Assignment")
Assignment.developer = Property(f"{Assignment} has {Developer}", short_name="developer")
Assignment.issue = Property(f"{Assignment} has {Issue}", short_name="issue")
Assignment.sprint = Property(f"{Assignment} has {Sprint}", short_name="sprint")

model.define(
    Assignment.new(developer=Developer, issue=Issue, sprint=Sprint)
).where(
    Skill.developer_id == Developer.id,
    Skill.team == Issue.team,
    Sprint.number >= Issue.target_sprint_number,
)
```

This dramatically reduces the search space by only creating assignment variables where a valid assignment could exist.

### 4. Binary assignment variables and constraints

Each valid assignment gets a binary variable (1 = assigned, 0 = not assigned). The "each issue assigned exactly once" constraint is defined once as a named expression, while the capacity constraint references a `capacity_multiplier` that varies per scenario:

```python
p.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=["assign", Assignment.issue.key, Assignment.developer.name, Assignment.sprint.name],
)

# Static constraint: each issue assigned exactly once
issue_once = model.require(
    sum(Assignment.x_assigned).per(Issue) == 1
).where(Assignment.issue == Issue)
p.satisfy(issue_once)

# Parameterized constraint: developer capacity per sprint (references capacity_multiplier)
p.satisfy(model.require(
    sum(Assignment.x_assigned * Assignment.issue.story_points).per(Developer, Sprint)
    <= Developer.capacity_points_per_sprint * capacity_multiplier
).where(Assignment.developer == Developer, Assignment.sprint == Sprint))
```

### 5. Weighted completion time objective

The objective minimizes a weighted sum where high-priority issues (lower priority number) incur a higher cost when placed in later sprints. It is defined once and reused across scenario iterations:

```python
max_priority = 3
weighted_completion = sum(
    Assignment.x_assigned
    * (max_priority + 1 - Assignment.issue.priority)
    * Assignment.sprint.number
)
p.minimize(weighted_completion)
```

A priority-1 issue in Sprint 4 costs `(4-1+1) * 4 = 12`, while a priority-3 issue in Sprint 4 costs `(4-3+1) * 4 = 8`. This pushes the most urgent work into the earliest sprints.

## Customize this template

- **Change the planning horizon**: Edit `planning_start` and `planning_end` to include more or fewer sprints. Add corresponding rows to `sprints.csv`.
- **Adjust developer capacity**: Modify `capacity_points_per_sprint` in `developers.csv` or edit `SCENARIO_VALUES` to sweep different `capacity_multiplier` levels (e.g., `[0.5, 0.75, 1.0]`).
- **Add cross-team skills**: Append rows to `skills.csv` to let developers work on issues outside their primary team. Grace and Hank already have cross-team skills in the sample data.
- **Change the priority scheme**: Adjust `max_priority` and the weight formula in the objective to match your team's priority scale.
- **Add sprint-specific constraints**: For example, require that certain issues are completed by a specific sprint using additional `.where()` clauses.

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
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake account has the RAI Native App installed and your user has the required permissions. Run `rai init` to configure your connection profile. See the [RelationalAI documentation](https://docs.relational.ai) for setup details.
</details>
