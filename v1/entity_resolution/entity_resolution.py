"""Entity Resolution (graph + rules-based reasoning) template.

This script resolves duplicate policyholder records that an insurer accumulates
across separate policy systems (auto, home, life) and an acquired book of
business, collapsing them into one record per real-world insured party:

- Pre-process (pandas): normalize fields, generate candidate pairs with
  blocking, and score each pair with field-level similarity (name, date of
  birth, government-ID fragment, email, phone, address). Blocking avoids the
  quadratic blow-up of comparing every record to every other record.
- Stage 1 -- Graph: load accepted pairs as match edges and run
  weakly-connected-components. Transitive closure groups records into one
  insured party even when two of them never matched directly (A-B and B-C
  matched, A-C did not) -- the case a pairwise spreadsheet misses, which
  fragments a customer view and understates total exposure.
- Stage 2 -- Rules-based: classify each match into a confidence tier
  (HIGH / MEDIUM / REVIEW) and flag records that belong to a multi-record
  party. Both are bound back to the ontology as queryable facts.
- Resolution summary & evaluation: derive one golden (surviving) record per
  party and score the resolution against ground-truth labels (pairwise
  precision / recall / F1).

Run:
    `python entity_resolution.py`

Output:
    Prints blocking statistics, the graph size, the resolved-party and
    golden-record summary, the match confidence-tier breakdown, and pairwise
    precision / recall / F1 against the ground-truth labels.
"""

import re
from itertools import combinations
from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# A candidate pair at or above this score is treated as the same party and
# becomes a match edge. Lower it to merge more aggressively, raise it to be
# more conservative. See the README "Tune parameters" section.
MATCH_THRESHOLD = 0.55

# Score bands for the rules stage. HIGH merges are unambiguous; REVIEW merges
# clear the bar but rest on the weakest evidence and are worth a steward's spot-check.
HIGH_TIER = 0.90
MEDIUM_TIER = 0.75

# Nickname -> legal first name, so "Bob" and "Robert" compare as equal. Extend
# this map for your own population.
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

# Record concept: one raw party record from a source policy system, before resolution.
records_df = read_csv(
    DATA_DIR / "records.csv",
    dtype={"postal_code": str, "gov_id_last4": str},
).fillna("")

Record = Concept("Record", identify_by={"record_id": Integer})
Record.source_system = Property(f"{Record} has {String:source_system}")
Record.full_name = Property(f"{Record} has {String:full_name}")
Record.date_of_birth = Property(f"{Record} has {String:date_of_birth}")
Record.gov_id_last4 = Property(f"{Record} has {String:gov_id_last4}")
Record.email = Property(f"{Record} has {String:email}")
Record.phone = Property(f"{Record} has {String:phone}")
Record.street = Property(f"{Record} has {String:street}")
Record.city = Property(f"{Record} has {String:city}")
Record.state = Property(f"{Record} has {String:state}")
Record.postal_code = Property(f"{Record} has {String:postal_code}")
Record.created_at = Property(f"{Record} has {String:created_at}")

# Always-present columns load via schema. Optional columns (date of birth,
# government-ID fragment, email, phone) are loaded only over the rows that have
# a value -- otherwise a single missing cell drops the whole record at load time.
REQUIRED_COLS = ["record_id", "source_system", "full_name", "street", "city",
                 "state", "postal_code", "created_at"]
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
# Generate candidate pairs with blocking (records sharing an email handle,
# phone, or name+postal key), then score each candidate. Only pairs at or above
# MATCH_THRESHOLD become match edges in the graph.

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

match_rows = []
for pair_id, (a, b) in enumerate(sorted(candidates)):
    s = pair_score(rows[a], rows[b])
    if s >= MATCH_THRESHOLD:
        match_rows.append({"pair_id": pair_id, "rec_a": a, "rec_b": b, "score": round(s, 4)})

n_records = len(record_ids)
all_pairs = n_records * (n_records - 1) // 2
print("=" * 60)
print("Blocking & scoring")
print("=" * 60)
print(f"Records:                {n_records}")
print(f"All possible pairs:     {all_pairs}")
print(f"Candidate pairs:        {len(candidates)}  "
      f"({100 * (1 - len(candidates) / all_pairs):.1f}% fewer comparisons)")
print(f"Accepted match edges:   {len(match_rows)}  (score >= {MATCH_THRESHOLD})")

matches_df = DataFrame(match_rows, columns=["pair_id", "rec_a", "rec_b", "score"])

# CandidateMatch concept: an accepted pairwise match between two records. rec_a
# and rec_b are functional links to Record, so they are Properties, not Relationships.
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

# --------------------------------------------------
# Stage 1: Graph -- transitive clustering (weakly-connected components)
# --------------------------------------------------
# An undirected graph over records; each accepted match is an edge. Weakly-
# connected-components collapses every connected group into one resolved party,
# so a chain of pairwise matches becomes a single insured customer. All records
# are nodes, so a record with no matches forms its own single-record party.

graph = Graph(model, directed=False, weighted=False, node_concept=Record)

match_ref = CandidateMatch.ref()
rec_a, rec_b = Record.ref(), Record.ref()
model.where(
    match_ref.rec_a == rec_a,
    match_ref.rec_b == rec_b
).define(graph.Edge.new(src=rec_a, dst=rec_b))

