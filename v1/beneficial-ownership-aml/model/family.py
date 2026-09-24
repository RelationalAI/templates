"""Families from personal links (P3 Rules 1-3; P1 §2 "Detecting personal connections").

Kin closure is depth-unrolled (kin_0 ... kin_K): DuckDB materializes aggregates over recursive
relations wrongly, and families are bounded by MAX_FAMILY_SIZE anyway. A Family entity
exists only for 2+ members; a family whose closure is still growing at depth K, or that is larger
than MAX_FAMILY_SIZE, is flagged oversized and excluded from family holdings and control.
"""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import strings


def register(m, o, S):
    Pe, F = o.Person, o.Family
    a, b, c = Pe.ref(), Pe.ref(), Pe.ref()
    t, cf = String.ref(), Float.ref()

    Pe.adj = m.Relationship(f"{Pe:a} directly linked to {Pe:b}")
    m.where(a.link(b, t, cf), cf >= S.LINK_T_MIN).define(a.adj(b), b.adj(a))

    layers = []
    K0 = m.Relationship(f"{Pe:a} kin at depth 0 {Pe:b}")
    setattr(Pe, "kin_0", K0)
    m.define(K0(a, a))                                                     # P3 Rule 2: own family
    layers.append(K0)
    for k in range(1, S.MAX_FAMILY_SIZE):
        prev = layers[-1]
        Kk = m.Relationship(f"{Pe:a} kin at depth {k} {Pe:b}")
        setattr(Pe, f"kin_{k}", Kk)
        m.where(prev(a, b)).define(Kk(a, b))
        m.where(prev(a, b), b.adj(c)).define(Kk(a, c))                    # P3 Rule 3: merge
        layers.append(Kk)

    Pe.kin = m.Relationship(f"{Pe:a} is kin of {Pe:b}")
    m.where(layers[-1](a, b)).define(a.kin(b))
    Pe.kin_truncated = m.Relationship(f"{Pe} has a kin closure still growing at the depth limit")
    if len(layers) > 1:
        m.where(layers[-1](a, b), m.not_(layers[-2](a, b))).define(a.kin_truncated())

    Pe.family_key = m.Property(f"{Pe} has family key {Integer:family_key}")
    Pe.family_size = m.Property(f"{Pe} has family size {Integer:family_size}")
    m.define(a.family_key(aggs.min(b.num).per(a).where(a.kin(b))))
    m.define(a.family_size(aggs.count(b).per(a).where(a.kin(b))))

    Pe.family = m.Property(f"{Pe} belongs to {F:family}")
    F.size = m.Property(f"{F} has {Integer:size} members")
    F.confidence = m.Property(f"{F} has link confidence {Float:confidence}")
    F.is_oversized = m.Relationship(f"{F} is oversized")
    m.where(a.family_size >= 2).define(
        f := F.new(eid=strings.concat("F:", strings.string(a.family_key))), a.family(f))
    f = F.ref()
    # count members of the family itself: in a truncated closure, members can disagree on family_size
    m.define(f.size(aggs.count(a).per(f).where(a.family(f))))
    conf = aggs.min(cf).per(f).where(a.family(f), b.family(f), a.link(b, t, cf))
    m.define(f.confidence(conf | 1.0))
    m.where(a.family(f), a.kin_truncated()).define(f.is_oversized())
    m.where(f.size > S.MAX_FAMILY_SIZE).define(f.is_oversized())
    o.has_families = True
    o.kin_layers = layers
