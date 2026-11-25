"""Audit report: reads the deployed underwriting_audit model.

Run `python -m queries.audit_report` after `rai models deploy --path model`. For each property
in the catalog, prints the verdict (PASS, FAIL, or INCONCLUSIVE) the model classifies from the
status and number of witnesses of the latest refresh's solve and, for FAILs, the witness table,
then a verdict-matrix recap covering every property.
"""

from model import (
    MAX_WITNESSES,
    PROPERTIES,
    AgeBucket,
    CoverageBand,
    HitWitnessLimit,
    NumPoints,
    NumProperties,
    PropertyVerdict,
    SolveStatus,
    VerdictTally,
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
    # An infeasible audit has no witness, and its solve publishes no count.
    if n_witnesses is None and status == "INFEASIBLE":
        n_witnesses = 0
    verdict_ref = String.ref()
    verdict = (
        model.select(verdict_ref.alias("verdict"))
        .where(PropertyVerdict(name, verdict_ref))
        .to_df()["verdict"]
        .iloc[0]
    )
    count_text = "no count" if n_witnesses is None else str(n_witnesses)
    print(f"Verdict: {verdict}  ({count_text} witness(es), status={status})")
    limit_ref = String.ref()
    hit_limit = model.select(limit_ref).where(HitWitnessLimit(limit_ref), limit_ref == name).to_df()
    if not hit_limit.empty:
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
    tally = (
        model.select(VerdictTally.verdict.alias("verdict"), VerdictTally.n_properties.alias("n"))
        .to_df()
        .set_index("verdict")["n"]
    )
    n_properties = int(model.select(NumProperties).to_df().iloc[0, 0])
    print("\n" + "=" * 80)
    print(
        f"Audit report ({n_properties} properties: "
        f"{tally['PASS']} PASS, {tally['FAIL']} FAIL, {tally['INCONCLUSIVE']} INCONCLUSIVE)"
    )
    print("=" * 80)
    print(f"  {'Property':<32} {'Verdict':<14} {'Witnesses':>10}  Description")
    print("  " + "-" * 90)
    for r in results:
        print(f"  {r['name']:<32} {r['verdict']:<14} {r['num_witnesses']:>10}  {r['description']}")
