"""Experimental harness comparing alternative formulations of
``count(...).per(c).where(...)`` for the per-(user, candidate) typed
path-count features in ``book_slate_recommendation``.

The known pitfall: ``count(x).per(c).where(P)`` returns no row for
``c``-groups with no matches. Downstream composite properties (e.g.
``path_count_total = via_a + via_s + via_walk``) and prescriptive
sum-floor ICs (e.g. ``sum(path_count_total * pick).per(user) >= K``)
then silently drop those candidates -- the INFEASIBLE that arises
when ``| 0`` defaults are missing.

``| 0`` is the documented PyRel fallback/default idiom for this
shape. The prescriptive reasoner's rewriter preserves PyRel rule
semantics ("empty sum = empty relation") and supports the Match-form
default end-to-end.

This harness probes six variants and uses ``problem.display()`` to
inspect the grounded MIP rather than running E2E solves.

Variants
--------
A: three counts each with ``| 0`` (current production form).
B: three counts each via an intermediate typed-evidence relationship
   (``shared_author`` / ``shared_subject`` / ``walked_to``), counted
   over the relationship -- still ``| 0`` to densify.
C: single ``Candidate.union_evidence`` relation populated by three
   define rules (PyRel rule-union semantics), then a single count
   over it -- still ``| 0`` because count-empty drops.
D: regression -- three counts, no ``| 0``. Reproduces the empty-
   group cascade-drop that breaks explanation_ic grounding.
E: ``model.union`` *inside* the count-where body; one count over the
   set-style union. Aggregates over a body Union flow through PyRel's
   Match-rewrite preserving set-style dedup semantics. Still ``| 0``.
F: sum the union of the three per-typed counts. Demonstrates the
   user-facing footgun: ``sum(model.union(propA, propB, propC))``
   silently undercounts whenever two operands share a value for the
   same Candidate (set-style projected-value dedup).

For each variant we:
- count Candidates and Candidates with path_count_total defined,
- show min/max path_count_total,
- run ``problem.display(explanation_ic)`` and report the number of
  picks bound into the constraint for the smoke-test user (id=5).
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from pandas import read_csv
from relationalai.semantics import (
    Float,
    Integer,
    Model,
    String,
    count,
    sum,
)
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std.paths import PathTraversal

DATA_DIR = Path(__file__).parent.parent / "data"
SLATE_SIZE_K = 3
MAX_HOPS = 2
MAX_PER_SUBJECT = 3
MAX_PER_AUTHOR = 1
FRESH_WINDOW_DAYS = 365 * 30
FRESHNESS_FLOOR = 1
ORIGINALS_FLOOR = 1
COLD_START_CAP = 2
WEAK_EXPLANATION_THRESHOLD = 2
EXPLANATION_FLOOR = 4
PAGERANK_WEIGHT = 100.0
PATH_SIGNAL_WEIGHT = 30.0


def build_base(name):
    model = Model(name)
    Item = model.Concept("Item")
    User = model.Concept("User", extends=[Item], identify_by={"id": Integer})
    User.name = model.Property(f"{User} has {String:name}")
    Book = model.Concept("Book", extends=[Item], identify_by={"id": Integer})
    Book.title = model.Property(f"{Book} has {String:title}")
    Book.age_days = model.Property(f"{Book} has {Integer:age_days}")
    Book.in_house = model.Property(f"{Book} has {Integer:in_house}")
    Author = model.Concept("Author", extends=[Item], identify_by={"id": Integer})
    Author.name = model.Property(f"{Author} has {String:name}")
    Subject = model.Concept("Subject", extends=[Item], identify_by={"id": Integer})
    Subject.name = model.Property(f"{Subject} has {String:name}")

    model.define(User.new(model.data(read_csv(DATA_DIR / "users.csv")).to_schema()))
    model.define(Book.new(model.data(read_csv(DATA_DIR / "books.csv")).to_schema()))
    model.define(Author.new(model.data(read_csv(DATA_DIR / "authors.csv")).to_schema()))
    model.define(
        Subject.new(model.data(read_csv(DATA_DIR / "subjects.csv")).to_schema())
    )

    User.read = model.Relationship(
        f"{User:user} read {Book:book} with rating {Integer:rating}",
        short_name="read",
    )
    rd = model.data(read_csv(DATA_DIR / "read.csv"))
    rr = Integer.ref()
    model.define(User.read(User, Book, rr)).where(
        User.id == rd.user_id, Book.id == rd.book_id, rr == rd.rating
    )

    Book.written_by = model.Relationship(
        f"{Book:book} written by {Author:author}", short_name="written_by"
    )
    ba = model.data(read_csv(DATA_DIR / "book_author.csv"))
    model.define(Book.written_by(Book, Author)).where(
        Book.id == ba.book_id, Author.id == ba.author_id
    )

    Book.about = model.Relationship(
        f"{Book:book} about subject {Subject:subject}", short_name="about"
    )
    bs = model.data(read_csv(DATA_DIR / "book_subject.csv"))
    model.define(Book.about(Book, Subject)).where(
        Book.id == bs.book_id, Subject.id == bs.subject_id
    )

    Book.similar_to = model.Relationship(
        f"{Book:book} similar to {Book:other}", short_name="similar_to"
    )
    bsim = model.data(read_csv(DATA_DIR / "book_similar.csv"))
    sb, db = Book.ref(), Book.ref()
    model.define(Book.similar_to(sb, db)).where(
        sb.id == bsim.src_book_id, db.id == bsim.dst_book_id
    )

    Item.connected_to = model.Relationship(
        f"{Item:src} connected to {Item:dst}", short_name="connected_to"
    )
    ue, be, re_ = User.ref(), Book.ref(), Integer.ref()
    model.define(Item.connected_to(ue, be)).where(User.read(ue, be, re_))
    model.define(Item.connected_to(be, ue)).where(User.read(ue, be, re_))
    bx, ax = Book.ref(), Author.ref()
    model.define(Item.connected_to(bx, ax)).where(Book.written_by(bx, ax))
    model.define(Item.connected_to(ax, bx)).where(Book.written_by(bx, ax))
    by, sy = Book.ref(), Subject.ref()
    model.define(Item.connected_to(by, sy)).where(Book.about(by, sy))
    model.define(Item.connected_to(sy, by)).where(Book.about(by, sy))
    bs1, bs2 = Book.ref(), Book.ref()
    model.define(Item.connected_to(bs1, bs2)).where(Book.similar_to(bs1, bs2))
    model.define(Item.connected_to(bs2, bs1)).where(Book.similar_to(bs1, bs2))

    sg = Graph(
        model, directed=False, weighted=False, node_concept=Book, aggregator="sum"
    )
    sgi, sgj = Book.ref(), Book.ref()
    model.define(sg.Edge.new(src=sgi, dst=sgj)).where(Book.similar_to(sgi, sgj))
    Book.pagerank_score = model.Property(
        f"{Book} has structural score {Float:pagerank_score}"
    )
    pg = sg.pagerank()
    bp, sp = Book.ref(), Float.ref()
    model.define(bp.pagerank_score(sp)).where(pg(bp, sp))

    kg_paths = model.path(Item.connected_to.repeat(1, MAX_HOPS)).all_paths()
    Candidate = model.Concept(
        "Candidate", identify_by={"user_id": Integer, "book_id": Integer}
    )
    uc, bc = User.ref(), Book.ref()
    pc = PathTraversal.ref()
    model.define(Candidate.new(user_id=uc.id, book_id=bc.id)).where(
        kg_paths(pc), pc.nodes(0, uc), pc.nodes(pc.length, bc)
    )
    Candidate.path_count_via_author = model.Property(
        f"{Candidate} has author connections {Integer:n}"
    )
    Candidate.path_count_via_subject = model.Property(
        f"{Candidate} has subject connections {Integer:n}"
    )
    Candidate.path_count_via_kg_walk = model.Property(
        f"{Candidate} has KG-walk paths {Integer:n}"
    )
    Candidate.path_count_total = model.Property(
        f"{Candidate} has total connections {Integer:n}"
    )
    return model, Item, User, Book, Author, Subject, Candidate, kg_paths


def add_v_A(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant A: three counts each with ``| 0`` (current)."""
    c, n = Candidate.ref(), Integer.ref()
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.path_count_via_author(c, n)).where(
        Candidate(c),
        n
        == count(ar)
        .per(c)
        .where(
            c.user_id == uc.id,
            c.book_id == bc.id,
            User.read(uc, bra, Integer.ref()),
            Book.written_by(bra, ar),
            Book.written_by(bc, ar),
        )
        | 0,
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.path_count_via_subject(c, n)).where(
        Candidate(c),
        n
        == count(sr)
        .per(c)
        .where(
            c.user_id == uc.id,
            c.book_id == bc.id,
            User.read(uc, brs, Integer.ref()),
            Book.about(brs, sr),
            Book.about(bc, sr),
        )
        | 0,
    )
    ps = PathTraversal.ref()
    model.define(Candidate.path_count_via_kg_walk(c, n)).where(
        Candidate(c),
        n
        == count(ps)
        .per(c)
        .where(
            kg_paths(ps),
            c.user_id == uc.id,
            c.book_id == bc.id,
            ps.nodes(0, uc),
            ps.nodes(ps.length, bc),
        )
        | 0,
    )
    model.define(Candidate.path_count_total(c, n)).where(
        Candidate(c),
        n
        == c.path_count_via_author
        + c.path_count_via_subject
        + c.path_count_via_kg_walk,
    )


