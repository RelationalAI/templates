"""Suspiciousness scoring and suspicion classification (P3 derived tasks).

score(s)   = 1 - prod_r (1 - w_r * c_r)          noisy-OR over the rules that fired, in log space
offence(s) = offence of the finding with the largest w*c (ties: smallest rule priority)
"""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math

HIGH = 0.8
REVIEW = 0.5


def register(m, o, S):
    STR, Finding = o.STR, o.Finding
    fd, fd2 = Finding.ref(), Finding.ref()
    s = STR.ref()

    Finding.wc = m.Property(f"{Finding} has weighted confidence {Float:wc}")
    m.define(fd.wc(math.minimum(fd.confidence * fd.rule_id.weight, 0.999)))

    STR.score = m.Property(f"{STR} has suspicion score {Float:score}")
    lsum = aggs.sum(fd, math.natural_log(1.0 - fd.wc)).per(s).where(fd.str == s)
    m.define(s.score((1.0 - math.exp(lsum)) | 0.0))

    STR.top_wc = m.Property(f"{STR} has strongest finding {Float:top_wc}")
    m.define(s.top_wc(aggs.max(fd.wc).per(s).where(fd.str == s)))
    STR.top_priority = m.Property(f"{STR} has top-finding priority {Integer:priority}")
    m.define(s.top_priority(aggs.min(fd.rule_id.priority).per(s).where(fd.str == s, fd.wc == s.top_wc)))
    STR.offence_raw = m.Property(f"{STR} indicates raw offence {String:offence}")
    m.where(fd2.str == s, fd2.wc == s.top_wc, fd2.rule_id.priority == s.top_priority).define(
        s.offence_raw(fd2.rule_id.offence))
    STR.offence = m.Property(f"{STR} indicates offence {String:offence}")
    m.define(s.offence(s.offence_raw | "NONE"))

    HighRiskSTR = m.Concept("HighRiskSTR", extends=[STR])
    ReviewSTR = m.Concept("ReviewSTR", extends=[STR])
    m.where(s.score >= HIGH).define(HighRiskSTR(s))
    m.where(s.score >= REVIEW, s.score < HIGH).define(ReviewSTR(s))
    o.HighRiskSTR, o.ReviewSTR = HighRiskSTR, ReviewSTR
