"""Reconstruction (P3 derived task): explain why an STR is suspicious from facts the rules derived.

Nothing is recomputed here: explain() reads Findings, ControlSteps, family lifts, personal links and
accumulated ownership from the model, and render_text() only formats them.
"""

from __future__ import annotations

from relationalai.semantics import Float, String


def register(m, o, S):
    """Evidence is already written by the rules (ControlStep, Family.lifted, Finding); nothing to add."""


def _df(model, *where, **cols):
    return model.where(*where).select(*[v.alias(k) for k, v in cols.items()]).to_df()


def explain(model, o, str_id: str) -> dict:
    s, fd = o.STR.ref(), o.Finding.ref()
    head = _df(model, s.str_id == str_id, subject=s.subject.eid, bank=s.bank.eid, kind=s.instrument_type,
               amount=s.amount, score=s.score, offence=s.offence)
    if head.empty:
        raise KeyError(str_id)
    h = head.iloc[0].to_dict()
    findings = _df(model, fd.str.str_id == str_id, rule=fd.rule_id.rule_id, description=fd.rule_id.description,
                   weight=fd.rule_id.weight, confidence=fd.confidence, wc=fd.wc)
    out = {"str_id": str_id, **h, "findings": findings.sort_values("wc", ascending=False).to_dict("records")}

    # who controls the bank: the subject, or the subject's family
    x, f = o.Person.ref(), o.Family.ref()
    fam = _df(model, x.eid == h["subject"], x.family(f), family=f.eid, size=f.size, confidence=f.confidence)
    controllers = [h["subject"]] + ([fam.iloc[0]["family"]] if len(fam) else [])
    if len(fam):
        p, q, t, cf = o.Person.ref(), o.Person.ref(), String.ref(), Float.ref()
        members = _df(model, p.family(f), f.eid == fam.iloc[0]["family"], member=p.eid)
        links = _df(model, p.family(f), q.family(f), f.eid == fam.iloc[0]["family"], p.link(q, t, cf),
                    a=p.eid, b=q.eid, link_type=t, confidence=cf)
        out["family"] = {"id": fam.iloc[0]["family"], "members": sorted(members["member"]),
                         "confidence": float(fam.iloc[0]["confidence"]), "links": links.to_dict("records")}

    cs = o.ControlStep.ref()
    step_owners = controllers + out.get("family", {}).get("members", [])
    steps = _df(model, cs.controller.eid.in_(step_owners), controller=cs.controller.eid, target=cs.target.eid,
                via=cs.via.eid, share=cs.share, depth=cs.depth)
    out["control_steps"] = steps.to_dict("records")
    if len(fam):
        y, mm = o.Company.ref(), o.Person.ref()
        lifts = _df(model, f.eid == fam.iloc[0]["family"], f.lifted(y, mm), target=y.eid, member=mm.eid)
        out["lifts"] = lifts.to_dict("records")
        c, v = o.Company.ref(), Float.ref()
        acc = _df(model, f.eid == fam.iloc[0]["family"], f.accumulated_share(c, v), company=c.eid, share=v)
        out["accumulated"] = {r["company"]: float(r["share"]) for r in acc.to_dict("records")}
    out["chain"] = _chain(out, controllers)
    return out


def _chain(out, controllers):
    """Walk ControlSteps back from the bank to the controller (formatting only)."""
    steps = out["control_steps"]
    lifts = {r["target"]: r["member"] for r in out.get("lifts", [])}
    by_target = {}
    for s in steps:
        by_target.setdefault((s["controller"], s["target"]), []).append(s)
    lines, seen = [], set()

    def walk(ctrl, target, indent):
        if (ctrl, target) in seen:
            return
        seen.add((ctrl, target))
        contribs = by_target.get((ctrl, target), [])
        if contribs:
            total = sum(float(c["share"]) for c in contribs)
            parts = ", ".join(f"{'own stake' if c['via'] == ctrl else c['via']} {float(c['share']):.2f}"
                              for c in sorted(contribs, key=lambda c: -float(c["share"])))
            lines.append(f"{'  ' * indent}{ctrl} controls {target}: {parts} (total {total:.2f})")
            for c in contribs:
                if c["via"] != ctrl:
                    walk(ctrl, c["via"], indent + 1)
        elif ctrl.startswith("F:") and target in lifts:
            lines.append(f"{'  ' * indent}{ctrl} controls {target} through member {lifts[target]}")
            walk(lifts[target], target, indent + 1)

    for ctrl in controllers:
        walk(ctrl, out["bank"], 0)
    return lines


def render_text(e: dict) -> str:
    lines = [f"STR {e['str_id']}: {e['kind'].lower()} of {float(e['amount']):,.0f} involving {e['subject']} at {e['bank']}",
             f"  suspicion score {float(e['score']):.3f}  likely offence: {e['offence']}"]
    for f in e["findings"]:
        lines.append(f"  - {f['rule']} (w={float(f['weight']):.2f}, c={float(f['confidence']):.2f}): {f['description']}")
    if "family" in e:
        fam = e["family"]
        lines.append(f"  family {fam['id']}: {', '.join(fam['members'])} (link confidence {fam['confidence']:.2f})")
        for ln in fam["links"]:
            lines.append(f"    {ln['a']} {ln['link_type']} {ln['b']} (p={float(ln['confidence']):.2f})")
        for c, v in sorted(e.get("accumulated", {}).items(), key=lambda kv: -kv[1])[:3]:
            lines.append(f"    family accumulated ownership of {c}: {v:.2f}")
    if e["chain"]:
        lines.append("  control chain:")
        lines += [f"    {ln}" for ln in e["chain"]]
    return "\n".join(lines)
