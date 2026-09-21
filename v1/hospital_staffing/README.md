---
title: "Hospital Staffing"
description: "Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint."
featured: false
experience_level: intermediate
industry: "Healthcare & Life Sciences"
reasoning_types:
  - Prescriptive
tags:
  - Staffing
  - Scheduling
  - Healthcare
  - Multi-Objective
---

## What this template is for

This template uses **prescriptive reasoning (optimization)** to frame hospital nurse scheduling as a bi-objective problem with two competing objectives: minimize overtime cost versus minimize unmet patient demand. The original single-objective formulation bundled both goals into one weighted penalty sum, forcing the modeler to choose a penalty weight up front. This version unbundles them using the epsilon constraint method: it sweeps a range of caps on allowable unmet demand, and at each cap the solver minimizes overtime cost subject to that service-level constraint.

The result is a Pareto frontier that reveals exactly how much overtime cost each level of patient service requires -- making the tradeoff explicit and auditable rather than hidden inside a penalty weight.

## Who this is for

- Healthcare operations managers building nurse scheduling systems
- Data engineers integrating optimization into hospital workforce platforms
- Developers learning to model staffing problems with mixed binary and continuous variables
- Anyone exploring multi-objective optimization with coverage and skill constraints

## What you'll build

- A nurse-to-shift assignment model with binary decision variables
- Overtime tracking with continuous variables and cost multipliers
- Patient throughput and unmet demand calculations per shift
- Minimum staffing and skill-level coverage constraints
- Epsilon constraint method sweeping unmet demand caps to trace the cost-service frontier
- Pareto analysis with marginal cost per patient and knee detection

## What's included

- `hospital_staffing.py` -- Main script with model definition, epsilon constraint sweep, and Pareto analysis
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/nurses.csv` -- Nurse roster with skill levels, hourly costs, and overtime parameters
- `data/shifts.csv` -- Shift definitions with timing, staffing requirements, and patient demand
- `data/availability.csv` -- Nurse-to-shift availability matrix
- `pyproject.toml` -- Python project configuration with dependencies

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
   curl -O https://docs.relational.ai/templates/zips/v1/hospital_staffing.zip
   unzip hospital_staffing.zip
   cd hospital_staffing
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
   python hospital_staffing.py
   ```

6. Expected output:
   ```text
   ======================================================================
   ANCHOR SOLVE 1: Minimize overtime cost (no unmet demand constraint)
   ======================================================================
   Overtime cost: $0.00
   Unmet demand: 130.0 patients

   ======================================================================
   ANCHOR SOLVE 2: Minimize unmet demand (no overtime cost objective)
   ======================================================================
   Min unmet demand: 0.0 patients

   Feasible unmet demand range: [0.0, 130.0]

   ======================================================================
   EPSILON SWEEP: 5 interior points
   Unmet demand targets: ['108.3', '86.7', '65.0', '43.3', '21.7']
   ======================================================================

   ======================================================================
   EFFICIENT FRONTIER: Overtime Cost vs Patient Service
   ======================================================================
     #          Label   Unmet Demand  Overtime Cost
   ------------------------------------------------
     1       cheapest          130.0 $         0.00
     2          eps_1          108.3 $         0.00
     3          eps_2           86.7 $         0.00
     4          eps_3           65.0 $         0.00
     5          eps_4           43.3 $         0.00
     6          eps_5           21.7 $       336.00
     7   best_service            0.0 $      1728.00

   Overtime Cost
   $ 1,728.00 |7                                                 |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |                                                  |
              |        6                                         |
              |                                                  |
              |                                                  |
   $     0.00 |                5       4       3       2        1|
              +--------------------------------------------------+
               0                                              130 patients
                                  Unmet Demand

   Marginal analysis (cost of reducing unmet demand by 1 patient):
       cheapest -> eps_4         : $0.00/patient (free capacity available)
          eps_4 -> eps_5         : $15.51/patient
          eps_5 -> best_service  : $64.25/patient

     Knee: Point 5 (eps_4) -- marginal cost jumps 15.5x beyond this point
     Recommendation: Target 43 unmet patients at $0.00 overtime cost --
     further service improvement costs significantly more per patient.

     Knee-point assignments:
       A_Afternoon: Nurse
       B_Night: Nurse
       C_Afternoon: Nurse
       D_Morning: Nurse
       E_Morning: Nurse
       F_Night: Nurse
   ```

   The Pareto frontier reveals a sharp knee at point 5: the first 67% of
   demand reduction (130 to 43 patients) is free, but reducing the last 43
   patients costs $1,728 in overtime -- the marginal cost jumps from $0 to
   $15.51 then $64.25 per patient.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── hospital_staffing.py
└── data/
    ├── nurses.csv
    ├── shifts.csv
    └── availability.csv
