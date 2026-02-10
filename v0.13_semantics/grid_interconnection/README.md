---
title: "Grid Interconnection"
description: "Approve data center interconnection requests and substation upgrades to maximize net revenue within capital budget."
featured: false
experience_level: intermediate
industry: "Energy & Utilities"
reasoning_types:
  - Prescriptive
tags:
  - Design
  - MILP
---

# Grid Interconnection

## What is this problem?

Utilities managing power grid infrastructure face a surge of data center interconnection requests. AI training facilities, hyperscale cloud campuses, and enterprise colocation sites each require substantial substation capacity (80-350 MW) and connection infrastructure. With limited capital budgets and substation capacity constraints, utilities must strategically select which projects to approve and where to invest in infrastructure upgrades.

This template models the capital allocation decision: maximizing net revenue (10-year NPV minus connection costs) from approved data center projects while managing substation capacity limits and upgrade investments.

## Why is optimization valuable?

- **Investment prioritization**: Identify the highest-value portfolio of data center projects given budget and infrastructure constraints
- **Infrastructure planning**: Determine which substation upgrades provide the best return on investment
- **Budget sensitivity**: Evaluate how different capital budgets affect which projects get approved and total net revenue

## What are similar problems?

- **Telecom tower site selection**: Choose cell tower locations balancing coverage, capacity, and installation costs
- **Cloud resource allocation**: Assign workloads to servers across availability zones with capacity and cost constraints
- **Retail network planning**: Select store locations considering market potential, real estate costs, and distribution reach
- **Renewable interconnection queues**: Prioritize solar/wind projects competing for limited grid capacity

## Problem Details

### Model

**Concepts:**
- `Substation`: Grid connection points with current capacity (MW)
- `Project`: Data center interconnection requests with capacity needs, 10-year revenue (NPV), and connection costs
- `Upgrade`: Substation capacity expansion options with cost and added capacity

**Relationships:**
- `Project` connects to `Substation` for grid access
- `Upgrade` applies to `Substation` for capacity expansion

### Decision Variables

- `Project.approved` (binary): 1 if project is approved, 0 otherwise
- `Upgrade.selected` (binary): 1 if substation upgrade is performed, 0 otherwise

### Objective

Maximize net revenue:
```
maximize sum(approved * (revenue - connection_cost))
```

Revenue represents 10-year NPV of each data center project. Connection cost is the one-time infrastructure cost to connect the project to the grid.

### Constraints

1. **Capacity**: Total capacity of approved projects at each substation cannot exceed current capacity plus upgrades
2. **Single upgrade**: At most one upgrade can be selected per substation
3. **Budget**: Total investment (connection costs + upgrade costs) must be within budget

## Data

Data files are located in the `data/` subdirectory.

### substations.csv

6 substations with varying current capacity (220-500 MW).

| Column | Description |
|--------|-------------|
| id | Unique substation identifier |
| name | Substation name (e.g., Permian_Basin, Dallas_North) |
| current_capacity | Existing capacity (MW) |
| max_capacity | Maximum possible capacity after upgrades (MW) |

### projects.csv

14 data center interconnection requests spanning AI training, hyperscale cloud, and enterprise colocation facilities.

| Column | Description |
|--------|-------------|
| id | Unique project identifier |
| name | Project name (e.g., Stargate_Phase2, xAI_Permian, HyperCloud_DFW) |
| substation_id | Substation where project connects |
| capacity_needed | Capacity required (MW), ranges 80-350 MW |
| revenue | 10-year NPV ($), ranges $176M-$2.03B |
| connection_cost | One-time connection cost ($), ranges $85M-$520M |

Revenue margins vary by project type: AI training (64-74%), hyperscale cloud (61-65%), enterprise colocation (47-55%).

### upgrades.csv

12 upgrade options (2 per substation) with capacity additions of 100-500 MW and costs of $90M-$420M.

| Column | Description |
|--------|-------------|
| id | Unique upgrade identifier |
| substation_id | Substation to upgrade |
| capacity_added | Additional capacity from upgrade (MW) |
| upgrade_cost | Cost of upgrade ($) |

## Usage

```bash
python grid_interconnection.py
```

## Expected Output

```
Running scenario: budget = 500000000
  Status: OPTIMAL, Objective: 1200000000.0

  Approved projects:
  ...

Running scenario: budget = 1000000000
  Status: OPTIMAL, Objective: 2710000000.0

  Approved projects:
  ...

Running scenario: budget = 2000000000
  Status: OPTIMAL, Objective: 4398000000.0

  Approved projects:
  ...

==================================================
Scenario Analysis Summary
==================================================
  500000000: OPTIMAL, obj=1200000000.0
  1000000000: OPTIMAL, obj=2710000000.0
  2000000000: OPTIMAL, obj=4398000000.0
```

At $500M, only a few high-margin projects can be approved. Doubling the budget to $1B more than doubles net revenue ($2.71B) as additional projects and substation upgrades become affordable. At $2B, most viable projects are approved, yielding $4.4B in net revenue.

## Scenario Analysis

This template includes **budget sensitivity analysis** — how does capital budget affect which data center projects get approved and total net revenue?

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `budget` | Numeric | `500000000`, `1000000000`, `2000000000` | Total capital budget for connection costs and substation upgrades |

At $500M budget, only the highest-margin projects are feasible ($1.2B net revenue). At $1B, the optimizer can approve additional projects and fund substation upgrades to unlock capacity ($2.71B net revenue, +126%). At $2B, most viable projects are approved ($4.4B), but returns diminish as remaining projects have lower margins or require expensive upgrades.

---

## Next steps

- Add entity exclusion scenarios (e.g., exclude a substation for maintenance) to analyze infrastructure resilience.
- Extend with multi-period planning to model phased project approvals over time.
- Add priority tiers or contractual commitments as additional constraints.
