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

import re
from itertools import combinations
from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Matching bands. A candidate at or above AUTO_MERGE is merged automatically; a
# candidate in [REVIEW_FLOOR, AUTO_MERGE) is held in a review queue, not merged.
AUTO_MERGE = 0.70
REVIEW_FLOOR = 0.55
HIGH_TIER = 0.90          # auto-merge confidence split: HIGH vs MEDIUM

# Accumulation control. Each insured party's total sum insured is capped; the
# excess over a breached party is what gets ceded to reinsurance.
ACCUMULATION_LIMIT = 1_000_000.0
REINSURANCE_RATE = 0.12        # premium as a fraction of ceded excess (rate on line)
REINSURANCE_BUDGET = 120_000.0  # premium the carrier can spend ceding this period

# Nickname -> legal first name, so "Bob" and "Robert" compare as equal.
NICKNAMES = {
    "bob": "robert", "rob": "robert", "bobby": "robert",
    "bill": "william", "will": "william", "billy": "william",
    "mike": "michael", "mick": "michael",
    "jen": "jennifer", "jenny": "jennifer",
    "kathy": "katherine", "katie": "katherine", "kate": "katherine",
    "liz": "elizabeth", "beth": "elizabeth", "lizzie": "elizabeth",
    "maggie": "margaret", "peggy": "margaret", "meg": "margaret",
    "dave": "david", "trish": "patricia", "patty": "patricia", "pat": "patricia",
    "chris": "christopher", "jim": "james", "jimmy": "james",
    "andy": "andrew", "drew": "andrew", "tom": "thomas", "tommy": "thomas",
}


# --------------------------------------------------
# Field normalization & similarity helpers
# --------------------------------------------------
# Pure functions used by the blocking and scoring steps below.

