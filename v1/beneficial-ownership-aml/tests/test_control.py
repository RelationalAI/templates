"""Phase 4: effective holdings, depth-layered control, control evidence and accumulated ownership."""

import pytest
from model.control import ControlNotConverged, check_converged
from relationalai.semantics import Float, Integer

from tests.helpers import BACKENDS, expected, fixture_model, pairs

STAGES = ("holdings", "control", "ownership")


def controls(model, o):
    a, b = o.Entity.ref(), o.Entity.ref()
    return pairs(model.where(a.controls(b)).select(a.eid.alias("a"), b.eid.alias("b")).to_df(), "a", "b")


def phi(model, o):
    a, b, v = o.Entity.ref(), o.Company.ref(), Float.ref()
    df = model.where(a.phi(b, v)).select(a.eid.alias("a"), b.eid.alias("b"), v.alias("v")).to_df()
    return {f"{r.a}|{r.b}": float(r.v) for r in df.itertuples()}


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("fixture", ["F1", "F2", "F3"])
def test_control_fixture(fixture, backend):
    model, o = fixture_model(fixture, backend, STAGES)
    got = controls(model, o)
    exp = expected(fixture)
    missing = {tuple(p) for p in exp["controls"]} - got
    wrong = {tuple(p) for p in exp["not_controls"]} & got
    assert not missing and not wrong, f"missing={missing} wrong={wrong}"
    check_converged(model, o)


@pytest.mark.parametrize("backend", BACKENDS)
def test_control_depth_and_steps_F1(backend):
    model, o = fixture_model("F1", backend, STAGES)
    a, b, d = o.Entity.ref(), o.Company.ref(), Integer.ref()
    df = model.where(a.control_depth(b, d)).select(a.eid.alias("a"), b.eid.alias("b"), d.alias("d")).to_df()
    depth = {f"{r.a}|{r.b}": int(r.d) for r in df.itertuples()}
    for k, v in expected("F1")["control_depth"].items():
        assert depth.get(k) == v, (k, depth.get(k), v)
    s = o.ControlStep.ref()
    df = model.where(s.controller.eid == "P:P1", s.target.eid == "C:F").select(
        s.via.eid.alias("via"), s.share.alias("share")).to_df()
    got = sorted((r.via, round(float(r.share), 6)) for r in df.itertuples())
    assert got == sorted((v, s_) for v, s_ in expected("F1")["control_steps"]["P:P1|C:F"])


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("fixture", ["F1", "F2", "F3"])
def test_phi_values(fixture, backend):
    model, o = fixture_model(fixture, backend, STAGES)
    got = phi(model, o)
    for k, v in expected(fixture).get("phi", {}).items():
        assert got.get(k) == pytest.approx(v, abs=1e-4), (k, got.get(k), v)


@pytest.mark.parametrize("backend", BACKENDS)
def test_phi_unrolled_overcounts_intermediate_cycle_F2(backend):
    model, o = fixture_model("F2", backend, STAGES)
    got = phi(model, o)
    assert got["C:C8|C:C9"] == pytest.approx(1.0, abs=1e-9)   # walks back to the source are dropped
    for k, v in expected("F2")["phi_unrolled_gt"].items():
        assert got[k] > v + 0.1, (k, got[k])                    # P3->C8->C9->C8->C9 adds 0.15
    assert max(got.values()) <= 1.0                               # capped: a share cannot exceed 100%


@pytest.mark.snowflake
def test_phi_paths_exact_on_cycle_F2():
    model, o = fixture_model("F2", "snowflake", STAGES, PHI_METHOD="paths")
    got = phi(model, o)
    for k, v in expected("F2")["phi_paths"].items():
        assert got[k] == pytest.approx(v, abs=1e-9), k
    assert got["C:C4|C:C7"] == pytest.approx(0.2, abs=1e-9)


@pytest.mark.snowflake
def test_ceo_rule_toggle():
    model, o = fixture_model("F3", "snowflake", STAGES, CEO_RULE=False)
    assert "P:P1|C:MY_BANK" not in phi(model, o)
    assert ("P:P1", "C:PEOPLE_BANK") not in controls(model, o)


@pytest.mark.snowflake
def test_not_converged_raises():
    model, o = fixture_model("F1", "snowflake", STAGES, MAX_CONTROL_DEPTH=2)   # F needs depth 3
    with pytest.raises(ControlNotConverged):
        check_converged(model, o)
