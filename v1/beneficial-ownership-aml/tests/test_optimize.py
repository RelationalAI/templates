"""Phase 9: case grouping and triage optimization (select and assign modes) vs the naive ranking."""

import pandas as pd
import pytest
from config import Settings
from model import build_model, optimize
from model.contracts import read_dir
from model.load import FrameSource

from tests.helpers import FIXTURES, ROOT


@pytest.fixture(scope="module")
def ci_model():
    S = Settings().with_calibration(ROOT / "data" / "sample")
    m, o = build_model(S, FrameSource.from_dir(ROOT / "data" / "ci"), name="bo_test_triage_ci")
    return S, m, o


@pytest.mark.snowflake
def test_cases_group_related_strs():
    """Add an STR on P2 (same family as X) to the Acme fixture: S1 and S2 must form one case."""
    t = read_dir(ROOT / "data" / "fixtures" / FIXTURES["F3"])
    extra = pd.DataFrame([{"str_id": "S2", "num": 2, "subject_eid": "P:P2", "bank_eid": "C:MY_BANK",
                           "instrument_type": "LOAN", "instrument_id": "L1", "amount": 1000.0, "filed_on": "2026-03-06"}])
    t["strs"] = pd.concat([t["strs"], extra], ignore_index=True)
    src = FrameSource(t, FrameSource.from_dir(ROOT / "data" / "fixtures" / FIXTURES["F3"]).shared)
    m, o = build_model(Settings(), src, name="bo_test_cases_f3")
    strs = optimize.str_table(m, o)
    assert strs.cid.nunique() == 1 and len(strs) == 2
    cases = optimize.case_table(m, o)
    assert int(cases.n_strs.iloc[0]) == 2
    assert float(cases.hours.iloc[0]) == Settings().CASE_SETUP_HOURS + 2 * Settings().HOURS_PER_STR


@pytest.mark.snowflake
def test_milp_optimal_budget_and_diversity(ci_model):
    S, m, o = ci_model
    budget = 60.0
    plan = optimize.solve_select(m, o, S, budget=budget)
    assert plan["status"] == "OPTIMAL"
    cases = optimize.case_table(m, o).set_index("cid")
    chosen = cases.loc[plan["chosen"]]
    assert chosen.hours.sum() <= budget + 1e-6
    assert (chosen.groupby("offence").hours.sum() <= S.MAX_CLASS_SHARE * budget + 1e-6).all()
    assert plan["objective"] == pytest.approx(chosen.value.sum(), rel=1e-6)


@pytest.mark.snowflake
def test_milp_at_least_naive(ci_model):
    S, m, o = ci_model
    budget = 60.0
    plan = optimize.solve_select(m, o, dataclasses_replace(S, MAX_CLASS_SHARE=1.0), budget=budget)
    naive = optimize.naive_topk(optimize.str_table(m, o), optimize.case_table(m, o), S, budget)
    assert plan["objective"] >= naive["value"] - 1e-6


@pytest.mark.snowflake
def test_assign_mode_capacity(ci_model):
    S, m, o = ci_model
    res = optimize.solve_assign(m, o, S)
    assert res["status"] == "OPTIMAL"
    rows = pd.DataFrame(res["assignments"])
    cases = optimize.case_table(m, o).set_index("cid")
    analysts = pd.read_csv(ROOT / "data" / "analysts.csv").set_index("analyst_id")
    assert rows.cid.is_unique
    load = rows.assign(h=rows.cid.map(cases.hours)).groupby("analyst").h.sum()
    assert (load <= analysts.hours.reindex(load.index) + 1e-6).all()
    for r in rows.itertuples():
        skills = analysts.loc[r.analyst, "skills"]
        assert skills == "ANY" or cases.loc[r.cid, "offence"] in skills


def dataclasses_replace(S, **kw):
    import dataclasses

    return dataclasses.replace(S, **kw)
