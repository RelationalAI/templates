"""Accumulated ownership Phi(x, y) (P1 Def 2.5, Eq. 1-2; P3 Rule 8).

Two methods behind Settings.PHI_METHOD, both writing Entity.phi(y, value):
  "unrolled" (default, both backends): per-hop walk products, pruned below PHI_EPS. Counts walks,
             so cycles among intermediate companies inflate it versus Def 2.5; capped at 1.0.
  "paths"    (Snowflake only): exact sum over simple paths with model.path.
Families are not sources: family figures are sums over members (Family.accumulated_share).
"""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math


def register(m, o, S):
    E, Co = o.Entity, o.Company
    E.phi = m.Property(f"{E:src} accumulates ownership of {Co:dst} {Float:phi}")
    E.is_phi_source = m.Relationship(f"{E} is an accumulated-ownership source")
    x = E.ref()
    m.where(o.Person(x)).define(x.is_phi_source())
    m.where(o.Company(x)).define(x.is_phi_source())
    if S.PHI_METHOD == "paths":
        _register_paths(m, o, S)
    else:
        _register_unrolled(m, o, S)
    if getattr(o, "has_families", False):
        f, mm, y, v = o.Family.ref(), o.Person.ref(), Co.ref(), Float.ref()
        o.Family.accumulated_share = m.Property(f"{o.Family} accumulates {Co:company} {Float:share}")
        tot = aggs.sum(mm, v).per(f, y).where(mm.family(f), mm.phi(y, v))
        m.where(tot > 0).define(f.accumulated_share(y, math.minimum(tot, 1.0)))


def _register_unrolled(m, o, S):
    E, Co = o.Entity, o.Company
    PhiTerm = m.Concept("PhiTerm", identify_by={"src": E, "dst": Co, "hops": Integer})
    PhiTerm.w = m.Property(f"{PhiTerm} has weight {Float:w}")
    x, z = E.ref(), Co.ref()
    y = Co.ref()
    w, w1 = Float.ref(), Float.ref()
    H1 = m.Property(f"{E:src} reaches {Co:dst} in 1 hop with {Float:w}")
    m.where(x.is_phi_source(), x.holds(y, w), w >= S.EDGE_EPS).define(H1(x, y, w))
    layers = [H1]
    for k in range(2, S.PHI_MAX_HOPS + 1):
        prev = layers[-1]
        Hk = m.Property(f"{E:src} reaches {Co:dst} in {k} hops with {Float:w}")
        setattr(E, f"phi_hop_{k}", Hk)
        tot = aggs.sum(z, w1 * w).per(x, y).where(prev(x, z, w1), z.holds(y, w), w >= S.EDGE_EPS)
        m.where(tot >= S.PHI_EPS, x != y).define(Hk(x, y, tot))
        layers.append(Hk)
    for k, H in enumerate(layers, start=1):
        m.where(H(x, y, w), x != y).define(pt := PhiTerm.new(src=x, dst=y, hops=k), pt.w(w))
    t = PhiTerm.ref()
    phi = aggs.sum(t, t.w).per(x, y).where(t.src == x, t.dst == y)
    # walks through a cross-holding cycle can push the sum past 1 (a cycle with round-trip product 0.4
    # inflates by 1/(1-0.4)); an ownership share cannot exceed 100%, so cap it. PHI_METHOD="paths" is exact.
    m.where(phi > 0).define(x.phi(y, math.minimum(phi, 1.0)))
    o.PhiTerm = PhiTerm


def _register_paths(m, o, S):
    E, Co = o.Entity, o.Company
    E.holds_edge = m.Relationship(f"{E:src} holds shares in {E:dst}")
    a, c, w = E.ref(), Co.ref(), Float.ref()
    m.where(a.holds(c, w), w >= S.EDGE_EPS).define(a.holds_edge(c))
    src, dst = E.ref(), Co.ref()
    p = m.path(src, E.holds_edge.repeat(1, S.PHI_MAX_HOPS), dst).all().paths()
    i, j = Integer.ref(), Integer.ref()
    ww = Float.ref()
    logw = aggs.sum(i, math.natural_log(ww)).per(p).where(
        i >= 0, i < p.length, E(p.nodes(i)).holds(Co(p.nodes(i + 1)), ww))
    n_distinct = aggs.count(m.distinct(E(p.nodes(j)))).per(p)
    phi = aggs.sum(p, math.exp(logw)).per(src, dst).where(p, src.is_phi_source(), n_distinct == p.length + 1)
    m.where(phi > 0, src != dst).define(src.phi(dst, phi))
