"""Calibrate the Graham family-link classifier (P1 Eq. 3) — P3's "parameter inference" on the learning bus.

    python calibrate.py [--data data/sample] [--offline] [--with-gnn]

1. Features for family_pairs_train are computed IN THE MODEL (same rules as candidates), then
   p(link | feature matched?) = P(m|L) / (P(m|L) + P(m|not L))   (equal priors, Laplace-smoothed)
   is written to <data>/feature_probs.csv.
2. The model is rebuilt with those probabilities; for each link type the threshold T maximizing F1 on
   family_pairs_val is written to <data>/link_thresholds.json (Settings.load_overrides reads it).
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from config import Settings, offline_config
from model import augmentation, build_model
from model.contracts import read_dir
from model.load import FrameSource
from relationalai.semantics import Integer, String


def pair_features(model, o, origin):
    pr, fn, mt = o.Pair.ref(), String.ref(), Integer.ref()
    return model.where(pr.origin == origin, pr.feat(fn, mt)).select(
        pr.a.eid.alias("a_eid"), pr.b.eid.alias("b_eid"), pr.link_type.alias("link_type"),
        pr.label.alias("label"), fn.alias("feature"), mt.alias("matched")).to_df()


def pair_probs(model, o, origin):
    pr = o.Pair.ref()
    return model.where(pr.origin == origin).select(
        pr.a.eid.alias("a_eid"), pr.b.eid.alias("b_eid"), pr.link_type.alias("link_type"),
        pr.label.alias("label"), pr.prob.alias("prob")).to_df()


def feature_probabilities(feats: pd.DataFrame, alpha=1.0) -> pd.DataFrame:
    feats = feats.astype({"label": int, "matched": int})
    rows = []
    for (lt, fn), g in feats.groupby(["link_type", "feature"]):
        n_pos, n_neg = (g.label == 1).sum(), (g.label == 0).sum()
        for mt in (0, 1):
            pm_l = ((g.label == 1) & (g.matched == mt)).sum() + alpha
            pm_n = ((g.label == 0) & (g.matched == mt)).sum() + alpha
            a, b = pm_l / (n_pos + 2 * alpha), pm_n / (n_neg + 2 * alpha)
            rows.append({"link_type": lt, "feature": fn, "matched": mt, "p": float(np.clip(a / (a + b), 0.01, 0.99)),
                         "n_pos": int(n_pos), "n_neg": int(n_neg)})
    return pd.DataFrame(rows)


def best_thresholds(probs: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    probs = probs.astype({"label": int, "prob": float})
    out, report = {}, []
    for lt, g in probs.groupby("link_type"):
        best = (0.0, 0.9)
        for t in np.round(np.arange(0.50, 0.995, 0.01), 2):
            pred = g.prob > t
            tp = int((pred & (g.label == 1)).sum())
            prec = tp / max(int(pred.sum()), 1)
            rec = tp / max(int((g.label == 1).sum()), 1)
            f1 = 2 * prec * rec / max(prec + rec, 1e-9)
            report.append({"link_type": lt, "t": t, "precision": prec, "recall": rec, "f1": f1})
            if f1 > best[0]:
                best = (f1, float(t))
        out[lt] = best[1]
    return out, pd.DataFrame(report)


def gnn_feature_probabilities(scores: pd.DataFrame, val: pd.DataFrame, alpha=1.0) -> pd.DataFrame:
    """Graham rows for the `gnn` feature (pair in the GNN's top-k, either direction), calibrated on the
    validation pairs: the GNN trained on the train pairs, so they would be in-sample."""
    top = set(map(tuple, scores[["a_eid", "b_eid"]].values))
    feats = val.assign(feature="gnn", matched=[int((a, b) in top or (b, a) in top) for a, b in val[["a_eid", "b_eid"]].values])
    return feature_probabilities(feats[["link_type", "feature", "label", "matched"]], alpha)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/sample")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--with-gnn", dest="with_gnn", action="store_true",
                    help="train the GNN link model (Snowflake) and add its calibrated `gnn` feature")
    a = ap.parse_args()
    data = Path(a.data)
    t = read_dir(data)
    pairs = {"train": t["family_pairs_train"], "val": t["family_pairs_val"]}
    S = Settings()
    source = FrameSource.from_dir(data)
    cfg = offline_config() if a.offline else None

    m1, o1 = build_model(S, source, name="bo_aml_calibrate_1", stages=[], config=cfg)
    augmentation.register(m1, o1, S, pairs={"train": pairs["train"]}, candidates=False, score=False)
    fp = feature_probabilities(pair_features(m1, o1, "train"))
    fp.to_csv(data / "feature_probs.csv", index=False)
    print(fp.to_string(index=False))

    m2, o2 = build_model(S, source, name="bo_aml_calibrate_2", stages=[], config=cfg)
    augmentation.register(m2, o2, S, pairs={"val": pairs["val"]}, feature_probs=fp, candidates=False)
    thresholds, report = best_thresholds(pair_probs(m2, o2, "val"))
    (data / "link_thresholds.json").write_text(json.dumps(thresholds, indent=1))
    best = report.loc[report.groupby("link_type")["f1"].idxmax()]
    print("\nvalidation (best F1 per link type):\n" + best.to_string(index=False))

    if a.with_gnn:
        import gc

        from model import gnn_links

        del m1, o1, m2, o2          # the GNN library needs to be the only model in the process
        gc.collect()

        scores, rep = gnn_links.run(S, source)
        scores.to_csv(data / "gnn_link_scores.csv", index=False)
        g = gnn_feature_probabilities(scores, pairs["val"])
        pd.concat([fp, g], ignore_index=True).to_csv(data / "feature_probs.csv", index=False)
        print(f"\nGNN link model: {rep}\n" + g.to_string(index=False))



if __name__ == "__main__":
    main()
