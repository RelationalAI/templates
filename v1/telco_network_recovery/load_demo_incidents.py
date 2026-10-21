"""Load demo-only incidents without changing the baseline telco source or solve."""

from pathlib import Path

import pandas as pd

from reasoner_common import DEPLOYED_SCHEMA, RESULTS_SCHEMA, replace_table, snowflake_connection

INPUT = Path(__file__).resolve().parent / "data" / "demo_incidents.csv"
TABLE_NAME = "DEMO_INCIDENT_INPUT"
REQUIRED = {"INCIDENT_ID", "TOWER_ID", "INCIDENT_TYPE", "SEVERITY", "STATE", "OPENED_AT"}


def load_fixture(path: Path = INPUT) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if set(df.columns) != REQUIRED:
        raise ValueError(f"Expected columns {sorted(REQUIRED)}, got {sorted(df.columns)}")
    if df.empty or df.INCIDENT_ID.duplicated().any():
        raise ValueError("Incident IDs must be nonempty and unique")
    if not df.TOWER_ID.str.fullmatch(r"TWR-\d{4}").all():
        raise ValueError("Every incident must reference a tower ID")
    if not df.STATE.isin(["OPEN", "RESOLVED"]).all():
        raise ValueError("STATE must be OPEN or RESOLVED")
    if not df.SEVERITY.isin(["CRITICAL", "HIGH", "MEDIUM", "LOW"]).all():
        raise ValueError("Invalid severity")
    if not df.apply(lambda row: all(str(value).strip() for value in row), axis=1).all():
        raise ValueError("Incident fields must be nonempty")
    pd.to_datetime(df.OPENED_AT, errors="raise")
    return df


def validate_references(df: pd.DataFrame) -> None:
    conn = snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT ID FROM {DEPLOYED_SCHEMA}.CELLTOWER")
        towers = {row[0] for row in cur.fetchall()}
        cur.execute(f"SELECT TOWER_ID FROM {RESULTS_SCHEMA}.TOWER_FAILURE_SCORE")
        scored = {row[0] for row in cur.fetchall()}
        cur.execute(f"SELECT TOWER_ID FROM {RESULTS_SCHEMA}.TOWER_CUSTOMER_IMPACT")
        impacted = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    requested = set(df.TOWER_ID)
    for label, available in [("CELLTOWER", towers), ("TOWER_FAILURE_SCORE", scored), ("TOWER_CUSTOMER_IMPACT", impacted)]:
        missing = requested - available
        if missing:
            raise ValueError(f"Fixture towers missing from {label}: {sorted(missing)}")


def main() -> None:
    df = load_fixture()
    validate_references(df)
    replace_table(df, TABLE_NAME)
    conn = snowflake_connection()
    try:
        conn.cursor().execute(
            f"ALTER TABLE {RESULTS_SCHEMA}.{TABLE_NAME} SET CHANGE_TRACKING = TRUE"
        )
    finally:
        conn.close()
    print(f"Loaded {len(df)} synthetic incidents ({(df.STATE == 'OPEN').sum()} open).")


if __name__ == "__main__":
    main()