def add_v_B(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant B: typed evidence relationships, count over them."""
    Candidate.shared_author = model.Relationship(
        f"{Candidate:c} shares author {Author:a}", short_name="shared_author"
    )
    Candidate.shared_subject = model.Relationship(
        f"{Candidate:c} shares subject {Subject:s}", short_name="shared_subject"
    )
    Candidate.walked_to = model.Relationship(
        f"{Candidate:c} walked via path {PathTraversal:p}", short_name="walked_to"
    )

    c = Candidate.ref()
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.shared_author(c, ar)).where(
        c.user_id == uc.id,
        c.book_id == bc.id,
        User.read(uc, bra, Integer.ref()),
        Book.written_by(bra, ar),
        Book.written_by(bc, ar),
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.shared_subject(c, sr)).where(
        c.user_id == uc.id,
        c.book_id == bc.id,
        User.read(uc, brs, Integer.ref()),
        Book.about(brs, sr),
        Book.about(bc, sr),
    )
    ps = PathTraversal.ref()
    model.define(Candidate.walked_to(c, ps)).where(
        c.user_id == uc.id,
        c.book_id == bc.id,
        kg_paths(ps),
        ps.nodes(0, uc),
        ps.nodes(ps.length, bc),
    )

    cc, n = Candidate.ref(), Integer.ref()
    a2 = Author.ref()
    model.define(Candidate.path_count_via_author(cc, n)).where(
        Candidate(cc),
        n == count(a2).per(cc).where(Candidate.shared_author(cc, a2)) | 0,
    )
    s2 = Subject.ref()
    model.define(Candidate.path_count_via_subject(cc, n)).where(
        Candidate(cc),
        n == count(s2).per(cc).where(Candidate.shared_subject(cc, s2)) | 0,
    )
    p2 = PathTraversal.ref()
    model.define(Candidate.path_count_via_kg_walk(cc, n)).where(
        Candidate(cc),
        n == count(p2).per(cc).where(Candidate.walked_to(cc, p2)) | 0,
    )
    model.define(Candidate.path_count_total(cc, n)).where(
        Candidate(cc),
        n
        == cc.path_count_via_author
        + cc.path_count_via_subject
        + cc.path_count_via_kg_walk,
    )


def add_v_C(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant C: single union_evidence relation, single count.

    Uses PyRel rule-level union: three define rules contribute rows to
    ``Candidate.union_evidence(c, kind, key)``. ``path_count_total``
    is then a single count over the union extension.

    We still define per-typed sub-counts ``| 0`` for inspection /
    cold-start IC. The structural difference: ``path_count_total`` is
    a *single* count, not a sum of three.
    """
    Candidate.union_evidence = model.Relationship(
        f"{Candidate:c} has evidence kind {Integer:kind} key {Integer:key}",
        short_name="union_evidence",
    )

    c = Candidate.ref()
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.union_evidence(c, 1, ar.id)).where(
        c.user_id == uc.id,
        c.book_id == bc.id,
        User.read(uc, bra, Integer.ref()),
        Book.written_by(bra, ar),
        Book.written_by(bc, ar),
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.union_evidence(c, 2, sr.id)).where(
        c.user_id == uc.id,
        c.book_id == bc.id,
        User.read(uc, brs, Integer.ref()),
        Book.about(brs, sr),
        Book.about(bc, sr),
    )
    ps = PathTraversal.ref()
    bp = Book.ref()
    model.define(Candidate.union_evidence(c, 3, bp.id)).where(
        c.user_id == uc.id,
        c.book_id == bp.id,
        kg_paths(ps),
        ps.nodes(0, User.ref()),
        ps.nodes(ps.length, bp),
    )

    # Per-type sub-counts for inspections.
    cc, n = Candidate.ref(), Integer.ref()
    key2 = Integer.ref()
    model.define(Candidate.path_count_via_author(cc, n)).where(
        Candidate(cc),
        n == count(key2).per(cc).where(Candidate.union_evidence(cc, 1, key2)) | 0,
    )
    key3 = Integer.ref()
    model.define(Candidate.path_count_via_subject(cc, n)).where(
        Candidate(cc),
        n == count(key3).per(cc).where(Candidate.union_evidence(cc, 2, key3)) | 0,
    )
    key4 = Integer.ref()
    model.define(Candidate.path_count_via_kg_walk(cc, n)).where(
        Candidate(cc),
        n == count(key4).per(cc).where(Candidate.union_evidence(cc, 3, key4)) | 0,
    )

    # Single count over union_evidence -- the headline test for variant C.
    cc2 = Candidate.ref()
    n2 = Integer.ref()
    kkx, kxk = Integer.ref(), Integer.ref()
    model.define(Candidate.path_count_total(cc2, n2)).where(
        Candidate(cc2),
        n2
        == count(kkx, kxk).per(cc2).where(Candidate.union_evidence(cc2, kkx, kxk)) | 0,
    )


