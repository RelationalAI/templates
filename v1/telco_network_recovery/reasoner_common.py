"""Shared utilities for standalone telco reasoner jobs."""

from pathlib import Path

import snowflake.connector
import yaml
from snowflake.connector.pandas_tools import write_pandas

DEPLOYED_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY"
RESULTS_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS"
EXP_DATABASE = "BERTOLANI"
EXP_SCHEMA = "TELCO_NETWORK_RECOVERY_EXPERIMENTS"


def table(name: str, schema: str = DEPLOYED_SCHEMA) -> str:
    return f"{schema}.{name}"


def snowflake_connection():
    cfg = yaml.safe_load(Path("raiconfig.yaml").read_text())
    conn_cfg = cfg["connections"]["sf"]
    token = Path(conn_cfg["token_file_path"]).read_text().strip()
    return snowflake.connector.connect(
        account=conn_cfg["account"],
        user=conn_cfg["user"],
        authenticator="programmatic_access_token",
        token=token,
        warehouse=conn_cfg["warehouse"],
        database=conn_cfg["database"],
        schema=conn_cfg["schema"],
        role=conn_cfg["role"],
    )


def ensure_results_schema():
    database, schema = RESULTS_SCHEMA.split(".", 1)
    conn = snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {RESULTS_SCHEMA}")
    finally:
        conn.close()


def replace_table(df, table_name: str):
    database, schema = RESULTS_SCHEMA.split(".", 1)
    df = df.reset_index(drop=True)
    conn = snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {RESULTS_SCHEMA}")
        cur.execute(f"DROP TABLE IF EXISTS {RESULTS_SCHEMA}.{table_name}")
        success, _chunks, rows, _ = write_pandas(
            conn,
            df,
            table_name=table_name,
            database=database,
            schema=schema,
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
        )
        if not success:
            raise RuntimeError(f"write_pandas failed for {RESULTS_SCHEMA}.{table_name}")
        print(f"{RESULTS_SCHEMA}.{table_name}: {rows} rows")
    finally:
        conn.close()
