"""Report from the deployed model: butterfly (scatter-gather) motifs.

Run after `rai models deploy --path model`:
    python -m queries.butterfly_motifs
"""

from model import Account, Transaction, model
from model.butterfly import (
    MAX_BUTTERFLY_MOTIFS,
    ButterflyDest,
    ButterflyEdge,
    ButterflyHub,
    ButterflySource,
    NumPoints,
    SolveStatus,
)
from relationalai.semantics import Integer

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("BUTTERFLY (scatter-gather with per-hub conservation)")
    print("CSP technique: per-vertex aggregate equality over decision-selected edge subset")
    print("=" * 70)

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
    points = model.select(NumPoints).to_df().iloc[:, 0].tolist()
    motif_count = points[0] if points else 0
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
    solution = Integer.ref()
    model.select(
        solution.alias("solution"),
        Transaction.tx_id.alias("tx_id"),
        Transaction.src.id.alias("src_account_id"),
        Transaction.src.name.alias("src_name"),
        Transaction.dst.id.alias("dst_account_id"),
        Transaction.dst.name.alias("dst_name"),
        Transaction.amount_dollars.alias("amount"),
        Transaction.ts_minutes.alias("ts_min"),
    ).where(ButterflyEdge(solution, Transaction)).inspect()

    print("\nButterfly: chosen motif hubs per solution (with shared beneficial owner):")
    model.select(
        solution.alias("solution"),
        Account.id.alias("hub_id"),
        Account.name.alias("hub_name"),
        Account.bo_id.alias("bo_id"),
    ).where(ButterflyHub(solution, Account)).inspect()

    print("\nButterfly: chosen motif source and destination per solution:")
    source, dest = Account.ref(), Account.ref()
    model.select(
        solution.alias("solution"),
        source.id.alias("source_id"),
        source.name.alias("source_name"),
        dest.id.alias("dest_id"),
        dest.name.alias("dest_name"),
    ).where(ButterflySource(solution, source), ButterflyDest(solution, dest)).inspect()
