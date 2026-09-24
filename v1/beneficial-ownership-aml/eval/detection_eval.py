"""Detection metrics against the planted ground truth (str_labels is evaluation-only, never modelled).

    python -m eval.detection_eval [--no-gnn]     # full pipeline + ablation without predicted links
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from config import Settings
from model.contracts import read_dir
from model.load import FrameSource

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "out"


def metrics(strs: pd.DataFrame, labels: pd.DataFrame, k=50) -> dict:
    d = strs.merge(labels, on="str_id")
    d = d.sort_values("score", ascending=False)
    pos = d.is_laundering == 1
    ubo = d.offence_y == "SELF_LENDING"
    top = d.head(k)
    hi = d[d.score >= 0.8]
    return {
        "strs": len(d), "positives": int(pos.sum()),
        f"precision@{k}": float(top.is_laundering.mean()),
        "high_count": len(hi),
        "precision@0.8": float(hi.is_laundering.mean()) if len(hi) else 0.0,
        "recall@0.8": float((hi.is_laundering == 1).sum() / max(pos.sum(), 1)),
        "recall@0.5": float(((d.score >= 0.5) & pos).sum() / max(pos.sum(), 1)),
        "ubo_loan_recall@0.8": float(((d.score >= 0.8) & ubo).sum() / max(ubo.sum(), 1)),
        "offence_accuracy_on_positives": float((d[pos].offence_x == d[pos].offence_y).mean()),
    }


def main():
    import pipeline

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gnn", action="store_true")
    ap.add_argument("--data", default="data/sample")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    S = Settings().with_calibration(ROOT / a.data)
    source = FrameSource.from_dir(ROOT / a.data)
    labels = read_dir(ROOT / a.data)["str_labels"]
    res = {}
    for label, kw in [("with predicted links", {}), ("without predicted links (ablation)", {"augment_links": False})]:
        r = pipeline.run(S, source, gnn=not a.no_gnn, triage=False, log=lambda *_: None,
                         name=f"bo_aml_eval_{'aug' if not kw else 'noaug'}", **kw)
        res[label] = metrics(r["strs"], labels)
        print(label, json.dumps(res[label], indent=1), flush=True)
    (OUT / "detection.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
