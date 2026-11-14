"""Synthetic Eligibility Records (constrained generation, multi-solution) template: the model.

Generate K distinct, internally consistent member eligibility records per
solve. Each record is a tuple of three categorical decisions (age bucket,
plan, primary care provider) that satisfies CMS Medicare-eligibility,
age-by-plan-type cascading functional dependencies, and PCP-network
attribution. Solve as constraint satisfaction with `solution_limit=K`
(MiniZinc) and enumerate every feasible record via
`Variable.values(solution_index, value)` -- synthetic-data tooling consumers
(test-data generation, claim-engine fuzzing, RegTech rules certification)
want a batch of records per solve, not one.

Run:
    `rai models deploy --path model` deploys this package to the schemas in raiconfig.yaml
    and waits for its first refresh, which runs the solve.
    `python -m queries.eligibility_records` then prints the report from the deployed model.
"""

from .reasoning import (
    MAX_RECORDS,
    SENIOR_THRESHOLD_YEARS,
    NumPoints,
    SolveStatus,
    age_bucket_var,
    plan_id_var,
    problem,
    provider_id_var,
)
from .schema import AgeBucket, Plan, Provider, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "MAX_RECORDS",
    "SENIOR_THRESHOLD_YEARS",
    "AgeBucket",
    "NumPoints",
    "Plan",
    "Provider",
    "SolveStatus",
    "age_bucket_var",
    "model",
    "plan_id_var",
    "problem",
    "provider_id_var",
]