def norm(s: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace."""
    s = (s or "").lower().strip()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s))


def canonical_name(name: str) -> str:
    """Normalize a name and fold nicknames to their legal first name."""
    return " ".join(NICKNAMES.get(t, t) for t in norm(name).split())


def last_name(name: str) -> str:
    toks = canonical_name(name).split()
    return toks[-1] if toks else ""


def email_local(email: str) -> str:
    """Local part of an email, ignoring dots and plus-addressing."""
    e = (email or "").lower().strip()
    return e.split("@")[0].split("+")[0].replace(".", "") if "@" in e else ""


def phone_key(phone: str) -> str:
    """Last 10 digits of a phone number (area code included)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else ""


def digits_only(s: str) -> str:
    """Strip everything but digits (for date-of-birth and government-ID compares)."""
    return re.sub(r"\D", "", s or "")


def jaro_winkler(s1: str, s2: str) -> float:
    """Jaro-Winkler string similarity in [0, 1] (favours common prefixes)."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    reach = max(len(s1), len(s2)) // 2 - 1
    s1_m, s2_m = [False] * len(s1), [False] * len(s2)
    matches = 0
    for i, c in enumerate(s1):
        for j in range(max(0, i - reach), min(i + reach + 1, len(s2))):
            if not s2_m[j] and s2[j] == c:
                s1_m[i] = s2_m[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    k = transpositions = 0
    for i in range(len(s1)):
        if s1_m[i]:
            while not s2_m[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
    transpositions //= 2
    jaro = (matches / len(s1) + matches / len(s2)
            + (matches - transpositions) / matches) / 3
    prefix = 0
    for a, b in zip(s1[:4], s2[:4]):
        if a == b:
            prefix += 1
        else:
            break
    return jaro + prefix * 0.1 * (1 - jaro)


def blocking_keys(row) -> set:
    """Cheap keys that put plausibly-matching records in the same bucket."""
    keys = set()
    if email_local(row["email"]):
        keys.add("e:" + email_local(row["email"]))
    if phone_key(row["phone"]):
        keys.add("p:" + phone_key(row["phone"]))
    ln = last_name(row["full_name"])
    if ln:
        keys.add(f"n:{ln[:4]}|{str(row['postal_code'])[:3]}")
    if digits_only(row["date_of_birth"]):
        keys.add("d:" + digits_only(row["date_of_birth"]))
    return keys


def pair_score(a, b) -> float:
    """Weighted field-similarity score in [0, 1] for two records."""
    score = 0.0
    a_email = (a["email"] or "").lower().strip()
    b_email = (b["email"] or "").lower().strip()
    if a_email and a_email == b_email:
        score += 0.45
    elif email_local(a["email"]) and email_local(a["email"]) == email_local(b["email"]):
        score += 0.32
    if phone_key(a["phone"]) and phone_key(a["phone"]) == phone_key(b["phone"]):
        score += 0.42
    if digits_only(a["date_of_birth"]) and digits_only(a["date_of_birth"]) == digits_only(b["date_of_birth"]):
        score += 0.30
    if digits_only(a["gov_id_last4"]) and digits_only(a["gov_id_last4"]) == digits_only(b["gov_id_last4"]):
        score += 0.20
    score += 0.30 * jaro_winkler(canonical_name(a["full_name"]), canonical_name(b["full_name"]))
    addr_a = norm(f"{a['street']} {a['city']} {a['state']} {str(a['postal_code'])[:5]}")
    addr_b = norm(f"{b['street']} {b['city']} {b['state']} {str(b['postal_code'])[:5]}")
    score += 0.15 * jaro_winkler(addr_a, addr_b)
    return min(score, 1.0)


# --------------------------------------------------
# Stage 0: Ontology -- load policyholder records
# --------------------------------------------------

model = Model("entity_resolution")
Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

# Record concept: one raw party record (one policy) from a source system.
records_df = read_csv(
    DATA_DIR / "records.csv",
    dtype={"postal_code": str, "gov_id_last4": str},
).fillna("")
records_df["coverage_amount"] = records_df["coverage_amount"].astype(float)

Record = Concept("Record", identify_by={"record_id": Integer})
Record.source_system = Property(f"{Record} has {String:source_system}")
Record.full_name = Property(f"{Record} has {String:full_name}")
Record.street = Property(f"{Record} has {String:street}")
Record.city = Property(f"{Record} has {String:city}")
Record.state = Property(f"{Record} has {String:state}")
Record.postal_code = Property(f"{Record} has {String:postal_code}")
Record.created_at = Property(f"{Record} has {String:created_at}")
Record.coverage_amount = Property(f"{Record} has {Float:coverage_amount}")
Record.date_of_birth = Property(f"{Record} has {String:date_of_birth}")
Record.gov_id_last4 = Property(f"{Record} has {String:gov_id_last4}")
Record.email = Property(f"{Record} has {String:email}")
Record.phone = Property(f"{Record} has {String:phone}")

# Always-present columns load via schema. Optional columns (date of birth,
# government-ID fragment, email, phone) are loaded only over the rows that have
# a value -- otherwise a single missing cell drops the whole record at load time.
REQUIRED_COLS = ["record_id", "source_system", "full_name", "street", "city",
                 "state", "postal_code", "created_at", "coverage_amount"]
model.define(Record.new(model.data(records_df[REQUIRED_COLS]).to_schema()))


def load_optional_property(column: str) -> None:
    """Set an optional Record property for just the rows where it is present."""
    present = records_df[records_df[column] != ""][["record_id", column]]
    present_data = model.data(present)
    model.define(
        getattr(Record.lookup(record_id=present_data.record_id), column)(
            getattr(present_data, column)
        )
    )


load_optional_property("date_of_birth")
load_optional_property("gov_id_last4")
load_optional_property("email")
load_optional_property("phone")

# --------------------------------------------------
# Candidate generation: blocking + similarity scoring (pandas)
# --------------------------------------------------
# Block on a shared email handle, phone, name+postal key, or date of birth, then
# score each candidate. Pairs >= AUTO_MERGE become match edges; pairs in
# [REVIEW_FLOOR, AUTO_MERGE) go to a review queue instead of being merged.

rows = {int(r["record_id"]): r for _, r in records_df.iterrows()}
record_ids = sorted(rows)

blocks: dict = {}
for rid in record_ids:
    for key in blocking_keys(rows[rid]):
        blocks.setdefault(key, []).append(rid)

candidates = set()
for members in blocks.values():
    for a, b in combinations(sorted(members), 2):
        candidates.add((a, b))

auto_rows, review_rows = [], []
for pair_id, (a, b) in enumerate(sorted(candidates)):
    s = round(pair_score(rows[a], rows[b]), 4)
    if s >= AUTO_MERGE:
        auto_rows.append({"pair_id": pair_id, "rec_a": a, "rec_b": b, "score": s})
    elif s >= REVIEW_FLOOR:
        review_rows.append({"pair_id": pair_id, "rec_a": a, "rec_b": b, "score": s})

n_records = len(record_ids)
all_pairs = n_records * (n_records - 1) // 2
print("=" * 64)
print("Blocking & scoring")
print("=" * 64)
print(f"Records:                 {n_records}")
print(f"All possible pairs:      {all_pairs}")
print(f"Candidate pairs:         {len(candidates)}  "
      f"({100 * (1 - len(candidates) / all_pairs):.1f}% fewer comparisons)")
print(f"Auto-merge matches:      {len(auto_rows)}  (score >= {AUTO_MERGE})")
print(f"Held for review:         {len(review_rows)}  ([{REVIEW_FLOOR}, {AUTO_MERGE}))")

matches_df = DataFrame(auto_rows, columns=["pair_id", "rec_a", "rec_b", "score"])
review_df = DataFrame(review_rows, columns=["pair_id", "rec_a", "rec_b", "score"])

# CandidateMatch concept: an accepted (auto-merge) match. rec_a/rec_b are
# functional links to Record, so they are Properties, not Relationships.
CandidateMatch = Concept("CandidateMatch", identify_by={"pair_id": Integer})
CandidateMatch.rec_a = Property(f"{CandidateMatch} has first {Record:rec_a}")
CandidateMatch.rec_b = Property(f"{CandidateMatch} has second {Record:rec_b}")
CandidateMatch.score = Property(f"{CandidateMatch} has {Float:score}")
match_data = model.data(matches_df)
model.define(
    CandidateMatch.new(
        pair_id=match_data.pair_id,
        rec_a=Record.lookup(record_id=match_data.rec_a),
        rec_b=Record.lookup(record_id=match_data.rec_b),
        score=match_data.score,
    )
)

# ReviewPair concept: a possible match held for a steward (not merged).
ReviewPair = Concept("ReviewPair", identify_by={"pair_id": Integer})
ReviewPair.rec_a = Property(f"{ReviewPair} has first {Record:rec_a}")
ReviewPair.rec_b = Property(f"{ReviewPair} has second {Record:rec_b}")
ReviewPair.score = Property(f"{ReviewPair} has {Float:score}")
review_data = model.data(review_df)
model.define(
    ReviewPair.new(
        pair_id=review_data.pair_id,
        rec_a=Record.lookup(record_id=review_data.rec_a),
        rec_b=Record.lookup(record_id=review_data.rec_b),
        score=review_data.score,
    )
)

# --------------------------------------------------
# Stage 1: Graph -- transitive clustering (weakly-connected components)
# --------------------------------------------------
# Each auto-merge match is an undirected edge; weakly-connected-components
# collapses every connected group into one resolved party. All records are
# nodes, so a record with no auto-merge match forms its own single-record party.

graph = Graph(model, directed=False, weighted=False, node_concept=Record)

match_ref = CandidateMatch.ref()
rec_a, rec_b = Record.ref(), Record.ref()
model.where(
    match_ref.rec_a == rec_a,
    match_ref.rec_b == rec_b
).define(graph.Edge.new(src=rec_a, dst=rec_b))

graph.Node.entity_id = graph.weakly_connected_component()

# WCC returns the component-representative Record (a node), so expose a stable
# integer party key -- the representative's record_id -- for grouping and joins.
Record.entity_key = Property(f"{Record} has {Integer:entity_key}")
rep_node = Record.ref()
model.where(Record.entity_id == rep_node).define(Record.entity_key(rep_node.record_id))

n_nodes = int(model.select(graph.num_nodes().alias("n")).to_df()["n"].iloc[0])
n_edges = int(model.select(graph.num_edges().alias("n")).to_df()["n"].iloc[0])
print(f"Graph:                   {n_nodes} nodes, {n_edges} match edges")

# --------------------------------------------------
# Stage 2: Rules-based -- tiers, duplicate flag, resolved-party exposure
# --------------------------------------------------
# Declarative classifications and aggregations bound back to the ontology.

CandidateMatch.confidence_tier = Property(f"{CandidateMatch} has tier {String:confidence_tier}")
model.define(CandidateMatch.confidence_tier("HIGH")).where(CandidateMatch.score >= HIGH_TIER)
model.define(CandidateMatch.confidence_tier("MEDIUM")).where(CandidateMatch.score < HIGH_TIER)

# A record is a duplicate when two or more records resolve to its party.
Record.is_duplicate = Relationship(f"{Record} is a duplicate")
records_per_entity = aggregates.count(Record).per(Record.entity_key)
model.define(Record.is_duplicate(Record)).where(records_per_entity >= 2)

# ResolvedParty: one real insured party. Total exposure = sum insured across the
# party's resolved policies; a party breaches when that total exceeds the limit.
ResolvedParty = Concept("ResolvedParty", identify_by={"key": Integer})
model.define(ResolvedParty.new(key=Record.entity_key))

ResolvedParty.total_exposure = Property(f"{ResolvedParty} has {Float:total_exposure}")
party_rec = Record.ref()
model.where(party_rec.entity_key == ResolvedParty.key).define(
    ResolvedParty.total_exposure(aggregates.sum(party_rec.coverage_amount).per(ResolvedParty))
)

ResolvedParty.is_over_limit = Relationship(f"{ResolvedParty} is over the accumulation limit")
model.define(ResolvedParty.is_over_limit(ResolvedParty)).where(
    ResolvedParty.total_exposure > ACCUMULATION_LIMIT
)

# Excess over the limit and the premium to cede it (only for breached parties).
ResolvedParty.excess = Property(f"{ResolvedParty} has {Float:excess}")
model.where(ResolvedParty.total_exposure > ACCUMULATION_LIMIT).define(
    ResolvedParty.excess(ResolvedParty.total_exposure - ACCUMULATION_LIMIT)
)
ResolvedParty.premium = Property(f"{ResolvedParty} has {Float:premium}")
model.define(ResolvedParty.premium(ResolvedParty.excess * REINSURANCE_RATE))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------
# Knapsack: with a finite reinsurance premium budget, choose which breached
# households to cede so the most excess exposure is transferred off the book.

problem = Problem(model, Float)
ResolvedParty.cede = Property(f"{ResolvedParty} cede decision {Float:cede}")
problem.solve_for(
    ResolvedParty.cede,
    where=[ResolvedParty.is_over_limit()],
    name=["cede", ResolvedParty.key],
    type="bin",
    lower=0.0,
    upper=1.0,
)
problem.satisfy(
    model.require(aggregates.sum(ResolvedParty.premium * ResolvedParty.cede) <= REINSURANCE_BUDGET),
    name=["reinsurance_budget"],
)
problem.maximize(aggregates.sum(ResolvedParty.excess * ResolvedParty.cede))

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

problem.solve("highs", time_limit_sec=60)
si = problem.solve_info()

# --------------------------------------------------
# Stage 4: Resolution, accumulation, cession plan, evaluation
# --------------------------------------------------

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

# Golden record per party: most recent record wins (recency survivorship).
resolved = resolved.sort_values(["entity_id", "created_at"])
golden = resolved.groupby("entity_id").tail(1).set_index("entity_id")
sizes = resolved.groupby("entity_id").size()
print("\nMulti-record parties (golden record in CAPS):")
for entity_id in sizes[sizes > 1].index:
    g = golden.loc[entity_id]
    members = resolved[resolved["entity_id"] == entity_id]
    exposure = members["coverage_amount"].sum()
    print(f"  {g['full_name'].upper():<22} {len(members)} policies  "
          f"total exposure ${exposure:>12,.0f}")

# Accumulation contrast: nothing looks dangerous per policy; resolved, households breach.
rec_level_breaches = int((resolved["coverage_amount"] > ACCUMULATION_LIMIT).sum())
over = (
    model.select(ResolvedParty.key.alias("id"), ResolvedParty.total_exposure.alias("exposure"))
    .where(ResolvedParty.is_over_limit())
    .to_df()
)
print("\n" + "=" * 64)
print(f"Accumulation control (limit ${ACCUMULATION_LIMIT:,.0f})")
print("=" * 64)
print(f"Policies over the limit at the RECORD level:      {rec_level_breaches}")
print(f"Households over the limit after RESOLUTION:       {len(over)}")

# Reinsurance cession plan (prescriptive result).
print(f"\nReinsurance cession plan  (status {si.termination_status}, "
      f"budget ${REINSURANCE_BUDGET:,.0f} at {REINSURANCE_RATE:.0%} rate on line):")
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
total_prem = total_ceded = 0.0
for _, r in ceded.iterrows():
    chosen = r["cede"] > 0.5
    mark = "CEDE " if chosen else "keep "
    if chosen:
        total_prem += r["premium"]
        total_ceded += r["excess"]
    print(f"  {mark} {r['name']:<22} exposure ${r['exposure']:>11,.0f}  "
          f"excess ${r['excess']:>9,.0f}  premium ${r['premium']:>8,.0f}")
print(f"  -> ceded ${total_ceded:,.0f} of excess exposure for ${total_prem:,.0f} premium "
      f"(of ${REINSURANCE_BUDGET:,.0f})")

# Review queue: the matches a steward must confirm -- and the breach still hidden.
auto_entity = dict(zip(resolved["record_id"], resolved["entity_id"]))
cov_by_rec = dict(zip(resolved["record_id"], resolved["coverage_amount"]))
confirmed = {rid: auto_entity[rid] for rid in record_ids}
for _, r in review_df.iterrows():
    ra_, rb_ = int(r["rec_a"]), int(r["rec_b"])
    tgt, src = confirmed[ra_], confirmed[rb_]
    for rid in record_ids:
        if confirmed[rid] == src:
            confirmed[rid] = tgt
confirmed_ex: dict = {}
for rid in record_ids:
    confirmed_ex[confirmed[rid]] = confirmed_ex.get(confirmed[rid], 0.0) + cov_by_rec[rid]
confirmed_breaches = sum(1 for v in confirmed_ex.values() if v > ACCUMULATION_LIMIT)
print("\n" + "=" * 64)
print("Review queue")
print("=" * 64)
print(f"Pairs held for steward review: {len(review_df)}")
print(f"Breaches surfaced only if the review queue is confirmed: "
      f"{confirmed_breaches - len(over)} "
      f"(resolution would then show {confirmed_breaches} breached households, not {len(over)})")

# Evaluate auto-resolution against ground truth: pairwise precision / recall / F1.
truth = read_csv(DATA_DIR / "ground_truth.csv")
truth_map = dict(zip(truth["record_id"], truth["true_entity_id"]))
true_pairs = {(a, b) for a, b in combinations(record_ids, 2) if truth_map[a] == truth_map[b]}
pred_pairs = {(a, b) for a, b in combinations(record_ids, 2) if auto_entity[a] == auto_entity[b]}
tp = len(pred_pairs & true_pairs)
fp = len(pred_pairs - true_pairs)
fn = len(true_pairs - pred_pairs)
precision = tp / (tp + fp) if tp + fp else 1.0
recall = tp / (tp + fn) if tp + fn else 1.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
print("\n" + "=" * 64)
print("Evaluation vs ground truth (pairwise, auto-resolution)")
print("=" * 64)
print(f"  precision: {precision:.3f}   recall: {recall:.3f}   f1: {f1:.3f}")
print(f"  (true positives={tp}, false positives={fp}, false negatives={fn}; "
      f"the {fn} miss is the held review pair)")
