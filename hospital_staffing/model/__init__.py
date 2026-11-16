"""Hospital Staffing (prescriptive optimization) template: the model.

This template demonstrates **multi-objective optimization** via epsilon constraint
for a nurse scheduling problem with two competing objectives:

- **Primary**: Minimize overtime cost
- **Secondary**: Minimize unmet patient demand (service level)

Instead of bundling both into a single weighted objective
(overtime_cost + penalty × unmet_demand), the epsilon constraint method unbundles
them — sweeping the maximum allowed unmet demand from zero to the worst case.
This produces the **efficient frontier** showing exactly how much overtime cost
each level of patient service requires.

TRANSFORMATION FROM SINGLE-OBJECTIVE:
  The original template bundled two concerns into one objective:
    problem.minimize(overtime_cost + PENALTY * sum(Shift.x_unmet_demand))
  The bi-objective version splits them:
    Primary:    problem.minimize(overtime_cost)
    Secondary → constraint: problem.satisfy(require(sum(Shift.x_unmet_demand) <= eps))
  This eliminates the arbitrary penalty weight and reveals the true tradeoff.
  The same "unbundle the penalty" pattern applies to any template that combines
  a primary cost with a penalty term (machine_maintenance, demand_planning,
  supply_chain_transport, supplier_reliability).

Every solve is a named Problem in the model: the two anchors, and the sweep points whose
unmet-demand bounds are rules over the anchors' results, so one refresh solves the anchors
first and then the sweep.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.staffing_frontier` then prints the report from the deployed model.
"""

from .reasoning import N_INTERIOR
from .schema import FrontierPoint, Nurse, Shift, SweepPoint, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "N_INTERIOR", "FrontierPoint", "Nurse", "Shift", "SweepPoint", "model"]
