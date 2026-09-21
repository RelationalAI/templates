"""Read, normalize, score, and load entity-resolution source data."""

import re
from itertools import combinations
from pathlib import Path

from pandas import DataFrame, read_csv

from .schema import CandidateMatch, Record, ReviewPair, model

DATA_DIR = Path(__file__).parent.parent / "data"

AUTO_MERGE = 0.70
REVIEW_FLOOR = 0.55

NICKNAMES = {
    "bob": "robert",
    "rob": "robert",
    "bobby": "robert",
    "bill": "william",
    "will": "william",
    "billy": "william",
    "mike": "michael",
    "mick": "michael",
    "jen": "jennifer",
    "jenny": "jennifer",
    "kathy": "katherine",
    "katie": "katherine",
    "kate": "katherine",
    "liz": "elizabeth",
    "beth": "elizabeth",
    "lizzie": "elizabeth",
    "maggie": "margaret",
    "peggy": "margaret",
    "meg": "margaret",
    "dave": "david",
    "trish": "patricia",
    "patty": "patricia",
    "pat": "patricia",
    "chris": "christopher",
    "jim": "james",
    "jimmy": "james",
    "andy": "andrew",
    "drew": "andrew",
    "tom": "thomas",
    "tommy": "thomas",
}

REQUIRED_COLS = [
    "record_id",
    "source_system",
    "full_name",
    "street",
    "city",
    "state",
    "postal_code",
    "created_at",
    "coverage_amount",
]
OPTIONAL_COLS = ["date_of_birth", "gov_id_last4", "email", "phone"]


