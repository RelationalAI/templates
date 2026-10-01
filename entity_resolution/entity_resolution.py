"""Entity Resolution (graph + rules-based + prescriptive reasoning) template.

Resolution is the step that makes the downstream reasoning correct. An insurer's
policyholder records are scattered across policy systems (auto, home, life) and
an acquired book, so the same insured looks like several customers -- and their
combined exposure to the carrier is invisible until the records are resolved.
This template resolves them, then aggregates and acts on the resolved exposure:

- Pre-process (pandas): normalize fields, block, and score candidate pairs.
  Scores split into two bands -- AUTO_MERGE (merge automatically) and REVIEW
  (held for a steward) -- so high-precision automation and human review coexist.
- Stage 1 -- Graph: weakly-connected-components over the auto-merged match edges
  clusters records into one insured party, closing transitive chains.
- Stage 2 -- Rules-based: confidence tiers on matches, a duplicate flag, and the
  payoff -- total exposure per resolved party and an accumulation-limit breach
  flag. At the record level no policy looks dangerous; resolved, households breach.
- Stage 3 -- Prescriptive: with a finite reinsurance budget, choose which breached
  households to cede to reinsurance (a knapsack) to transfer the most excess
  exposure off the book.
- Stage 4: the record-level vs resolved-level contrast, the review queue (and the
  breach it still hides), the cession plan, and pairwise precision / recall / F1.

Run:
    `python entity_resolution.py`

Output:
    Prints blocking/banding stats, graph size, resolved-party and golden-record
    summary, the accumulation contrast, the reinsurance cession plan, the review
    queue, and pairwise precision / recall / F1 against the ground-truth labels.
"""

from itertools import combinations

from model import (
    AUTO_MERGE,
    REVIEW_FLOOR,
    CandidateMatch,
    Record,
    ResolvedParty,
    candidate_count,
    load_ground_truth,
    matches_df,
    model,
    record_ids,
    review_df,
)
from relationalai.semantics import Float
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates

HIGH_TIER = 0.90

ACCUMULATION_LIMIT = 1_000_000.0
REINSURANCE_RATE = 0.12
REINSURANCE_BUDGET = 120_000.0

n_records = len(record_ids)
all_pairs = n_records * (n_records - 1) // 2
print("=" * 64)
print("Blocking & scoring")
print("=" * 64)
print(f"Records:                 {n_records}")
print(f"All possible pairs:      {all_pairs}")
print(
    f"Candidate pairs:         {candidate_count}  "
    f"({100 * (1 - candidate_count / all_pairs):.1f}% fewer comparisons)"
)
print(f"Auto-merge matches:      {len(matches_df)}  (score >= {AUTO_MERGE})")
print(
    f"Held for review:         {len(review_df)}  "
    f"([{REVIEW_FLOOR}, {AUTO_MERGE}))"
)


def cluster_accepted_matches() -> tuple[int, int]:
    """Cluster records connected by accepted match edges."""
    graph = Graph(model, directed=False, weighted=False, node_concept=Record)

    match_ref = CandidateMatch.ref()
    rec_a, rec_b = Record.ref(), Record.ref()
    model.where(match_ref.rec_a == rec_a, match_ref.rec_b == rec_b).define(
        graph.Edge.new(src=rec_a, dst=rec_b)
    )

    graph.Node.entity_id = graph.weakly_connected_component()

    rep_node = Record.ref()
    model.where(Record.entity_id == rep_node).define(
        Record.entity_key(rep_node.record_id)
    )

    n_nodes = int(model.select(graph.num_nodes().alias("n")).to_df()["n"].iloc[0])
    n_edges = int(model.select(graph.num_edges().alias("n")).to_df()["n"].iloc[0])
    return n_nodes, n_edges


