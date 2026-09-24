"""Effective holdings and company control (P1 Def 2.3 / Alg. 5; P3 Rules 4-7; P1 Def 2.8 / Alg. 8).

Control is a depth-bounded fixpoint: layer k reads only layer k-1, so no rule recurses through
an aggregate (unsupported on Snowflake, silently incomplete on DuckDB).
"""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs


class ControlNotConverged(RuntimeError):
    pass


def register_holdings(m, o, S):
    """`holds` = EDB ownership (minus buy-back self-loops) + CEO rule + family aggregates."""
    E, Co, Pe = o.Entity, o.Company, o.Person
    E.holds = m.Property(f"{E:holder} holds {Co:held} with {Float:share}")
    x, y, w = E.ref(), Co.ref(), Float.ref()
    m.where(x.owns(y, w), x != y).define(x.holds(y, w))
    if S.CEO_RULE:                                                         # P3 Rule 7
        p = Pe.ref()
        m.where(p.is_ceo_at(y), m.not_(p.owns(y, Float.ref()))).define(p.holds(y, 1.0))
    if getattr(o, "has_families", False):                                  # P3 Rule 9 / P1 Def 2.8
        f, mm = o.Family.ref(), Pe.ref()
        tot = aggs.sum(mm, w).per(f, y).where(mm.family(f), mm.owns(y, w))
        m.where(m.not_(f.is_oversized()), tot > 0).define(f.holds(y, tot))


def register_control(m, o, S):
    E, Co, Pe = o.Entity, o.Company, o.Person
    x, z, e = E.ref(), E.ref(), E.ref()
    y = Co.ref()
    w = Float.ref()
    T = S.CONTROL_T

    ControlStep = m.Concept("ControlStep", identify_by={"controller": E, "target": Co, "via": E})
    ControlStep.share = m.Property(f"{ControlStep} contributes {Float:share}")
    ControlStep.depth = m.Property(f"{ControlStep} at depth {Integer:depth}")
    E.control_depth = m.Property(f"{E:controller} first controls {Co:controlled} at depth {Integer:depth}")
    families = getattr(o, "has_families", False)
    if families:
        o.Family.lifted = m.Relationship(f"{o.Family} controls {Co} through member {Pe}")

    layers = []
    L0 = m.Relationship(f"{E:controller} controls at depth 0 {E:controlled}")
    setattr(E, "ctrl_0", L0)
    m.define(L0(x, x))                                                     # P3 Rule 4
    m.where(x.holds(y, w), w > T).define(L0(x, y))                         # P3 Rule 5
    m.where(x.holds(y, w), w > T).define(
        cs := ControlStep.new(controller=x, target=y, via=x), cs.share(w), cs.depth(0))
    m.where(L0(x, y), x != y).define(x.control_depth(y, 0))
    layers.append(L0)

    for k in range(1, S.MAX_CONTROL_DEPTH + 1):
        prev = layers[-1]
        Lk = m.Relationship(f"{E:controller} controls at depth {k} {E:controlled}")
        setattr(E, f"ctrl_{k}", Lk)
        m.where(prev(x, e)).define(Lk(x, e))                               # carry-over: untyped target keeps persons' self pairs
        tot = aggs.sum(z, w).per(x, y).where(prev(x, z), z.holds(y, w))    # P3 Rule 6 over layer k-1
        m.where(tot > T).define(Lk(x, y))
        m.where(tot > T, m.not_(prev(x, y)), prev(x, z), z.holds(y, w)).define(
            cs := ControlStep.new(controller=x, target=y, via=z), cs.share(w), cs.depth(k))
        if families:                                                       # P1 Alg. 8(1): members lift
            f, mm = o.Family.ref(), Pe.ref()
            m.where(mm.family(f), m.not_(f.is_oversized()), prev(mm, y), mm != y).define(Lk(f, y))
            m.where(mm.family(f), m.not_(f.is_oversized()), prev(mm, y), m.not_(prev(f, y))).define(f.lifted(y, mm))
        m.where(Lk(x, y), m.not_(prev(x, y)), x != y).define(x.control_depth(y, k))
        layers.append(Lk)

    E.controls = m.Relationship(f"{E:controller} controls {E:controlled}")
    m.where(layers[-1](x, e), x != e).define(x.controls(e))
    o.control_layers = layers
    o.ControlStep = ControlStep


def check_converged(m, o):
    """Raise if the last control layer still grew (raise MAX_CONTROL_DEPTH)."""
    a, b = o.Entity.ref(), o.Entity.ref()
    counts = []
    for L in o.control_layers[-2:]:
        df = m.where(L(a, b)).select(aggs.count(a, b).alias("n")).to_df()
        counts.append(int(df["n"].iloc[0]) if len(df) else 0)
    if counts[0] != counts[1]:
        raise ControlNotConverged(
            f"control still growing at depth {len(o.control_layers) - 1} ({counts[0]} -> {counts[1]}); "
            f"raise MAX_CONTROL_DEPTH")
    return counts[1]
