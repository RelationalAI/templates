# Vehicle Scheduling

Assign trips to vehicles to minimize total cost including fixed and variable components.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Scheduling |
| **Industry** | Logistics / Transportation |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Fleet operators must assign trips to vehicles while minimizing total cost. Each vehicle has a fixed cost (insurance, depreciation, parking) that applies if the vehicle is used at all, plus variable mileage costs. This template models assigning trips to a mixed fleet of vans and trucks with different capacities and cost structures.

The optimizer determines both which vehicles to use and which trips each vehicle should handle, minimizing the combination of fixed and variable costs.

## Why is optimization valuable?

- **Fleet size optimization**: Determine the minimum number of vehicles needed to complete all trips
- **Cost minimization**: Find the lowest-cost assignment considering both fixed and variable costs
- **Utilization improvement**: Maximize use of lower-cost vehicles before activating expensive ones

## What are similar problems?

- **School bus routing**: Assign students to buses and routes to minimize fleet size and distance
- **Delivery route assignment**: Assign packages to delivery vehicles for last-mile delivery
- **Field service dispatch**: Assign technician visits to service vehicles
- **Taxi/rideshare dispatch**: Assign ride requests to available drivers

## Problem Details

### Model

**Concepts:**
- `Vehicle`: Fleet units with capacity and cost structure
- `Trip`: Delivery tasks with origin, destination, load, and time windows
- `Assignment`: Decision entity for vehicle-trip assignment
- `VehicleUsage`: Tracks whether each vehicle is used (for fixed costs)

**Relationships:**
- `Assignment` connects `Vehicle` → `Trip`

### Decision Variables

- `Assignment.assigned` (binary): 1 if vehicle is assigned to trip, 0 otherwise
- `VehicleUsage.used` (binary): 1 if vehicle is used at all, 0 otherwise

### Objective

Minimize total cost:
```
minimize sum(used * fixed_cost) + sum(assigned * distance * cost_per_mile)
```

### Constraints

1. **Trip coverage**: Each trip must be assigned to exactly one vehicle
2. **Vehicle capacity**: Total load assigned to a vehicle cannot exceed its capacity
3. **Usage linking**: If any trip is assigned to a vehicle, that vehicle is marked as used

## Data

Data files are located in the `data/` subdirectory.

### vehicles.csv

| Column | Description |
|--------|-------------|
| id | Unique vehicle identifier |
| name | Vehicle name (e.g., Van_1, Truck_1) |
| capacity | Maximum load capacity (units) |
| cost_per_mile | Variable cost per mile ($) |
| fixed_cost | Fixed cost if vehicle is used ($) |

### trips.csv

| Column | Description |
|--------|-------------|
| id | Unique trip identifier |
| name | Trip name |
| origin | Starting location |
| destination | Ending location |
| distance | Trip distance (miles) |
| load | Load requirement (units) |
| start_time | Earliest start time |
| end_time | Latest end time |

## Usage

```python
from vehicle_scheduling import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python vehicle_scheduling.py
```

## Expected Output

```

Status: OPTIMAL
Total cost: $196.00
Vehicle assignments:
name  float
   4    1.0
 4_1    1.0
 4_2    1.0
 4_3    1.0
 4_4    1.0
 4_5    1.0
 4_6    1.0
```