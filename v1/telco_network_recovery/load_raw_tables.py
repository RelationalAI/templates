"""Load bundled telco CSVs into Snowflake source tables for deploy mode.

By default this is non-destructive: existing raw tables are left untouched.
Pass --replace to refresh the dedicated demo raw tables from the bundled CSVs.
"""

import argparse
from pathlib import Path

import pandas as pd
import snowflake.connector
import yaml
from snowflake.connector.pandas_tools import write_pandas

DATA_DIR = Path(__file__).parent / "data"
RAW_SCHEMA = "BERTOLANI.TELCO_NETWORK_RECOVERY_SOURCE"

CSV_TABLES = {
    "CELL_TOWERS": {
        "file": "cell_towers.csv",
        "datetimes": ["INSTALL_DATE"],
    },
    "NETWORK_EQUIPMENT": {
        "file": "network_equipment.csv",
        "datetimes": ["INSTALL_DATE"],
    },
    "EQUIPMENT_HEALTH": {
        "file": "equipment_health.csv",
        "datetimes": ["LAST_FAILURE_DATE", "MEASUREMENT_DATE"],
    },
    "MODEL_ADVISORIES": {
        "file": "model_advisories.csv",
        "datetimes": ["ISSUED_DATE"],
    },
    "NETWORK_PERFORMANCE": {
        "file": "network_performance.csv",
        "datetimes": ["TIMESTAMP"],
    },
    "SUBSCRIBERS": {
        "file": "subscribers.csv",
        "datetimes": ["SIGNUP_DATE"],
    },
    "CALL_DETAIL_RECORDS": {
        "file": "call_detail_records.csv",
        "datetimes": ["CALL_START_TIME"],
    },
    "TOWER_UPGRADE_OPTIONS": {
        "file": "tower_upgrade_options.csv",
        "datetimes": [],
    },
}

TABLE_DDL = {
    "CELL_TOWERS": [
        "TOWER_ID VARCHAR",
        "TOWER_NAME VARCHAR",
        "POSTAL_CODE NUMBER",
        "LATITUDE FLOAT",
        "LONGITUDE FLOAT",
        "TOWER_TYPE VARCHAR",
        "CAPACITY_GBPS NUMBER",
        "INSTALL_DATE VARCHAR",
        "STATUS VARCHAR",
        "REGION VARCHAR",
    ],
    "NETWORK_EQUIPMENT": [
        "EQUIPMENT_ID VARCHAR",
        "TOWER_ID VARCHAR",
        "EQUIPMENT_TYPE VARCHAR",
        "PART_ID VARCHAR",
        "MANUFACTURER VARCHAR",
        "MODEL VARCHAR",
        "SERIAL_NUMBER VARCHAR",
        "INSTALL_DATE VARCHAR",
        "FIRMWARE_VERSION VARCHAR",
        "STATUS VARCHAR",
    ],
    "EQUIPMENT_HEALTH": [
        "HEALTH_ID VARCHAR",
        "EQUIPMENT_ID VARCHAR",
        "MTBF_HOURS NUMBER",
        "FAILURE_RATE FLOAT",
        "LAST_FAILURE_DATE VARCHAR",
        "TEMPERATURE_AVG_C FLOAT",
        "POWER_CONSUMPTION_KW FLOAT",
        "HEALTH_SCORE FLOAT",
        "MEASUREMENT_DATE VARCHAR",
    ],
    "MODEL_ADVISORIES": [
        "MODEL VARCHAR",
        "ADVISORY_TYPE VARCHAR",
        "SEVERITY FLOAT",
        "ISSUED_DATE VARCHAR",
    ],
    "NETWORK_PERFORMANCE": [
        "METRIC_ID VARCHAR",
        "TOWER_ID VARCHAR",
        "TIMESTAMP VARCHAR",
        "LATENCY_MS FLOAT",
        "THROUGHPUT_MBPS FLOAT",
        "PACKET_LOSS_PCT FLOAT",
        "JITTER_MS FLOAT",
        "SIGNAL_STRENGTH_DBM NUMBER",
        "ACTIVE_CONNECTIONS NUMBER",
        "BANDWIDTH_UTILIZATION_PCT FLOAT",
        "ERROR_RATE FLOAT",
    ],
    "SUBSCRIBERS": [
        "SUB_ID VARCHAR",
        "FIRST_NAME VARCHAR",
        "LAST_NAME VARCHAR",
        "EMAIL VARCHAR",
        "PHONE VARCHAR",
        "POSTAL_CODE NUMBER",
        "SUBSCRIBER_TYPE VARCHAR",
        "SEGMENT VARCHAR",
        "SIGNUP_DATE VARCHAR",
        "LIFETIME_VALUE_USD FLOAT",
        "CHURN_RISK_SCORE FLOAT",
        "NPS_SCORE NUMBER",
        "STATUS VARCHAR",
    ],
    "CALL_DETAIL_RECORDS": [
        "CDR_ID VARCHAR",
        "CALLER_SUB_ID VARCHAR",
        "CALLEE_SUB_ID VARCHAR",
        "CALL_TYPE VARCHAR",
        "CALL_START_TIME VARCHAR",
        "CALL_DURATION_SECONDS NUMBER",
        "CALL_STATUS VARCHAR",
        "TOWER_ID VARCHAR",
        "DATA_USED_MB FLOAT",
        "CALL_QUALITY_SCORE FLOAT",
    ],
    "TOWER_UPGRADE_OPTIONS": [
        "TOWER_ID VARCHAR",
        "UPGRADE_TIER VARCHAR",
        "CAPACITY_INCREASE_GBPS NUMBER",
        "COST_USD NUMBER",
        "INSTALL_WEEKS NUMBER",
    ],
}


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


def read_csv(spec):
    df = pd.read_csv(DATA_DIR / spec["file"])
    for col in spec["datetimes"]:
        df[col] = df[col].astype(str)
    return df


def create_table(cur, database: str, schema: str, table_name: str):
    columns = ", ".join(TABLE_DDL[table_name])
    cur.execute(f"CREATE TABLE {database}.{schema}.{table_name} ({columns})")


def table_exists(cur, database: str, schema: str, table_name: str) -> bool:
    cur.execute(
        f"SHOW TABLES LIKE '{table_name}' IN SCHEMA {database}.{schema}"
    )
    return cur.fetchone() is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace existing raw demo tables before loading",
    )
    args = parser.parse_args()

    database, schema = RAW_SCHEMA.split(".", 1)
    conn = snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")

        for table_name, spec in CSV_TABLES.items():
            df = read_csv(spec)
            if table_exists(cur, database, schema, table_name):
                if not args.replace:
                    print(f"{RAW_SCHEMA}.{table_name}: exists, skipped")
                    continue
                cur.execute(f"DROP TABLE IF EXISTS {RAW_SCHEMA}.{table_name}")
            create_table(cur, database, schema, table_name)
            success, _chunks, rows, _ = write_pandas(
                conn,
                df,
                table_name=table_name,
                database=database,
                schema=schema,
                auto_create_table=False,
                overwrite=False,
                quote_identifiers=False,
            )
            if not success:
                raise RuntimeError(f"write_pandas failed for {table_name}")
            print(f"{RAW_SCHEMA}.{table_name}: {rows} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
