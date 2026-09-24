"""Phase 5: families (kin closure), family holdings and control, close links, family close links."""

from collections import defaultdict

import pandas as pd
import pytest
from config import Settings
from model import build_model
from model.load import FrameSource
from relationalai.semantics import Float

from tests.helpers import BACKENDS, expected, fixture_model

STAGES = ("family", "holdings", "control", "ownership", "close_links")


def families(model, o):
    p, f = o.Person.ref(), o.Family.ref()
    df = model.where(p.family(f)).select(f.eid.alias("f"), p.eid.alias("p")).to_df()
    out = defaultdict(set)
    for r in df.itertuples():
        out[r.f].add(r.p)
    return out


def family_controls(model, o):
    fam = families(model, o)
    f, c = o.Family.ref(), o.Company.ref()
    df = model.where(f.controls(c)).select(f.eid.alias("f"), c.eid.alias("c")).to_df()
    return {(frozenset(fam[r.f]), r.c) for r in df.itertuples()}


def unordered(model, rel, o, extra=False):
    a, b = o.Company.ref(), o.Company.ref()
    if extra:
        f = o.Family.ref()
        df = model.where(rel(a, b, f)).select(a.eid.alias("a"), b.eid.alias("b")).to_df()
    else:
        df = model.where(rel(a, b)).select(a.eid.alias("a"), b.eid.alias("b")).to_df()
    return {frozenset((r.a, r.b)) for r in df.itertuples()}


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("fixture", ["F1", "F2", "F3"])
def test_families_and_family_control(fixture, backend):
    model, o = fixture_model(fixture, backend, STAGES)
    exp = expected(fixture)
    fams = {frozenset(v) for v in families(model, o).values()}
    assert fams == {frozenset(x) for x in exp["families"]}
    got = family_controls(model, o)
    for fc in exp["family_controls"]:
        assert (frozenset(fc["members"]), fc["company"]) in got, fc


@pytest.mark.parametrize("backend", BACKENDS)
def test_family_accumulated_share_F3(backend):
    model, o = fixture_model("F3", backend, STAGES)
    f, c, v = o.Family.ref(), o.Company.ref(), Float.ref()
    df = model.where(f.accumulated_share(c, v), c.eid == "C:MY_BANK").select(v.alias("v")).to_df()
    assert float(df["v"].iloc[0]) == pytest.approx(expected("F3")["family_accumulated_share"]["C:MY_BANK"], abs=1e-4)


@pytest.mark.parametrize("backend", BACKENDS)
def test_close_links_F1(backend):
    model, o = fixture_model("F1", backend, STAGES)
    exp = expected("F1")
    assert unordered(model, o.Company.close_link, o) == {frozenset(p) for p in exp["close_links"]}
    fcl = unordered(model, o.Company.family_close_link, o, extra=True)
    assert frozenset(("C:D", "C:G")) in fcl
    assert len(fcl) == exp["family_close_links_count"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_close_links_F2(backend):
    model, o = fixture_model("F2", backend, STAGES)
    got = unordered(model, o.Company.close_link, o)
    for p in expected("F2")["close_links_contains"]:
        assert frozenset(p) in got, p


@pytest.mark.snowflake
def test_oversized_family_excluded():
    """13 persons chained by links: closure is truncated at MAX_FAMILY_SIZE=12, family is flagged and
    contributes no family control even though together they hold 0.65 of a company."""
    n = 13
    persons = pd.DataFrame([{
        "eid": f"P:{i}", "num": i, "first_name": "A", "surname": f"S{i}", "sex": "M", "birth_date": "1970-01-01",
        "birth_year": 1970, "birth_city": "X", "address": f"{i} Via", "province": "PR00", "is_pep": 0,
        "has_record": 0} for i in range(1, n + 1)])
    companies = pd.DataFrame([{"eid": "C:Z", "name": "Z", "legal_form": "SPA", "sector": "HOLDING",
                               "province": "PR00", "inc_date": "2000-01-01", "is_bank": 0}])
    sh = pd.DataFrame([{"owner_eid": f"P:{i}", "owned_eid": "C:Z", "share": 0.05, "right_type": "ownership"}
                       for i in range(1, n + 1)])
    links = pd.DataFrame([{"a_eid": f"P:{i}", "b_eid": f"P:{i + 1}", "link_type": "SIBLING_OF", "source": "registry"}
                          for i in range(1, n)])
    src = FrameSource({"persons": persons, "companies": companies, "shareholdings": sh, "family_links_known": links})
    model, o = build_model(Settings(), src, name="bo_test_oversized", stages=list(STAGES))
    f = o.Family.ref()
    over = model.where(f.is_oversized()).select(f.eid.alias("f")).to_df()
    assert len(over) >= 1
    assert not family_controls(model, o)
