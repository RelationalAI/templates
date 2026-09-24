"""AML pattern rules: each writes Finding(str, rule_id) with a confidence (P3 §3 Rule 10, P3 Eq. 1-2,
P4 §2.1-2.2). Rule weights, offences and priorities live in data/rule_catalog.csv, not here.
"""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math


def register(m, o, S):
    E, Pe, Co, STR, Acc = o.Entity, o.Person, o.Company, o.STR, o.Account
    Finding = m.Concept("Finding", identify_by={"str": STR, "rule_id": o.Rule})
    Finding.confidence = m.Property(f"{Finding} has confidence {Float:confidence}")
    o.Finding = Finding

    s = STR.ref()
    x = E.ref()
    b, y = Co.ref(), Co.ref()
    a = Acc.ref()
    ln = o.Loan.ref()
    d = Integer.ref()
    families = getattr(o, "has_families", False)

    def find(rule_id, conf, *where):
        m.where(*where, r := o.Rule.lookup(rule_id=rule_id)).define(
            fd := Finding.new(str=s, rule_id=r), fd.confidence(conf))

    # --- P3 Rule 10: the loan applicant (or their family) controls the lending bank
    loan = [s.loan(ln), ln.lender(b), s.subject(x)]
    find("P3.R10", 1.0, *loan, x.controls(b))
    find("P3.PYRAMID", 1.0, *loan, x.controls(b), x.control_depth(b, d), d >= 3)
    pp = Pe.ref()                                    # Person-only relationships need a Person variable
    ploan = [s.loan(ln), ln.lender(b), s.subject(pp)]
    if families:
        f = o.Family.ref()
        find("P3.R10", f.confidence, *ploan, m.not_(pp.controls(b)), pp.family(f), f.controls(b))
        find("P3.PYRAMID", f.confidence, *ploan, m.not_(pp.controls(b)), pp.family(f), f.controls(b),
             f.control_depth(b, d), d >= 3)

    # --- P3 Eq. 2: subject (or a company they / their family control) invoiced without being paid
    find("P3.SLUSH", 1.0, s.subject(x), x.potential_slush_fund())
    find("P3.SLUSH", 1.0, s.subject(x), x.controls(y), y.potential_slush_fund())
    if families:
        f2 = o.Family.ref()
        find("P3.SLUSH", 1.0, s.subject(pp), pp.family(f2), f2.controls(y), y.potential_slush_fund())

    # --- P4 transaction-monitoring rules on the subject's accounts
    t = o.Transfer.ref()
    find("P4.NEAR_MISS", 1.0, s.transfer(t), t.is_near_miss())
    E.max_structuring_days = m.Property(f"{E} has at most {Integer:days} structuring days on one account")
    m.define(x.max_structuring_days(aggs.max(a.structuring_days).per(x).where(a.holder(x))))
    find("P4.STRUCTURING", math.minimum(x.max_structuring_days / 3.0, 1.0),
         s.subject(x), x.max_structuring_days >= 1)
    find("P4.PEP_HIGH_RISK", 1.0, s.subject(x), a.holder(x), a.pep_high_risk())
    find("P4.UNKNOWN_CP", 1.0, s.subject(x), a.holder(x), a.unknown_counterparty())
    find("P4.CYCLE", 1.0, s.subject(x), a.holder(x), a.in_cycle())
    find("P4.FAN", 1.0, s.subject(x), a.holder(x), a.is_fan())
    find("P4.RECORD", 1.0, s.subject(pp), pp.has_record())

    # --- GNN account classifier (Phase 8): registered only when predictions were loaded
    if getattr(o, "has_gnn_account_probs", False):   # set by model/gnn_accounts.py
        v = Float.ref()
        find("GNN.ACCOUNT", v, s.subject(x), x.gnn_account_prob(v))
