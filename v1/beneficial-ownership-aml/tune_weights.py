"""Tune rule weights on labeled STRs (P3: rule parameters inferred from data on the learning bus).

    python tune_weights.py [--data data/sample]

Findings (which rules fired, with what confidence) come from the model; only the weights are searched.
Coordinate search over w in {0.1, ..., 0.95} per rule, maximizing average precision on the earlier 80% of
STRs (by filing date); reports AP on the later 20% for default vs tuned weights. Writes
<data>/rule_catalog.tuned.csv; to use it, copy it over data/rule_catalog.csv after reviewing it.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
GRID = [0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 0.85, 0.95]


def average_precision(y, s):
    order = np.argsort(-np.asarray(s, dtype=float), kind="stable")
    y = np.asarray(y)[order]
    hits = np.cumsum(y)
    return float((hits / np.arange(1, len(y) + 1))[y == 1].mean()) if y.sum() else 0.0


def scores(findings: pd.DataFrame, weights: dict, str_ids) -> np.ndarray:
    f = findings.assign(wc=np.minimum(findings.confidence * findings.rule_id.map(weights), 0.999))
    agg = np.log1p(-f.wc).groupby(f.str_id).sum()
    return (1 - np.exp(pd.Series(str_ids).map(agg).fillna(0.0))).values


def tune(findings, labels, weights, rounds=3):
    w = dict(weights)
    for _ in range(rounds):
        for rule in sorted(findings.rule_id.unique()):
            best = max(GRID, key=lambda g: average_precision(labels.is_laundering, scores(findings, {**w, rule: g}, labels.str_id)))
            w[rule] = best
    return w


def main():
    import pipeline
    from config import Settings
    from model.contracts import read_dir
    from model.load import FrameSource

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/sample")
    a = ap.parse_args()
    data = ROOT / a.data
    S = Settings().with_calibration(data)
    r = pipeline.run(S, FrameSource.from_dir(data), gnn=False, triage=False, name="bo_aml_tune")
    m, o = r["model"], r["onto"]
    fd = o.Finding.ref()
    findings = m.select(fd.str.str_id.alias("str_id"), fd.rule_id.rule_id.alias("rule_id"),
                        fd.confidence.alias("confidence")).to_df().astype({"confidence": float})
    t = read_dir(data)
    labels = t["strs"][["str_id", "filed_on"]].merge(t["str_labels"], on="str_id").sort_values("filed_on")
    cut = int(0.8 * len(labels))
    train, test = labels.iloc[:cut], labels.iloc[cut:]
    catalog = pd.read_csv(ROOT / "data" / "rule_catalog.csv")
    default = dict(zip(catalog.rule_id, catalog.weight))
    tuned = tune(findings, train, default)
    for name, w in [("default", default), ("tuned", tuned)]:
        print(f"{name:8s} AP train {average_precision(train.is_laundering, scores(findings, w, train.str_id)):.3f}  "
              f"test {average_precision(test.is_laundering, scores(findings, w, test.str_id)):.3f}")
    out = catalog.assign(weight=catalog.rule_id.map(tuned).fillna(catalog.weight))
    out.to_csv(data / "rule_catalog.tuned.csv", index=False)
    print(out[["rule_id", "weight"]].merge(catalog[["rule_id", "weight"]], on="rule_id", suffixes=("_tuned", "_default")).to_string(index=False))


if __name__ == "__main__":
    main()