def derive_exposure_and_breaches() -> None:
    """Derive match tiers, resolved membership, exposure, and breaches."""
    model.define(CandidateMatch.confidence_tier("HIGH")).where(
        CandidateMatch.score >= HIGH_TIER
    )
    model.define(CandidateMatch.confidence_tier("MEDIUM")).where(
        CandidateMatch.score < HIGH_TIER
    )

    records_per_entity = aggregates.count(Record).per(Record.entity_key)
    model.define(Record.is_duplicate(Record)).where(records_per_entity >= 2)

    model.define(ResolvedParty.new(key=Record.entity_key))
    record, party = Record.ref(), ResolvedParty.ref()
    model.where(record.entity_key == party.key).define(
        record.resolved_party(party)
    )

    party_record = Record.ref()
    model.where(party_record.entity_key == ResolvedParty.key).define(
        ResolvedParty.total_exposure(
            aggregates.sum(party_record.coverage_amount).per(ResolvedParty)
        )
    )
    model.define(ResolvedParty.is_over_limit(ResolvedParty)).where(
        ResolvedParty.total_exposure > ACCUMULATION_LIMIT
    )
    model.where(ResolvedParty.total_exposure > ACCUMULATION_LIMIT).define(
        ResolvedParty.excess(
            ResolvedParty.total_exposure - ACCUMULATION_LIMIT
        )
    )
    model.define(
        ResolvedParty.premium(ResolvedParty.excess * REINSURANCE_RATE)
    )


def choose_reinsurance_cessions():
    """Solve the reinsurance-budget knapsack for breached parties."""
    problem = Problem(model, Float)
    problem.solve_for(
        ResolvedParty.cede,
        where=[ResolvedParty.is_over_limit()],
        name=["cede", ResolvedParty.key],
        type="bin",
        lower=0.0,
        upper=1.0,
    )
    problem.satisfy(
        model.require(
            aggregates.sum(
                ResolvedParty.premium * ResolvedParty.cede
            )
            <= REINSURANCE_BUDGET
        ),
        name=["reinsurance_budget"],
    )
    problem.maximize(
        aggregates.sum(ResolvedParty.excess * ResolvedParty.cede)
    )
    problem.solve("highs", time_limit_sec=60)
    return problem.solve_info()


n_nodes, n_edges = cluster_accepted_matches()
print(f"Graph:                   {n_nodes} nodes, {n_edges} match edges")

derive_exposure_and_breaches()
si = choose_reinsurance_cessions()

resolved = model.select(
    Record.record_id.alias("record_id"),
    Record.entity_key.alias("entity_id"),
    Record.source_system.alias("source_system"),
    Record.full_name.alias("full_name"),
    Record.created_at.alias("created_at"),
    Record.coverage_amount.alias("coverage_amount"),
).to_df()
resolved["entity_id"] = resolved["entity_id"].astype(str)

n_entities = resolved["entity_id"].nunique()
print("\n" + "=" * 64)
print("Resolved parties")
print("=" * 64)
print(f"Auto-resolved {n_records} records into {n_entities} insured parties.")

resolved = resolved.sort_values(["entity_id", "created_at"])
golden = resolved.groupby("entity_id").tail(1).set_index("entity_id")
sizes = resolved.groupby("entity_id").size()
print("\nMulti-record parties (golden record in CAPS):")
for entity_id in sizes[sizes > 1].index:
    golden_record = golden.loc[entity_id]
    members = resolved[resolved["entity_id"] == entity_id]
    exposure = members["coverage_amount"].sum()
    print(
        f"  {golden_record['full_name'].upper():<22} "
        f"{len(members)} policies  total exposure ${exposure:>12,.0f}"
    )

record_level_breaches = int(
    (resolved["coverage_amount"] > ACCUMULATION_LIMIT).sum()
)
over = (
    model.select(
        ResolvedParty.key.alias("id"),
        ResolvedParty.total_exposure.alias("exposure"),
    )
    .where(ResolvedParty.is_over_limit())
    .to_df()
)
print("\n" + "=" * 64)
print(f"Accumulation control (limit ${ACCUMULATION_LIMIT:,.0f})")
print("=" * 64)
print(
    "Policies over the limit at the RECORD level:      "
    f"{record_level_breaches}"
)
print(f"Households over the limit after RESOLUTION:       {len(over)}")

