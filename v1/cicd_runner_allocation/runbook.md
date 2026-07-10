# CI/CD Runner Allocation — Analyst Runbook

A platform team wants to assign every CI/CD workflow job to a compatible runner at minimum pipeline cost, see how that cost moves as runner concurrency scales, and — when a maintenance outage makes the schedule impossible — get a precise diagnosis of *why* rather than a bare "infeasible." The dataset is 8 runner types (each with a cost per minute and a concurrency cap), 20 workflow jobs (each with OS and resource requirements and an estimated runtime), and 70 precomputed compatible job-runner pairs. The analysis solves an assignment program, sweeps a concurrency multiplier, and runs an outage scenario that returns an irreducible infeasible subsystem (IIS).

```text
8 runners (cost/min, concurrency cap) · 20 workflow jobs (OS/cpu/mem, minutes) · 70 compatible pairs
      │
      ▼
/rai-prescriptive-problem
   • decision: binary assign per compatible (job, runner) pair
   • constraints: each job on exactly one compatible runner; per-runner jobs ≤ cap x multiplier
   • objective: minimize total cost = sum(assign x cost/min x job minutes)
   • concurrency multiplier 0.5 / 1.0 / 1.5      -> OPTIMAL $10.18 / $9.62 / $9.53
      │
      ▼
/rai-prescriptive-results
   • cheaper self-hosted-linux absorbs more jobs as the cap loosens, so cost falls
   • outage (2 runners offline) → INFEASIBLE; the IIS pins ubuntu-xlarge's cap (5) against
     6 of the 7 high-CPU Linux jobs — restore a runner or raise that one cap
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — later steps read the `Runner`/`Workflow`/`Compatibility` concepts and the assignment decisions earlier steps wrote back.

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/runners.csv` (each runner has a cost per minute and a max concurrency), `data/workflows.csv` (each job has a required OS, a minimum CPU and memory, and an estimated runtime in minutes), and `data/compatibility.csv` (the precomputed compatible job-runner pairs). Model compatibility as a relationship linking a workflow job to the runners it can run on.

**Response:** Loads `Runner` (8, with `cost_per_minute` and `max_concurrent`), `Workflow` (20, with OS and resource requirements and `estimated_minutes`), and `Compatibility` (70 compatible job-runner pairs) — the cheapest runner is self-hosted-linux at $0.005/min.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many of each?

**Response:** Three concepts — 8 `Runner` (cost, concurrency cap), 20 `Workflow` (OS / CPU / memory / minutes), and 70 `Compatibility` pairs (the only allowed assignments) — so each job can run on a restricted subset of runners.

## 3. Assign jobs at minimum cost across capacity scenarios

**Prompt:** /rai-prescriptive-problem Which runner should each job run on to minimize total pipeline cost — runner cost-per-minute times the job's estimated minutes — given that each job must go to exactly one compatible runner and each runner can run at most its concurrency cap of jobs? Solve it for three capacity scenarios that scale every runner's concurrency cap to 0.5x, 1.0x, and 1.5x. Persist the assignment to the ontology.

**Response:** OPTIMAL in all three scenarios (HiGHS), all 20 jobs assigned each time. Minimum total cost is **$10.18 at 0.5x, $9.62 at 1.0x, and $9.53 at 1.5x**. The binary assignment is written back as `Assignment.x_assigned`; the assign-one and per-runner concurrency constraints are keyed by workflow and runner so their conflict membership can be read back later.

## 4. Read the cost-vs-capacity curve

**Prompt:** /rai-prescriptive-results How does minimum pipeline cost change as concurrency capacity scales, and what drives the difference?

**Response:** Cost falls as caps loosen — $10.18 → $9.62 → $9.53 — but with diminishing returns (most of the saving is from 0.5x to 1.0x). The driver is the cheapest runner, **self-hosted-linux**: as its concurrency cap rises it absorbs more jobs (about 4 at 0.5x, 8 at 1.0x, 12 at 1.5x), displacing work from pricier runners. OS-specific jobs (macOS, Windows) are pinned to their only compatible runner and don't move.

## 5. Diagnose a maintenance outage

**Prompt:** /rai-prescriptive-results If two runners — ubuntu-large and self-hosted-linux — go offline for maintenance at normal (1.0x) capacity, can every job still be scheduled? If not, return the minimal conflict (the IIS): which runner's concurrency cap, and which jobs, make it infeasible?

**Response:** INFEASIBLE — the solver returns a conflict. The irreducible infeasible subsystem pins **ubuntu-xlarge's concurrency cap (max 5)** against the high-CPU Linux jobs that, with the two runners offline, have nowhere else to go: **6 of the 7 high-CPU Linux jobs are stranded** (the minimal conflict names cap-plus-one = 6; exactly which 6 is solver-dependent). The fix is named directly: restore one of the offline runners or raise ubuntu-xlarge's cap — far more actionable than a bare "infeasible."

## Data

Bundled CSVs in `data/`: 8 runners, 20 workflows, 70 compatibility pairs. The concurrency multipliers (0.5, 1.0, 1.5) and the outage runner list are constants in the script. Full model in `cicd_runner_allocation.py`.
