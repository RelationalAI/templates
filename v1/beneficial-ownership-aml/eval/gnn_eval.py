"""Learning-bus ablation (P3: deduction + induction together; P4: GCN on SAR labels). Snowflake only.

    python -m eval.gnn_eval

Test set = STRs filed in the last 20% of the period (the account GNN trained on earlier ones).
  (a) GNN, raw account attributes only           -> STR score = max account probability of the subject
  (b) GNN + rule features (learning bus: rules -> GNN)
  (c) rules only                                  -> STR.score without the GNN finding
  (d) rules + GNN finding (learning bus: GNN -> rules)
Metrics: ROC-AUC and precision@k on test STRs. Writes eval/out/account_ablation.csv.
"""

import gc
from pathlib import Path

import numpy as np
import pandas as pd
from config import Settings
from model.contracts import read_dir
from model.load import FrameSource

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "out"


def roc_auc(y, s) -> float:
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    ranks = pd.Series(np.concatenate([pos, neg])).rank().values
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def precision_at(y, s, k):
    order = np.argsort(-np.asarray(s, dtype=float))[:k]
    return float(np.asarray(y)[order].mean())


def main(data="data/sample", k=20):
    import pipeline
    from model import gnn_accounts

    OUT.mkdir(parents=True, exist_ok=True)
    S = Settings().with_calibration(ROOT / data)
    source = FrameSource.from_dir(ROOT / data)
    t = read_dir(ROOT / data)
    strs = t["strs"].merge(t["str_labels"], on="str_id")
    cut = strs.filed_on.sort_values().iloc[int(0.8 * len(strs))]
    test = strs[strs.filed_on >= cut]
    links = pd.read_csv(OUT / "predicted_links.csv") if (OUT / "predicted_links.csv").exists() else None

    rows = []
    feats = gnn_accounts.rule_features(S, source, links)
    for label, use_rules in [("(a) GNN, raw attributes", False), ("(b) GNN + rule features", True)]:
        preds = gnn_accounts.train_predict(S, source, feats, use_rule_features=use_rules)
        preds["prob"] = preds["probs"].map(gnn_accounts._positive_prob)
        subj = preds.groupby("eid")["prob"].max()
        sc = test.subject_eid.map(subj).fillna(0.0)
        rows.append({"model": label, "roc_auc": roc_auc(test.is_laundering, sc),
                     f"precision@{k}": precision_at(test.is_laundering, sc, k)})
        if use_rules:
            gnn_probs = subj.reset_index().rename(columns={"prob": "prob"})
        print(rows[-1], flush=True)
        gc.collect()

    for label, probs in [("(c) rules only", None), ("(d) rules + GNN finding", gnn_probs)]:
        r = pipeline.run(S, source, gnn=False, triage=False, log=lambda *_: None, name="bo_aml_gnn_eval")
        if probs is not None:
            from model import build_model

            m, o = build_model(S, source, extra_links=r["links"], name="bo_aml_gnn_eval_d", gnn_account_probs=probs)
            from model.optimize import str_table
            r["strs"] = str_table(m, o)
        d = test.merge(r["strs"][["str_id", "score"]], on="str_id")
        rows.append({"model": label, "roc_auc": roc_auc(d.is_laundering, d.score),
                     f"precision@{k}": precision_at(d.is_laundering, d.score, k)})
        print(rows[-1], flush=True)
        del r
        gc.collect()
    out = pd.DataFrame(rows).assign(test_strs=len(test), positives=int(test.is_laundering.sum()))
    out.to_csv(OUT / "account_ablation.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
