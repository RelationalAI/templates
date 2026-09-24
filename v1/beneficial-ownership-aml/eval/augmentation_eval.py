"""Evaluate VADA-LINK augmentation against the hidden family links (P1 §6.2 protocol).

    python -m eval.augmentation_eval                      # default settings, full augmentation loop
    python -m eval.augmentation_eval --sweep              # blocking sweep -> eval/out/recall_vs_blocks.csv

recall     = |predicted ∩ hidden| / |hidden|        (links removed from the registry, to be recovered)
precision  = predicted links that are true kin (any type) / predicted
Also reported: typed recall (right link type), candidates, blocks, seconds.
"""

import argparse
import dataclasses
import time
from pathlib import Path

import pandas as pd
from config import Settings
from model.augmentation import augment
from model.contracts import read_dir
from model.load import FrameSource

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "out"


def score_links(pred: pd.DataFrame, tables) -> dict:
    und = lambda a, b: frozenset((a, b))  # noqa: E731
    hidden = {und(a, b): t for a, b, t in tables["family_links_hidden"][["a_eid", "b_eid", "link_type"]].values}
    # true kin = same generated family (read from all true links: known + hidden)
    kin = set(hidden)
    for a, b in tables["family_links_known"][["a_eid", "b_eid"]].values:
        kin.add(und(a, b))
    pred_pairs = {und(a, b): lt for a, b, lt in pred[["a_eid", "b_eid", "link_type"]].values} if len(pred) else {}
    found = [p for p in pred_pairs if p in hidden]
    typed = [p for p in found if pred_pairs[p] == hidden[p]]
    true_pred = [p for p in pred_pairs if p in kin]
    return {
        "hidden": len(hidden), "predicted": len(pred_pairs),
        "recall": len(found) / max(len(hidden), 1),
        "typed_recall": len(typed) / max(len(hidden), 1),
        "precision": len(true_pred) / max(len(pred_pairs), 1),
    }


def run(S, data="data/sample", log=print, gnn_scores=None):
    tables = read_dir(ROOT / data)
    source = FrameSource.from_dir(ROOT / data)
    t0 = time.time()
    links, history = augment(S, source, log=log, gnn_scores=gnn_scores)
    res = score_links(links, tables)
    res.update(seconds=round(time.time() - t0, 1), rounds=len(history),
               candidates=history[0]["candidates"], blocks=history[0]["blocks"], max_block=history[0]["max_block"])
    return res, links, history


SWEEP = [
    # (label, BLOCKING_L1, PARTNER_OF keys, SIBLING_OF keys) — increasing selectivity of level 2
    ("L1 none, coarse", "none", ("province",), ("surname3",)),
    ("L1 none, medium", "none", ("province", "birth_decade"), ("surname3", "birth_city")),
    ("L1 louvain, none", "louvain_projection", (), ()),
    ("L1 louvain, coarse (default)", "louvain_projection", ("province",), ("surname3",)),
    ("L1 louvain, medium", "louvain_projection", ("province",), ("surname3", "birth_city")),
    ("L1 louvain, fine", "louvain_projection", ("province", "birth_decade"), ("surname3", "birth_city", "birth_decade")),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--data", default="data/sample")
    ap.add_argument("--gnn-ablation", dest="gnn_ablation", action="store_true",
                    help="Bayes-only vs Bayes+GNN feature (needs <data>/gnn_link_scores.csv from calibrate.py --with-gnn)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    base = Settings().with_calibration(ROOT / a.data)
    if a.gnn_ablation:
        scores = pd.read_csv(ROOT / a.data / "gnn_link_scores.csv")
        rows = []
        for label, g, cand in [("Graham, registry features only", None, False),
                               ("Graham + GNN top-k feature (default)", scores, False),
                               ("Graham + GNN feature + GNN top-k as candidates", scores, True)]:
            S = dataclasses.replace(base, GNN_CANDIDATES=cand)
            res, _, _ = run(S, a.data, log=lambda *_: None, gnn_scores=g)
            rows.append({"model": label, **res})
            print(rows[-1], flush=True)
        pd.DataFrame(rows).to_csv(OUT / "link_ablation.csv", index=False)
        return
    if not a.sweep:
        res, links, history = run(base, a.data)
        print(res)
        links.to_csv(OUT / "predicted_links.csv", index=False)
        pd.DataFrame(history).to_csv(OUT / "augmentation_rounds.csv", index=False)
        return
    rows = []
    for label, l1, pk, sk in SWEEP:
        S = dataclasses.replace(base, BLOCKING_L1=l1, BLOCK_KEYS={"PARTNER_OF": pk, "SIBLING_OF": sk}, MAX_ROUNDS=1)
        res, _, _ = run(S, a.data, log=lambda *_: None)
        rows.append({"config": label, **res})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "recall_vs_blocks.csv", index=False)


if __name__ == "__main__":
    main()