```

**Start here**: run `python hospital_staffing.py` for the full anchor-solve, epsilon-sweep, and Pareto analysis end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is small and illustrative — a single hospital day with a handful of nurses and shifts, sized so the whole epsilon sweep solves in seconds. It is designed to make the cost-service tradeoff visible, not to match a specific hospital's roster.

- **`nurses.csv`** — the nurse roster: skill level, hourly cost, regular-hour limit, and an overtime pay multiplier per nurse.
- **`shifts.csv`** — shift definitions: start hour, duration, minimum nurses, minimum skill, patient demand, and the patients each nurse-hour can serve.
- **`availability.csv`** — a nurse-to-shift availability matrix; `available = 1` means the nurse can work that shift.

## Model overview

The model is a small optimization ontology: two entities (nurses, shifts) linked by an availability matrix, with a per-availability assignment decision the solver fills in.

- **Key entities**: `Nurse` — a nurse with a skill level and cost parameters (the solver adds overtime hours); `Shift` — a shift with coverage requirements and patient demand (the solver adds patients-served and unmet-demand quantities); `Availability` — a nurse's eligibility for a shift; `Assignment` — the decision to staff a nurse on a shift, the MILP's decision space.
- **Primary identifiers**: `Nurse.id` and `Shift.id` (integers); `Availability` is keyed by the `(nurse_id, shift_id)` pair; `Assignment` is keyed by its `Availability`.
- **Important invariants**: overtime hours, patients served, and unmet demand are non-negative continuous quantities; each nurse works one to two shifts; every shift meets its minimum-nurse and minimum-skill floor; assignment decisions are binary.

For the full concept and property definitions, see `hospital_staffing.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

**Define concepts and load CSV data.** The model defines three core concepts: nurses with skill levels and cost parameters, shifts with coverage requirements and patient demand, and an availability relationship linking nurses to shifts. A per-availability `Assignment` carries the binary staffing decision the solver fills in.

**Define decision variables, constraints, and objective.** A `solve_staffing` helper encapsulates the full formulation. It registers four variable types -- the binary assignment, each nurse's overtime hours, and each shift's patients-served and unmet-demand quantities -- and applies all constraints: availability, minimum staffing, skill coverage, overtime tracking, and patient-demand accounting (each nurse works one to two shifts; every shift meets its minimum-nurse floor). The original single-objective template bundled overtime cost and unmet demand into one weighted penalty sum, forcing the modeler to pick a penalty weight up front. The bi-objective version splits them: the primary objective minimizes overtime cost, while unmet demand is bounded by an epsilon constraint that caps total unmet demand across all shifts. This eliminates the arbitrary penalty weight and reveals the true tradeoff.

**Solve anchor points and run the epsilon sweep.** Two anchor solves establish the feasible unmet-demand range: anchor 1 minimizes overtime with no demand constraint (the cheapest schedule, which may leave patients unserved), and anchor 2 minimizes unmet demand (the best achievable service level). The epsilon sweep then traces interior points between the anchors, each solve minimizing overtime cost subject to a progressively tighter cap on unmet demand.

**Pareto analysis output.** The script prints the efficient frontier showing how overtime cost rises as the unmet-demand cap tightens. Marginal analysis computes the cost of reducing unmet demand by one patient, and a knee detector flags the point where that marginal cost jumps sharply -- recommending the best cost-service balance.

See `hospital_staffing.py` for the implementation, and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own roster, shifts, and availability; keep the column names listed in *Sample data* above.
- Ensure `availability.csv` only references valid nurse and shift IDs, and that available nurses provide enough coverage to meet each shift's `min_nurses` and `min_skill` requirements.
- Add more nurses or shifts simply by appending rows to the CSVs.

### Tune parameters

- **Frontier resolution** — increase `n_interior` for a finer-grained Pareto frontier (more interior epsilon points between the two anchors).
- **Solve budget** — `time_limit_sec` on `problem.solve("highs", ...)` caps each solve; raise it if larger rosters time out.

### Extend the model

- **Add shift preferences** by introducing a preference weight per nurse-shift pair and folding it into the objective.
- **Model consecutive-shift restrictions** by adding constraints that prevent nurses from working back-to-back shifts without rest.
- **Introduce part-time nurses** with different regular-hour limits and availability patterns.

### Scale up / productionize

- Swap the `read_csv(...)` loads for `model.data(snowflake_table)` calls to run against roster and demand tables maintained in Snowflake.
- Pin `relationalai` in `pyproject.toml` for reproducible solves, and schedule the run to refresh the frontier as demand forecasts update.

## Troubleshooting

<details>
<summary>Solver returns INFEASIBLE</summary>

Check that nurse availability in `availability.csv` provides enough coverage to meet the minimum staffing requirements in `shifts.csv`. With the current data, each shift requires at least 2 nurses, so ensure enough nurses are available per shift.
</details>

<details>
<summary>High unmet demand in the solution</summary>

Tighten the epsilon constraint by reducing the unmet demand cap (or increase `n_interior` to explore finer gradations). If even the best-service anchor shows high unmet demand, the nurse roster may need more staff or broader availability.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>

## Learn more

### Core concepts

- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.
- [PyRel v1 modeling](https://docs.relational.ai/) — concepts, properties, and loading CSV data into relations.

### Modeling reference

- [Multi-objective optimization](https://docs.relational.ai/) — trading off competing objectives, including epsilon-constraint sweeps.

### Deeper dives

- [Sensitivity and marginal analysis](https://docs.relational.ai/) — reading shadow prices and marginal costs, as the Pareto knee detection does here.

## Support

- File issues at the RelationalAI templates repository.