print(
    f"\nReinsurance cession plan  (status {si.termination_status}, "
    f"budget ${REINSURANCE_BUDGET:,.0f} at "
    f"{REINSURANCE_RATE:.0%} rate on line):"
)
ceded = (
    model.select(
        ResolvedParty.key.alias("id"),
        ResolvedParty.total_exposure.alias("exposure"),
        ResolvedParty.excess.alias("excess"),
        ResolvedParty.premium.alias("premium"),
        ResolvedParty.cede.alias("cede"),
    )
    .where(ResolvedParty.is_over_limit())
    .to_df()
)
ceded["id"] = ceded["id"].astype(str)
name_by_entity = golden["full_name"].to_dict()
ceded["name"] = ceded["id"].map(name_by_entity).fillna("(party)")
ceded = ceded.sort_values("excess", ascending=False)
total_premium = total_ceded = 0.0
for _, row in ceded.iterrows():
    chosen = row["cede"] > 0.5
    mark = "CEDE " if chosen else "keep "
    if chosen:
        total_premium += row["premium"]
        total_ceded += row["excess"]
    print(
        f"  {mark} {row['name']:<22} exposure "
        f"${row['exposure']:>11,.0f}  excess ${row['excess']:>9,.0f}  "
        f"premium ${row['premium']:>8,.0f}"
    )
print(
    f"  -> ceded ${total_ceded:,.0f} of excess exposure for "
    f"${total_premium:,.0f} premium (of ${REINSURANCE_BUDGET:,.0f})"
)

auto_entity = dict(zip(resolved["record_id"], resolved["entity_id"]))
coverage_by_record = dict(
    zip(resolved["record_id"], resolved["coverage_amount"])
)
confirmed = {record_id: auto_entity[record_id] for record_id in record_ids}
for _, row in review_df.iterrows():
    rec_a, rec_b = int(row["rec_a"]), int(row["rec_b"])
    target, source = confirmed[rec_a], confirmed[rec_b]
    for record_id in record_ids:
        if confirmed[record_id] == source:
            confirmed[record_id] = target
confirmed_exposure: dict[str, float] = {}
for record_id in record_ids:
    party_id = confirmed[record_id]
    confirmed_exposure[party_id] = (
        confirmed_exposure.get(party_id, 0.0)
        + coverage_by_record[record_id]
    )
confirmed_breaches = sum(
    1 for exposure in confirmed_exposure.values()
    if exposure > ACCUMULATION_LIMIT
)
print("\n" + "=" * 64)
print("Review queue")
print("=" * 64)
print(f"Pairs held for steward review: {len(review_df)}")
print(
    "Breaches surfaced only if the review queue is confirmed: "
    f"{confirmed_breaches - len(over)} "
    f"(resolution would then show {confirmed_breaches} breached "
    f"households, not {len(over)})"
)

truth_df = load_ground_truth()
truth_map = dict(
    zip(truth_df["record_id"], truth_df["true_entity_id"])
)
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
true_positives = len(predicted_pairs & true_pairs)
false_positives = len(predicted_pairs - true_pairs)
false_negatives = len(true_pairs - predicted_pairs)
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
f1 = (
    2 * precision * recall / (precision + recall)
    if precision + recall
    else 0.0
)
print("\n" + "=" * 64)
print("Evaluation vs ground truth (pairwise, auto-resolution)")
print("=" * 64)
print(f"  precision: {precision:.3f}   recall: {recall:.3f}   f1: {f1:.3f}")
print(
    f"  (true positives={true_positives}, false positives={false_positives}, "
    f"false negatives={false_negatives}; the {false_negatives} miss is the "
    "held review pair)"
)
