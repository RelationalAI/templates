"""Phase 7: transaction features, AML pattern findings, scoring, offence classification, explanations."""

import math

import pytest
from model.explain import explain, render_text

from tests.helpers import BACKENDS, expected, fixture_model

ALL = ("family", "holdings", "control", "ownership", "close_links", "transactions", "patterns", "scoring",
       "explain", "cases")


def findings(model, o):
    fd = o.Finding.ref()
    df = model.select(fd.str.str_id.alias("s"), fd.rule_id.rule_id.alias("r")).to_df()
    out = {}
    for r in df.itertuples():
        out.setdefault(r.s, set()).add(r.r)
    return out


def scores(model, o):
    s = o.STR.ref()
    df = model.select(s.str_id.alias("s"), s.score.alias("score"), s.offence.alias("offence")).to_df()
    return {r.s: (float(r.score), r.offence) for r in df.itertuples()}


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("fixture", ["F3", "F5"])
def test_findings_and_scores(fixture, backend):
    model, o = fixture_model(fixture, backend, ALL)
    exp = expected(fixture)
    got = findings(model, o)
    for sid, rules in exp["findings"].items():
        assert set(rules) <= got.get(sid, set()), (sid, got.get(sid))
    sc = scores(model, o)
    for sid, lo in exp["score_min"].items():
        assert sc[sid][0] >= lo, (sid, sc[sid])


@pytest.mark.parametrize("backend", BACKENDS)
def test_f3_score_and_offence_exact(backend):
    model, o = fixture_model("F3", backend, ALL)
    score, offence = scores(model, o)["S1"]
    assert score == pytest.approx(1 - (1 - 0.85) * (1 - 0.3) * (1 - 0.15), abs=1e-9)   # R10 + PYRAMID + RECORD
    assert offence == "SELF_LENDING"                                          # strongest finding wins


@pytest.mark.parametrize("backend", BACKENDS)
def test_f3_explanation(backend):
    model, o = fixture_model("F3", backend, ALL)
    text = render_text(explain(model, o, "S1"))
    for needle in expected("F3")["explain_contains"]["S1"]:
        assert needle in text, (needle, text)
    assert "C:MY_BANK" in text and "C:ACME_BANK" in text


@pytest.mark.parametrize("backend", BACKENDS)
def test_f4_slush_fund(backend):
    model, o = fixture_model("F4", backend, ALL)
    x, t = o.Entity.ref(), o.Transfer.ref()
    slush = set(model.where(x.potential_slush_fund()).select(x.eid.alias("e")).to_df()["e"])
    missing = set(model.where(t.missing_invoice()).select(t.transfer_id.alias("t")).to_df()["t"])
    exp = expected("F4")
    assert slush == set(exp["potential_slush_fund"])
    assert missing == set(exp["missing_invoice"])
    assert not missing & set(exp["clean_transfers"])


@pytest.mark.parametrize("backend", BACKENDS)
def test_f5_score_exact(backend):
    model, o = fixture_model("F5", backend, ALL)
    score, offence = scores(model, o)["S5"]
    assert score == pytest.approx(1 - 0.7 * 0.5 * 0.7, abs=1e-9)            # NEAR_MISS, PEP, UNKNOWN_CP
    assert offence == "CORRUPTION"                                            # PEP (0.5) is the strongest


@pytest.mark.offline
def test_noisy_or_math():
    ws = [0.85, 0.3]
    assert 1 - math.exp(sum(math.log(1 - w) for w in ws)) == pytest.approx(0.895)


@pytest.mark.offline
def test_tune_weights_scoring_matches_model_formula():
    """tune_weights.scores must reproduce the in-model noisy-OR (Acme: R10 + PYRAMID + RECORD = 0.91075)."""
    import pandas as pd
    from tune_weights import average_precision, scores

    f = pd.DataFrame({"str_id": ["S1"] * 3, "rule_id": ["P3.R10", "P3.PYRAMID", "P4.RECORD"], "confidence": [1.0] * 3})
    w = {"P3.R10": 0.85, "P3.PYRAMID": 0.3, "P4.RECORD": 0.15}
    assert scores(f, w, ["S1", "S2"]) == pytest.approx([0.91075, 0.0])
    assert average_precision([1, 0, 1], [0.9, 0.8, 0.7]) == pytest.approx((1 + 2 / 3) / 2)
