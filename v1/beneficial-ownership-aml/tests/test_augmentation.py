"""Phase 6: VADA-LINK blocking, candidates, Graham scoring, reinforcement rounds, recall on hidden links."""

import dataclasses
import math

import pandas as pd
import pytest
from calibrate import feature_probabilities
from config import Settings, offline_config
from model import augmentation, build_model
from model.contracts import read_dir
from model.load import FrameSource

from tests.helpers import BACKENDS, FIXTURES, ROOT

SAMPLE = ROOT / "data" / "sample"


def settings(**kw):
    return dataclasses.replace(Settings().with_calibration(SAMPLE), **kw)


def graham(ps):
    num = math.prod(ps)
    return num / (num + math.prod(1 - p for p in ps))


@pytest.mark.offline
def test_graham_math():
    assert graham([0.9, 0.8, 0.3]) == pytest.approx(0.216 / 0.230)


@pytest.fixture(scope="module")
def f3_without_partner_link():
    t = read_dir(ROOT / "data" / "fixtures" / FIXTURES["F3"])
    kl = t["family_links_known"]
    t["family_links_known"] = kl[~((kl.a_eid == "P:X") & (kl.b_eid == "P:P1"))].reset_index(drop=True)
    return FrameSource(t, FrameSource.from_dir(ROOT / "data" / "fixtures" / FIXTURES["F3"]).shared)


@pytest.mark.parametrize("backend", BACKENDS)
def test_f3_partner_link_recovered(f3_without_partner_link, backend):
    """Acme case with the X-P1 partner link removed: VADA-LINK must predict it (address, age, sex match)."""
    S = settings(BLOCKING_L1="none")
    cfg = offline_config() if backend == "offline" else None
    m, o = build_model(S, f3_without_partner_link, name=f"bo_test_f3_aug_{backend}", stages=[], config=cfg,
                       augment=True)
    links = augmentation.predicted_links(m, o)
    got = {(r.a_eid, r.b_eid, r.link_type): r.confidence for r in links.itertuples()}
    key = [k for k in got if {"P:X", "P:P1"} == {k[0], k[1]}]
    assert key and key[0][2] == "PARTNER_OF", got
    fp = pd.read_csv(SAMPLE / "feature_probs.csv").set_index(["link_type", "feature", "matched"])["p"]
    expected = graham([fp[("PARTNER_OF", "address", 1)], fp[("PARTNER_OF", "age_gap", 1)],
                       fp[("PARTNER_OF", "sex_diff", 1)], fp[("PARTNER_OF", "coinvest", 0)],
                       fp[("PARTNER_OF", "surname", 0)]])
    assert got[key[0]] == pytest.approx(expected, abs=1e-6)
    assert got[key[0]] > S.LINK_T["PARTNER_OF"]


@pytest.mark.snowflake
def test_candidates_within_blocks_and_not_linked():
    S = settings(BLOCKING_L1="none")
    src = FrameSource.from_dir(ROOT / "data" / "ci")
    m, o = build_model(S, src, name="bo_test_blocks_ci", stages=[], augment=True)
    pr, bk = o.Pair.ref(), o.Block.ref()
    bad = m.where(pr.origin == "candidate", m.not_(pr.a.in_block(bk), pr.b.in_block(bk),
                                                   bk.link_type == pr.link_type)).select(pr.a.eid.alias("a")).to_df()
    assert bad.empty
    linked = m.where(pr.origin == "candidate", pr.a.linked_any(pr.b)).select(pr.a.eid.alias("a")).to_df()
    assert linked.empty
    assert augmentation.block_stats(m, o)["candidates"] > 0


@pytest.mark.offline
def test_feature_probabilities_equal_prior():
    feats = pd.DataFrame({"link_type": ["X"] * 4, "feature": ["f"] * 4, "label": [1, 1, 0, 0], "matched": [1, 1, 0, 1]})
    fp = feature_probabilities(feats, alpha=0).set_index("matched")["p"]
    # P(m=1|L)=1, P(m=1|not L)=.5 -> p = 1/1.5
    assert fp[1] == pytest.approx(min(1 / 1.5, 0.99))


@pytest.mark.snowflake
def test_sample_recall():
    from eval.augmentation_eval import run

    res, links, history = run(settings(), "data/sample", log=lambda *_: None)
    assert history[-1]["new_links"] == 0, "reinforcement loop must terminate within MAX_ROUNDS"
    # regression guard, not a target: the sample measures recall 0.78 / precision 0.90 (README)
    assert res["recall"] >= 0.75 and res["precision"] >= 0.85, res
