"""Beneficial Ownership & Control for AML — primary runner on the bundled sample (data/sample).

    python beneficial_ownership_local.py                 # full pipeline: rules, graph, GNNs, MILP (Snowflake)
    python beneficial_ownership_local.py --no-gnn        # skip the two GNN stages (fastest full run)
    python beneficial_ownership_local.py --case S:12     # also explain one STR in detail
    python beneficial_ownership_local.py --offline       # DuckDB, rules only (slow; see README)

Settings come from config.py (override with environment variables, e.g. AUDIT_HOURS=200) and the
calibration files in data/sample (feature_probs.csv, link_thresholds.json from calibrate.py).
"""

import argparse
import json
from pathlib import Path

import pipeline
from config import Settings
from model.explain import explain, render_text
from model.load import FrameSource

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "eval" / "out"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/sample")
    ap.add_argument("--offline", action="store_true", help="local DuckDB, rules only")
    ap.add_argument("--no-gnn", dest="gnn", action="store_false")
    ap.add_argument("--no-triage", dest="triage", action="store_false")
    ap.add_argument("--case", help="STR id to explain, e.g. S:12")
    ap.add_argument("--budgets", default="", help="comma-separated analyst-hour budgets for a sweep, e.g. 100,200,400")
    a = ap.parse_args()

    S = Settings.from_env().with_calibration(ROOT / a.data)
    source = FrameSource.from_dir(ROOT / a.data)
    budgets = [float(b) for b in a.budgets.split(",") if b]
    r = pipeline.run(S, source, offline=a.offline, gnn=a.gnn, triage=a.triage, budgets=budgets)

    print("\n" + "=" * 100)
    print(pipeline.headline(r))
    print("=" * 100)

    OUT.mkdir(parents=True, exist_ok=True)
    r["strs"].sort_values("score", ascending=False).to_csv(OUT / "str_scores.csv", index=False)
    r["links"].to_csv(OUT / "predicted_links.csv", index=False)
    if r["triage"]:
        (OUT / "triage.json").write_text(json.dumps({k: v for k, v in r["triage"].items()}, indent=1, default=float))

    top = r["strs"].sort_values("score", ascending=False)
    case_id = a.case or (top.str_id.iloc[0] if len(top) else None)
    if case_id:
        print(f"\nExplanation for {case_id}" + ("" if a.case else " (highest-scoring STR)") + ":")
        print(render_text(explain(r["model"], r["onto"], case_id)))


if __name__ == "__main__":
    main()