def add_v_D(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant D: regression -- three counts, NO ``| 0``."""
    c, n = Candidate.ref(), Integer.ref()
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.path_count_via_author(c, n)).where(
        Candidate(c),
        n
        == count(ar)
        .per(c)
        .where(
            c.user_id == uc.id,
            c.book_id == bc.id,
            User.read(uc, bra, Integer.ref()),
            Book.written_by(bra, ar),
            Book.written_by(bc, ar),
        ),
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.path_count_via_subject(c, n)).where(
        Candidate(c),
        n
        == count(sr)
        .per(c)
        .where(
            c.user_id == uc.id,
            c.book_id == bc.id,
            User.read(uc, brs, Integer.ref()),
            Book.about(brs, sr),
            Book.about(bc, sr),
        ),
    )
    ps = PathTraversal.ref()
    model.define(Candidate.path_count_via_kg_walk(c, n)).where(
        Candidate(c),
        n
        == count(ps)
        .per(c)
        .where(
            kg_paths(ps),
            c.user_id == uc.id,
            c.book_id == bc.id,
            ps.nodes(0, uc),
            ps.nodes(ps.length, bc),
        ),
    )
    model.define(Candidate.path_count_total(c, n)).where(
        Candidate(c),
        n
        == c.path_count_via_author
        + c.path_count_via_subject
        + c.path_count_via_kg_walk,
    )


def add_v_E(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant E: ``model.union`` inside count.where; one count over set-style union.

    A Union inside an aggregate body flows through PyRel's
    Match-rewrite, and the aggregate sees a single Union as its body
    -- preserving set-style dedup semantics. We probe this with a
    single count over a 3-branch union of typed-evidence fragments.

    Each branch's projected key has a uniform ``(kind, key)`` shape
    so the union is well-typed.
    """
    cc, n = Candidate.ref(), Integer.ref()

    # Per-type sub-counts (kept for inspection).
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.path_count_via_author(cc, n)).where(
        Candidate(cc),
        n
        == count(ar)
        .per(cc)
        .where(
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            User.read(uc, bra, Integer.ref()),
            Book.written_by(bra, ar),
            Book.written_by(bc, ar),
        )
        | 0,
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.path_count_via_subject(cc, n)).where(
        Candidate(cc),
        n
        == count(sr)
        .per(cc)
        .where(
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            User.read(uc, brs, Integer.ref()),
            Book.about(brs, sr),
            Book.about(bc, sr),
        )
        | 0,
    )
    ps = PathTraversal.ref()
    model.define(Candidate.path_count_via_kg_walk(cc, n)).where(
        Candidate(cc),
        n
        == count(ps)
        .per(cc)
        .where(
            kg_paths(ps),
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            ps.nodes(0, uc),
            ps.nodes(ps.length, bc),
        )
        | 0,
    )

    # Variant-E composite: one count over model.union of three
    # branches, using the canonical PyRel union-unpacking idiom:
    # ``ec, ekind, ekey = m.union(branch1, branch2, branch3)`` makes
    # the union's columns first-class refs we can group on.
    c_total = Candidate.ref()
    uc2, bc2 = User.ref(), Book.ref()
    bra2, ar2 = Book.ref(), Author.ref()
    a_branch = model.where(
        c_total.user_id == uc2.id,
        c_total.book_id == bc2.id,
        User.read(uc2, bra2, Integer.ref()),
        Book.written_by(bra2, ar2),
        Book.written_by(bc2, ar2),
    ).select(c_total, 1, ar2.id)

    uc3, bc3 = User.ref(), Book.ref()
    brs3, sr3 = Book.ref(), Subject.ref()
    s_branch = model.where(
        c_total.user_id == uc3.id,
        c_total.book_id == bc3.id,
        User.read(uc3, brs3, Integer.ref()),
        Book.about(brs3, sr3),
        Book.about(bc3, sr3),
    ).select(c_total, 2, sr3.id)

    uc4, bc4 = User.ref(), Book.ref()
    ps4 = PathTraversal.ref()
    p_branch = model.where(
        c_total.user_id == uc4.id,
        c_total.book_id == bc4.id,
        kg_paths(ps4),
        ps4.nodes(0, uc4),
        ps4.nodes(ps4.length, bc4),
    ).select(c_total, 3, bc4.id)

    ec, ekind, ekey = model.union(a_branch, s_branch, p_branch)
    cc_E = Candidate.ref()
    n_E = Integer.ref()
    model.define(Candidate.path_count_total(cc_E, n_E)).where(
        Candidate(cc_E),
        cc_E == ec,
        n_E == count(ekind, ekey).per(ec) | 0,
    )


