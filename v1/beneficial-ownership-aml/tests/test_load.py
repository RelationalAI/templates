import pytest
from model.contracts import read_dir
from model.load import FrameSource, TableSource
from relationalai.semantics.std import aggregates as aggs

from tests.helpers import FIXTURES, LOAD_BACKENDS, ROOT, fixture_model


def _count(model, concept):
    x = concept.ref()
    df = model.select(aggs.count(x).alias("n")).to_df()
    return int(df["n"].iloc[0]) if len(df) else 0


@pytest.mark.parametrize("backend", LOAD_BACKENDS)
@pytest.mark.parametrize("fixture", list(FIXTURES))
def test_counts_match_csv(fixture, backend):
    model, o = fixture_model(fixture, backend, stages=())
    t = read_dir(ROOT / "data" / "fixtures" / FIXTURES[fixture])
    assert _count(model, o.Company) == len(t["companies"])
    assert _count(model, o.Person) == len(t["persons"])
    for name, concept in [("accounts", o.Account), ("transfers", o.Transfer), ("invoices", o.Invoice),
                          ("loans", o.Loan), ("strs", o.STR)]:
        assert _count(model, concept) == len(t.get(name, [])), name
    x, c = o.Entity.ref(), o.Company.ref()
    from relationalai.semantics import Float
    w = Float.ref()
    n_owns = model.where(x.owns(c, w)).select(aggs.count(x, c).alias("n")).to_df()
    assert (int(n_owns["n"].iloc[0]) if len(n_owns) else 0) == len(t["shareholdings"])


@pytest.mark.offline
def test_unknown_account_holder_still_loaded():
    """F5's account A:XYZ belongs to an unregistered company: the account must exist without a holder."""
    model, o = fixture_model("F5", "offline", stages=())
    a = o.Account.ref()
    df = model.where(a.account_id == "A:XYZ", model.not_(a.holder)).select(a.account_id.alias("id")).to_df()
    assert list(df["id"]) == ["A:XYZ"]


@pytest.mark.offline
def test_hidden_never_loaded():
    src = FrameSource.from_dir(ROOT / "data" / "sample")
    assert "family_links_hidden" not in src.tables and "str_labels" not in src.tables
    with pytest.raises(ValueError):
        src.rows(None, "family_links_hidden")
    with pytest.raises(ValueError):
        TableSource("X.Y").rows(None, "str_labels")


@pytest.mark.snowflake
def test_table_source_matches_frames():
    """The sample loaded from Snowflake tables gives the same counts as the bundled CSVs."""
    import os

    from config import Settings
    from model import build_model

    os.chdir(ROOT)
    m_sf, o_sf = build_model(Settings(), TableSource("BENEFICIAL_OWNERSHIP.DATA"), name="bo_test_table_source", stages=[])
    t = read_dir(ROOT / "data" / "sample")
    assert _count(m_sf, o_sf.Company) == len(t["companies"])
    assert _count(m_sf, o_sf.Person) == len(t["persons"])
    assert _count(m_sf, o_sf.Transfer) == len(t["transfers"])
    assert _count(m_sf, o_sf.STR) == len(t["strs"])
