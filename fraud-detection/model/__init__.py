"""Fraud-detection model: schema, the bundled PaySim sample, and the predict-then-optimize reasoning.

Predict-then-optimize on a small bundled demo dataset (~16K transactions,
~50% fraud -- class-balanced to give the GNN enough positive signal on CPU).
`load_local_data()` maps the CSVs through `model.data()`; no Snowflake data
loading or GPU is required. The five stages live in four modules, each of
which imports the modules whose declarations it reads:
  1. Graph       -- PageRank on an Account-Account funds-flow graph, fed to
                    the GNN as a continuous node feature (`account_signals.py`).
  2. Rules       -- `Account.activity_count`, sender-side transaction volume,
                    fed to the GNN as an integer feature (`account_signals.py`).
  3. Predictive  -- GNN binary classification of fraudulent transactions on
                    the Transaction-to-Account bipartite graph
                    (`fraud_classifier.py`).
  4. Bridge      -- alert score combining the GNN probability with the
                    dataset's pre-existing `is_flagged_fraud` heuristic, and
                    the alert queue order (`alert_scores.py`).
  5. Prescriptive-- investigator-budget allocation (knapsack MILP): maximize
                    expected loss averted (alert_score * amount) subject to a
                    fixed-hours audit budget plus a per-receiver cap, compared
                    with a naive sort-and-take queue (`investigation_queue.py`).

The rule-based identity-graph intro remains in fraud_detection_rules.ipynb.

`rai models deploy --path model` deploys everything this package declares. To
run it over your own Snowflake tables, call `load_snowflake_data()` below in
place of `load_local_data()`.
"""

from .account_signals import acct_graph
from .alert_scores import AuditCandidate
from .fraud_classifier import TrainClassBalance, gnn
from .investigation_queue import (
    AUDIT_BUDGET_HOURS,
    AuditQueue,
    AuditUplift,
    SolveObjective,
    SolveStatus,
    problem,
)
from .schema import (
    Account,
    Test,
    TestTable,
    Train,
    TrainTable,
    Transaction,
    Val,
    ValTable,
    model,
)
from .source import load_local_data, load_snowflake_data

load_local_data()

__all__ = [
    "AUDIT_BUDGET_HOURS",
    "Account",
    "AuditCandidate",
    "AuditQueue",
    "AuditUplift",
    "SolveObjective",
    "SolveStatus",
    "Test",
    "TestTable",
    "Train",
    "TrainClassBalance",
    "TrainTable",
    "Transaction",
    "Val",
    "ValTable",
    "acct_graph",
    "gnn",
    "load_snowflake_data",
    "model",
    "problem",
]
