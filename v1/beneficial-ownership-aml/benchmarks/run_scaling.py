"""Scale benchmark (Phase 11): generate, load to Snowflake, run the pipeline, record stage timings.

    python benchmarks/run_scaling.py --sizes 10000,100000 [--density normal] [--gnn]

Each size is loaded into BENEFICIAL_OWNERSHIP.BENCH_<size>_<density> and run with the default settings
(and the sample's calibration). Results append to benchmarks/out/scaling.csv. The design follows P1 §6 /
P2 §3 (runtime vs nodes and density) and P3 §3 (batch evaluation of all STRs).
"""

import argparse
import dataclasses
import gc
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pipeline  # noqa: E402
from config import Settings  # noqa: E402
from data.generator.generate import GenConfig, generate  # noqa: E402
from data.generator.snowflake_load import load_tables  # noqa: E402
from data.generator.stats import graph_stats  # noqa: E402
from model.load import TableSource  # noqa: E402

OUT = ROOT / "benchmarks" / "out"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="10000,100000")
    ap.add_argument("--density", default="normal")
    ap.add_argument("--gnn", action="store_true")
    ap.add_argument("--skip-load", dest="skip_load", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in [int(x) for x in a.sizes.split(",")]:
        schema = f"BENEFICIAL_OWNERSHIP.BENCH_{n}_{a.density.upper()}"
        t0 = time.time()
        cfg = GenConfig(seed=7, companies=n, persons=int(0.6 * n), density=a.density)
        if not a.skip_load:
            tables = generate(cfg)
            gen_s = time.time() - t0
            stats = graph_stats(tables) if n <= 200_000 else {}
            from relationalai.semantics import Model

            Model("bo_bench_mkschema").config.get_session().sql(f"CREATE SCHEMA IF NOT EXISTS {schema}").collect()
            gc.collect()
            t1 = time.time()
            load_tables(tables, schema)
            load_s = time.time() - t1
        else:
            gen_s = load_s = 0.0
            stats = {}
        gc.collect()
        S = dataclasses.replace(Settings.from_env().with_calibration(ROOT / "data" / "sample"), DATA_SCHEMA=schema)
        t2 = time.time()
        r = pipeline.run(S, TableSource(schema), gnn=a.gnn, name=f"bo_bench_{n}", log=print)
        row = {"companies": n, "persons": int(0.6 * n), "density": a.density, "generate_s": gen_s, "load_s": load_s,
               "pipeline_s": time.time() - t2, **{f"t_{k}": v for k, v in r["timings"].items()},
               **r["summary"], "predicted_links": len(r["links"]),
               "rounds": len(r["augmentation"]), "candidates_r1": r["augmentation"][0]["candidates"] if r["augmentation"] else 0,
               "triage_status": r["triage"]["plan"]["status"] if r["triage"] else None,
               **{f"graph_{k}": v for k, v in stats.items() if k in ("edges", "avg_degree", "largest_wcc", "largest_scc")}}
        rows.append(row)
        print(json.dumps(row, default=float, indent=1), flush=True)
        f = OUT / "scaling.csv"
        frame = pd.DataFrame([row])
        if f.exists():
            frame = pd.concat([pd.read_csv(f), frame], ignore_index=True)
        frame.to_csv(f, index=False)
        del r
        gc.collect()


if __name__ == "__main__":
    main()
