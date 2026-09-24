import hashlib
import json

import pytest
from data.generator.generate import GenConfig, generate
from data.generator.stats import graph_stats
from model.contracts import CONTRACTS, read_dir, validate

CI = GenConfig(seed=7, companies=500, persons=300)


@pytest.fixture(scope="module")
def tables():
    return generate(CI)


def _digest(tables):
    h = hashlib.sha256()
    for name in sorted(tables):
        h.update(name.encode())
        h.update(tables[name].to_csv(index=False).encode())
    return h.hexdigest()


@pytest.mark.offline
def test_deterministic(tables):
    assert _digest(tables) == _digest(generate(CI))


@pytest.mark.offline
def test_contracts(tables):
    for name, df in tables.items():
        validate(df, name)
    assert set(tables) <= set(CONTRACTS)


@pytest.mark.offline
def test_incoming_shares_le_1(tables):
    sh = tables["shareholdings"]
    assert sh.groupby("owned_eid")["share"].sum().max() <= 1.0 + 1e-9


@pytest.mark.offline
def test_stats_shape():
    s = graph_stats(read_dir("data/sample"))
    assert 0.7 <= s["avg_degree"] <= 1.5
    assert s["largest_scc"] <= 50
    assert s["self_loop_rate"] < 0.002
    assert -3.2 <= s["out_degree_tail_slope"] <= -1.8


@pytest.mark.offline
def test_manifest_consistency():
    t = read_dir("data/sample")
    m = json.loads(open("data/sample/manifest.json").read())
    companies, persons = set(t["companies"].eid), set(t["persons"].eid)
    for chain in m["planted"]["pyramids"]:
        assert set(chain) <= companies
    for case in m["planted"]["ubo_cases"]:
        assert case["applicant"] in persons and case["bank"] in companies
        assert case["bank"] in set(t["companies"][t["companies"].is_bank == 1].eid)
    known = set(map(tuple, t["family_links_known"][["a_eid", "b_eid"]].values))
    hidden = set(map(tuple, t["family_links_hidden"][["a_eid", "b_eid"]].values))
    assert not known & hidden
    assert len(hidden) > 0


@pytest.mark.offline
def test_ubo_pyramid_gives_family_control():
    """The planted pyramid hop shares (>0.5) guarantee control down the chain to the bank."""
    t = read_dir("data/sample")
    sh = t["shareholdings"].set_index(["owner_eid", "owned_eid"])["share"]
    m = json.loads(open("data/sample/manifest.json").read())
    for case in m["planted"]["ubo_cases"]:
        chain = case["chain"]
        top = sum(sh.get((h, chain[0]), 0.0) for h in case["holders"])
        assert top > 0.5, case
        for a, b in zip(chain, chain[1:]):
            assert sh[(a, b)] > 0.5, (a, b)
        # the applicant holds nothing directly in the bank
        assert (case["applicant"], case["bank"]) not in sh.index


@pytest.mark.offline
def test_fixtures_valid():
    import glob

    for d in glob.glob("data/fixtures/f*/"):
        read_dir(d)
