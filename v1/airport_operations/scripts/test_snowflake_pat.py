#!/usr/bin/env python3
"""Smoke-test Snowflake PAT auth without using RelationalAI.

Loads SF_PAT from the repo-local .env file and uses snowflake-connector-python
directly. This helps separate Snowflake auth/account issues from RAI config
issues.

Usage:
    .venv/bin/python scripts/test_snowflake_pat.py
"""
from __future__ import annotations

import os
from pathlib import Path

import snowflake.connector
import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "raiconfig.yaml"
ENV_PATH = ROOT / ".env"


def _load_config() -> dict:
    with CONFIG_PATH.open() as fh:
        cfg = yaml.safe_load(fh)
    conn_name = cfg["default_connection"]
    return cfg["connections"][conn_name]


def main() -> int:
    load_dotenv(ENV_PATH)
    token = os.environ.get("SF_PAT")
    if not token:
        raise SystemExit("SF_PAT is not set in .env")

    cfg = _load_config()
    print("Snowflake PAT smoke test")
    print(f"  account:   {cfg['account']}")
    print(f"  user:      {cfg['user']}")
    print(f"  role:      {cfg.get('role', '')}")
    print(f"  warehouse: {cfg['warehouse']}")
    print(f"  token:     present ({len(token)} chars)")

    con = snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        authenticator="programmatic_access_token",
        token=token,
        role=cfg.get("role"),
        warehouse=cfg["warehouse"],
    )

    try:
        cur = con.cursor()
        try:
            cur.execute(
                """
                SELECT
                    CURRENT_ACCOUNT() AS account,
                    CURRENT_USER() AS user,
                    CURRENT_ROLE() AS role,
                    CURRENT_WAREHOUSE() AS warehouse
                """
            )
            row = cur.fetchone()
            print("\nConnected:")
            print(f"  account:   {row[0]}")
            print(f"  user:      {row[1]}")
            print(f"  role:      {row[2]}")
            print(f"  warehouse: {row[3]}")

            cur.execute(
                """
                SELECT table_name, row_count
                FROM ACDM_DEMO.INFORMATION_SCHEMA.TABLES
                WHERE table_schema = 'EHAM'
                ORDER BY table_name
                """
            )
            rows = cur.fetchall()
            print("\nACDM_DEMO.EHAM tables:")
            for table_name, row_count in rows:
                print(f"  {table_name}: {row_count}")

            cur.execute("SELECT COUNT(*) FROM ACDM_DEMO.EHAM.FLIGHT")
            flight_count = cur.fetchone()[0]
            print(f"\nACDM_DEMO.EHAM.FLIGHT count: {flight_count}")
        finally:
            cur.close()
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
