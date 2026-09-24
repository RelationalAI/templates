"""Transaction-monitoring features (P4 §2.1-2.2) and invoice rules (P3 Eq. 1-2).

Simplifications (documented in the README): fan-in/out counts distinct counterparties over the whole
data period, not sliding windows; cycles are searched only from accounts of STR subjects (P3's
query-driven scope), up to MAX_CYCLE_LEN hops, ignoring time order.
"""

from relationalai.semantics import Date, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import datetime as dt
from relationalai.semantics.std import math

MAX_CYCLE_LEN = 6
FAN_THRESHOLD = 10


def register(m, o, S):
    E, Acc, Tr, Inv = o.Entity, o.Account, o.Transfer, o.Invoice
    t = Tr.ref()
    a, b = Acc.ref(), Acc.ref()
    x, y = E.ref(), E.ref()

    Tr.day = m.Property(f"{Tr} on day {Date:day}")
    m.define(t.day(dt.datetime.to_date(t.ts)))
    Tr.is_large = m.Relationship(f"{Tr} is at or above the reporting threshold")
    Tr.is_near_miss = m.Relationship(f"{Tr} is just under the reporting threshold")
    Tr.is_round = m.Relationship(f"{Tr} has a large round amount")
    m.where(t.amount >= 10000.0).define(t.is_large())
    m.where(t.amount >= 9000.0, t.amount < 10000.0).define(t.is_near_miss())
    m.where(t.amount >= 5000.0, math.floor(t.amount / 1000.0) * 1000.0 == t.amount).define(t.is_round())

    # structuring: >= 5 outgoing transfers of 1,000-3,000 totalling >= 9,000 on one day
    AccountDay = m.Concept("AccountDay", identify_by={"account": Acc, "day": Date})
    m.where(t.from_account(a)).define(AccountDay.new(account=a, day=t.day))
    ad = AccountDay.ref()
    small = [t.from_account(ad.account), t.day == ad.day, t.amount >= 1000.0, t.amount <= 3000.0]
    AccountDay.is_structuring = m.Relationship(f"{AccountDay} shows structuring")
    m.where(aggs.count(t).per(ad).where(*small) >= 5,
            aggs.sum(t, t.amount).per(ad).where(*small) >= 9000.0).define(ad.is_structuring())
    Acc.structuring_days = m.Property(f"{Acc} has {Integer:structuring_days} structuring days")
    m.define(a.structuring_days(aggs.count(ad).per(a).where(ad.account == a, ad.is_structuring()) | 0))
    Acc.near_miss_count = m.Property(f"{Acc} has {Integer:near_miss_count} near-miss credits")
    m.define(a.near_miss_count(aggs.count(t).per(a).where(t.to_account(a), t.is_near_miss()) | 0))

    Acc.fan_in = m.Property(f"{Acc} is credited by {Integer:fan_in} distinct accounts")
    Acc.fan_out = m.Property(f"{Acc} pays {Integer:fan_out} distinct accounts")
    m.define(a.fan_in(aggs.count(b).per(a).where(t.to_account(a), t.from_account(b)) | 0))
    m.define(a.fan_out(aggs.count(b).per(a).where(t.from_account(a), t.to_account(b)) | 0))
    Acc.is_fan = m.Relationship(f"{Acc} shows fan-in or fan-out")
    m.where(a.fan_in >= FAN_THRESHOLD).define(a.is_fan())
    m.where(a.fan_out >= FAN_THRESHOLD).define(a.is_fan())

    p = o.Person.ref()
    Acc.pep_high_risk = m.Relationship(f"{Acc} is a PEP account credited from a high-risk jurisdiction")
    m.where(t.to_account(a), a.holder(p), p.is_pep(), t.from_account(b),
            o.HighRisk.lookup(country=b.country)).define(a.pep_high_risk())
    Acc.unknown_counterparty = m.Relationship(f"{Acc} is credited by an unregistered holder")
    m.where(t.to_account(a), t.from_account(b), m.not_(b.holder)).define(a.unknown_counterparty())

    # cycles: bounded reachability from accounts of STR subjects (no recursion)
    Acc.sends_to = m.Relationship(f"{Acc:src} sends money to {Acc:dst}")
    m.where(t.from_account(a), t.to_account(b), a != b).define(a.sends_to(b))
    Acc.is_cycle_seed = m.Relationship(f"{Acc} belongs to an STR subject")
    s = o.STR.ref()
    m.where(s.subject(x), a.holder(x)).define(a.is_cycle_seed())
    c = Acc.ref()
    R = m.Relationship(f"{Acc:seed} reaches {Acc:acct} in 1 hop")
    m.where(a.is_cycle_seed(), a.sends_to(b)).define(R(a, b))
    Acc.in_cycle = m.Relationship(f"{Acc} lies on a circular chain of transfers")
    for k in range(2, MAX_CYCLE_LEN + 1):
        Rk = m.Relationship(f"{Acc:seed} reaches {Acc:acct} in {k} hops")
        setattr(Acc, f"reach_{k}", Rk)
        m.where(R(a, b), b.sends_to(c), b != a).define(Rk(a, c))
        m.where(Rk(a, a)).define(a.in_cycle())
        R = Rk

    # P3 Eq. 1-2: invoices vs payments
    pr = String.ref()
    E.pays_for = m.Relationship(f"{E:payer} pays {E:payee} for {String:product}")
    m.where(t.from_account(a), a.holder(x), t.to_account(b), b.holder(y), t.product(pr)).define(x.pays_for(y, pr))
    i = Inv.ref()
    E.potential_slush_fund = m.Relationship(f"{E} invoiced for goods it was never paid for")
    m.where(i.issuer(y), i.payee(x), i.product(pr), m.not_(x.pays_for(y, pr))).define(y.potential_slush_fund())
    Tr.missing_invoice = m.Relationship(f"{Tr} was paid without an invoice")
    j = Inv.ref()
    m.where(t.from_account(a), a.holder(x), t.to_account(b), b.holder(y), t.product(pr),
            m.not_(j.issuer(y), j.payee(x), j.product(pr))).define(t.missing_invoice())
    o.AccountDay = AccountDay
