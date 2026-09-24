"""Beneficial Ownership & Control for AML — reference runner on Snowflake tables.

    python beneficial_ownership.py                     # reads Settings.DATA_SCHEMA (default BENEFICIAL_OWNERSHIP.DATA)
    DATA_SCHEMA=MYDB.AML python beneficial_ownership.py --no-gnn

Tables follow data/SCHEMA.md. Results are written back to the same schema:
  AUGMENTED_LINKS  predicted family links (a_eid, b_eid, link_type, confidence, round)
  STR_SCORES       str_id, case id, suspicion score, offence
  FINDINGS         str_id, rule_id, confidence
  CASE_PLAN        chosen cases and the naive baseline for the analyst-hours budget
Calibration (feature_probs.csv, link_thresholds.json) is read from --calibration (default data/sample).
"""

import argparse
from pathlib import Path

import pipeline
from config import Settings
from model.load import TableSource

ROOT = Path(__file__).resolve().parent


def export(r, schema: str):
    m, o = r["model"], r["onto"]
    fd = o.Finding.ref()
    m.select(fd.str.str_id.alias("STR_ID"), fd.rule_id.rule_id.alias("RULE_ID"),
             fd.confidence.alias("CONFIDENCE")).into(m.Table(f"{schema}.FINDINGS")).exec()
    s = o.STR.ref()
    m.select(s.str_id.alias("STR_ID"), s.case.cid.alias("CASE_ID"), s.score.alias("SCORE"),
             s.offence.alias("OFFENCE")).into(m.Table(f"{schema}.STR_SCORES")).exec()
    session = m.config.get_session()
    db, sch = schema.split(".")
    links = r["links"].rename(columns=str.upper)
    if len(links):
        session.write_pandas(links, "AUGMENTED_LINKS", database=db, schema=sch, auto_create_table=True, overwrite=True)
    if r["triage"]:
        plan = r["triage"]["plan"]
        cases = r["cases"].assign(CHOSEN=r["cases"].cid.isin(plan["chosen"]),
                                  NAIVE=r["cases"].cid.isin(r["triage"]["naive"]["cases_opened"]))
        session.write_pandas(cases.rename(columns=str.upper), "CASE_PLAN", database=db, schema=sch,
                             auto_create_table=True, overwrite=True)
    print(f"exported FINDINGS, STR_SCORES, AUGMENTED_LINKS, CASE_PLAN to {schema}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", default="data/sample")
    ap.add_argument("--no-gnn", dest="gnn", action="store_false")
    ap.add_argument("--no-export", dest="export", action="store_false")
    a = ap.parse_args()
    S = Settings.from_env().with_calibration(ROOT / a.calibration)
    r = pipeline.run(S, TableSource(S.DATA_SCHEMA), gnn=a.gnn, name="bo_aml_reference")
    print(pipeline.headline(r))
    if a.export:
        export(r, S.DATA_SCHEMA)


if __name__ == "__main__":
    main()
