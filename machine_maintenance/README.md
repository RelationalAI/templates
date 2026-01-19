# Machine Maintenance

Schedule preventive maintenance for machines to minimize cost while avoiding conflicts.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Scheduling |
| **Industry** | Manufacturing |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Equipment requires periodic preventive maintenance, but scheduling is complex: maintenance crews have limited hours, some machines can't be serviced simultaneously (they share resources or technicians), and weekend/overtime slots cost more. This template models scheduling maintenance across time slots while respecting crew capacity and machine conflicts.

The goal is to minimize total maintenance cost by scheduling machines in the right slots—avoiding expensive overtime when possible while ensuring all machines get serviced.

## Why is optimization valuable?

- **Downtime reduction**: Reduces unplanned downtime through optimally timed maintenance <!-- TODO: Add % improvement from results -->
- **Cost reduction**: Lowers total maintenance spend by avoiding unnecessary overtime slots
- **Resource utilization**: Ensures skilled maintenance crews are efficiently allocated across machines

## What are similar problems?

- **Aircraft maintenance scheduling**: Schedule heavy checks and line maintenance for a fleet
- **Wind turbine maintenance**: Coordinate maintenance crews across remote turbine sites
- **HVAC preventive maintenance**: Schedule building system maintenance across a property portfolio
- **Server patching windows**: Schedule system updates during maintenance windows to minimize disruption

## Problem Description

A factory has machines that require periodic preventive maintenance. Maintenance must be scheduled during available time slots, each with limited crew hours. Some machines cannot be maintained simultaneously (conflicts). Each time slot may have different cost multipliers (e.g., weekend overtime).

The goal is to schedule each machine for maintenance at minimum total cost while respecting crew capacity and conflict constraints.

### Decision Variables

- `Schedule.assigned` (binary): 1 if machine is scheduled in time slot, 0 otherwise

### Objective

Minimize weighted scheduling cost:
```
minimize sum(assigned * machine_priority * slot_cost_multiplier)
```

Where `machine_priority` (called `failure_cost` in data) represents the criticality of each machine—higher values mean more critical machines that should be scheduled in cheaper (non-overtime) slots when possible.

### Constraints

1. **Single scheduling**: Each machine must be scheduled exactly once
2. **Crew capacity**: Total maintenance hours per slot cannot exceed crew hours available
3. **No conflicts**: Machines that conflict cannot be scheduled in the same slot

## Data

Data files are located in the `data/` subdirectory.

### machines.csv

| Column | Description |
|--------|-------------|
| id | Unique machine identifier |
| name | Machine name |
| maintenance_hours | Hours required for maintenance |
| failure_cost | Cost impact if maintenance is delayed ($) |
| importance | Priority level (1=low, 3=high) |

### time_slots.csv

| Column | Description |
|--------|-------------|
| id | Unique slot identifier |
| day | Day name (Monday, Tuesday, etc.) |
| crew_hours | Maintenance crew hours available |
| cost_multiplier | Cost multiplier (1.0=normal, 1.5=overtime) |

### conflicts.csv

| Column | Description |
|--------|-------------|
| machine1_id | First machine in conflict pair |
| machine2_id | Second machine in conflict pair |

Machines in a conflict pair cannot be maintained in the same time slot.

## Usage

```python
from machine_maintenance import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python machine_maintenance.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Total Maintenance Cost: $X.XX
...
```
