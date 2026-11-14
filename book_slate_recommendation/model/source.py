"""Load the sample reader, book, and reading-history data, and check it before the model is built."""

from pathlib import Path

from pandas import DataFrame, read_csv
from relationalai.semantics import Integer

from .schema import Author, Book, Slot, Subject, User, model

# Slate size: the K of "row of K things". Tune to taste.
SLATE_SIZE_K = 3

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Load all CSVs upfront so pre-solve invariants can validate the data
# integrity before any model.define rules are installed.
# --------------------------------------------------

users_csv = read_csv(DATA_DIR / "users.csv")
books_csv = read_csv(DATA_DIR / "books.csv")
authors_csv = read_csv(DATA_DIR / "authors.csv")
subjects_csv = read_csv(DATA_DIR / "subjects.csv")
reads_csv = read_csv(DATA_DIR / "read.csv")
book_authors_csv = read_csv(DATA_DIR / "book_author.csv")
book_subjects_csv = read_csv(DATA_DIR / "book_subject.csv")
book_similarities_csv = read_csv(DATA_DIR / "book_similar.csv")

# Slot positions 1..K. The Slot concept exists so the slot-uniqueness
# IC counts distinct slot Concept values (the social_golfer idiom)
# rather than distinct anonymous Integer values. K+1 is the unpicked
# sentinel and is intentionally not a Slot row -- only filled
# positions are counted.
slots_df = DataFrame({"pos": list(range(1, SLATE_SIZE_K + 1))})

# --------------------------------------------------
# Pre-solve invariants
#
# Catch the common silent-failure modes before the solver runs:
# duplicate keys (would collapse rows), dangling FKs (would silently
# drop joins), and negative ages (would break the freshness predicate).
# Each helper raises a focused ValueError naming the offending rows.
# --------------------------------------------------


def _assert_no_nulls(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    null_cols = [c for c in cols if df[c].isna().any()]
    if null_cols:
        raise ValueError(
            f"{source} has null/NaN values in column(s) {null_cols}. Required "
            f"columns must be fully populated; drop or impute the offending rows."
        )


def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    _assert_no_nulls(df, cols, source)
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate ({', '.join(cols)})={duplicates}. "
            f"Each key must be unique; remove or merge the conflicting rows."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    _assert_no_nulls(child_df, child_col, source)
    parent_ids = set(int(v) for v in parent_df[parent_col].unique())
    dangling = sorted({int(v) for v in child_df[child_col].unique() if int(v) not in parent_ids})
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve."
        )


def _assert_nonneg_column(df, col, source):
    _assert_no_nulls(df, col, source)
    bad = sorted({int(v) for v in df[col].tolist() if int(v) < 0})
    if bad:
        raise ValueError(f"{source} has negative {col}={bad}. {col} must be >= 0.")


def _assert_in_set(df, col, allowed, source):
    _assert_no_nulls(df, col, source)
    bad = sorted({int(v) for v in df[col].tolist() if int(v) not in allowed})
    if bad:
        raise ValueError(
            f"{source} has {col}={bad} outside the allowed set {sorted(allowed)}. "
            f"{col} is a {sorted(allowed)} flag; values outside this set will silently "
            f"miscompare in IC predicates."
        )


for _df, _key, _src in [
    (users_csv, "id", "users.csv"),
    (books_csv, "id", "books.csv"),
    (authors_csv, "id", "authors.csv"),
    (subjects_csv, "id", "subjects.csv"),
]:
    _assert_unique_keys(_df, _key, _src)

# Similarity edges must be unique on (src, dst) -- duplicate edges
# would inflate triangle counts and skew hero-pin eligibility.
_assert_unique_keys(book_similarities_csv, ["src_book_id", "dst_book_id"], "book_similar.csv")

# Foreign-key edges in the schema. Each row says "<source>.<col>
# references <parent_source>.<parent_col>". Update this table when you
# add a new edge table or rewire a FK; the loop below validates every
# edge in one place.
_FK_EDGES = [
    (reads_csv, "user_id", users_csv, "id", "read.csv", "users.csv"),
    (reads_csv, "book_id", books_csv, "id", "read.csv", "books.csv"),
    (book_authors_csv, "book_id", books_csv, "id", "book_author.csv", "books.csv"),
    (book_authors_csv, "author_id", authors_csv, "id", "book_author.csv", "authors.csv"),
    (book_subjects_csv, "book_id", books_csv, "id", "book_subject.csv", "books.csv"),
    (book_subjects_csv, "subject_id", subjects_csv, "id", "book_subject.csv", "subjects.csv"),
    (book_similarities_csv, "src_book_id", books_csv, "id", "book_similar.csv", "books.csv"),
    (book_similarities_csv, "dst_book_id", books_csv, "id", "book_similar.csv", "books.csv"),
]
for _cdf, _ccol, _pdf, _pcol, _csrc, _psrc in _FK_EDGES:
    _assert_no_dangling_fks(_cdf, _ccol, _pdf, _pcol, _csrc, _psrc)

_assert_nonneg_column(books_csv, "age_days", "books.csv")
_assert_in_set(books_csv, "in_house", {0, 1}, "books.csv")

model.define(User.new(model.data(users_csv).to_schema()))
model.define(Book.new(model.data(books_csv).to_schema()))
model.define(Author.new(model.data(authors_csv).to_schema()))
model.define(Subject.new(model.data(subjects_csv).to_schema()))
model.define(Slot.new(model.data(slots_df).to_schema()))

read_data = model.data(reads_csv)
rating_ref = Integer.ref()
model.define(User.read(User, Book, rating_ref)).where(
    User.id == read_data.user_id,
    Book.id == read_data.book_id,
    rating_ref == read_data.rating,
)

ba_data = model.data(book_authors_csv)
model.define(Book.written_by(Book, Author)).where(
    Book.id == ba_data.book_id,
    Author.id == ba_data.author_id,
)

bs_data = model.data(book_subjects_csv)
model.define(Book.about(Book, Subject)).where(
    Book.id == bs_data.book_id,
    Subject.id == bs_data.subject_id,
)

bsim_data = model.data(book_similarities_csv)
src_b, dst_b = Book.ref(), Book.ref()
model.define(Book.similar_to(src_b, dst_b)).where(
    src_b.id == bsim_data.src_book_id,
    dst_b.id == bsim_data.dst_book_id,
)