def norm(s: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace."""
    s = (s or "").lower().strip()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s))


def canonical_name(name: str) -> str:
    """Normalize a name and fold nicknames to their legal first name."""
    return " ".join(NICKNAMES.get(token, token) for token in norm(name).split())


def last_name(name: str) -> str:
    tokens = canonical_name(name).split()
    return tokens[-1] if tokens else ""


def email_local(email: str) -> str:
    """Return an email's local part, ignoring dots and plus-addressing."""
    email = (email or "").lower().strip()
    return (
        email.split("@")[0].split("+")[0].replace(".", "") if "@" in email else ""
    )


def phone_key(phone: str) -> str:
    """Return the last 10 digits of a phone number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else ""


def digits_only(s: str) -> str:
    """Strip everything but digits."""
    return re.sub(r"\D", "", s or "")


def jaro_winkler(s1: str, s2: str) -> float:
    """Return Jaro-Winkler string similarity in [0, 1]."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    reach = max(len(s1), len(s2)) // 2 - 1
    s1_matches, s2_matches = [False] * len(s1), [False] * len(s2)
    matches = 0
    for i, char in enumerate(s1):
        for j in range(max(0, i - reach), min(i + reach + 1, len(s2))):
            if not s2_matches[j] and s2[j] == char:
                s1_matches[i] = s2_matches[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    k = transpositions = 0
    for i in range(len(s1)):
        if s1_matches[i]:
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
    transpositions //= 2
    jaro = (
        matches / len(s1)
        + matches / len(s2)
        + (matches - transpositions) / matches
    ) / 3
    prefix = 0
    for a, b in zip(s1[:4], s2[:4]):
        if a != b:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1 - jaro)


def blocking_keys(row) -> set[str]:
    """Return inexpensive keys for grouping plausibly matching records."""
    keys = set()
    if email_local(row["email"]):
        keys.add("e:" + email_local(row["email"]))
    if phone_key(row["phone"]):
        keys.add("p:" + phone_key(row["phone"]))
    surname = last_name(row["full_name"])
    if surname:
        keys.add(f"n:{surname[:4]}|{str(row['postal_code'])[:3]}")
    if digits_only(row["date_of_birth"]):
        keys.add("d:" + digits_only(row["date_of_birth"]))
    return keys


def pair_score(a, b) -> float:
    """Return the weighted field-similarity score for two records."""
    score = 0.0
    a_email = (a["email"] or "").lower().strip()
    b_email = (b["email"] or "").lower().strip()
    if a_email and a_email == b_email:
        score += 0.45
    elif email_local(a["email"]) and email_local(a["email"]) == email_local(
        b["email"]
    ):
        score += 0.32
    if phone_key(a["phone"]) and phone_key(a["phone"]) == phone_key(b["phone"]):
        score += 0.42
    if digits_only(a["date_of_birth"]) and digits_only(
        a["date_of_birth"]
    ) == digits_only(b["date_of_birth"]):
        score += 0.30
    if digits_only(a["gov_id_last4"]) and digits_only(
        a["gov_id_last4"]
    ) == digits_only(b["gov_id_last4"]):
        score += 0.20
    score += 0.30 * jaro_winkler(
        canonical_name(a["full_name"]), canonical_name(b["full_name"])
    )
    addr_a = norm(
        f"{a['street']} {a['city']} {a['state']} {str(a['postal_code'])[:5]}"
    )
    addr_b = norm(
        f"{b['street']} {b['city']} {b['state']} {str(b['postal_code'])[:5]}"
    )
    score += 0.15 * jaro_winkler(addr_a, addr_b)
    return min(score, 1.0)


def load_records() -> DataFrame:
    """Read policyholder records and load their base facts."""
    records = read_csv(
        DATA_DIR / "records.csv",
        dtype={"postal_code": str, "gov_id_last4": str},
    ).fillna("")
    records["coverage_amount"] = records["coverage_amount"].astype(float)
    model.define(Record.new(model.data(records[REQUIRED_COLS]).to_schema()))

    for column in OPTIONAL_COLS:
        present = records[records[column] != ""][["record_id", column]]
        present_data = model.data(present)
        model.define(
            getattr(Record.lookup(record_id=present_data.record_id), column)(
                getattr(present_data, column)
            )
        )
    return records


def build_candidate_pairs(records: DataFrame):
    """Block and score records, returning accepted and review-band pairs."""
    rows = {int(row["record_id"]): row for _, row in records.iterrows()}
    ids = sorted(rows)

    blocks: dict[str, list[int]] = {}
    for record_id in ids:
        for key in blocking_keys(rows[record_id]):
            blocks.setdefault(key, []).append(record_id)

    candidates: set[tuple[int, int]] = set()
    for members in blocks.values():
        for rec_a, rec_b in combinations(sorted(members), 2):
            candidates.add((rec_a, rec_b))

    accepted, review = [], []
    for pair_id, (rec_a, rec_b) in enumerate(sorted(candidates)):
        score = round(pair_score(rows[rec_a], rows[rec_b]), 4)
        pair = {
            "pair_id": pair_id,
            "rec_a": rec_a,
            "rec_b": rec_b,
            "score": score,
        }
        if score >= AUTO_MERGE:
            accepted.append(pair)
        elif score >= REVIEW_FLOOR:
            review.append(pair)

    matches = DataFrame(
        accepted, columns=["pair_id", "rec_a", "rec_b", "score"]
    )
    reviews = DataFrame(review, columns=["pair_id", "rec_a", "rec_b", "score"])
    return ids, len(candidates), matches, reviews


def load_candidate_facts(matches: DataFrame, reviews: DataFrame) -> None:
    """Load accepted matches and review pairs into the model."""
    match_data = model.data(matches)
    model.define(
        CandidateMatch.new(
            pair_id=match_data.pair_id,
            rec_a=Record.lookup(record_id=match_data.rec_a),
            rec_b=Record.lookup(record_id=match_data.rec_b),
            score=match_data.score,
        )
    )

    review_data = model.data(reviews)
    model.define(
        ReviewPair.new(
            pair_id=review_data.pair_id,
            rec_a=Record.lookup(record_id=review_data.rec_a),
            rec_b=Record.lookup(record_id=review_data.rec_b),
            score=review_data.score,
        )
    )


def load_ground_truth() -> DataFrame:
    """Read the optional labels used by the runner's evaluation section."""
    return read_csv(DATA_DIR / "ground_truth.csv")


def load_source_data():
    """Load records, candidate facts, and review facts."""
    records = load_records()
    ids, candidate_total, matches, reviews = build_candidate_pairs(records)
    load_candidate_facts(matches, reviews)
    return records, ids, candidate_total, matches, reviews


(
    records_df,
    record_ids,
    candidate_count,
    matches_df,
    review_df,
) = load_source_data()
