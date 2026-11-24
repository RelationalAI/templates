"""Disease Outbreak Prevention Network (graph analytics) template: the model.

This package declares a public health network and its weighted degree centrality in
RelationalAI:

- Load a network of healthcare facilities and their connections from CSV.
- Calculate weighted degree centrality for each facility (considering connection weights).
- Calculate each facility's incoming and outgoing connection counts.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which computes the graph metrics.
    `python -m queries.facility_ranking` then prints the ranked report, and
    `streamlit run app.py` starts the interactive app, both from the deployed model.
"""

from .reasoning import graph
from .schema import Facility, FacilityConnection, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "Facility",
    "FacilityConnection",
    "graph",
    "model",
]
