"""Semantic schema for the book slate template: readers, books, authors, subjects, slots, and the edges between them."""

from relationalai.semantics import Integer, Model, String

model = Model("book_slate_recommendation")

# Item super-concept: heterogeneous-KG node base for User/Book/Author/
# Subject. The path walker traverses a single 2-arity edge relationship
# (Item.connected_to, defined in candidate_paths.py) across the whole KG. The
# unified-edge layer is needed because a path() call walks one 2-arity
# relationship at a time, so the symmetric union of typed edges is
# pre-materialised onto Item.connected_to.
Item = model.Concept("Item")

# User concept: a reader.
User = model.Concept("User", extends=[Item], identify_by={"id": Integer})
User.name = model.Property(f"{User} has {String:name}")

# Book concept: a catalog item with bibliographic and freshness/
# in-house attributes. ``in_house`` is an Integer 0/1 flag.
Book = model.Concept("Book", extends=[Item], identify_by={"id": Integer})
Book.title = model.Property(f"{Book} has {String:title}")
Book.age_days = model.Property(f"{Book} has {Integer:age_days}")
Book.in_house = model.Property(f"{Book} has {Integer:in_house}")

# Author concept: a book's writer.
Author = model.Concept("Author", extends=[Item], identify_by={"id": Integer})
Author.name = model.Property(f"{Author} has {String:name}")

# Subject concept: a topical category attached to books.
Subject = model.Concept("Subject", extends=[Item], identify_by={"id": Integer})
Subject.name = model.Property(f"{Subject} has {String:name}")

# Slot concept: positions 1..K in the slate. Used by the slot-
# uniqueness IC to express a per-pair count cap (at most one
# Candidate per (user, Slot.pos)) -- the GCC-style CSP idiom.
# Slot K+1 (unpicked) is intentionally not a Slot row, so the cap
# only applies to filled positions.
Slot = model.Concept("Slot", identify_by={"pos": Integer})

# Typed edges between concepts: read events, authorship, subject
# attachment, and the book-similarity input.

User.read = model.Relationship(
    f"{User:user} read {Book:book} with rating {Integer:rating}",
    short_name="read",
)

Book.written_by = model.Relationship(
    f"{Book:book} written by {Author:author}",
    short_name="written_by",
)

Book.about = model.Relationship(
    f"{Book:book} about subject {Subject:subject}",
    short_name="about",
)

Book.similar_to = model.Relationship(
    f"{Book:book} similar to {Book:other}",
    short_name="similar_to",
)
