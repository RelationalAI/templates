"""GNN family-link prediction (P3 "#sim" embedded ML; P1 "more sophisticated models can be plugged in").

Trains `link_prediction` on Person -> Person over the ownership graph plus known links, then returns the
GNN's top-k predicted partners per person as (a_eid, b_eid, score). Those pairs become the Graham feature
`gnn` (in top-k or not) inside VADA-LINK, so link confidences stay probabilities. Snowflake only.
"""

from __future__ import annotations

import uuid

import pandas as pd
from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

from model.load import Only, load
from model.ontology import declare


def run(S, source, *, log=print, name=None, epochs=15) -> tuple[pd.DataFrame, dict]:
    import gc

    from relationalai.semantics.reasoners.graph import Graph
    from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

    gc.collect()   # GNN internals use standalone PyRel functions: no other live Model may exist
    if len(Model.all_models):
        raise RuntimeError(f"{len(Model.all_models)} other model(s) still referenced; release them before GNN training")

    m = Model(name or f"bo_aml_gnn_link_{uuid.uuid4().hex[:6]}")
    o = declare(m)
    load(m, o, Only(source, frozenset({"companies", "persons", "shareholdings", "family_links_known"})))
    Pe, Co = o.Person, o.Company

    def positives(split):
        df = source.frame(f"family_pairs_{split}")
        return df[df.label == 1][["a_eid", "b_eid"]].rename(columns={"a_eid": "src", "b_eid": "dst"}).reset_index(drop=True)

    train, val = positives("train"), positives("val")
    persons = source.frame("persons")[["eid"]].rename(columns={"eid": "src"})
    TrainT, ValT, TestT = m.Concept("LinkTrainTable"), m.Concept("LinkValTable"), m.Concept("LinkTestTable")
    m.define(TrainT.new(m.data(train).to_schema()))
    m.define(ValT.new(m.data(val).to_schema()))
    m.define(TestT.new(m.data(persons).to_schema()))
    Train = m.Relationship(f"{Pe:src} has {Pe:dst}")
    Val = m.Relationship(f"{Pe:src} has {Pe:dst}")
    Test = m.Relationship(f"{Pe:src}")
    s, d = Pe.ref(), Pe.ref()
    m.where(s.eid == TrainT.src, d.eid == TrainT.dst).define(Train(s, d))
    m.where(s.eid == ValT.src, d.eid == ValT.dst).define(Val(s, d))
    m.where(s.eid == TestT.src).define(Test(s))

    g = Graph(m, directed=True, weighted=False)
    p, q, c, c2 = Pe.ref(), Pe.ref(), Co.ref(), Co.ref()
    w = Float.ref()
    m.where(p.owns(c, w)).define(g.Edge.new(src=p, dst=c))                  # one direction per edge type (both directions warn)
    m.where(c2.owns(c, w)).define(g.Edge.new(src=c2, dst=c))
    t, cf = String.ref(), Float.ref()
    m.where(p.link(q, t, cf)).define(g.Edge.new(src=p, dst=q))
    # co-residence as graph structure; skip very common addresses (registered offices) to bound fan-out
    Pe.address_count = m.Property(f"{Pe} shares an address with {Integer:n} persons")
    r2 = Pe.ref()
    m.define(p.address_count(aggs.count(r2).per(p).where(r2.address == p.address)))
    m.where(p.address == q.address, p.num < q.num, p.address_count <= 20).define(g.Edge.new(src=p, dst=q))

    pt = PropertyTransformer(
        category=[Pe.province, Pe.sex, Pe.birth_city, Co.sector, Co.legal_form],
        continuous=[Pe.birth_year],
        text=[Pe.surname, Pe.address],
    )
    gnn = GNN(exp_database=S.EXP_DATABASE, exp_schema=S.EXP_SCHEMA, graph=g, property_transformer=pt,
              train=Train, validation=Val, task_type="link_prediction", eval_metric="link_prediction_precision@5",
              has_time_column=False, device=S.GNN_DEVICE, n_epochs=epochs, seed=S.SEED)
    log(f"[gnn-link] training on {len(train)} known links ({S.GNN_DEVICE}, {epochs} epochs)")
    gnn.fit()
    Pe.link_predictions = gnn.predictions(domain=Test)
    r = Pe.ref()
    df = m.where(Pe.link_predictions.predicted_person == r).select(
        Pe.eid.alias("a_eid"), r.eid.alias("b_eid"), Pe.link_predictions.scores.alias("score"),
        Pe.link_predictions.rank.alias("rank")).to_df()
    df = df[df.a_eid != df.b_eid].astype({"score": float})
    # hit@k on validation pairs (the GNN never trained on them)
    tops = df.groupby("a_eid")["b_eid"].apply(set).to_dict()
    hits = [(b in tops.get(a, set())) or (a in tops.get(b, set())) for a, b in val[["src", "dst"]].values]
    report = {"predictions": len(df), "val_pairs": len(val), "val_hit@k": sum(hits) / max(len(hits), 1)}
    log(f"[gnn-link] {report}")
    return df[["a_eid", "b_eid", "score"]].reset_index(drop=True), report
