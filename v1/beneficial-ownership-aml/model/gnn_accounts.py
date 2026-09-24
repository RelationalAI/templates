"""GNN account classifier (P4's semi-supervised GCN on SAR labels) fed with rule outputs (P3's learning bus).

Two steps, because the GNN export treats many-to-many relations on node concepts (e.g. Entity.controls) as
functional:
  1. a rule model computes per-account features (structuring days, near misses, cycles, PEP exposure,
     holder / holder's family controls a bank, ...) -> DataFrame
  2. a lean GNN model (accounts, transfers, persons, companies, ownership) carries those features as plain
     properties and trains `binary_classification` on account_labels_train/val.
Predictions (max over a subject's accounts) come back to the rules as Finding GNN.ACCOUNT.
"""

from __future__ import annotations

import gc
import uuid

import pandas as pd
from relationalai.semantics import Float, Integer, Model

from model.load import Only, load
from model.ontology import declare

RULE_FEATURES = ["structuring_days", "near_miss_count", "pep_high_risk_i", "unknown_cp_i", "in_cycle_i",
                 "holder_controls_bank_i", "holder_family_controls_bank_i", "holder_pep_i", "holder_record_i"]
RAW_FEATURES = ["fan_in", "fan_out", "n_in", "n_out", "amount_in", "amount_out"]


def rule_features(S, source, links, *, log=print) -> pd.DataFrame:
    """Step 1: per-account features from the rules (Snowflake)."""
    from model import build_model

    m, o = build_model(S, source, extra_links=links, name=f"bo_aml_acctfeat_{uuid.uuid4().hex[:6]}",
                       stages=["family", "holdings", "control", "transactions"])
    A, Pe, Co = o.Account, o.Person, o.Company
    a, t = A.ref(), o.Transfer.ref()
    x, p, f, b = o.Entity.ref(), Pe.ref(), o.Family.ref(), Co.ref()
    feats = {}
    for name, cond in {
        "pep_high_risk_i": lambda: (a.pep_high_risk(),),
        "unknown_cp_i": lambda: (a.unknown_counterparty(),),
        "in_cycle_i": lambda: (a.in_cycle(),),
        "holder_controls_bank_i": lambda: (a.holder(x), x.controls(b), b.is_bank()),
        "holder_family_controls_bank_i": lambda: (a.holder(p), p.family(f), f.controls(b), b.is_bank()),
        "holder_pep_i": lambda: (a.holder(p), p.is_pep()),
        "holder_record_i": lambda: (a.holder(p), p.has_record()),
    }.items():
        rel = m.Property(f"{A} has indicator {name} {Integer:v}")
        setattr(A, name, rel)
        m.where(*cond()).define(rel(a, 1))
        m.where(m.not_(*cond())).define(rel(a, 0))
        feats[name] = rel
    from relationalai.semantics.std import aggregates as aggs

    A.n_in = m.Property(f"{A} receives {Integer:n} transfers")
    A.n_out = m.Property(f"{A} sends {Integer:n} transfers")
    A.amount_in = m.Property(f"{A} receives total {Float:v}")
    A.amount_out = m.Property(f"{A} sends total {Float:v}")
    m.define(a.n_in(aggs.count(t).per(a).where(t.to_account(a)) | 0))
    m.define(a.n_out(aggs.count(t).per(a).where(t.from_account(a)) | 0))
    m.define(a.amount_in(aggs.sum(t, t.amount).per(a).where(t.to_account(a)) | 0.0))
    m.define(a.amount_out(aggs.sum(t, t.amount).per(a).where(t.from_account(a)) | 0.0))
    cols = {"account_id": a.account_id, "structuring_days": a.structuring_days, "near_miss_count": a.near_miss_count,
            "fan_in": a.fan_in, "fan_out": a.fan_out, "n_in": a.n_in, "n_out": a.n_out,
            "amount_in": a.amount_in, "amount_out": a.amount_out}
    v = {k: Integer.ref() for k in feats}
    df = m.where(*[feats[k](a, v[k]) for k in feats]).select(
        *[e.alias(k) for k, e in cols.items()], *[v[k].alias(k) for k in feats]).to_df()
    del m, o
    gc.collect()
    log(f"[gnn-account] rule features for {len(df)} accounts")
    return df


