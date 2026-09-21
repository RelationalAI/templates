# Sprint Scheduling — Analyst Runbook

An engineering manager needs to decide which developer works which backlog issue in which sprint — balancing priorities, story points, team-skill matches, and per-developer capacity across a multi-sprint horizon. The dataset is 8 developers, 30 backlog issues (25 inside the planning horizon), 4 sprints, and a developer-skill map. The analysis solves a binary assignment program that front-loads urgent work, and sweeps developer capacity to find where the plan stops being feasible.

```text
8 developers (team, capacity) · 30 issues (25 in horizon: story points, priority, team) · 4 sprints · skill map
      │
      ▼
/rai-prescriptive-problem
   • decision: binary assign per valid (developer, issue, sprint) — 259 candidates
   • constraints: each in-scope issue assigned once; per-developer-per-sprint story points ≤ capacity x multiplier;
     only skill-matched developers, only sprints at or after the issue's target sprint
   • objective: minimize weighted completion time (urgent issues cost more in later sprints)
   • capacity scenarios 0.35 / 0.5 / 1.0          -> INFEASIBLE / OPTIMAL 112 / OPTIMAL 112
      │
      ▼
/rai-prescriptive-results
   • 0.35x capacity can't fit the backlog (INFEASIBLE); 0.5x already suffices (objective 112, same as full)
   • the plan front-loads Sprint 1 (10 of 25 issues); per-sprint developer capacity is the binding limit
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the formulate step reads the `Developer`/`Issue`/`Sprint`/`Skill` concepts the build step created, and the interpret step reads the assignment decisions the solve produced.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/developers.csv` (each developer has a team and a capacity in story points per sprint), `data/sprints.csv` (each sprint has a number and start/end dates), `data/issues.csv` (each issue has story points, a priority, a team, and a creation date), and `data/skills.csv` (which teams each developer can work). Keep only issues created within the planning horizon, and derive each issue's target sprint (the earliest sprint it could be worked) from its creation date.

**Response:** Loads `Developer` (8, with team and `capacity_points_per_sprint`), `Sprint` (4 two-week periods), `Issue` (30, of which **25 fall inside the horizon**; the 5 created before the horizon are filtered out), and `Skill` (the developer-team map). Each in-scope issue gets a derived `target_sprint_number`.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Four concepts — 8 `Developer`, 4 `Sprint`, 30 `Issue` (25 in the planning horizon), and a 10-row `Skill` map (two developers carry cross-team skills) — the inputs to a developer-issue-sprint assignment.

## 3. Build the sprint plan across capacity scenarios

**Prompt:** /rai-prescriptive-problem Assign each in-scope issue to exactly one developer in one sprint to minimize weighted completion time — where an urgent (low-priority-number) issue costs more the later its sprint. A developer can only take an issue if their team matches the issue's team and the sprint is at or after the issue's target sprint, and each developer's assigned story points per sprint can't exceed their capacity. Solve three capacity scenarios — scaling every developer's capacity to 35%, 50%, and 100% — and persist the assignment.

**Response:** The decision is a binary assignment over the 259 valid (developer, issue, sprint) combinations, with 57 constraints per scenario (HiGHS). At **0.35x capacity the problem is INFEASIBLE** — the backlog can't fit — while **0.5x and 1.0x are both OPTIMAL with objective 112.0**. The assignment is read back per scenario from the solved decision.

## 4. Read the plan

**Prompt:** /rai-prescriptive-results At what capacity does the backlog stop fitting, how does the plan distribute work across sprints, and what's the binding limit?

**Response:** The backlog is infeasible at 35% capacity but fits from **50% upward — and 50% already achieves the same optimal objective (112) as full capacity**, so the team has slack at 100%. The plan **front-loads Sprint 1 with 10 of the 25 issues** (then 8 and 7 into Sprints 2 and 3), because urgent issues are cheaper to finish early. The binding limit is **per-sprint developer capacity** — it's what makes 0.35x infeasible and what shapes the front-loading. (Specific developer assignments vary between the 0.5x and 1.0x optima; the objective and sprint distribution are stable.)

## Data

Bundled CSVs in `data/`: 8 developers, 30 issues, 4 sprints, 10 skill rows. The capacity multipliers (0.35, 0.5, 1.0) and planning horizon are constants in the script. Full model in `sprint_scheduling.py`.
