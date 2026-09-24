"""End-to-end pipeline shared by the runners, the notebook and the benchmarks.

    augmentation rounds (VADA-LINK)  ->  [GNN link scores -> augmentation]  ->  [GNN account classifier]
    ->  final model (families, control, Phi, close links, patterns, scoring, cases)  ->  triage (MILP)
"""

from __future__ import annotations

import dataclasses
import time

import pandas as pd
from config import Settings, offline_config
from model import build_model, optimize
from model.augmentation import augment
from model.control import check_converged
from relationalai.semantics.std import aggregates as aggs

TRANSIENT = ("SSLError", "403 Client Error", "Connection aborted", "ConnectionResetError", "Read timed out",
             "RemoteDisconnected")


def with_retry(fn, *args, attempts=3, log=print, **kw):
    """Retry long GNN stages on transient network errors (expired result URLs, SSL read errors)."""
    import gc as _gc

    for i in range(1, attempts + 1):
        try:
            return fn(*args, **kw)
        except Exception as e:  # noqa: BLE001 - re-raised unless transient
            msg = f"{type(e).__name__}: {e}"
            if i == attempts or not any(t in msg for t in TRANSIENT):
                raise
            log(f"[retry] {fn.__module__}.{fn.__name__} attempt {i} failed with a transient error; retrying")
            _gc.collect()


def _count(m, *where, what):
    df = m.where(*where).select(aggs.count(*what).alias("n")).to_df() if where else \
        m.select(aggs.count(*what).alias("n")).to_df()
    return int(df["n"].iloc[0]) if len(df) else 0


def summarize(m, o) -> dict:
    a, b, f = o.Entity.ref(), o.Entity.ref(), o.Family.ref()
    c1, c2 = o.Company.ref(), o.Company.ref()
    s = o.STR.ref()
    pe = o.Person.ref()
    return {
        "control_pairs": _count(m, a.controls(b), what=(a, b)),
        "direct_control": _count(m, a.ctrl_0(b), a != b, what=(a, b)),
        "families": _count(m, f.size >= 2, what=(f,)),
        "family_control_pairs": _count(m, f.controls(b), what=(f, b)),
        "oversized_families": _count(m, f.is_oversized(), what=(f,)),
        "close_links": _count(m, c1.close_link(c2), c1.eid < c2.eid, what=(c1, c2)),
        "family_close_links": _count(m, c1.family_close_link(c2, f), c1.eid < c2.eid, what=(c1, c2)),
        "strs": _count(m, what=(s,)),
        "strs_high": _count(m, s.score >= 0.8, what=(s,)),
        "strs_review": _count(m, s.score >= 0.5, s.score < 0.8, what=(s,)),
        "persons": _count(m, what=(pe,)),
    }


def run(S: Settings, source, *, offline=False, gnn=True, triage=True, augment_links=True, log=print,
        name="bo_aml", budgets=None) -> dict:
    t0 = time.time()
    timings = {}
    cfg = offline_config() if offline else None
    if offline:
        S = dataclasses.replace(S, BLOCKING_L1="none")
        gnn, triage_solver = False, False
    else:
        triage_solver = triage

    gnn_pair_scores = gnn_account_probs = None
    gnn_report = {}
    if gnn and S.USE_GNN_LINK:
        from model import gnn_links
        t = time.time()
        gnn_pair_scores, rep = with_retry(gnn_links.run, S, source, log=log)
        gnn_report["link"] = rep
        timings["gnn_link"] = time.time() - t

    links = pd.DataFrame(columns=["a_eid", "b_eid", "link_type", "confidence", "round"])
    history = []
    if augment_links:
        t = time.time()
        links, history = augment(S, source, config=cfg, name=f"{name}_aug", log=log, gnn_scores=gnn_pair_scores)
        timings["augmentation"] = time.time() - t

    if gnn and S.USE_GNN_ACCOUNT:
        from model import gnn_accounts
        t = time.time()
        gnn_account_probs, rep = with_retry(gnn_accounts.run, S, source, links, log=log)
        gnn_report["account"] = rep
        timings["gnn_account"] = time.time() - t

    t = time.time()
    m, o = build_model(S, source, extra_links=links, name=name, config=cfg, gnn_account_probs=gnn_account_probs)
    check_converged(m, o)
    summary = summarize(m, o)
    strs = optimize.str_table(m, o)
    cases = optimize.case_table(m, o)
    timings["reasoning"] = time.time() - t

    tri = {}
    if triage:
        t = time.time()
        naive = optimize.naive_topk(strs, cases, S)
        best = optimize.solve_select(m, o, S) if triage_solver else optimize.greedy_select(cases, S)
        tri = {"plan": best, "naive": naive,
               "uplift": (best["objective"] or 0.0) - naive["value"]}
        if budgets and triage_solver:
            tri["sweep"] = [dict(optimize.solve_select(m, o, S, budget=bgt), naive_value=optimize.naive_topk(strs, cases, S, bgt)["value"])
                            for bgt in budgets]
        timings["triage"] = time.time() - t
    timings["total"] = time.time() - t0
    return {"model": m, "onto": o, "settings": S, "summary": summary, "links": links, "augmentation": history,
            "strs": strs, "cases": cases, "triage": tri, "gnn": gnn_report, "timings": timings}


def headline(r) -> str:
    s, tri = r["summary"], r["triage"]
    aug = r["augmentation"]
    lines = [
        f"Control pairs derived:          {s['control_pairs']:>7,}  (direct {s['direct_control']:,}; "
        f"family-level {s['family_control_pairs']:,} across {s['families']:,} families)",
        f"Close links / family close:     {s['close_links']:>7,} / {s['family_close_links']:,}",
        f"Hidden family links predicted:  {len(r['links']):>7,}  in {len(aug)} VADA-LINK rounds "
        f"({aug[0]['candidates'] if aug else 0:,} candidates in round 1)",
        f"STRs scored >= 0.8 / 0.5-0.8:   {s['strs_high']:>7,} / {s['strs_review']:,}  of {s['strs']:,}",
    ]
    if tri:
        p, n = tri["plan"], tri["naive"]
        lines += [f"Triage ({p['status']}, {p['budget']:.0f} h):       value {p['objective'] or 0:>14,.0f}  "
                  f"({len(p['chosen'])} cases)",
                  f"Naive top-by-score:             value {n['value']:>14,.0f}  ({len(n['cases_opened'])} cases)",
                  f"Uplift over naive:              {tri['uplift']:>+20,.0f}"]
    lines.append("Timings (s): " + ", ".join(f"{k} {v:.0f}" for k, v in r["timings"].items()))
    return "\n".join(lines)
