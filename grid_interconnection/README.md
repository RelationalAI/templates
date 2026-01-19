# Grid Interconnection

Approve renewable energy projects and substation upgrades to maximize net revenue.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Design |
| **Industry** | Energy / Utilities |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

Electric utilities face a growing queue of renewable energy projects seeking grid connection—solar farms, wind installations, and battery storage facilities. Each project requires substation capacity and connection infrastructure. With limited budgets and capacity constraints, utilities must strategically select which projects to approve and where to invest in infrastructure upgrades.

This template models the capital allocation decision: maximizing long-term revenue from approved projects while managing connection costs and substation capacity limits.

## Why is optimization valuable?

- **Investment prioritization**: Identify the highest-value portfolio of projects given budget and infrastructure constraints <!-- TODO: Add % improvement from results -->
- **Infrastructure planning**: Determine which substation upgrades provide the best return on investment
- **Scenario analysis**: Evaluate how different budget levels or capacity expansions affect project approvals before committing capital

## What are similar problems?

- **Data center server placement**: Decide which servers to deploy across racks with power and cooling constraints
- **Telecom tower site selection**: Choose cell tower locations balancing coverage, capacity, and installation costs
- **Retail network planning**: Select store locations considering market potential, real estate costs, and distribution reach
- **Cloud resource allocation**: Assign workloads to servers across availability zones with capacity and cost constraints

## Problem Description

An electric utility evaluates renewable energy projects (solar farms, wind farms, batteries) that want to connect to the grid. Each project connects to a specific substation, generates annual revenue, and requires a connection cost. Substations have capacity limits that can be expanded through upgrades.

The goal is to decide which projects to approve and which substation upgrades to make to maximize net revenue (annual revenue minus costs) while staying within budget.

### Decision Variables

- `Project.approved` (binary): 1 if project is approved, 0 otherwise
- `Upgrade.selected` (binary): 1 if substation upgrade is performed, 0 otherwise

### Objective

Maximize net value:
```
maximize sum(approved * (annual_revenue - connection_cost))
```

Note: This simplified formulation treats connection costs (one-time) and annual revenue as comparable for ranking purposes. In practice, you would discount annual revenue over a planning horizon or use NPV calculations.

### Constraints

1. **Capacity**: Total capacity of approved projects at each substation cannot exceed current capacity plus upgrades
2. **Single upgrade**: At most one upgrade can be selected per substation
3. **Budget**: Total investment (connection costs + upgrade costs) must be within budget

## Data

Data files are located in the `data/` subdirectory.

### substations.csv

| Column | Description |
|--------|-------------|
| id | Unique substation identifier |
| name | Substation name |
| current_capacity | Existing capacity (MW) |
| max_capacity | Maximum possible capacity after upgrades (MW) |

### projects.csv

| Column | Description |
|--------|-------------|
| id | Unique project identifier |
| name | Project name (e.g., Solar_Farm_A) |
| substation_id | Substation where project connects |
| capacity_needed | Capacity required (MW) |
| annual_revenue | Expected annual revenue ($) |
| connection_cost | One-time connection cost ($) |

### upgrades.csv

| Column | Description |
|--------|-------------|
| id | Unique upgrade identifier |
| substation_id | Substation to upgrade |
| capacity_added | Additional capacity from upgrade (MW) |
| upgrade_cost | Cost of upgrade ($) |

## Usage

```python
from grid_interconnection import solve, extract_solution

# Run optimization with $500,000 budget
solver_model = solve(budget=500000)
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Net revenue: ${result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python grid_interconnection.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Net Annual Revenue: $X.XX
...
```
