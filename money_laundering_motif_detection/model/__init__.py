"""Money-laundering motif detection: one model, three motif solves.

The shared schema (`schema.py`) and sample data (`source.py`) feed three
independent motif problems (`butterfly.py`, `kyc_burst.py`, `smurf_army.py`),
each with its own decisions, constraints, and solver settings. `rai models
deploy --path model` deploys this package to the schemas in raiconfig.yaml, and
each refresh of the deployment runs all three solves. Each
`queries/<motif>_motifs.py` prints one motif's report from the deployed model.
"""

from . import butterfly, kyc_burst, smurf_army
from .schema import Account, Transaction, model
from .source import DATA_DIR

__all__ = ["DATA_DIR", "Account", "Transaction", "butterfly", "kyc_burst", "model", "smurf_army"]
