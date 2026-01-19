# Hospital Staffing

Assign nurses to shifts to ensure adequate coverage while minimizing staffing cost.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Allocation |
| **Industry** | Healthcare |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Hospitals must schedule nurses across shifts while ensuring patient safety, meeting regulatory requirements, and controlling labor costs—typically 40-60% of a hospital's operating budget. This template models assigning nurses with different skill levels and hourly rates to Morning, Afternoon, and Night shifts, respecting individual availability and ensuring each shift has adequate coverage including at least one highly-skilled nurse.

## Why is optimization valuable?

- **Cost reduction**: Reduces overtime and agency nurse spending through optimal shift assignments <!-- TODO: Add % improvement from results -->
- **Patient safety**: Ensures consistent staffing ratios that directly impact patient outcomes
- **Staff satisfaction**: Creates fair, predictable schedules that reduce burnout and turnover

## What are similar problems?

- **Call center staffing**: Schedule agents across time slots to meet service level targets
- **Retail workforce scheduling**: Assign employees to shifts matching demand patterns
- **Security guard rostering**: Cover facilities 24/7 with appropriate skill mix
- **Airline crew scheduling**: Assign pilots and flight attendants to flights respecting regulations

## Problem Description

A hospital needs to staff three shifts (Morning, Afternoon, Night) with nurses who have different skill levels and hourly rates. Each shift has minimum staffing requirements and needs at least one nurse with sufficient skill. Nurses have varying availability and can only work one shift per day.

The goal is to find the lowest-cost assignment that meets all coverage and skill requirements.

### Decision Variables

- `Assignment.assigned` (binary): 1 if nurse is assigned to shift, 0 otherwise

### Objective

Minimize total staffing cost:
```
minimize sum(assigned * shift_duration * nurse_hourly_cost)
```

### Constraints

1. **Availability**: Nurses can only work shifts they're available for
2. **Single shift**: Each nurse works at most one shift per day
3. **Minimum coverage**: Each shift must have at least `min_nurses` assigned
4. **Skill requirement**: Each shift must have at least one nurse with `skill_level >= min_skill`

## Data

Data files are located in the `data/` subdirectory.

### nurses.csv

| Column | Description |
|--------|-------------|
| id | Unique nurse identifier |
| name | Nurse name |
| skill_level | Skill rating (1=basic, 2=intermediate, 3=advanced) |
| hourly_cost | Cost per hour ($) |

### shifts.csv

| Column | Description |
|--------|-------------|
| id | Unique shift identifier |
| name | Shift name (Morning, Afternoon, Night) |
| start_hour | Shift start time (24-hour format) |
| duration | Shift length in hours |
| min_nurses | Minimum nurses required |
| min_skill | Minimum skill level required for at least one nurse |

### availability.csv

| Column | Description |
|--------|-------------|
| nurse_id | Reference to nurse |
| shift_id | Reference to shift |
| available | 1 if nurse can work this shift, 0 otherwise |

## Usage

```python
from hospital_staffing import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python hospital_staffing.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Total Staffing Cost: $X.XX
...
```
