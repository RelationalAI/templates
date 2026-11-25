"""Resolution report: reads the deployed entity_resolution model.

Run `python -m queries.resolution_report` after `rai models deploy --path model`.
Prints blocking/banding stats, graph size, resolved-party and golden-record
summary, the accumulation contrast, the reinsurance cession plan, the review
queue, and pairwise precision / recall / F1 against the ground-truth labels.
Every figure comes from the deployed model except the labels, which are evaluation
data read from `data/ground_truth.csv`.
"""

from itertools import combinations

from model import (
    ACCUMULATION_LIMIT,
    AUTO_MERGE,
    REINSURANCE_BUDGET,
    REINSURANCE_RATE,
    REVIEW_FLOOR,
    CandidatePairCount,
    Record,
    ResolvedParty,
    ReviewPair,
    SolveStatus,
    ceded_excess,
    ceded_premium,
    comparison_reduction,
    load_ground_truth,
    model,
    num_all_pairs,
    num_auto_merges,
    num_confirmed_breaches,
    num_edges,
    num_nodes,
    num_parties,
    num_party_breaches,
    num_record_breaches,
    num_review_pairs,
    num_surfaced_breaches,
)


def published(relationship):
    """The one value a nullary relationship of the deployed model holds."""
    return model.select(relationship.alias("value")).to_df()["value"].iloc[0]


