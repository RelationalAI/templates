"""Candidate set: bounded knowledge-graph walks from each reader, the explanation path counts of each
candidate, and which candidates the reader has already read."""

from relationalai.semantics import Integer, count

from .schema import Author, Book, Item, Subject, User, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Bounded path depth for the KG walk. MAX_HOPS = 2 enumerates
# ``User -> read_Book`` (length 1, pruned by exclude_read_ic) and
# ``User -> read_Book -> similar_Book`` (length 2). Bumping to 3+
# saturates fast on a heterogeneous KG (most users reach most books).
MAX_HOPS = 2

# Unified KG edge: a single 2-arity Item.connected_to relationship
# the path walker traverses, because a path() call walks one 2-arity
# relationship at a time. Each define() below contributes one direction
# of one typed edge to this symmetric union; the walker treats them all
# as the same generic hop. The typed-evidence
# properties below join candidate books directly against the user's
# read history via Book.written_by / Book.about rather than
# introspecting walker paths -- simpler and faster.
Item.connected_to = model.Relationship(
    f"{Item:src} connected to {Item:dst}",
    short_name="connected_to",
)

# User <-> Book via read (both directions; user-anchor walks).
u_e, b_e = User.ref(), Book.ref()
rating_e = Integer.ref()
model.define(Item.connected_to(u_e, b_e)).where(
    User.read(u_e, b_e, rating_e),
)
model.define(Item.connected_to(b_e, u_e)).where(
    User.read(u_e, b_e, rating_e),
)

# Book <-> Author.
b_a, a_e = Book.ref(), Author.ref()
model.define(Item.connected_to(b_a, a_e)).where(Book.written_by(b_a, a_e))
model.define(Item.connected_to(a_e, b_a)).where(Book.written_by(b_a, a_e))

# Book <-> Subject.
b_s, s_e = Book.ref(), Subject.ref()
model.define(Item.connected_to(b_s, s_e)).where(Book.about(b_s, s_e))
model.define(Item.connected_to(s_e, b_s)).where(Book.about(b_s, s_e))

# Book <-> Book via similar_to (both directions; the similarity graph
# is conceptually undirected for traversal purposes).
b_s1, b_s2 = Book.ref(), Book.ref()
model.define(Item.connected_to(b_s1, b_s2)).where(Book.similar_to(b_s1, b_s2))
model.define(Item.connected_to(b_s2, b_s1)).where(Book.similar_to(b_s1, b_s2))

# --------------------------------------------------
# Stage 1: Bounded KG walks via the paths library (architectural centerpiece)
#
# This is the load-bearing stage. The Candidate concept is derived
# from the path walker; without paths there are no candidates and no
# CSP variables. The per-typed counts produced here feed the
# engagement-weighted explanation floor, the cold-start cap, and the
# objective.
# --------------------------------------------------

# Walk the unified ``Item.connected_to`` edge from each User up to
# MAX_HOPS hops. The path pattern bounds the walk to MAX_HOPS, so the
# candidate set is the bounded reachable set under the KG. Naming the
# endpoints as a User and a Book lets the same pattern answer both
# "is this book reachable from this user" (``exists``, no
# enumeration) and "how many walks reach it" (``count``).
walk_user, walk_book = User.ref(), Book.ref()
kg_walks = model.path(
    walk_user,
    Item.connected_to.repeat(1, MAX_HOPS),
    walk_book,
)

# Candidate set: any (user, book) joined by a bounded KG walk. Books the
# user already read stay candidates; the already-read exclusion below
# forces them to the unpicked slot K+1.
Candidate = model.Concept(
    "Candidate",
    identify_by={"user_id": Integer, "book_id": Integer},
)
model.define(Candidate.new(user_id=walk_user.id, book_id=walk_book.id)).where(
    kg_walks.exists(),
)

# Per-(user, candidate) explanation features: counts of distinct
# typed connections between the candidate and the user's read
# history.
#
# The author and subject ``count`` expressions are followed by ``| 0``
# so the property is defined for *every* Candidate (not only those
# with at least one match). PyRel aggregates over an empty group produce no row, and
# the position-weighted explanation IC would silently drop Candidates
# whose property is undefined.
#
# Arithmetic ``a + s + w`` (not ``sum(model.union(a, s, w))``) --
# union inside an aggregate body strips keys and deduplicates on
# projected values, undercounting whenever two of the three typed
# counts share a value.
Candidate.path_count_via_author = model.Property(f"{Candidate} has author connections {Integer:n}")
Candidate.path_count_via_subject = model.Property(
    f"{Candidate} has subject connections {Integer:n}"
)
Candidate.path_count_via_kg_walk = model.Property(f"{Candidate} has KG-walk paths {Integer:n}")
Candidate.path_count_total = model.Property(f"{Candidate} has total connections {Integer:n}")

c = Candidate.ref()
n = Integer.ref()
u_c, b_c = User.ref(), Book.ref()

# via-author: the number of distinct authors the candidate shares
# with the user's read books. count(a_ref) counts each shared author
# once, however many of the user's read books it appears on.
b_read_a = Book.ref()
a_ref = Author.ref()
model.define(Candidate.path_count_via_author(c, n)).where(
    Candidate(c),
    n
    == count(a_ref)
    .per(c)
    .where(
        c.user_id == u_c.id,
        c.book_id == b_c.id,
        User.read(u_c, b_read_a, Integer.ref()),
        Book.written_by(b_read_a, a_ref),
        Book.written_by(b_c, a_ref),
    )
    | 0,
)

# via-subject: the number of distinct subjects the candidate shares
# with the user's read books, counted like via-author.
b_read_s = Book.ref()
s_ref = Subject.ref()
model.define(Candidate.path_count_via_subject(c, n)).where(
    Candidate(c),
    n
    == count(s_ref)
    .per(c)
    .where(
        c.user_id == u_c.id,
        c.book_id == b_c.id,
        User.read(u_c, b_read_s, Integer.ref()),
        Book.about(b_read_s, s_ref),
        Book.about(b_c, s_ref),
    )
    | 0,
)

# via-walk: number of bounded heterogeneous KG paths from this user
# to the candidate (the actual paths-walk count -- the headline
# explanation-strength signal). Every Candidate has at least one walk,
# so this count is always defined.
model.define(Candidate.path_count_via_kg_walk(c, n)).where(
    Candidate(c),
    c.user_id == walk_user.id,
    c.book_id == walk_book.id,
    n == kg_walks.all().count().per(walk_user, walk_book),
)

# Total: sum across types as a single integer feature for cold-start
# threshold checks and explanation/objective weighting.
model.define(Candidate.path_count_total(c, n)).where(
    Candidate(c),
    n == c.path_count_via_author + c.path_count_via_subject + c.path_count_via_kg_walk,
)

# Already-read candidates: the user has read the book. Only a candidate the user
# has not read can be picked for the slate.
Candidate.is_read = model.Relationship(f"{Candidate} is a book its user has read")
u_read, b_read = User.ref(), Book.ref()
model.where(
    User.read(u_read, b_read, Integer.ref()),
    Candidate.user_id == u_read.id,
    Candidate.book_id == b_read.id,
).define(Candidate.is_read())
