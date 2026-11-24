"""Audit report: reads the deployed underwriting_audit model.

Run `python -m queries.audit_report` after `rai models deploy --path model`. For each property
in the catalog, prints the verdict (PASS, FAIL, or INCONCLUSIVE) classified from the status and
number of witnesses of the latest refresh's solve and, for FAILs, the witness table, then a
verdict-matrix recap covering every property.
"""

from model import (
    MAX_WITNESSES,
    PROPERTIES,
    AgeBucket,
    CoverageBand,
    NumPoints,
    SolveStatus,
    Witness,
    model,
)
from pandas import set_option as pd_set_option
from relationalai.semantics import Integer, String

# Make sure every column of the witness table makes it into the printed
# output; the default pandas display width collapses to "..." when more
# than ~80 chars wide, which would hide the indicator columns the audit
# is supposed to surface.
pd_set_option("display.max_columns", None)
pd_set_option("display.width", 200)


def _classify_verdict(status, num_points):
    """Map solver termination + witness count to an audit verdict.

    - Any status with num_points >= 1 -> FAIL: a counterexample exists,
      which falsifies the property regardless of whether the search was
      exhaustive. The witness count is partial when status is not
      OPTIMAL/SOLUTION_LIMIT, but the verdict itself is conclusive.
    - INFEASIBLE, or OPTIMAL with a published count of zero -> PASS: solver proved
      no counterexample exists (or exhausted the search and found none),
      so the property holds under the encoded rule pack. Soundness is
      bounded by encoding fidelity: missing rule arms can produce a
      silent pass. Local-only statuses (e.g. LOCALLY_SOLVED from an LP
      solver) do not count as exhaustion and route to INCONCLUSIVE
      below.
    - Anything else (TIME_LIMIT, MEMORY_LIMIT, OTHER_ERROR, ... with
      zero witnesses, or OPTIMAL with no published count) -> INCONCLUSIVE:
      the audit did not finish or its count is missing, and no witness was
      found, so neither pass nor fail can be concluded.
    """
    if num_points is not None and num_points >= 1:
        return "FAIL"
    if status == "INFEASIBLE" or (status == "OPTIMAL" and num_points == 0):
        return "PASS"
    return "INCONCLUSIVE"


def report_audit(name, description):
    """Print one property's verdict line and (on FAIL) its witness table.

    Returns a result dict for the verdict-matrix recap.
    """
    print(f"\n===== Auditing property: {name} =====")
    print(f"Description: {description}")

    # Status and count are read in one query, so both come from the same refresh. The status
    # is read alone only when no count is published.
    status_ref, count_ref = String.ref(), Integer.ref()
    result = model.select(status_ref.alias("status"), count_ref.alias("count")).where(
        SolveStatus[name](status_ref), NumPoints[name](count_ref)
    ).to_df()
    if result.empty:
        statuses = model.select(SolveStatus[name]).to_df().iloc[:, 0].tolist()
        n_witnesses = None
    else:
        statuses = result["status"].tolist()
        n_witnesses = result["count"].iloc[0]
    status = ", ".join(statuses)
    verdict = _classify_verdict(status, n_witnesses)
    count_text = "no count" if n_witnesses is None else str(n_witnesses)
    print(f"Verdict: {verdict}  ({count_text} witness(es), status={status})")
    if verdict == "FAIL" and status == "SOLUTION_LIMIT":
        print(
            f"Note: hit MAX_WITNESSES={MAX_WITNESSES}; raise it to enumerate more counterexamples."
        )

    # Per-FAIL witness table: the deployed model publishes one `Witness` row per
    # returned solution, with the age bucket and coverage band the solver chose and
    # the 0/1 value of each flag.
    if verdict == "FAIL":
        print(f"\nWitnesses (up to {MAX_WITNESSES} per run):")
        sol_idx = Integer.ref()
        chr_v = Integer.ref()
        sen_v = Integer.ref()
        frl_v = Integer.ref()
        mr_v = Integer.ref()
        model.select(
            sol_idx.alias("solution"),
            AgeBucket.age_years.alias("age_years"),
            chr_v.alias("has_chronic"),
            CoverageBand.coverage_dollars.alias("coverage_dollars"),
            sen_v.alias("is_senior"),
            frl_v.alias("is_frail"),
            mr_v.alias("is_manual_review"),
        ).where(
            Witness[name](sol_idx, AgeBucket, chr_v, CoverageBand, sen_v, frl_v, mr_v),
        ).inspect()

    return {
        "name": name,
        "description": description,
        "verdict": verdict,
        "num_witnesses": count_text,
        "status": status,
    }


# --------------------------------------------------
# Main: report every property, then print the verdict matrix
# --------------------------------------------------

if __name__ == "__main__":
    results = [report_audit(name, description) for name, description, _ in PROPERTIES]

    # The verdict matrix is the audit's headline deliverable: one line per
    # property, in catalog order. The PASS-and-FAIL mix in a single run
    # is the demo -- the audit isn't rigged to always fail; it
    # distinguishes properties the ruleset satisfies from those it
    # violates. Cross-referencing FAIL witness tables for shared decision
    # values (e.g. all witnesses with `has_chronic=1`) usually surfaces the
    # common root cause; comparing witness counts across FAILs surfaces
    # which sub-populations the bug touches.
    fail_count = sum(1 for r in results if r["verdict"] == "FAIL")
    pass_count = sum(1 for r in results if r["verdict"] == "PASS")
    incon_count = sum(1 for r in results if r["verdict"] == "INCONCLUSIVE")
    print("\n" + "=" * 80)
    print(
        f"Audit report ({len(results)} properties: "
        f"{pass_count} PASS, {fail_count} FAIL, {incon_count} INCONCLUSIVE)"
    )
    print("=" * 80)
    print(f"  {'Property':<32} {'Verdict':<14} {'Witnesses':>10}  Description")
    print("  " + "-" * 90)
    for r in results:
        print(f"  {r['name']:<32} {r['verdict']:<14} {r['num_witnesses']:>10}  {r['description']}")
