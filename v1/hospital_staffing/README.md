---
title: "Hospital Staffing"
description: "Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Prescriptive
tags:
  - Staffing
  - Scheduling
  - Healthcare
  - Multi-Objective
---

# Hospital Staffing

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
- RelationalAI Python SDK (`relationalai`) >= 1.0.13

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
     7   best_service            0.0 $      1116.00

   Overtime Cost
   $ 1,116.00 |7                                                 |
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
          eps_5 -> best_service  : $36.00/patient

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
   patients costs $1,116 in overtime -- the marginal cost jumps from $0 to
   $15.51 then $36.00 per patient.

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

## How it works

This section walks through the highlights in `hospital_staffing.py`.

### Define concepts and load CSV data

The model defines three core concepts: nurses with skill levels and cost parameters, shifts with coverage requirements and patient demand, and an availability relationship linking nurses to shifts.

```python
Nurse = Concept("Nurse", identify_by={"id": Integer})
Nurse.name = Property(f"{Nurse} has {String:name}")
Nurse.skill_level = Property(f"{Nurse} has {Integer:skill_level}")
Nurse.hourly_cost = Property(f"{Nurse} has {Float:hourly_cost}")

Shift = Concept("Shift", identify_by={"id": Integer})
Shift.min_nurses = Property(f"{Shift} has {Integer:min_nurses}")
Shift.min_skill = Property(f"{Shift} has {Integer:min_skill}")
Shift.patient_demand = Property(f"{Shift} has {Integer:patient_demand}")
```

### Define decision variables, constraints, and objective

The `solve_staffing` helper encapsulates the full formulation. It registers four variable types and applies all constraints, then switches between objectives and an optional epsilon bound on unmet demand.

The original single-objective template bundled overtime cost and unmet demand into one weighted penalty sum (`p.minimize(overtime_cost + PENALTY * sum(Shift.x_unmet_demand))`). The bi-objective version splits them: the primary objective minimizes overtime cost, while unmet demand is bounded by an epsilon constraint. This eliminates the arbitrary penalty weight and reveals the true tradeoff.

```python
def solve_staffing(objective="min_overtime", eps_unmet=None):
    p = Problem(model, Float)

    p.solve_for(Assignment.x_assigned, type="bin", populate=False,
                name=["assigned", Assignment.availability.nurse.name,
                      Assignment.availability.shift.name])
    p.solve_for(Nurse.x_overtime_hours, type="cont", populate=False,
                name=["ot", Nurse.name], lower=0)
    p.solve_for(Shift.x_patients_served, type="cont", populate=False,
                name=["pt", Shift.name], lower=0)
    p.solve_for(Shift.x_unmet_demand, type="cont", populate=False,
                name=["ud", Shift.name], lower=0)
```

Constraints enforce availability, minimum staffing, skill coverage, overtime tracking, and patient demand accounting.

```python
    # Each nurse works 1-2 shifts
    nurse_shift_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.nurse == Nurse).per(Nurse)
    p.satisfy(model.require(nurse_shift_count >= 1))
    p.satisfy(model.require(nurse_shift_count <= 2))

    # Minimum nurses per shift with skill requirements
    shift_staff_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.shift == Shift).per(Shift)
    p.satisfy(model.require(shift_staff_count >= Shift.min_nurses))
```

When `eps_unmet` is provided, a constraint caps total unmet demand across all shifts.

```python
    if eps_unmet is not None:
        p.satisfy(model.require(sum(Shift.x_unmet_demand) <= eps_unmet))
```

The objective switches between minimizing overtime cost (primary) and minimizing unmet demand (used for anchor solve 2).

```python
    overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)

    if objective == "min_overtime":
        p.minimize(overtime_cost)
    elif objective == "min_unmet":
        p.minimize(sum(Shift.x_unmet_demand))

    p.solve("highs", time_limit_sec=60)
```

### Solve anchor points and run the epsilon sweep

Two anchor solves establish the feasible unmet demand range. Anchor 1 minimizes overtime with no demand constraint (finding the cheapest schedule, which may leave patients unserved). Anchor 2 minimizes unmet demand (finding the best achievable service level).

```python
result1 = solve_staffing("min_overtime", eps_unmet=None)
result2 = solve_staffing("min_unmet", eps_unmet=None)
```

The epsilon sweep then traces interior points between the anchors. Each solve minimizes overtime cost subject to a progressively tighter cap on unmet demand.

```python
n_interior = 5
epsilon_values = [
    unmet_max - i * (unmet_max - unmet_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]

for i, eps in enumerate(epsilon_values):
    result = solve_staffing("min_overtime", eps_unmet=eps)
```

### Pareto analysis output

The script prints the efficient frontier showing how overtime cost increases as the unmet demand cap tightens. Marginal analysis computes the cost of reducing unmet demand by one patient, and a knee detector identifies the point where the marginal cost jumps sharply -- recommending the best cost-service balance.

```python
print(f"{'#':>3} {'Label':>14} {'Unmet Demand':>14} {'Overtime Cost':>14}")
for j, pt in enumerate(pareto):
    print(f"{j+1:>3} {pt['label']:>14} {pt['unmet_demand']:>14.1f} ${pt['overtime_cost']:>13.2f}")

# Marginal analysis (cost of reducing unmet demand by 1 patient)
for j in range(len(pareto) - 1):
    d_cost = pareto[j+1]['overtime_cost'] - pareto[j]['overtime_cost']
    d_unmet = pareto[j]['unmet_demand'] - pareto[j+1]['unmet_demand']
    if abs(d_unmet) > 1e-6:
        rate = d_cost / d_unmet
        # ...

# Knee detection
print(f"\n  Knee: Point {knee_idx + 1} ({pareto[knee_idx]['label']}) "
      f"— marginal cost jumps {max_jump:.1f}x beyond this point")
print(f"  Recommendation: Target {pareto[knee_idx]['unmet_demand']:.0f} unmet patients "
      f"at ${pareto[knee_idx]['overtime_cost']:.2f} overtime cost — "
      f"further service improvement costs significantly more per patient.")
```

## Customize this template

- **Add more nurses or shifts** by extending the CSV files with additional rows.
- **Adjust frontier resolution**: Increase `n_interior` for a finer-grained Pareto frontier.
- **Add shift preferences** by introducing a preference weight per nurse-shift pair and including it in the objective.
- **Model consecutive shift restrictions** by adding constraints that prevent nurses from working back-to-back shifts without rest.
- **Introduce part-time nurses** with different regular hour limits and availability patterns.

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
