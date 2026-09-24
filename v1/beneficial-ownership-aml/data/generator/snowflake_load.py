"""Load contract tables into Snowflake (DB.SCHEMA) and grant the RAI app read access.

    python -m data.generator.snowflake_load data/sample BENEFICIAL_OWNERSHIP.DATA

Column names are upper-cased so they need no quoting in SQL; PyRel matches them case-insensitively.
Evaluation-only tables are loaded too (the Snowflake reference runner reads them for metrics),
but the model loaders never read them.
"""

import sys
import time

import pandas as pd
from model.contracts import CONTRACTS, read_dir


def _typed(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = df.copy()
    for col, t in CONTRACTS[name].items():
        if t == "date":  # the model stores calendar dates as ISO strings (no date arithmetic needed)
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d")
        elif t == "datetime":
            out[col] = pd.to_datetime(out[col])
        elif t == "float":
            out[col] = out[col].astype(float)
    out.columns = [c.upper() for c in out.columns]
    return out


def load_tables(tables: dict[str, pd.DataFrame], db_schema: str) -> None:
    from relationalai.semantics import Model

    db, schema = db_schema.split(".")
    session = Model("bo_aml_loader").config.get_session()
    for name, df in tables.items():
        for attempt in range(1, 6):   # stage uploads fail intermittently (S3 403s, connector PUT parse
            try:                      # errors); overwrite=True makes a retry safe
                session.write_pandas(_typed(df, name), name.upper(), database=db, schema=schema,
                                     auto_create_table=True, overwrite=True, use_logical_type=True)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 5:
                    raise
                print(f"retrying {name} after {type(e).__name__}: {str(e)[:120]}")
                time.sleep(15 * attempt)
        print(f"loaded {db_schema}.{name.upper()} ({len(df)} rows)")
    # FUTURE grants to an application are not allowed, so grant after every load.
    session.sql(f"GRANT SELECT ON ALL TABLES IN SCHEMA {db_schema} TO APPLICATION RELATIONALAI").collect()
    for name in tables:
        session.sql(f"ALTER TABLE {db_schema}.{name.upper()} SET CHANGE_TRACKING = TRUE").collect()
    print(f"granted SELECT on {db_schema} to RELATIONALAI and enabled change tracking")


if __name__ == "__main__":
    load_tables(read_dir(sys.argv[1]), sys.argv[2])
