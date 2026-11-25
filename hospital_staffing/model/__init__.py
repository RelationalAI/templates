"""Hospital Staffing (prescriptive optimization) template: the model.

Nurse scheduling with two competing objectives, overtime cost and unmet patient
demand, traded off by the epsilon-constraint method: two anchor solves bound the range
of unmet demand, and each sweep point minimizes overtime cost under a cap on total
unmet demand within that range, tracing overtime cost against service level.

Every solve is a named Problem in the model: the two anchors, and the sweep points whose
unmet-demand bounds are rules over the anchors' results, so one refresh solves the anchors
first and then the sweep (`shift_staffing.py`). The model then reads the results as an
efficient frontier: which solves lie on it, the marginal cost of each step along it, the knee,
and the nurses on each shift at the knee (`frontier_analysis.py`).

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solves.
    `python -m queries.staffing_frontier` then prints the report from the deployed model.
"""

from .frontier_analysis import FreeKnee, FrontierStep, JumpKnee, KneeRoster
from .schema import FrontierPoint, Nurse, Shift, SweepPoint, model
from .shift_staffing import N_INTERIOR
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "N_INTERIOR",
    "FreeKnee",
    "FrontierPoint",
    "FrontierStep",
    "JumpKnee",
    "KneeRoster",
    "Nurse",
    "Shift",
    "SweepPoint",
    "model",
]
