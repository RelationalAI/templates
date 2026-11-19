"""Eligibility records report: reads the deployed synthetic_eligibility_records model.

Run `python -m queries.eligibility_records` after `rai models deploy --path model`. Prints
the status and number of solutions of the latest refresh's solve and every generated member
record (one row per solution). Prints a no-records diagnostic when the reference data is
over-constrained or the search budget expired.
"""

from model import (
    MAX_RECORDS,
    AgeBucket,
    MemberRecord,
    NumPoints,
    Plan,
    Provider,
    SolveStatus,
    model,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    points = model.select(NumPoints).to_df().iloc[:, 0].tolist()
    num_points = points[0] if points else 0
    print(f"\nSolve result:\n• status: {', '.join(status)}\n• num_points: {num_points}\n")

    if num_points == 0:
        print(
            "\nThe solver returned no eligibility records. See the printed solve status "
            "above and the troubleshooting section in the README for likely causes "
            "(over-constrained reference data, mismatched plan/provider networks, or "
            "the search budget expired before a record was found)."
        )

    # ----------------------------------------------
    # Inspect every generated member record
    # ----------------------------------------------

    # `MemberRecord` holds every returned solution's age bucket, plan and
    # provider, so one select reads each record's columns in one step.
    # Every row prints `age_years` next to `plan_type` and `plan_network` next to
    # `provider_network`, so the age-by-plan rule and the network attribution
    # can be read off the table.

    sol_idx = Integer.ref()
    records_df = (
        model.select(
            sol_idx.alias("solution"),
            AgeBucket.age_years.alias("age_years"),
            Plan.plan_type.alias("plan_type"),
            Plan.network_id.alias("plan_network"),
            Provider.network_id.alias("provider_network"),
            Provider.name.alias("provider"),
        )
        .where(MemberRecord(sol_idx, AgeBucket, Plan, Provider))
        .to_df()
        .sort_values("solution")
        .reset_index(drop=True)
    )
    print(f"\nGenerated member records (up to {MAX_RECORDS} per run):")
    print(records_df.to_string(index=False))
