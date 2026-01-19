# Traveling Salesman

Find the shortest route visiting all cities exactly once and returning to the start.

## Classification

| Dimension | Value |
|-----------|-------|
| **Reasoner** | Prescriptive |
| **Problem Type** | Routing |
| **Industry** | Logistics / Routing |
| **Method** | MILP (Mixed-Integer Linear Programming) |
| **Complexity** | Intermediate |

## What is this problem?

The traveling salesman problem (TSP) is one of the most studied optimization problems. A salesperson (or vehicle, robot, or tool) must visit multiple locations and return to the start. The challenge is finding the shortest route among the astronomical number of possibilities—for just 20 cities, there are over 60 quadrillion possible routes.

This template provides a working MILP formulation using subtour elimination constraints, making it a foundation for real-world routing applications.

## Why is optimization valuable?

- **Distance reduction**: Finding optimal routes reduces travel compared to intuitive or greedy approaches <!-- TODO: Add % improvement from results -->
- **Fuel and time savings**: Shorter routes directly translate to lower fuel costs and faster completion times
- **Scalable methodology**: The same formulation extends to larger instances with solution quality guarantees

## What are similar problems?

- **Delivery routing**: Optimize package delivery sequences for couriers, food delivery, or postal services
- **Field service dispatch**: Plan technician routes visiting customer sites for repairs or installations
- **Manufacturing toolpaths**: Minimize drill or laser head movement visiting multiple positions on a workpiece
- **Genome sequencing**: Find optimal orderings of DNA fragments for assembly

## Problem Description

A salesperson needs to visit a set of cities and return to the starting city. Each pair of cities has a known travel distance. The salesperson must visit each city exactly once.

The goal is to find the shortest possible route (tour) that visits all cities and returns to the origin.

This template uses the Miller-Tucker-Zemlin (MTZ) formulation, which adds ordering variables to prevent "subtours" (disconnected loops that don't include all cities).

### Decision Variables

- `Edge.x_edge` (binary): 1 if edge is included in tour, 0 otherwise
- `Node.u_node` (integer): Position of node in the tour sequence (for subtour elimination)

### Objective

Minimize total tour distance:
```
minimize sum(distance * x_edge) for all selected edges
```

### Constraints

1. **Degree constraints**: Each city has exactly one incoming and one outgoing edge
2. **Subtour elimination**: MTZ ordering constraints ensure a single connected tour

## Data

Data files are located in the `data/` subdirectory.

### distances.csv

| Column | Description |
|--------|-------------|
| i | Origin city (node number) |
| j | Destination city (node number) |
| dist | Distance between cities |

The file contains all directed edges (i→j and j→i separately).

## Usage

```python
from traveling_salesman import solve, extract_solution

# Run optimization
solver_model = solve()
result = extract_solution(solver_model)

print(f"Status: {result['status']}")
print(f"Tour distance: {result['objective']:.2f}")
print(result['variables'])
```

Or run directly:

```bash
python traveling_salesman.py
```

## Expected Output

<!-- TODO: Run template and paste actual output here -->
```
Status: OPTIMAL
Shortest tour distance: X.XX
...
```
