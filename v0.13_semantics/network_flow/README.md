---
title: "Network Flow"
description: "Find the maximum flow through a network from source to sink."
featured: false
experience_level: beginner
industry: "Supply Chain"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - LP
  - Network Flow
---

# Network Flow

## What is this problem?

The maximum flow problem is a fundamental network optimization: given a network of nodes and edges with capacity limits, find the maximum amount of "flow" that can be pushed from a source node to a sink node. Flow must be conserved at intermediate nodes—what flows in must flow out.

This template models a simple network where node 1 is the source (origin of flow) and the highest-numbered node is the sink (destination).

This is a fundamental problem with applications in transportation planning, telecommunications, and supply chain logistics.

## Why is optimization valuable?

- **Capacity analysis**: Determine the maximum throughput of a network given current infrastructure <!-- TODO: Add % improvement from results -->
- **Bottleneck identification**: Find which edges limit overall flow (the "min-cut"), enabling targeted infrastructure investment
- **What-if scenarios**: Quantify the impact of adding capacity to specific edges before committing to expensive upgrades

## What are similar problems?

- **Highway traffic flow**: Determine maximum vehicle throughput from suburbs to downtown
- **Data center bandwidth**: Find maximum data transfer rate between servers through network switches
- **Pipeline capacity**: Determine maximum oil/gas flow through a pipeline network
- **Supply chain throughput**: Find maximum product flow from suppliers through distribution to customers

## Problem Details

### Model

**Concepts:**
- `Node`: Network locations (sources, sinks, transshipment points)
- `Arc`: Connections between nodes with capacity and cost
- `Flow`: Decision entity for flow amount on each arc

**Relationships:**
- `Arc` connects source `Node` → destination `Node`

### Decision Variables

- `Edge.flow` (continuous): Flow on each edge

### Objective

Maximize total flow reaching the sink:
```
maximize sum(flow into sink)
```

### Constraints

1. **Capacity**: Flow on each edge cannot exceed edge capacity
2. **Conservation**: At each intermediate node, inflow equals outflow

## Data

Data files are located in the `data/` subdirectory.

### edges.csv

| Column | Description |
|--------|-------------|
| i | Source node of the edge |
| j | Target node of the edge |
| cap | Maximum flow capacity of this edge |

Node 1 is the source, and the highest-numbered node is the sink.

## Usage

```python
from network_flow import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Maximum flow: {result['objective']:.0f}")
print(result['variables'])
```

Or run directly:

```bash
python network_flow.py
```

## Expected Output

```
Status: OPTIMAL
Maximum flow: 13

Edge flows:
i j  flow
1 2   5.0
1 3   8.0
2 4   4.0
2 5   1.0
3 5   5.0
3 6   3.0
4 6   4.0
5 6   6.0
```
