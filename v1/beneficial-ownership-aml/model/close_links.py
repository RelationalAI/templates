"""Close links (P1 Def 2.6 / Alg. 6, ECB threshold T) and family close links (P1 Def 2.9 / Alg. 9)."""

from relationalai.semantics import Float


def register(m, o, S):
    E, Co, Pe = o.Entity, o.Company, o.Person
    T = S.CLOSE_LINK_T
    x, y = Co.ref(), Co.ref()
    z = E.ref()
    v1, v2 = Float.ref(), Float.ref()

    Co.close_link = m.Relationship(f"{Co:a} is closely linked to {Co:b}")
    m.where(x.phi(y, v1), v1 >= T, x != y).define(x.close_link(y), y.close_link(x))      # (i), (ii)
    m.where(z.phi(x, v1), v1 >= T, z.phi(y, v2), v2 >= T, x != y).define(x.close_link(y))  # (iii)

    if getattr(o, "has_families", False):
        f = o.Family.ref()
        i, j = Pe.ref(), Pe.ref()
        Co.family_close_link = m.Relationship(f"{Co:a} is closely linked to {Co:b} through family {o.Family}")
        m.where(i.family(f), j.family(f), i != j, m.not_(f.is_oversized()),
                i.phi(x, v1), v1 >= T, j.phi(y, v2), v2 >= T, x != y).define(
            x.family_close_link(y, f), y.family_close_link(x, f))
