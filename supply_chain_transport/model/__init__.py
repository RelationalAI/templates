"""Supply Chain Transport (prescriptive optimization) template: the model.

This package demonstrates a multi-mode transportation optimization model in RelationalAI:

- Load sample CSVs describing freight groups with inventory and transport time windows.
- Model freight groups, transport types (TL/LTL), and LTL cost segments as *concepts*
  with typed properties.
- Choose shipment quantities, transport mode indicators, and arrival days per freight group.
- Enforce inventory flow conservation, all-or-nothing shipment, capacity limits, and
  piecewise-linear LTL cost structure.
- Minimize total cost (inventory holding + TL fixed cost + LTL variable cost).

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.transport_plan` then prints the report from the deployed model.
"""

from .reasoning import (
    FreightGroup_ref,
    SolveStatus,
    TotalTransportCost,
    problem,
    time_period_ref,
    x_inv,
    x_qty_tra,
)
from .schema import FreightGroup, TransportType, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "FreightGroup",
    "FreightGroup_ref",
    "SolveStatus",
    "TotalTransportCost",
    "TransportType",
    "model",
    "problem",
    "time_period_ref",
    "x_inv",
    "x_qty_tra",
]