def train_predict(S, source, features: pd.DataFrame, *, use_rule_features=True, log=print, epochs=10):
    """Step 2: GNN on accounts; returns per-account probabilities for accounts of STR subjects."""
    from relationalai.semantics.reasoners.graph import Graph
    from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

    gc.collect()
    if len(Model.all_models):
        raise RuntimeError("release other models before GNN training")
    m = Model(f"bo_aml_gnn_acct_{uuid.uuid4().hex[:6]}")
    o = declare(m)
    load(m, o, Only(source, frozenset({"companies", "persons", "shareholdings", "accounts", "transfers", "strs"})))
    A, Pe, Co = o.Account, o.Person, o.Company
    names = RAW_FEATURES + (RULE_FEATURES if use_rule_features else [])
    d = m.data(features[["account_id"] + names].reset_index(drop=True))
    for k in names:
        typ = Float if k.startswith("amount") else Integer
        # the GNN finds features by property FIELD name, so the field must be named f_<k>
        prop = m.Property(f"{A} has feature " + format(typ, f"f_{k}"))
        setattr(A, f"f_{k}", prop)
        m.where(a := A.lookup(account_id=d.account_id)).define(prop(a, getattr(d, k)))

    TrainT, ValT = m.Concept("AcctTrainTable"), m.Concept("AcctValTable")
    tr, va = source.frame("account_labels_train"), source.frame("account_labels_val")
    m.define(TrainT.new(m.data(tr[["account_id", "label"]]).to_schema()))
    m.define(ValT.new(m.data(va[["account_id", "label"]]).to_schema()))
    from relationalai.semantics import Any

    Train = m.Relationship(f"{A} has {Any:label}")
    Val = m.Relationship(f"{A} has {Any:label}")
    Test = m.Relationship(f"{A}")
    a, s, x = A.ref(), o.STR.ref(), o.Entity.ref()
    m.where(a.account_id == TrainT.account_id).define(Train(a, TrainT.label))
    m.where(a.account_id == ValT.account_id).define(Val(a, ValT.label))
    m.where(s.subject(x), a.holder(x)).define(Test(a))

    g = Graph(m, directed=True, weighted=False)
    t, a2, p, c, c2 = o.Transfer.ref(), A.ref(), Pe.ref(), Co.ref(), Co.ref()
    w = Float.ref()
    m.where(t.from_account(a), t.to_account(a2)).define(g.Edge.new(src=a, dst=a2))
    m.where(a.holder(p)).define(g.Edge.new(src=a, dst=p))
    m.where(a.holder(c)).define(g.Edge.new(src=a, dst=c))
    m.where(p.owns(c, w)).define(g.Edge.new(src=p, dst=c))
    m.where(c2.owns(c, w)).define(g.Edge.new(src=c2, dst=c))

    cont = [getattr(A, f"f_{k}") for k in names if k not in ("pep_high_risk_i", "unknown_cp_i", "in_cycle_i")]
    cat = [A.country, Pe.province, Co.sector] + [getattr(A, f"f_{k}") for k in names
                                                 if k in ("pep_high_risk_i", "unknown_cp_i", "in_cycle_i")]
    pt = PropertyTransformer(category=cat, continuous=cont + [Pe.birth_year])
    gnn = GNN(exp_database=S.EXP_DATABASE, exp_schema=S.EXP_SCHEMA, graph=g, property_transformer=pt,
              train=Train, validation=Val, task_type="binary_classification", eval_metric="roc_auc",
              has_time_column=False, device=S.GNN_DEVICE, n_epochs=epochs, seed=S.SEED)
    log(f"[gnn-account] training on {len(tr)} labeled accounts, rule features={'on' if use_rule_features else 'off'}")
    gnn.fit()
    A.predictions = gnn.predictions(domain=Test)
    df = m.select(A.account_id.alias("account_id"), A.holder.eid.alias("eid"),
                  A.predictions.probs.alias("probs")).to_df()
    del m, o, gnn
    gc.collect()
    return df.dropna(subset=["probs"]).reset_index(drop=True)   # only the Test domain gets predictions


def _positive_prob(v):
    if isinstance(v, (list, tuple)) or hasattr(v, "__len__") and not isinstance(v, str):
        return float(list(v)[-1])
    return float(v)


def run(S, source, links, *, log=print, use_rule_features=True) -> tuple[pd.DataFrame, dict]:
    feats = rule_features(S, source, links, log=log)
    preds = train_predict(S, source, feats, use_rule_features=use_rule_features, log=log)
    preds["prob"] = preds["probs"].map(_positive_prob)
    by_subject = preds.groupby("eid", as_index=False)["prob"].max()
    return by_subject, {"accounts_scored": len(preds), "subjects": len(by_subject), "account_probs": preds}
