"""Risk-driven triage (P3 derived task "risk-driven optimization"): which cases do analysts take?

select mode: maximize sum(value * x) over cases s.t. total hours <= AUDIT_HOURS and, per offence class,
             hours <= MAX_CLASS_SHARE * AUDIT_HOURS (keeps the plan diverse).
assign mode: cases -> analysts with matching skills, each case at most once, analyst hour capacities.
Baseline:    naive = rank STRs by score, open cases in that order until the hours run out.
Each solve uses populate=False, so several budgets can be solved on one model independently.
"""

from __future__ import annotations

import pandas as pd
from relationalai.semantics import Float, String
from relationalai.semantics import sum as rsum
from relationalai.semantics.std import strings


def _declare(m, o):
    if getattr(o, "_triage_declared", False):
        return
    Case = o.Case
    Case.x_inv = m.Property(f"{Case} investigated {Float:inv}")
    Off = m.Concept("OffenceClass", identify_by={"name": String})
    c = Case.ref()
    m.define(Off.new(name=c.offence))
    Assignment = m.Concept("Assignment", identify_by={"case": Case, "analyst": o.Analyst})
    Assignment.x = m.Property(f"{Assignment} is chosen {Float:x}")
    an = o.Analyst.ref()
    m.where(strings.contains(an.skills, c.offence)).define(Assignment.new(case=c, analyst=an))
    m.where(an.skills == "ANY").define(Assignment.new(case=c, analyst=an))
    o.OffenceClass, o.Assignment = Off, Assignment
    o._triage_declared = True


def solve_select(m, o, S, budget: float | None = None, time_limit=60) -> dict:
    from relationalai.semantics.reasoners.prescriptive import Problem

    _declare(m, o)
    budget = S.AUDIT_HOURS if budget is None else budget
    Case, Off = o.Case, o.OffenceClass
    pb = Problem(m, Float)
    var = pb.solve_for(Case.x_inv, type="bin", name=["inv", Case.cid], populate=False)
    c, oc = Case.ref(), Off.ref()
    pb.satisfy(m.require(rsum(Case.x_inv * Case.hours) <= budget))
    pb.satisfy(m.require(rsum(c.x_inv * c.hours).where(c.offence == oc.name).per(oc) <= S.MAX_CLASS_SHARE * budget))
    pb.maximize(rsum(Case.x_inv * Case.value))
    pb.solve("highs", time_limit_sec=time_limit)
    si = pb.solve_info()
    v = Float.ref()
    chosen = pd.DataFrame(columns=["cid"])
    if si.termination_status in ("OPTIMAL", "TIME_LIMIT", "SOLUTION_LIMIT"):
        chosen = m.select(var.case.cid.alias("cid")).where(var.values(0, v), v > 0.5).to_df()
    return {"status": si.termination_status, "objective": si.objective_value, "budget": budget,
            "solve_seconds": si.solve_time_sec, "chosen": sorted(int(x) for x in chosen["cid"])}


def solve_assign(m, o, S, time_limit=60) -> dict:
    from relationalai.semantics.reasoners.prescriptive import Problem

    _declare(m, o)
    A, Case, An = o.Assignment, o.Case, o.Analyst
    pb = Problem(m, Float)
    var = pb.solve_for(A.x, type="bin", name=["x", A.case.cid, A.analyst.analyst_id], populate=False)
    a = A.ref()
    pb.satisfy(m.require(rsum(a.x).where(a.case == Case).per(Case) <= 1))
    pb.satisfy(m.require(rsum(a.x * a.case.hours).where(a.analyst == An).per(An) <= An.hours))
    pb.maximize(rsum(A.x * A.case.value))
    pb.solve("highs", time_limit_sec=time_limit)
    si = pb.solve_info()
    v = Float.ref()
    rows = pd.DataFrame(columns=["cid", "analyst"])
    if si.termination_status in ("OPTIMAL", "TIME_LIMIT", "SOLUTION_LIMIT"):
        rows = m.select(var.assignment.case.cid.alias("cid"), var.assignment.analyst.analyst_id.alias("analyst")
                        ).where(var.values(0, v), v > 0.5).to_df()
    return {"status": si.termination_status, "objective": si.objective_value,
            "assignments": rows.astype({"cid": int}).sort_values("cid").to_dict("records")}


def case_table(m, o) -> pd.DataFrame:
    c = o.Case.ref()
    df = m.select(c.cid.alias("cid"), c.n_strs.alias("n_strs"), c.risk.alias("risk"), c.amount.alias("amount"),
                  c.hours.alias("hours"), c.value.alias("value"), c.offence.alias("offence")).to_df()
    return df.astype({"cid": int, "n_strs": int, "risk": float, "amount": float, "hours": float, "value": float})


def str_table(m, o) -> pd.DataFrame:
    s = o.STR.ref()
    df = m.select(s.str_id.alias("str_id"), s.num.alias("num"), s.case.cid.alias("cid"), s.score.alias("score"),
                  s.offence.alias("offence"), s.subject.eid.alias("subject"), s.amount.alias("amount")).to_df()
    return df.astype({"num": int, "cid": int, "score": float, "amount": float})


def naive_topk(strs: pd.DataFrame, cases: pd.DataFrame, S, budget: float | None = None) -> dict:
    """Rank STRs by score; opening a case costs CASE_SETUP_HOURS once, each STR HOURS_PER_STR."""
    budget = S.AUDIT_HOURS if budget is None else budget
    cases = cases.set_index("cid")
    used, opened, done = 0.0, set(), {}
    for r in strs.sort_values(["score", "num"], ascending=[False, True]).itertuples():
        cost = S.HOURS_PER_STR + (0 if r.cid in opened else S.CASE_SETUP_HOURS)
        if used + cost > budget:
            continue
        used += cost
        opened.add(r.cid)
        done[r.cid] = done.get(r.cid, 0) + 1
    value = sum(cases.loc[c, "value"] * n / cases.loc[c, "n_strs"] for c, n in done.items())
    return {"budget": budget, "hours_used": used, "value": value, "cases_opened": sorted(opened)}


def greedy_select(cases: pd.DataFrame, S, budget: float | None = None) -> dict:
    """Offline fallback (no solver): value per hour, respecting the budget. Labeled as a heuristic."""
    budget = S.AUDIT_HOURS if budget is None else budget
    used, chosen = 0.0, []
    for r in cases.assign(density=cases.value / cases.hours).sort_values("density", ascending=False).itertuples():
        if used + r.hours <= budget:
            used += r.hours
            chosen.append(int(r.cid))
    return {"status": "HEURISTIC", "objective": float(cases.set_index("cid").loc[chosen, "value"].sum()) if chosen else 0.0,
            "budget": budget, "chosen": sorted(chosen)}
