"""Fraud-detection model: schema, the bundled PaySim sample, and the predict-then-optimize reasoning.

Predict-then-optimize on a small bundled demo dataset (~16K transactions,
~50% fraud -- class-balanced to give the GNN enough positive signal on CPU).
`load_local_data()` maps the CSVs through `model.data()`; no Snowflake data
loading or GPU is required. The five stages are declared in `model/reasoning.py`:
  1. Graph       -- PageRank on an Account-Account funds-flow graph, fed to
                    the GNN as a continuous node feature.
  2. Rules       -- `Account.activity_count`, sender-side transaction volume,
                    fed to the GNN as an integer feature.
  3. Predictive  -- GNN binary classification of fraudulent transactions on
                    the Transaction-to-Account bipartite graph.
  4. Bridge      -- alert score combining the GNN probability with the
                    dataset's pre-existing `is_flagged_fraud` heuristic.
  5. Prescriptive-- investigator-budget allocation (knapsack MILP): maximize
                    expected loss averted (alert_score * amount) subject to a
                    fixed-hours audit budget plus a per-receiver cap.

The rule-based identity-graph intro remains in fraud_detection_rules.ipynb.

`rai models deploy --path model` deploys everything this package declares. To
run it over your own Snowflake tables, call `load_snowflake_data()` below in
place of `load_local_data()`.
"""

from .reasoning import (
    AUDIT_BUDGET_HOURS,
    AuditCandidate,
    SolveObjective,
    SolveStatus,
    gnn,
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
from .source import (
    LARGE_AMOUNT_THRESHOLD,
    LARGE_AUDIT_COST_HOURS,
    SMALL_AUDIT_COST_HOURS,
    load_local_data,
    load_snowflake_data,
)

load_local_data(
    large_amount_threshold=LARGE_AMOUNT_THRESHOLD,
    small_audit_cost_hours=SMALL_AUDIT_COST_HOURS,
    large_audit_cost_hours=LARGE_AUDIT_COST_HOURS,
)

__all__ = [
    "AUDIT_BUDGET_HOURS",
    "Account",
    "AuditCandidate",
    "SolveObjective",
    "SolveStatus",
    "Test",
    "TestTable",
    "Train",
    "TrainTable",
    "Transaction",
    "Val",
    "ValTable",
    "gnn",
    "load_snowflake_data",
    "model",
    "problem",
]
