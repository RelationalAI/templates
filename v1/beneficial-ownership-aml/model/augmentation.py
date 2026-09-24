"""VADA-LINK knowledge-graph augmentation (P1 §4, Alg. 1, 3, 7; P2 §2): predict hidden family links.

  level-1 blocks  b1: Louvain on a person-person projection (co-investment, known/predicted links,
                      shared address): Louvain on the raw ownership graph is too fine (at most 2 persons/community)
  level-2 blocks  b2: per-link-type feature keys (P2 "#GenerateBlocks", polymorphic by link type)
  candidates        : same block, not already linked (P1 Alg. 3 rule 2)
  scoring           : Graham combination of per-feature probabilities (P1 Eq. 3), log space
  reinforcement     : augment() rebuilds the model each round with the links predicted so far (P1 Alg. 1)

Calibration pairs (family_pairs_train/val) and candidates are both `Pair` entities, told apart by
`origin`, so the feature rules are written once and calibration measures exactly what scoring uses.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math, strings

FEATURES = {
    "PARTNER_OF": ["surname", "address", "age_gap", "sex_diff", "coinvest"],
    "SIBLING_OF": ["surname", "address", "birth_city", "age_gap", "coinvest"],
}
AGE_GAP = {"PARTNER_OF": 10, "SIBLING_OF": 15}
ROOT = Path(__file__).resolve().parents[1]


def key_expr(p, field):
    return {
        "province": lambda: p.province,
        "surname3": lambda: strings.substring(strings.lower(p.surname), 0, 3),
        "birth_city": lambda: p.birth_city,
        "birth_decade": lambda: strings.string(math.floor(p.birth_year / 10.0)),
        "address_key": lambda: strings.substring(strings.lower(p.address), 0, 12),
    }[field]()


def register(m, o, S, *, pairs: dict[str, pd.DataFrame] | None = None, feature_probs: pd.DataFrame | None = None,
             candidates: bool = True, score: bool = True, gnn_scores: pd.DataFrame | None = None):
    """Blocks, candidates, pair features and (when feature_probs is given) Graham scores.
    `pairs` = labeled calibration pairs by origin, e.g. {"train": df, "val": df}.
    `gnn_scores` (a_eid, b_eid, score): GNN link scores, used as one more Graham feature."""
    if candidates:
        _register_blocks(m, o, S)
    _register_pairs(m, o, S, pairs or {}, candidates)
    if gnn_scores is not None and len(gnn_scores):
        _register_gnn_scores(m, o, gnn_scores, add_candidates=candidates and S.GNN_CANDIDATES)
    _register_features(m, o, S)
    if not score:
        return
    if feature_probs is None:
        f = Path(S.FEATURE_PROBS) if S.FEATURE_PROBS else ROOT / "data" / "sample" / "feature_probs.csv"
        feature_probs = pd.read_csv(f) if f.exists() else None
    if feature_probs is not None:
        _register_scores(m, o, S, feature_probs)


# ------------------------------------------------------------------------------------------ blocks
def _register_blocks(m, o, S):
    Pe, Co = o.Person, o.Company
    a, b = Pe.ref(), Pe.ref()
    Pe.b1_raw = m.Property(f"{Pe} in level-1 community {Integer:b1}")
    Pe.b1 = m.Property(f"{Pe} in level-1 block {Integer:b1}")
    if S.BLOCKING_L1 == "louvain_projection":
        from relationalai.semantics.reasoners.graph import Graph

        g = Graph(m, directed=False, weighted=True, node_concept=Pe, aggregator="sum")
        y = Co.ref()
        w1, w2, cf = Float.ref(), Float.ref(), Float.ref()
        t = String.ref()
        m.where(a.owns(y, w1), b.owns(y, w2), a.num < b.num).define(g.Edge.new(src=a, dst=b, weight=1.0))
        m.where(a.link(b, t, cf), a.num < b.num).define(g.Edge.new(src=a, dst=b, weight=2.0))
        m.where(a.link(b, t, cf), b.num < a.num).define(g.Edge.new(src=b, dst=a, weight=2.0))
        Pe.address_count = m.Property(f"{Pe} shares an address with {Integer:n} persons")
        c = Pe.ref()
        m.define(a.address_count(aggs.count(c).per(a).where(c.address == a.address)))
        m.where(a.address == b.address, a.num < b.num, a.address_count <= 20).define(
            g.Edge.new(src=a, dst=b, weight=1.0))
        g.Node.community = g.louvain()
        m.where(g.Node == a).define(a.b1_raw(g.Node.community))
    else:  # "none": a single level-1 block (offline, or to measure the effect of level 1)
        m.define(a.b1_raw(0))
    m.define(a.b1(a.b1_raw | (0 - a.num)))                     # persons with no community: singleton


def _register_pairs(m, o, S, pairs, candidates=True):
    Pe = o.Person
    a, b = Pe.ref(), Pe.ref()
    Block = m.Concept("Block", identify_by={"link_type": String, "key": String})
    Block.size = m.Property(f"{Block} has {Integer:size} members")
    Pe.in_block = m.Relationship(f"{Pe} is in {Block}")
    Pair = m.Concept("Pair", identify_by={"a": Pe, "b": Pe, "link_type": String, "origin": String})
    Pair.label = m.Property(f"{Pair} has label {Integer:label}")
    Pe.linked_any = m.Relationship(f"{Pe:a} already linked to {Pe:b}")
    t, cf = String.ref(), Float.ref()
    m.where(a.link(b, t, cf)).define(a.linked_any(b), b.linked_any(a))

    for lt in (S.LINK_TYPES if candidates else ()):
        parts = [strings.string(a.b1)]
        for field in S.BLOCK_KEYS[lt]:
            parts += ["|", key_expr(a, field)]
        key = strings.concat(*parts) if len(parts) > 1 else parts[0]
        m.define(blk := Block.new(link_type=lt, key=key), a.in_block(blk))
    bk = Block.ref()
    if candidates:
        m.define(bk.size(aggs.count(a).per(bk).where(a.in_block(bk))))
        m.where(a.in_block(bk), b.in_block(bk), a.num < b.num, bk.size <= S.MAX_BLOCK,
                m.not_(a.linked_any(b))).define(Pair.new(a=a, b=b, link_type=bk.link_type, origin="candidate"))

    for origin, df in pairs.items():
        d = m.data(df[["a_eid", "b_eid", "link_type", "label"]].reset_index(drop=True))
        m.where(pa := Pe.lookup(eid=d.a_eid), pb := Pe.lookup(eid=d.b_eid)).define(
            pr := Pair.new(a=pa, b=pb, link_type=d.link_type, origin=origin), pr.label(d.label))
    o.Block, o.Pair = Block, Pair


def _register_gnn_scores(m, o, gnn_scores, add_candidates=True):
    """Pair.gnn_score / gnn_in_topk from the GNN's top-k predictions. With add_candidates, the top-k pairs
    also become candidates (P1's #GraphEmbedClust: embeddings propose neighbourhoods, rules decide)."""
    Pair, Pe = o.Pair, o.Person
    raw = m.Relationship(f"{Pe:a} has GNN link score to {Pe:b} of {Float:score}")
    d = m.data(gnn_scores[["a_eid", "b_eid", "score"]].reset_index(drop=True).astype({"score": float}))
    m.where(a := Pe.lookup(eid=d.a_eid), b := Pe.lookup(eid=d.b_eid)).define(raw(a, b, d.score), raw(b, a, d.score))
    if add_candidates:
        a, b, v = Pe.ref(), Pe.ref(), Float.ref()
        for lt in o.settings.LINK_TYPES:
            m.where(raw(a, b, v), a.num < b.num, m.not_(a.linked_any(b))).define(
                Pair.new(a=a, b=b, link_type=lt, origin="candidate"))
    Pair.gnn_score = m.Property(f"{Pair} has GNN link score {Float:score}")
    Pair.gnn_in_topk = m.Relationship(f"{Pair} is among the GNN's top-k predicted links")
    pr, v = Pair.ref(), Float.ref()
    m.define(pr.gnn_score(aggs.max(v).per(pr).where(raw(pr.a, pr.b, v))))
    m.where(raw(pr.a, pr.b, v)).define(pr.gnn_in_topk())
    o.has_gnn_link_scores = True


# ------------------------------------------------------------------------------------------ features
def _register_features(m, o, S):
    Pair, Co = o.Pair, o.Company
    Pair.feat = m.Relationship(f"{Pair} has feature {String:feature} matched {Integer:matched}")
    pr = Pair.ref()
    a, b = pr.a, pr.b
    y = Co.ref()
    w1, w2 = Float.ref(), Float.ref()
    conds = {  # each returns a tuple of conditions (conjunction)
        "surname": lambda: (strings.levenshtein(strings.lower(a.surname), strings.lower(b.surname)) <= 1,),
        "address": lambda: (strings.levenshtein(strings.lower(a.address), strings.lower(b.address)) <= 3,),
        "birth_city": lambda: (a.birth_city == b.birth_city,),
        "sex_diff": lambda: (a.sex != b.sex,),
        "coinvest": lambda: (a.owns(y, w1), b.owns(y, w2)),
    }
    for lt, feats in FEATURES.items():
        for fn in feats:
            if fn == "age_gap":
                gap = math.abs(a.birth_year - b.birth_year)
                m.where(pr.link_type == lt, gap <= AGE_GAP[lt]).define(pr.feat("age_gap", 1))
                m.where(pr.link_type == lt, gap > AGE_GAP[lt]).define(pr.feat("age_gap", 0))
                continue
            m.where(pr.link_type == lt, *conds[fn]()).define(pr.feat(fn, 1))
            m.where(pr.link_type == lt, m.not_(*conds[fn]())).define(pr.feat(fn, 0))
    if getattr(o, "has_gnn_link_scores", False):   # set when GNN scores are loaded (hasattr on a Concept is always True)
        m.where(pr.gnn_in_topk()).define(pr.feat("gnn", 1))       # GNN scores are unnormalized: use top-k membership
        m.where(m.not_(pr.gnn_in_topk())).define(pr.feat("gnn", 0))


# ------------------------------------------------------------------------------------------ scores
def _register_scores(m, o, S, feature_probs: pd.DataFrame):
    Pair, Pe = o.Pair, o.Person
    FP = m.Concept("FeatureProb", identify_by={"link_type": String, "feature": String, "matched": Integer})
    FP.p = m.Property(f"{FP} has probability {Float:p}")
    d = m.data(feature_probs[["link_type", "feature", "matched", "p"]].astype({"matched": "int64", "p": float}))
    m.define(fp := FP.new(link_type=d.link_type, feature=d.feature, matched=d.matched), fp.p(d.p))
    Thr = m.Concept("LinkThreshold", identify_by={"link_type": String})
    Thr.t = m.Property(f"{Thr} has threshold {Float:t}")
    td = m.data(pd.DataFrame({"link_type": list(S.LINK_T), "t": [float(v) for v in S.LINK_T.values()]}))
    m.define(th := Thr.new(link_type=td.link_type), th.t(td.t))

    pr, fp = Pair.ref(), FP.ref()
    fn, mt = String.ref(), Integer.ref()
    match = [pr.feat(fn, mt), fp.link_type == pr.link_type, fp.feature == fn, fp.matched == mt]
    lp = aggs.sum(fn, math.natural_log(fp.p)).per(pr).where(*match)
    lq = aggs.sum(fn, math.natural_log(1.0 - fp.p)).per(pr).where(*match)
    Pair.prob = m.Property(f"{Pair} has link probability {Float:prob}")
    m.define(pr.prob(math.exp(lp) / (math.exp(lp) + math.exp(lq))))            # P1 Eq. 3

    Pe.predicted_link = m.Property(f"{Pe:a} predicted linked to {Pe:b} as {String:link_type} with {Float:p}")
    th = Thr.ref()
    m.where(pr.origin == "candidate", th.link_type == pr.link_type, pr.prob > th.t).define(
        pr.a.predicted_link(pr.b, pr.link_type, pr.prob))                    # P1 Alg. 7
    o.FeatureProb = FP


# ------------------------------------------------------------------------------------------ driver
def predicted_links(model, o) -> pd.DataFrame:
    a, b, t, p = o.Person.ref(), o.Person.ref(), String.ref(), Float.ref()
    df = model.where(a.predicted_link(b, t, p)).select(
        a.eid.alias("a_eid"), b.eid.alias("b_eid"), t.alias("link_type"), p.alias("confidence")).to_df()
    return df


def block_stats(model, o) -> dict:
    pr, bk = o.Pair.ref(), o.Block.ref()
    c = model.where(pr.origin == "candidate").select(aggs.count(pr).alias("n")).to_df()
    s = model.select(aggs.count(bk).alias("blocks"), aggs.max(bk.size).alias("max_size")).to_df()
    return {"candidates": int(c["n"].iloc[0]) if len(c) else 0,
            "blocks": int(s["blocks"].iloc[0]), "max_block": int(s["max_size"].iloc[0])}


def augment(S, source, *, config=None, name="bo_aml_aug", log=print, gnn_scores=None):
    """P1 Alg. 1: rounds of (block -> candidates -> score -> add links) until nothing new."""
    from model import build_model

    links = pd.DataFrame(columns=["a_eid", "b_eid", "link_type", "confidence", "round"])
    history = []
    for r in range(1, S.MAX_ROUNDS + 1):
        model, o = build_model(S, source, extra_links=links, name=f"{name}_r{r}", stages=[], config=config,
                               augment=True, gnn_pair_scores=gnn_scores)
        new = predicted_links(model, o)
        stats = block_stats(model, o)
        history.append({"round": r, **stats, "new_links": len(new)})
        log(f"[augment] round {r}: {stats['blocks']} blocks (max {stats['max_block']}), "
            f"{stats['candidates']} candidates, {len(new)} new links")
        if new.empty:
            break
        links = pd.concat([links, new.assign(round=r)], ignore_index=True)
    return links, history
