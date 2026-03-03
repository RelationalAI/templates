---
title: "Hospital Staffing"
description: "Optimize nurse-to-shift assignments to minimize overtime costs and unmet patient demand."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Prescriptive
tags:
  - Staffing
  - Scheduling
  - Healthcare
---

# Hospital Staffing

## What this template is for

Hospitals must balance nurse staffing across shifts to ensure adequate patient care while controlling labor costs. Understaffing leads to unmet patient demand, while overstaffing drives up overtime expenses. Manually creating schedules that respect availability, skill requirements, and labor regulations is error-prone and time-consuming.

This template uses prescriptive reasoning to find the optimal assignment of nurses to shifts. It minimizes a combined objective of overtime costs and overflow penalties for unmet patient demand, while enforcing constraints on nurse availability, minimum staffing levels, skill coverage, and maximum working hours.

The model captures real-world complexity including per-nurse skill levels, shift-specific patient demand rates, and overtime cost multipliers, producing actionable schedules that balance cost efficiency with patient care quality.

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
- A combined cost minimization objective (overtime + demand overflow penalty)

## What's included

- `hospital_staffing.py` -- Main script that defines the model, solves it, and prints results
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
   Status: OPTIMAL
   Objective value: $270.00

   No overtime assigned.

   Patient throughput by shift:
       shift  patients_served  patient_demand  unmet_demand
     Morning             45.0              45           0.0
   Afternoon             60.0              60           0.0
       Night             24.0              25           1.0
   Total patients served: 129 / 130
   Total unmet demand: 1 patients

   Staff assignments:
      nurse      shift
    Nurse_A    Morning
    Nurse_B    Morning
    Nurse_B  Afternoon
    Nurse_C  Afternoon
    Nurse_D    Morning
    Nurse_E      Night
    Nurse_F  Afternoon
    Nurse_F      Night
   ```

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

### 1. Define the ontology and load data

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

### 2. Set up decision variables

The model uses four types of variables: binary assignment variables for nurse-shift pairings, continuous overtime hours per nurse, patients served per shift, and unmet demand per shift.

```python
s.solve_for(Assignment.x_assigned, type="bin",
    name=["assigned", Assignment.availability.nurse.name, Assignment.availability.shift.name])
s.solve_for(Nurse.x_overtime_hours, type="cont", name=["ot", Nurse.name], lower=0)
s.solve_for(Shift.x_patients_served, type="cont", name=["pt", Shift.name], lower=0)
s.solve_for(Shift.x_unmet_demand, type="cont", name=["ud", Shift.name], lower=0)
```

### 3. Add constraints

Constraints enforce availability, minimum staffing, skill coverage, overtime tracking, and patient demand accounting.

```python
# Each nurse works 1-2 shifts
nurse_shift_count = sum(AssignmentRef.x_assigned).where(
    AssignmentRef.availability.nurse == Nurse).per(Nurse)
s.satisfy(model.require(nurse_shift_count >= 1))
s.satisfy(model.require(nurse_shift_count <= 2))

# Minimum nurses per shift with skill requirements
shift_staff_count = sum(AssignmentRef.x_assigned).where(
    AssignmentRef.availability.shift == Shift).per(Shift)
s.satisfy(model.require(shift_staff_count >= Shift.min_nurses))
```

### 4. Minimize combined cost

The objective combines overtime labor costs with a penalty for each unmet patient.

```python
overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)
total_overflow_penalty = overflow_penalty_per_patient * sum(Shift.x_unmet_demand)
s.minimize(overtime_cost + total_overflow_penalty)
```

## Customize this template

- **Add more nurses or shifts** by extending the CSV files with additional rows.
- **Adjust the overflow penalty** (`overflow_penalty_per_patient`) to prioritize patient coverage over cost savings, or vice versa.
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

The overflow penalty (`overflow_penalty_per_patient = 20`) controls the trade-off between overtime cost and patient coverage. Increase this value to prioritize meeting patient demand, or add more nurses to the roster.
</details>

<details>
<summary>Connection or authentication errors</summary>

Run `rai init` to configure your Snowflake connection. Verify that the RAI Native App is installed and your user has the required permissions.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Ensure you activated the virtual environment and ran `python -m pip install .` to install all dependencies listed in `pyproject.toml`.
</details>