def add_v_F(model, Item, User, Book, Author, Subject, Candidate, kg_paths):
    """Variant F: sum the union of the per-typed counts.

    Three counts are computed (each ``| 0``) as separate properties.
    ``path_count_total`` is then ``sum(value).per(c)`` over a
    ``model.union`` of three branches, each branch projecting
    ``(c, value)`` from one of the typed-count properties.

    Caveat under set-style union semantics: tuples ``(c, v)`` are
    deduplicated. If two branches produce the same value for the same
    candidate (e.g. via_author=2 and via_subject=2 both yield (c,2)),
    the union collapses them and the sum is wrong relative to the
    arithmetic ``a + s + w`` form. We surface that as a finding rather
    than try to disambiguate.
    """
    cc, n = Candidate.ref(), Integer.ref()
    uc, bc = User.ref(), Book.ref()
    bra, ar = Book.ref(), Author.ref()
    model.define(Candidate.path_count_via_author(cc, n)).where(
        Candidate(cc),
        n
        == count(ar)
        .per(cc)
        .where(
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            User.read(uc, bra, Integer.ref()),
            Book.written_by(bra, ar),
            Book.written_by(bc, ar),
        )
        | 0,
    )
    brs, sr = Book.ref(), Subject.ref()
    model.define(Candidate.path_count_via_subject(cc, n)).where(
        Candidate(cc),
        n
        == count(sr)
        .per(cc)
        .where(
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            User.read(uc, brs, Integer.ref()),
            Book.about(brs, sr),
            Book.about(bc, sr),
        )
        | 0,
    )
    ps = PathTraversal.ref()
    model.define(Candidate.path_count_via_kg_walk(cc, n)).where(
        Candidate(cc),
        n
        == count(ps)
        .per(cc)
        .where(
            kg_paths(ps),
            cc.user_id == uc.id,
            cc.book_id == bc.id,
            ps.nodes(0, uc),
            ps.nodes(ps.length, bc),
        )
        | 0,
    )

    # Sum the union of the three count values, grouped per Candidate,
    # using the canonical PyRel union-unpacking idiom.
    cc_F = Candidate.ref()
    a_branch = model.select(cc_F, cc_F.path_count_via_author)
    s_branch = model.select(cc_F, cc_F.path_count_via_subject)
    w_branch = model.select(cc_F, cc_F.path_count_via_kg_walk)
    fc, fv = model.union(a_branch, s_branch, w_branch)
    cc_F2, n_F = Candidate.ref(), Integer.ref()
    model.define(Candidate.path_count_total(cc_F2, n_F)).where(
        Candidate(cc_F2),
        cc_F2 == fc,
        n_F == sum(fv).per(fc) | 0,
    )


