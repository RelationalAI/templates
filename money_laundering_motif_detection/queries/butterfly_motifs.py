"""Report from the deployed model: butterfly (scatter-gather) motifs.

Run after `rai models deploy --path model`:
    python -m queries.butterfly_motifs
"""

from model import model
from model.butterfly import (
    MAX_BUTTERFLY_MOTIFS,
    SolveStatus,
    is_dest_var,
    is_hub_var,
    is_motif_var,
    is_source_var,
    problem,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("BUTTERFLY (scatter-gather with per-hub conservation)")
    print("CSP technique: per-vertex aggregate equality over decision-selected edge subset")
    print("=" * 70)
    problem.display()

    # No `problem.verify(...)` call: `populate=False` on the `solve_for(...)`
    # calls in `model/butterfly.py` means the decision-variable values are NOT written back to
    # the relational `is_motif` / `is_source` / `is_hub` / `is_dest` properties.
    # Without those values in the relational layer, verify() cannot re-evaluate
    # ICs that reference them and prints spurious "Requirements not met"
    # warnings instead of doing real verification. The inspect tables below
    # surface the solver's choices directly; manual inspection against the IC
    # formulas is the verification path here.

    # Status of the latest refresh's solve and the number of solutions it found.
    status = ", ".join(model.select(SolveStatus).to_df().iloc[:, 0])
    motif_count = problem.solve_info().num_points or 0
    print(f"\nSolve result:\n• status: {status}\n• num_points: {motif_count}\n")
    if status == "INFEASIBLE":
        print(
            "\nResult: no butterfly motifs exist under the encoded constraints. "
            "The search space was exhausted with zero feasible motifs."
        )
    elif status == "OPTIMAL":
        print(
            f"\nResult: {motif_count} butterfly motif(s) found and search exhausted "
            "(no further motifs exist under the encoded constraints)."
        )
    elif status == "SOLUTION_LIMIT":
        print(
            f"\nResult: {motif_count} butterfly motif(s) found; "
            f"hit MAX_BUTTERFLY_MOTIFS={MAX_BUTTERFLY_MOTIFS}. "
            "More may exist -- raise the limit to enumerate further."
        )
    else:
        print(
            f"\nResult: search returned status={status} with {motif_count} motif(s); "
            "did not finish. Raise time_limit_sec or check the README troubleshooting."
        )

    print("\nButterfly: chosen motif transactions (one row per motif edge per solution):")
    sol_idx = Integer.ref()
    val = Integer.ref()
    model.select(
        sol_idx.alias("solution"),
        is_motif_var.transaction.tx_id.alias("tx_id"),
        is_motif_var.transaction.src.id.alias("src_account_id"),
        is_motif_var.transaction.src.name.alias("src_name"),
        is_motif_var.transaction.dst.id.alias("dst_account_id"),
        is_motif_var.transaction.dst.name.alias("dst_name"),
        is_motif_var.transaction.amount_dollars.alias("amount"),
        is_motif_var.transaction.ts_minutes.alias("ts_min"),
    ).where(is_motif_var.values(sol_idx, val), val == 1).inspect()

    print("\nButterfly: chosen motif hubs per solution (with shared beneficial owner):")
    model.select(
        sol_idx.alias("solution"),
        is_hub_var.account.id.alias("hub_id"),
        is_hub_var.account.name.alias("hub_name"),
        is_hub_var.account.bo_id.alias("bo_id"),
    ).where(is_hub_var.values(sol_idx, val), val == 1).inspect()

    print("\nButterfly: chosen motif source and destination per solution:")
    src_sol = Integer.ref()
    src_val = Integer.ref()
    dst_sol = Integer.ref()
    dst_val = Integer.ref()
    model.select(
        src_sol.alias("solution"),
        is_source_var.account.id.alias("source_id"),
        is_source_var.account.name.alias("source_name"),
        is_dest_var.account.id.alias("dest_id"),
        is_dest_var.account.name.alias("dest_name"),
    ).where(
        is_source_var.values(src_sol, src_val),
        src_val == 1,
        is_dest_var.values(dst_sol, dst_val),
        dst_val == 1,
        src_sol == dst_sol,
    ).inspect()
