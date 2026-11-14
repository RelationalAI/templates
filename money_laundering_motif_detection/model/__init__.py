"""Money-laundering motif detection: one model, three motif solves.

The shared ontology (`ontology.py`) and the three motifs (`butterfly.py`,
`kyc_burst.py`, `smurf_army.py`) form one model. `rai models deploy --path
model` deploys it, and each refresh of the deployment runs all three solves.
Each `queries/<motif>_motifs.py` prints one motif's report from the deployed
model.
"""

from . import butterfly, kyc_burst, smurf_army
from .ontology import Account, Transaction, model

__all__ = ["Account", "Transaction", "butterfly", "kyc_burst", "model", "smurf_army"]