VARIANT_BUILDERS = {
    "A": add_v_A,
    "B": add_v_B,
    "C": add_v_C,
    "D": add_v_D,
    "E": add_v_E,
    "F": add_v_F,
}


def run_variant(label):
    print(f"\n========== Variant {label} ==========")
    model, Item, User, Book, Author, Subject, Candidate, kg_paths = build_base(
        f"variant_{label}"
    )
    VARIANT_BUILDERS[label](
        model, Item, User, Book, Author, Subject, Candidate, kg_paths
    )

    Candidate.utility = model.Property(f"{Candidate} has utility {Float:utility}")
    bu, ut = Book.ref(), Float.ref()
    cc = Candidate.ref()
    model.define(Candidate.utility(cc, ut)).where(
        Candidate(cc),
        cc.book_id == bu.id,
        ut
        == PAGERANK_WEIGHT * bu.pagerank_score
        + PATH_SIGNAL_WEIGHT
        * (2 * cc.path_count_via_author + cc.path_count_via_subject),
    )

    Candidate.pick = model.Property(f"{Candidate} is picked iff {Float:p}")
    problem = Problem(model, Float)
    problem.solve_for(
        Candidate.pick,
        type="bin",
        name=["pick", Candidate.user_id, Candidate.book_id],
    )

    explanation_sub = problem.satisfy(
        model.require(
            sum(Candidate.path_count_total * Candidate.pick).per(Candidate.user_id)
            >= EXPLANATION_FLOOR
        ),
        name="explanation_ic",
    )
    problem.maximize(sum(Candidate.utility * Candidate.pick))

    # Stats via the model -- read by inspecting properties.
    cands = model.select(
        Candidate.user_id, Candidate.book_id, Candidate.path_count_total
    ).to_df()
    print(f"  candidates with path_count_total defined: {len(cands)}")
    if len(cands) > 0:
        col = cands.columns[2]
        vals = [int(v) for v in cands[col].tolist() if v is not None and not _is_na(v)]
        if vals:
            print(f"  path_count_total range: min={min(vals)}, max={max(vals)}")
        else:
            print("  path_count_total range: all undefined (NA)")
    full = model.select(Candidate.user_id, Candidate.book_id).to_df()
    print(f"  total Candidates: {len(full)}")

    # Inspect explanation_ic grounded constraint via problem.display.
    buf = io.StringIO()
    with redirect_stdout(buf):
        problem.display(explanation_sub)
    text = buf.getvalue()
    user_5_lines = [ln for ln in text.splitlines() if "pick_5_" in ln]
    print(
        f"  explanation_ic display: {len(text.splitlines())} lines total, "
        f"{len(user_5_lines)} contain a pick_5_* term"
    )
    for ln in user_5_lines:
        print(f"    {ln}")


def _is_na(v):
    import pandas as pd

    return bool(pd.isna(v))


def main():
    variants = sys.argv[1:] if len(sys.argv) > 1 else ["A", "B", "C", "D", "E", "F"]
    for v in variants:
        v = v.upper()
        try:
            run_variant(v)
        except Exception as e:
            print(f"\n========== Variant {v} ==========")
            print(f"  FAILED with {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
