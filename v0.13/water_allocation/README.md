---
title: "Water Allocation"
description: "Allocate water from sources to users at minimum cost while meeting demand."
featured: false
experience_level: beginner
industry: "Utilities"
reasoning_types:
  - Prescriptive
tags:
  - Design
  - LP
---

# Water Allocation

## What is this problem?

Water utilities must distribute water from sources (reservoirs, treatment plants, groundwater) to users (residential, industrial, agricultural) through a network of pipelines. This template models allocating flow across connections to meet all user demands at minimum cost, accounting for source costs, connection capacities, and transmission losses.

Different sources have different costs (groundwater pumping is typically more expensive than surface water), and some connections lose water to evaporation or leakage.

## Why is optimization valuable?

- **Cost minimization**: Use cheapest sources first while respecting capacity constraints and transmission losses <!-- TODO: Add % improvement from results -->
- **Demand satisfaction**: Ensure all users receive required water, prioritizing critical users during shortages
- **Infrastructure planning**: Identify capacity bottlenecks and quantify the value of potential upgrades

## What are similar problems?

- **Natural gas distribution**: Allocate gas from wells and storage to customers through pipeline networks
- **Electricity dispatch**: Distribute power from generators to load centers through transmission lines
- **District heating**: Allocate heat from plants to buildings through pipe networks
- **Irrigation canal management**: Distribute water from reservoirs to farms through canal systems

## Problem Details

### Model

**Concepts:**
- `Source`: Water supply points with capacity and cost per unit
- `User`: Demand points with required water volume
- `Connection`: Links sources to users with max flow and loss rate

**Relationships:**
- `Connection` connects `Source` → `User` with transmission parameters

### Decision Variables

- `Connection.flow` (continuous): Water units allocated from each source to each user

### Objective

Minimize total water cost:
```
minimize sum(flow * source_cost_per_unit)
```

### Constraints

1. **Source capacity**: Total outflow from each source cannot exceed capacity
2. **User demand**: Total inflow to each user (after losses) must meet demand
3. **Connection limits**: Flow on each connection cannot exceed max_flow

## Data

Data files are located in the `data/` subdirectory.

### sources.csv

| Column | Description |
|--------|-------------|
| id | Unique source identifier |
| name | Source name (e.g., Reservoir_A, Groundwater) |
| capacity | Maximum units available |
| cost_per_unit | Cost per unit of water ($) |

### users.csv

| Column | Description |
|--------|-------------|
| id | Unique user identifier |
| name | User name (e.g., Municipal, Industrial) |
| demand | Units of water required |
| priority | Priority level (1=highest) |

### connections.csv

| Column | Description |
|--------|-------------|
| source_id | Reference to source |
| user_id | Reference to user |
| max_flow | Maximum flow on this connection |
| loss_rate | Fraction of water lost in transmission (0.0 to 1.0) |

## Usage

```python
from water_allocation import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Total cost: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python water_allocation.py
```

## Expected Output

```

Status: OPTIMAL
Total cost: $874.28
Flow allocations:
                         name      float
flow_Reservoir_A_Agricultural 500.000000
  flow_Reservoir_A_Industrial 182.065217
   flow_Reservoir_A_Municipal 317.934783
flow_Reservoir_B_Agricultural  56.818182
  flow_Reservoir_B_Industrial 250.000000
   flow_Reservoir_B_Municipal 316.980805
```

The allocation shows water flowing from each reservoir to each user type, meeting all demands while respecting source capacities.