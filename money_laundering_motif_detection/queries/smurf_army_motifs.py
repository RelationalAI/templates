"""Report from the deployed model: smurf-army cohorts.

Run after `rai models deploy --path model`:
    python -m queries.smurf_army_motifs
"""

from model import Account, Transaction, model
from model.smurf_army import (
    MAX_SMURF_MOTIFS,
    SMURF_TARGET_DESTINATION_ID,
    NumPoints,
    SmurfAccount,
    SmurfTx,
    SolveStatus,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"SMURF ARMY (fan-in to account id {SMURF_TARGET_DESTINATION_ID})")
    print("CSP technique: pairwise distinctness + sum-target over chosen subset")
    print("=" * 70)

    # No `problem.verify(...)` call: `populate=False` on the `solve_for(...)`
    # calls in `model/smurf_army.py` means the decision-variable values are NOT written back to
    # the relational `is_smurf` / `is_smurf_tx` properties. Without those values
    # in the relational layer, verify() cannot re-evaluate ICs that reference
    # them and prints spurious "Requirements not met" warnings instead of
    # doing real verification. The inspect tables below surface the solver's
    # choices directly; manual inspection against the IC formulas is the
    # verification path here.

    # Status of the latest refresh's solve and the number of solutions it found.
    status = ", ".join(model.select(SolveStatus).to_df().iloc[:, 0])
    points = model.select(NumPoints).to_df().iloc[:, 0].tolist()
    motif_count = points[0] if points else 0
    print(f"\nSolve result:\n• status: {status}\n• num_points: {motif_count}\n")
    if status == "INFEASIBLE":
        print(
            "\nResult: no smurf-army cohort exists under the encoded constraints "
            f"for target id {SMURF_TARGET_DESTINATION_ID}. The search space was "
            "exhausted with zero feasible cohorts."
        )
    elif status == "OPTIMAL":
        print(
            f"\nResult: {motif_count} smurf-army cohort(s) found and search exhausted "
            "(no further cohorts exist under the encoded constraints)."
        )
    elif status == "SOLUTION_LIMIT":
        print(
            f"\nResult: {motif_count} smurf-army cohort(s) found; "
            f"hit MAX_SMURF_MOTIFS={MAX_SMURF_MOTIFS}. "
            "More may exist -- raise the limit to enumerate further."
        )
    else:
        print(
            f"\nResult: search returned status={status} with {motif_count} cohort(s); "
            "did not finish. Raise time_limit_sec or check the README troubleshooting."
        )

    print("\nSmurf army: chosen smurf-tx per solution:")
    solution = Integer.ref()
    model.select(
        solution.alias("solution"),
        Transaction.tx_id.alias("tx_id"),
        Transaction.src.id.alias("src_account_id"),
        Transaction.src.name.alias("src_name"),
        Transaction.src.bo_id.alias("src_bo_id"),
        Transaction.dst.name.alias("dst_name"),
        Transaction.amount_dollars.alias("amount"),
        Transaction.ts_minutes.alias("ts_min"),
    ).where(SmurfTx(solution, Transaction)).inspect()

    print("\nSmurf army: chosen smurf accounts per solution (with distinct BOs and jurisdictions):")
    model.select(
        solution.alias("solution"),
        Account.id.alias("smurf_id"),
        Account.name.alias("smurf_name"),
        Account.bo_id.alias("bo_id"),
        Account.kyc_tier.alias("kyc_tier"),
        Account.jurisdiction.alias("jurisdiction"),
    ).where(SmurfAccount(solution, Account)).inspect()
