"""Open Library (CC0) slice fetcher for book_slate_recommendation.

Pulls a deterministic small slice of Open Library data (~60 books,
~58 authors, 12 subjects) and emits the 8-CSV bundle the runner
ingests (books, authors, subjects, book_author, book_subject,
book_similar, users, read). Synthetic users and read events are
generated on top, and ``book_similar.csv`` is derived deterministi-
cally from shared-author / shared-subject overlap in the Open
Library data -- so the template is fully self-contained without
depending on user-reading data (which Open Library does not
publish).

Why Open Library: bibliographic catalog, 100% CC0
(<https://openlibrary.org/dev/docs/api>), explicitly safe for public
templates. MovieLens / Goodreads / Amazon-Book carry non-commercial
clauses incompatible with shippable customer templates. DBLP and
OpenFoodFacts are the other CC0 options; books read more naturally
for slate-recommendation framing than papers or food products.

Usage
-----
::

    python data/fetch_open_library_slice.py            # default slice (~60 books)
    python data/fetch_open_library_slice.py --size md  # ~250 books
    python data/fetch_open_library_slice.py --size lg  # ~600 books

The script writes 8 CSVs into ``data/`` and is idempotent: re-runs
that hit the cache (``data/_cache/``) produce identical CSVs without
re-querying the API. Customers wanting larger instances bump
``--size`` and re-run; the same script scales.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

# --- Configuration --------------------------------------------------

OPEN_LIBRARY_BASE = "https://openlibrary.org"

# Open Library asks API consumers to include a contact in the
# User-Agent (https://openlibrary.org/developers/api). Customers
# running ``--size md`` or ``--size lg`` should swap this stub for
# a real contact -- without it the unidentified rate limit (1 req/s)
# applies and high-volume runs will be throttled.
USER_AGENT = (
    "book-slate-recommendation-template/1.0 (RelationalAI; "
    "set CONTACT in fetch_open_library_slice.py before running --size md/lg)"
)

# Per-request sleep after a successful API call. 1.0s honours
# Open Library's documented unidentified rate limit; identified
# clients can drop this to ~0.35s.
REQUEST_SLEEP_S = 1.0

SEED = 20260430

# Reference year for ``age_days`` computation. Frozen (not
# ``date.today().year``) so the bundled CSVs and customer reruns are
# byte-deterministic across calendar years -- a rerun in 2030 from
# the same Open Library cache produces identical books.csv as a rerun
# today. Bump when refreshing the bundled snapshot.
REFERENCE_YEAR = 2026

# Curated subject seeds. These are stable Open Library subject slugs
# that return well-populated work lists; chosen for KG overlap (some
# books span 2-3 of these so the shared-subject graph has structure).
SUBJECT_SEEDS_DEFAULT = [
    "science_fiction",
    "fantasy",
    "mystery",
    "detective_fiction",
    "adventure",
    "horror",
    "historical_fiction",
    "love_stories",
    "humor",
    "biography",
    "philosophy",
    "war_stories",
]

# Per-size dataset dials.
SIZE_PROFILES = {
    "sm": {
        "works_per_subject": 8,
        "target_works": 60,
        "n_users": 25,
        "n_reads_per_user": 6,
        "n_similar_target": 400,
    },
    "md": {
        "works_per_subject": 25,
        "target_works": 250,
        "n_users": 80,
        "n_reads_per_user": 10,
        "n_similar_target": 1500,
    },
    "lg": {
        "works_per_subject": 60,
        "target_works": 600,
        "n_users": 200,
        "n_reads_per_user": 15,
        "n_similar_target": 4000,
    },
}

# Fraction of books marked as in-house "originals" (synthetic flag,
# since Open Library does not carry an "original-publisher" notion
# that maps cleanly to streaming-platform originals).
IN_HOUSE_FRACTION = 0.20


# --- Open Library API helpers ---------------------------------------


def _http_get_json(url: str, cache_dir: Path) -> dict:
    """GET ``url`` as JSON with a stable on-disk cache.

    The cache key is the URL path; reruns never re-query the API. This
    keeps the bundled CSVs reproducible and makes the script polite to
    the public Open Library service. A cache file that fails to parse
    (interrupted write, stale HTML error body) is treated as a cache
    miss and re-fetched; cache writes are atomic via temp-file rename
    so an interrupted write never poisons the cache.
    """
    cache_key = re.sub(r"[^a-zA-Z0-9._-]+", "_", url) + ".json"
    cache_file = cache_dir / cache_key
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            # Corrupt cache entry: drop it and re-fetch.
            cache_file.unlink(missing_ok=True)

    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            cache_dir.mkdir(parents=True, exist_ok=True)
            tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
            tmp_file.write_text(json.dumps(payload))
            tmp_file.replace(cache_file)
            time.sleep(REQUEST_SLEEP_S)
            return payload
        except (HTTPError, URLError, TimeoutError) as exc:
            last_err = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(
        f"Open Library fetch failed after 3 retries: {url} "
        f"({type(last_err).__name__}: {last_err})"
    ) from last_err


def fetch_subject(subject: str, limit: int, cache_dir: Path) -> list[dict]:
    """Return the works under an Open Library subject slug."""
    url = f"{OPEN_LIBRARY_BASE}/subjects/{quote(subject)}.json?limit={limit}"
    payload = _http_get_json(url, cache_dir)
    return payload.get("works", [])


def fetch_work(work_key: str, cache_dir: Path) -> dict:
    """Return the full work record for an Open Library work key."""
    url = f"{OPEN_LIBRARY_BASE}{work_key}.json"
    return _http_get_json(url, cache_dir)


# --- Slice extraction ----------------------------------------------


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build_slice(
    subjects: list[str],
    works_per_subject: int,
    target_works: int,
    cache_dir: Path,
) -> dict:
    """Pull works/authors/subjects from Open Library and dedupe.

    Returns a dict with normalized lists keyed on integer ids assigned
    deterministically here (Open Library keys are stable strings, but
    the runner uses integers for ``identify_by`` ergonomics).
    """
    print(
        f"Fetching {len(subjects)} subjects, up to {works_per_subject} works each ..."
    )
    raw_works: dict[str, dict] = {}
    subject_to_works: dict[str, list[str]] = {}
    for subject in subjects:
        works = fetch_subject(subject, works_per_subject, cache_dir)
        subject_to_works[subject] = []
        for w in works:
            key = w.get("key")
            if not key:
                continue
            raw_works.setdefault(key, w)
            subject_to_works[subject].append(key)
        print(f"  /subjects/{subject}: {len(works)} works")

    # Dedupe + cap to target.
    rng = random.Random(SEED)
    work_keys = sorted(raw_works.keys())
    rng.shuffle(work_keys)
    if len(work_keys) > target_works:
        work_keys = work_keys[:target_works]
    work_keys.sort()

    # Assign integer ids.
    work_id_by_key = {key: i + 1 for i, key in enumerate(work_keys)}

    # Collect authors + per-work subjects from the work records.
    print(f"Resolving {len(work_keys)} work records ...")
    authors_by_key: dict[str, str] = {}
    work_authors: dict[str, list[str]] = {}
    work_subjects: dict[str, list[str]] = {}
    work_titles: dict[str, str] = {}
    work_publish_year: dict[str, int | None] = {}
    for i, key in enumerate(work_keys, start=1):
        # Subject-listing payloads carry a partial work shape; for
        # complete subjects + authors we hit /works/<key>.json.
        record = fetch_work(key, cache_dir)
        title = (record.get("title") or "").strip()
        if not title:
            title = (
                raw_works.get(key, {}).get("title") or ""
            ).strip() or f"work_{i:03d}"
        work_titles[key] = title

        authors = []
        for ar in record.get("authors", []):
            akey = (ar.get("author") or {}).get("key")
            if akey:
                authors.append(akey)
        if not authors:
            for ar in raw_works.get(key, {}).get("authors", []):
                akey = ar.get("key")
                if akey and akey.startswith("/authors/"):
                    authors.append(akey)
                elif "name" in ar:
                    authors.append(f"/authors/_inline_{_slugify(ar['name'])}")
                    authors_by_key[authors[-1]] = ar["name"]
        work_authors[key] = sorted(set(authors))

        subj_list = (
            record.get("subjects") or raw_works.get(key, {}).get("subject") or []
        )
        norm = []
        for s in subj_list:
            if not isinstance(s, str):
                continue
            s2 = s.strip()
            if not s2:
                continue
            norm.append(s2.lower())
        work_subjects[key] = sorted(set(norm))[:8]

        year = record.get("first_publish_date") or raw_works.get(key, {}).get(
            "first_publish_year"
        )
        if isinstance(year, str):
            m = re.search(r"\b(\d{4})\b", year)
            year = int(m.group(1)) if m else None
        elif not isinstance(year, int):
            year = None
        work_publish_year[key] = year

    # Drop works with no authors (the runner's MAX_PER_AUTHOR cap and
    # the typed-evidence join silently exempt author-less books, which
    # produces surprising slate behavior). Author-less works in Open
    # Library are typically incomplete records; safer to omit than
    # propagate.
    keys_with_authors = [k for k in work_keys if work_authors[k]]
    n_dropped_no_authors = len(work_keys) - len(keys_with_authors)
    if n_dropped_no_authors:
        print(
            f"  WARNING: dropping {n_dropped_no_authors} work(s) "
            "with no resolvable authors."
        )
        work_keys = keys_with_authors
        work_id_by_key = {key: i + 1 for i, key in enumerate(work_keys)}

    # Resolve author names for keys we pulled from /works payloads.
    author_keys_to_resolve = sorted(
        {k for keys in work_authors.values() for k in keys if k not in authors_by_key}
    )
    print(f"Resolving {len(author_keys_to_resolve)} authors ...")
    n_author_resolve_failures = 0
    for akey in author_keys_to_resolve:
        if akey.startswith("/authors/_inline_"):
            continue
        try:
            payload = _http_get_json(f"{OPEN_LIBRARY_BASE}{akey}.json", cache_dir)
            authors_by_key[akey] = (payload.get("name") or akey).strip()
        except RuntimeError:
            # Fall back to the OL key tail (e.g. "OL12345A") so the
            # author still appears in the output. The slice will mix
            # real names with opaque tails for these rows.
            authors_by_key[akey] = akey.split("/")[-1]
            n_author_resolve_failures += 1
    if n_author_resolve_failures:
        print(
            f"  WARNING: {n_author_resolve_failures} author name(s) "
            "fell back to the Open Library key (HTTP fetch failed)."
        )

    n_year_synthesized = 0
    for key in work_keys:
        if work_publish_year.get(key) is None:
            n_year_synthesized += 1
    if n_year_synthesized:
        print(
            f"  WARNING: {n_year_synthesized} book(s) had no publishable "
            "year in Open Library; emit_csvs() will synthesise one in "
            "the 1900-current range so age_days is defined."
        )

    return {
        "work_keys": work_keys,
        "work_id_by_key": work_id_by_key,
        "work_titles": work_titles,
        "work_authors": work_authors,
        "work_subjects": work_subjects,
        "work_publish_year": work_publish_year,
        "authors_by_key": authors_by_key,
    }


# --- CSV emission ---------------------------------------------------


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def emit_csvs(slice_data: dict, profile: dict, data_dir: Path) -> None:
    rng = random.Random(SEED + 1)

    # Books.
    work_keys = slice_data["work_keys"]
    work_id_by_key = slice_data["work_id_by_key"]
    n_books = len(work_keys)
    in_house_target = max(1, int(round(n_books * IN_HOUSE_FRACTION)))
    in_house_ids = set(rng.sample(range(1, n_books + 1), in_house_target))

    current_year = REFERENCE_YEAR
    book_rows = []
    for key in work_keys:
        bid = work_id_by_key[key]
        year = slice_data["work_publish_year"].get(key)
        if not year or year < 1500 or year > current_year:
            year = rng.randint(1900, current_year - 1)
        age_years = max(0, current_year - year)
        age_days = age_years * 365 + rng.randint(0, 364)
        title = slice_data["work_titles"][key].replace("\n", " ").strip()[:120]
        book_rows.append(
            {
                "id": bid,
                "title": title,
                "age_days": age_days,
                "in_house": 1 if bid in in_house_ids else 0,
            }
        )
    _write_csv(
        data_dir / "books.csv",
        ["id", "title", "age_days", "in_house"],
        book_rows,
    )

    # Authors.
    authors_used = sorted(
        {a for key in work_keys for a in slice_data["work_authors"][key]}
    )
    author_id_by_key = {a: i + 1 for i, a in enumerate(authors_used)}
    author_rows = [
        {"id": aid, "name": slice_data["authors_by_key"].get(akey, akey).strip()[:120]}
        for akey, aid in author_id_by_key.items()
    ]
    _write_csv(data_dir / "authors.csv", ["id", "name"], author_rows)

    # Subjects (broad). Pick the most frequent across the slice; cap
    # to keep the genre cardinality balanced, the way the runner's
    # subject-diversity dial expects.
    subj_counts: dict[str, int] = {}
    for key in work_keys:
        for s in slice_data["work_subjects"][key]:
            subj_counts[s] = subj_counts.get(s, 0) + 1
    top_subjects = [
        s for s, _ in sorted(subj_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:12]
    subject_id_by_name = {s: i + 1 for i, s in enumerate(top_subjects)}
    _write_csv(
        data_dir / "subjects.csv",
        ["id", "name"],
        [{"id": sid, "name": name[:80]} for name, sid in subject_id_by_name.items()],
    )

    # Book -> Authors.
    book_author_rows = []
    for key in work_keys:
        bid = work_id_by_key[key]
        for akey in slice_data["work_authors"][key]:
            aid = author_id_by_key[akey]
            book_author_rows.append({"book_id": bid, "author_id": aid})
    book_author_rows.sort(key=lambda r: (r["book_id"], r["author_id"]))
    _write_csv(
        data_dir / "book_author.csv",
        ["book_id", "author_id"],
        book_author_rows,
    )

    # Book -> Subjects (only the top-N kept above; drop the long tail).
    book_subject_rows = []
    for key in work_keys:
        bid = work_id_by_key[key]
        kept = [s for s in slice_data["work_subjects"][key] if s in subject_id_by_name]
        if not kept:
            kept = [next(iter(top_subjects))]
        for sname in kept:
            book_subject_rows.append(
                {"book_id": bid, "subject_id": subject_id_by_name[sname]}
            )
    book_subject_rows.sort(key=lambda r: (r["book_id"], r["subject_id"]))
    _write_csv(
        data_dir / "book_subject.csv",
        ["book_id", "subject_id"],
        book_subject_rows,
    )

    # Similar_to: derived from shared author OR shared subject. Two
    # books are "similar" if they share at least one author, or at
    # least one subject. This produces a sparse, locally-dense graph
    # (the property KG-walk path counts need to differentiate users).
    book_authors_idx: dict[int, set[int]] = {}
    book_subjects_idx: dict[int, set[int]] = {}
    for r in book_author_rows:
        book_authors_idx.setdefault(r["book_id"], set()).add(r["author_id"])
    for r in book_subject_rows:
        book_subjects_idx.setdefault(r["book_id"], set()).add(r["subject_id"])
    sim_edges: set[tuple[int, int]] = set()
    book_ids = sorted(book_authors_idx)
    for i, a in enumerate(book_ids):
        for b in book_ids[i + 1 :]:
            shared_authors = book_authors_idx[a] & book_authors_idx[b]
            shared_subjects = book_subjects_idx.get(a, set()) & book_subjects_idx.get(
                b, set()
            )
            # Include any pair that shares an author or at least one
            # subject -- keeps the similarity graph dense enough that
            # every user's 2-hop reach covers a reasonable slice of
            # the catalog (otherwise users whose reads cluster in a
            # corner can have no fresh / in-house candidates).
            if shared_authors or shared_subjects:
                sim_edges.add((a, b))
                sim_edges.add((b, a))

    # Cap similar_to roughly to target with deterministic shuffle.
    target = profile["n_similar_target"]
    edge_list = sorted(sim_edges)
    if len(edge_list) > target:
        rng_e = random.Random(SEED + 2)
        rng_e.shuffle(edge_list)
        edge_list = sorted(edge_list[:target])
    _write_csv(
        data_dir / "book_similar.csv",
        ["src_book_id", "dst_book_id"],
        [{"src_book_id": a, "dst_book_id": b} for (a, b) in edge_list],
    )

    # Synthetic users.
    n_users = profile["n_users"]
    users = [{"id": i + 1, "name": f"user_{i + 1:03d}"} for i in range(n_users)]
    _write_csv(data_dir / "users.csv", ["id", "name"], users)

    # Synthetic read events with per-user subject bias so user tastes
    # diverge (this is what produces differentiable per-user candidate
    # sets and KG path counts).
    book_subject_lookup: dict[int, list[int]] = {}
    for r in book_subject_rows:
        book_subject_lookup.setdefault(r["book_id"], []).append(r["subject_id"])
    n_reads = profile["n_reads_per_user"]
    n_subjects = len(top_subjects)
    book_id_pool = sorted(book_authors_idx)
    fresh_pool = sorted(r["id"] for r in book_rows if r["age_days"] <= 365 * 30)
    in_house_pool = sorted(in_house_ids)
    rng_r = random.Random(SEED + 3)
    read_rows = []
    for user in users:
        bias_subject = rng_r.randint(1, max(1, n_subjects))
        weights = [
            (1.6 if bias_subject in book_subject_lookup.get(b, []) else 1.0)
            for b in book_id_pool
        ]
        picks: list[int] = []
        # Plant at least one in-house and one fresh read so each user's
        # 2-hop reach has a chance of containing in-house / fresh
        # candidates (the data-side analogue of pre-warming the slate-
        # composer's reach distribution -- without it, users whose
        # reads cluster in an old-only corner of the catalog have
        # zero feasible slates).
        if in_house_pool:
            picks.append(rng_r.choice(in_house_pool))
        if fresh_pool:
            f = rng_r.choice(fresh_pool)
            if f not in picks:
                picks.append(f)
        attempts = 0
        while len(picks) < n_reads and attempts < n_reads * 8:
            bid = rng_r.choices(book_id_pool, weights=weights)[0]
            if bid not in picks:
                picks.append(bid)
            attempts += 1
        for bid in picks:
            read_rows.append(
                {"user_id": user["id"], "book_id": bid, "rating": rng_r.randint(3, 5)}
            )
    _write_csv(
        data_dir / "read.csv",
        ["user_id", "book_id", "rating"],
        read_rows,
    )

    print(
        f"\nWrote CSVs to {data_dir}:\n"
        f"  users.csv:         {len(users)} users\n"
        f"  books.csv:         {len(book_rows)} books\n"
        f"  authors.csv:       {len(author_rows)} authors\n"
        f"  subjects.csv:      {len(top_subjects)} subjects\n"
        f"  book_author.csv:   {len(book_author_rows)} (book, author) edges\n"
        f"  book_subject.csv:  {len(book_subject_rows)} (book, subject) edges\n"
        f"  book_similar.csv:  {len(edge_list)} similar_to edges\n"
        f"  read.csv:          {len(read_rows)} read events\n"
    )


# --- CLI ------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size",
        choices=sorted(SIZE_PROFILES.keys()),
        default="sm",
        help="Slice size profile (default: sm). md/lg fetch more from Open Library.",
    )
    parser.add_argument(
        "--subjects",
        nargs="+",
        default=SUBJECT_SEEDS_DEFAULT,
        help="Open Library subject slugs to seed the slice from.",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent
    cache_dir = data_dir / "_cache"
    profile = SIZE_PROFILES[args.size]

    slice_data = build_slice(
        subjects=args.subjects,
        works_per_subject=profile["works_per_subject"],
        target_works=profile["target_works"],
        cache_dir=cache_dir,
    )
    emit_csvs(slice_data, profile, data_dir)


if __name__ == "__main__":
    main()