if __name__ == "__main__":
    resolved = model.select(
        Record.record_id.alias("record_id"),
        Record.entity_key.alias("entity_id"),
    ).to_df()
    resolved["entity_id"] = resolved["entity_id"].astype(str)
    record_ids = sorted(int(record_id) for record_id in resolved["record_id"])
    auto_entity = dict(zip(resolved["record_id"], resolved["entity_id"]))

    n_records = len(record_ids)
    print("=" * 64)
    print("Blocking & scoring")
    print("=" * 64)
    print(f"Records:                 {n_records}")
    print(f"All possible pairs:      {int(published(num_all_pairs))}")
    print(
        f"Candidate pairs:         {int(published(CandidatePairCount))}  "
        f"({100 * float(published(comparison_reduction)):.1f}% fewer comparisons)"
    )
    print(f"Auto-merge matches:      {int(published(num_auto_merges))}  (score >= {AUTO_MERGE})")
    n_review = int(published(num_review_pairs))
    print(f"Held for review:         {n_review}  ([{REVIEW_FLOOR}, {AUTO_MERGE}))")

    n_nodes = int(published(num_nodes))
    n_edges = int(published(num_edges))
    print(f"Graph:                   {n_nodes} nodes, {n_edges} match edges")

    print("\n" + "=" * 64)
    print("Resolved parties")
    print("=" * 64)
    print(f"Auto-resolved {n_records} records into {int(published(num_parties))} insured parties.")

    multi_record = (
        model.select(
            ResolvedParty.key.alias("entity_id"),
            ResolvedParty.golden_record.full_name.alias("name"),
            ResolvedParty.n_records.alias("n_records"),
            ResolvedParty.total_exposure.alias("exposure"),
        )
        .where(ResolvedParty.is_multi_record())
        .to_df()
    )
    multi_record["entity_id"] = multi_record["entity_id"].astype(str)
    print("\nMulti-record parties (golden record in CAPS):")
    for _, party in multi_record.sort_values("entity_id").iterrows():
        print(
            f"  {party['name'].upper():<22} "
            f"{int(party['n_records'])} policies  total exposure ${party['exposure']:>12,.0f}"
        )

    n_breached = int(published(num_party_breaches))
    print("\n" + "=" * 64)
    print(f"Accumulation control (limit ${ACCUMULATION_LIMIT:,.0f})")
    print("=" * 64)
    print(
        "Policies over the limit at the RECORD level:      "
        f"{int(published(num_record_breaches))}"
    )
    print(f"Households over the limit after RESOLUTION:       {n_breached}")

    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(
        f"\nReinsurance cession plan  (status {', '.join(status)}, "
        f"budget ${REINSURANCE_BUDGET:,.0f} at "
        f"{REINSURANCE_RATE:.0%} rate on line):"
    )
    ceded = (
        model.select(
            ResolvedParty.golden_record.full_name.alias("name"),
            ResolvedParty.total_exposure.alias("exposure"),
            ResolvedParty.excess.alias("excess"),
            ResolvedParty.premium.alias("premium"),
            ResolvedParty.cede.alias("cede"),
        )
        .where(ResolvedParty.is_over_limit())
        .to_df()
        .sort_values("excess", ascending=False)
    )
    for _, row in ceded.iterrows():
        mark = "CEDE " if row["cede"] > 0.5 else "keep "
        print(
            f"  {mark} {row['name']:<22} exposure "
            f"${row['exposure']:>11,.0f}  excess ${row['excess']:>9,.0f}  "
            f"premium ${row['premium']:>8,.0f}"
        )
    if n_breached and ceded.empty:
        print("  No cession plan: the solve returned no solution (see the status above).")
    else:
        print(
            f"  -> ceded ${float(published(ceded_excess)):,.0f} of excess exposure for "
            f"${float(published(ceded_premium)):,.0f} premium (of ${REINSURANCE_BUDGET:,.0f})"
        )

    print("\n" + "=" * 64)
    print("Review queue")
    print("=" * 64)
    print(f"Pairs held for steward review: {n_review}")
    print(
        "Breaches surfaced only if the review queue is confirmed: "
        f"{int(published(num_surfaced_breaches))} "
        f"(resolution would then show {int(published(num_confirmed_breaches))} breached "
        f"households, not {n_breached})"
    )

    truth_df = load_ground_truth()
    truth_map = {}
    if truth_df is not None:
        # A blank label, or two different labels for one record, leaves the record unlabeled.
        labels = truth_df.dropna(subset=["true_entity_id"]).drop_duplicates()
        labels = labels.drop_duplicates("record_id", keep=False)
        truth_map = dict(zip(labels["record_id"], labels["true_entity_id"]))
    print("\n" + "=" * 64)
    print("Evaluation vs ground truth (pairwise, auto-resolution)")
    print("=" * 64)
    n_labeled = sum(record_id in truth_map for record_id in record_ids)
    if n_labeled < n_records:
        print(
            f"  skipped: {n_labeled} of {n_records} records have exactly one label "
            "in data/ground_truth.csv"
        )
    else:
        review_df = model.select(
            ReviewPair.rec_a.record_id.alias("rec_a"),
            ReviewPair.rec_b.record_id.alias("rec_b"),
        ).to_df()
        true_pairs = {
            (rec_a, rec_b)
            for rec_a, rec_b in combinations(record_ids, 2)
            if truth_map[rec_a] == truth_map[rec_b]
        }
        predicted_pairs = {
            (rec_a, rec_b)
            for rec_a, rec_b in combinations(record_ids, 2)
            if auto_entity[rec_a] == auto_entity[rec_b]
        }
        review_pairs = {
            (min(rec_a, rec_b), max(rec_a, rec_b))
            for rec_a, rec_b in zip(review_df["rec_a"].astype(int), review_df["rec_b"].astype(int))
        }
        true_positives = len(predicted_pairs & true_pairs)
        false_positives = len(predicted_pairs - true_pairs)
        false_negatives = len(true_pairs - predicted_pairs)
        misses_held_for_review = len((true_pairs - predicted_pairs) & review_pairs)
        precision = (
            true_positives / (true_positives + false_positives)
            if true_positives + false_positives
            else 1.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if true_positives + false_negatives
            else 1.0
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        print(f"  precision: {precision:.3f}   recall: {recall:.3f}   f1: {f1:.3f}")
        print(
            f"  (true positives={true_positives}, false positives={false_positives}, "
            f"false negatives={false_negatives}, of which {misses_held_for_review} "
            "held for review)"
        )