# Each record's resolved entity id is its weakly-connected-component label,
# available directly on Record because node_concept=Record.
graph.Node.entity_id = graph.weakly_connected_component()

n_nodes = int(model.select(graph.num_nodes().alias("n")).to_df()["n"].iloc[0])
n_edges = int(model.select(graph.num_edges().alias("n")).to_df()["n"].iloc[0])
print(f"Graph:                  {n_nodes} nodes, {n_edges} match edges")

# --------------------------------------------------
# Stage 2: Rules-based -- match-confidence tiers + duplicate flags
# --------------------------------------------------
# Declarative classifications bound back to the ontology so a downstream query
# can filter on them directly.

CandidateMatch.confidence_tier = Property(f"{CandidateMatch} has tier {String:confidence_tier}")
model.define(CandidateMatch.confidence_tier("HIGH")).where(
    CandidateMatch.score >= HIGH_TIER
)
model.define(CandidateMatch.confidence_tier("MEDIUM")).where(
    CandidateMatch.score >= MEDIUM_TIER,
    CandidateMatch.score < HIGH_TIER
)
model.define(CandidateMatch.confidence_tier("REVIEW")).where(
    CandidateMatch.score >= MATCH_THRESHOLD,
    CandidateMatch.score < MEDIUM_TIER
)

# A record is a duplicate when two or more records resolve to its entity.
Record.is_duplicate = Relationship(f"{Record} is a duplicate")
records_per_entity = aggregates.count(Record).per(Record.entity_id)
model.define(Record.is_duplicate(Record)).where(records_per_entity >= 2)

# --------------------------------------------------
# Stage 3: Resolution summary & evaluation
# --------------------------------------------------

resolved = (
    model.select(
        Record.record_id.alias("record_id"),
        Record.entity_id.alias("entity_id"),
        Record.source_system.alias("source_system"),
        Record.full_name.alias("full_name"),
        Record.created_at.alias("created_at"),
    )
    .to_df()
)
resolved["entity_id"] = resolved["entity_id"].astype(str)

# email is optional (null for some records); left-join it so those records are
# not dropped from the resolved set.
emails = model.select(
    Record.record_id.alias("record_id"),
    Record.email.alias("email"),
).to_df()
resolved = resolved.merge(emails, on="record_id", how="left")
resolved["email"] = resolved["email"].fillna("")

n_entities = resolved["entity_id"].nunique()
dup_df = model.where(Record.is_duplicate()).select(Record.record_id.alias("record_id")).to_df()
print("\n" + "=" * 60)
print("Resolved parties")
print("=" * 60)
print(f"Resolved {n_records} records into {n_entities} insured parties "
      f"({n_records - n_entities} duplicate records collapsed).")
print(f"Records flagged as duplicates (in a multi-record party): {len(dup_df)}")

# Golden record per party: survivorship by most recent record (recency wins).
# Swap this rule for source-priority or most-complete in the README extensions.
resolved = resolved.sort_values(["entity_id", "created_at"])
golden = resolved.groupby("entity_id").tail(1).set_index("entity_id")

print("\nMulti-record parties (golden record in CAPS, then merged duplicates):")
sizes = resolved.groupby("entity_id").size()
for entity_id in sizes[sizes > 1].index:
    members = resolved[resolved["entity_id"] == entity_id]
    g = golden.loc[entity_id]
    print(f"\n  {g['full_name'].upper()}  <{g['email'] or 'no email'}>  "
          f"[golden from {g['source_system']}, {g['created_at']}]")
    for _, r in members.iterrows():
        flag = "  <- golden" if r["record_id"] == g["record_id"] else ""
        print(f"      record {r['record_id']} [{r['source_system']:<7}] "
              f"{r['full_name']:<22} {r['email'] or '-':<26}{flag}")

# Confidence-tier breakdown from the rules stage.
tiers = (
    model.select(
        CandidateMatch.score.alias("score"),
        CandidateMatch.confidence_tier.alias("confidence_tier"),
    )
    .to_df()
)
print("\n" + "=" * 60)
print("Match confidence tiers")
print("=" * 60)
for tier in ["HIGH", "MEDIUM", "REVIEW"]:
    print(f"  {tier:<7} {int((tiers['confidence_tier'] == tier).sum())} matches")

# Evaluate against ground truth: pairwise precision / recall / F1.
truth = read_csv(DATA_DIR / "ground_truth.csv")
truth_map = dict(zip(truth["record_id"], truth["true_entity_id"]))
entity_map = dict(zip(resolved["record_id"], resolved["entity_id"]))

true_pairs = {(a, b) for a, b in combinations(record_ids, 2) if truth_map[a] == truth_map[b]}
pred_pairs = {(a, b) for a, b in combinations(record_ids, 2) if entity_map[a] == entity_map[b]}
tp = len(pred_pairs & true_pairs)
fp = len(pred_pairs - true_pairs)
fn = len(true_pairs - pred_pairs)
precision = tp / (tp + fp) if tp + fp else 1.0
recall = tp / (tp + fn) if tp + fn else 1.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

print("\n" + "=" * 60)
print("Evaluation vs ground truth (pairwise)")
print("=" * 60)
print(f"  precision: {precision:.3f}")
print(f"  recall:    {recall:.3f}")
print(f"  f1:        {f1:.3f}")
print(f"  (true positives={tp}, false positives={fp}, false negatives={fn})")
