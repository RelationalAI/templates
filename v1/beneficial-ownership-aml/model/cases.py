"""Cases: cohesive groups of STRs with their context (P3 §2.1), the unit of analyst work for triage.

Two STRs are related when they share a subject, the subjects are in the same family, or both banks
are controlled by the same (non-oversized) family. Closure is depth-unrolled (no recursion); a case is
keyed by the smallest STR number in it.
"""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

MAX_CASE_DEPTH = 8


def register(m, o, S):
    STR, Pe = o.STR, o.Person
    s, t, u = STR.ref(), STR.ref(), STR.ref()
    x = o.Entity.ref()
    STR.related = m.Relationship(f"{STR:a} is related to {STR:b}")
    m.where(s.subject(x), t.subject(x), s != t).define(s.related(t))
    if getattr(o, "has_families", False):
        f, b1, b2 = o.Family.ref(), o.Company.ref(), o.Company.ref()
        px, py = Pe.ref(), Pe.ref()                  # Person-only relationships need Person variables
        m.where(s.subject(px), t.subject(py), s != t, px.family(f), py.family(f)).define(s.related(t))
        m.where(s.bank(b1), t.bank(b2), s != t, f.controls(b1), f.controls(b2), m.not_(f.is_oversized()),
                s.subject(px), px.family(f)).define(s.related(t), t.related(s))

    layers = []
    R0 = m.Relationship(f"{STR:a} in case at depth 0 with {STR:b}")
    m.define(R0(s, s))
    layers.append(R0)
    for k in range(1, MAX_CASE_DEPTH + 1):
        prev = layers[-1]
        Rk = m.Relationship(f"{STR:a} in case at depth {k} with {STR:b}")
        setattr(STR, f"case_{k}", Rk)
        m.where(prev(s, t)).define(Rk(s, t))
        m.where(prev(s, t), t.related(u)).define(Rk(s, u))
        layers.append(Rk)

    STR.case_key = m.Property(f"{STR} belongs to case {Integer:case_key}")
    m.define(s.case_key(aggs.min(t.num).per(s).where(layers[-1](s, t))))

    Case = m.Concept("Case", identify_by={"cid": Integer})
    STR.case = m.Property(f"{STR} is in {Case:case}")
    m.define(c := Case.new(cid=s.case_key), s.case(c))
    c = Case.ref()
    Case.n_strs = m.Property(f"{Case} has {Integer:n_strs} reports")
    Case.risk = m.Property(f"{Case} has risk {Float:risk}")
    Case.amount = m.Property(f"{Case} involves {Float:amount}")
    Case.hours = m.Property(f"{Case} needs {Float:hours} analyst hours")
    Case.value = m.Property(f"{Case} has expected value {Float:value}")
    Case.offence = m.Property(f"{Case} indicates {String:offence}")
    Case.top_score = m.Property(f"{Case} has top score {Float:top_score}")
    m.define(c.n_strs(aggs.count(s).per(c).where(s.case(c))))
    m.define(c.risk(1.0 - math.exp(aggs.sum(s, math.natural_log(1.0 - math.minimum(s.score, 0.999))).per(c).where(s.case(c)))))
    m.define(c.amount(aggs.sum(s, s.amount).per(c).where(s.case(c))))
    m.define(c.hours(S.CASE_SETUP_HOURS + S.HOURS_PER_STR * c.n_strs))
    m.define(c.value(c.risk * c.amount))
    m.define(c.top_score(aggs.max(s.score).per(c).where(s.case(c))))
    lead = aggs.min(s.num).per(c).where(s.case(c), s.score == c.top_score)
    m.where(t.case(c), t.score == c.top_score, t.num == lead).define(c.offence(t.offence))
    o.Case = Case
    o.case_layers = layers
