"""Traveling salesman (prescriptive optimization) template: the model.

This package demonstrates a mixed-integer linear optimization (MILP) problem
in RelationalAI:

- Load a directed distance matrix from CSV.
- Model the traveling salesman problem (TSP) as a MILP using the MTZ subtour
  elimination formulation.
- Solve for the shortest Hamiltonian cycle and print the selected edges.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.tour` then prints the report from the deployed model.
"""

from .reasoning import NumMinObjectives, NumVariables, SolveStatus, TourDistance, problem
from .schema import Edge, Node, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Edge",
    "Node",
    "NumMinObjectives",
    "NumVariables",
    "SolveStatus",
    "TourDistance",
    "model",
    "problem",
]
