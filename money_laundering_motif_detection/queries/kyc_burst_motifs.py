"""Report from the deployed model: KYC-mix burst cohorts.

Run after `rai models deploy --path model`:
    python -m queries.kyc_burst_motifs
"""

from model import model
from model.kyc_burst import (
    BURST_TARGET_DESTINATION_ID,
    MAX_BURST_MOTIFS,
    SolveStatus,
    is_burst_tx_var,
    is_burst_var,
    problem,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(f"KYC-MIX BURST (fan-in to account id {BURST_TARGET_DESTINATION_ID})")
    print("CSP technique: cardinality over chosen subset")
    print("=" * 70)
    problem.display()

    # No `problem.verify(...)` call: `populate=False` on the `solve_for(...)`
    # calls in `model/kyc_burst.py` means the decision-variable values are NOT written back to
    # the relational `is_burst` / `is_burst_tx` properties. Without those values
    # in the relational layer, verify() cannot re-evaluate ICs that reference
    # them and prints spurious "Requirements not met" warnings instead of
    # doing real verification. The inspect tables below surface the solver's
    # choices directly; manual inspection against the IC formulas is the
    # verification path here.

    # Status of the latest refresh's solve and the number of solutions it found.
    status = ", ".join(model.select(SolveStatus).to_df().iloc[:, 0])
    motif_count = problem.solve_info().num_points or 0
    print(f"\nSolve result:\n• status: {status}\n• num_points: {motif_count}\n")
    if status == "INFEASIBLE":
        print(
            "\nResult: no KYC-mix burst cohort exists under the encoded constraints "
            f"for target id {BURST_TARGET_DESTINATION_ID}. The search space was "
            "exhausted with zero feasible cohorts."
        )
    elif status == "OPTIMAL":
        print(
            f"\nResult: {motif_count} KYC-mix burst cohort(s) found and search exhausted "
            "(no further cohorts exist under the encoded constraints)."
        )
    elif status == "SOLUTION_LIMIT":
        print(
            f"\nResult: {motif_count} KYC-mix burst cohort(s) found; "
            f"hit MAX_BURST_MOTIFS={MAX_BURST_MOTIFS}. "
            "More may exist -- raise the limit to enumerate further."
        )
    else:
        print(
            f"\nResult: search returned status={status} with {motif_count} cohort(s); "
            "did not finish. Raise time_limit_sec or check the README troubleshooting."
        )

    print("\nKYC-burst: chosen burst-tx per solution:")
    sol_idx = Integer.ref()
    val = Integer.ref()
    model.select(
        sol_idx.alias("solution"),
        is_burst_tx_var.transaction.tx_id.alias("tx_id"),
        is_burst_tx_var.transaction.src.id.alias("src_account_id"),
        is_burst_tx_var.transaction.src.name.alias("src_name"),
        is_burst_tx_var.transaction.src.kyc_tier.alias("src_kyc_tier"),
        is_burst_tx_var.transaction.dst.name.alias("dst_name"),
        is_burst_tx_var.transaction.amount_dollars.alias("amount"),
        is_burst_tx_var.transaction.ts_minutes.alias("ts_min"),
    ).where(is_burst_tx_var.values(sol_idx, val), val == 1).inspect()

    print("\nKYC-burst: chosen burst accounts per solution (with KYC tier and jurisdiction):")
    model.select(
        sol_idx.alias("solution"),
        is_burst_var.account.id.alias("burst_id"),
        is_burst_var.account.name.alias("burst_name"),
        is_burst_var.account.kyc_tier.alias("kyc_tier"),
        is_burst_var.account.jurisdiction.alias("jurisdiction"),
        is_burst_var.account.bo_id.alias("bo_id"),
    ).where(is_burst_var.values(sol_idx, val), val == 1).inspect()
