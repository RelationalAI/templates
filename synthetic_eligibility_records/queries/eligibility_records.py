"""Eligibility records report: reads the deployed synthetic_eligibility_records model.

Run `python -m queries.eligibility_records` after `rai models deploy --path model`. Prints
the formulation, the termination status and number of solutions of the latest refresh's
solve, and every generated member record (one row per solution). Prints a no-records
diagnostic when the reference data is over-constrained or the search budget expired. The
report stops on a status other than OPTIMAL (every record enumerated), SOLUTION_LIMIT (the cap
was hit), INFEASIBLE (no record exists), TIME_LIMIT or UNKNOWN (the budget expired).
"""

from model import (
    MAX_RECORDS,
    AgeBucket,
    Plan,
    Provider,
    SolveStatus,
    age_bucket_var,
    model,
    plan_id_var,
    problem,
    provider_id_var,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    problem.display()

    # Status and number of solutions of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    reportable = ("OPTIMAL", "SOLUTION_LIMIT", "INFEASIBLE", "TIME_LIMIT", "UNKNOWN")
    if len(status) != 1 or status[0] not in reportable:
        raise SystemExit(f"Unexpected termination status {status}")
    si = problem.solve_info()
    print(f"\nSolve result:\n• status: {', '.join(status)}\n• num_points: {si.num_points}\n")

    if si.num_points is None or si.num_points == 0:
        print(
            "\nThe solver returned no eligibility records. See the printed solve status "
            "above and the troubleshooting section in the README for likely causes "
            "(over-constrained reference data, mismatched plan/provider networks, or "
            "the search budget expired before a record was found)."
        )

    # ----------------------------------------------
    # Inspect every generated member record
    # ----------------------------------------------

    # `Variable.values(sol_idx, value)` indexes the solver's outputs across
    # every returned solution; binding the value slot to a reference Concept's
    # `.id` walks the chosen ID back to that record's columns in one step.
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
        .where(
            age_bucket_var.values(sol_idx, AgeBucket.id),
            plan_id_var.values(sol_idx, Plan.id),
            provider_id_var.values(sol_idx, Provider.id),
        )
        .to_df()
        .sort_values("solution")
        .reset_index(drop=True)
    )
    print(f"\nGenerated member records (up to {MAX_RECORDS} per run):")
    print(records_df.to_string(index=False))
