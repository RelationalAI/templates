---
title: "Shift Assignment"
description: "Assign workers to shifts respecting availability and capacity constraints."
featured: true
experience_level: beginner
industry: "Workforce Management"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - CSP
  - Scheduling
---

# Shift Assignment

## What is this problem?

Businesses need to staff shifts with available workers, but workers have different availabilities and each shift has minimum coverage requirements. This template is a Constraint Satisfaction Problem (CSP)—unlike optimization problems, the goal is to find any valid schedule that satisfies all constraints, not necessarily the "best" one.

CSP is useful when multiple valid solutions exist and any is acceptable, or when you need to determine feasibility before optimizing.

## Why is constraint satisfaction valuable?

- **Feasibility checking**: Quickly determine if staffing requirements can be met with available workers
- **Alternative generation**: Find multiple valid schedules to offer employees choice
- **Constraint debugging**: When infeasible, identify which constraints are causing the problem

## What are similar problems?

- **Exam scheduling**: Assign exams to time slots avoiding student conflicts
- **Conference room booking**: Schedule meetings into rooms respecting capacity and equipment needs
- **Sports league scheduling**: Create game schedules avoiding conflicts and ensuring fairness
- **Course timetabling**: Assign classes to rooms and time slots respecting instructor and student constraints

## Problem Details

### Model

**Concepts:**
- `Worker`: Employees available for scheduling
- `Shift`: Time periods requiring coverage
- `Assignment`: Decision entity for worker-shift pairing

**Relationships:**
- `Assignment` connects `Worker` → `Shift` based on availability constraints

### Decision Variables

- `Assignment.assigned` (binary): 1 if worker is assigned to shift, 0 otherwise

### Constraints

1. **Availability**: Workers can only be assigned to shifts they're available for
2. **Shift capacity**: Number of workers per shift cannot exceed capacity
3. **Single assignment**: Each worker is assigned to at most one shift

### Goal

Find any feasible assignment satisfying all constraints (no optimization objective—this is a satisfaction problem).

## Data

Data files are located in the `data/` subdirectory.

### workers.csv

| Column | Description |
|--------|-------------|
| id | Unique worker identifier |
| name | Worker name |

### shifts.csv

| Column | Description |
|--------|-------------|
| id | Unique shift identifier |
| name | Shift name (e.g., Morning, Afternoon, Night) |
| capacity | Maximum number of workers for this shift |

### availability.csv

| Column | Description |
|--------|-------------|
| worker_id | Reference to worker |
| shift_id | Reference to shift |

Each row indicates that the worker is available for that shift.

## Usage

```python
from shift_assignment import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(result['assignments'])
```

Or run directly:

```bash
python shift_assignment.py
```

## Expected Output

```
Status: OPTIMAL

Assignments:
worker     shift
 Alice   Morning
   Bob   Morning
Carlos Afternoon
 Diana   Morning
 Ethan     Night
 Frank   Morning
 Grace Afternoon
 Henry   Morning
 Irene   Morning
  Jack     Night

Coverage per shift:
    shift  workers
Afternoon        2
  Morning        6
    Night        2
```

A valid shift assignment was found. Since this is a CSP (Constraint Satisfaction Problem), there is no objective value—any feasible assignment is equally valid. The solution satisfies:
- Each shift has at least 2 workers (min_coverage constraint)
- Each worker is assigned to at most 1 shift (max_shifts_per_worker constraint)

Note: CSP may return different valid solutions on different runs.
