#!/usr/bin/env python3
"""Inspect RAI reasoner/engine state through Snowflake SQL.

Uses the repo-local .env PAT and avoids the RAI CLI so status comes directly
from RELATIONALAI.API views/procedures.
"""
from __future__ import annotations

import os
from pathlib import Path

import snowflake.connector
import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> dict:
    with (ROOT / "raiconfig.yaml").open() as fh:
        config = yaml.safe_load(fh)
    return config["connections"][config["default_connection"]]


def _connect():
    load_dotenv(ROOT / ".env")
    token = os.environ.get("SF_PAT")
    if not token:
        raise SystemExit("SF_PAT is not set in .env")
    cfg = _cfg()
    return snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        authenticator="programmatic_access_token",
        token=token,
        role=cfg.get("role"),
        warehouse=cfg["warehouse"],
    )


def _print_rows(cur, sql: str) -> None:
    print(f"\nSQL> {sql}")
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for row in rows:
        print(" | ".join("" if v is None else str(v) for v in row))


def main() -> int:
    con = _connect()
    try:
        cur = con.cursor()
        try:
            _print_rows(
                cur,
                """
                SELECT table_name
                FROM RELATIONALAI.INFORMATION_SCHEMA.VIEWS
                WHERE table_schema = 'API'
                  AND table_name IN ('ENGINES', 'REASONERS', 'JOBS')
                ORDER BY table_name
                """,
            )
            for view in ("ENGINES", "REASONERS"):
                try:
                    _print_rows(
                        cur,
                        f"""
                        SELECT *
                        FROM RELATIONALAI.API.{view}
                        WHERE LOWER(name) LIKE 'acdm%'
                        ORDER BY name
                        """,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"\nRELATIONALAI.API.{view} unavailable: {exc}")

            for rtype, name in (
                ("logic", "acdm_logic_l"),
                ("prescriptive", "acdm_prescriptive_m"),
            ):
                try:
                    _print_rows(
                        cur,
                        f"CALL RELATIONALAI.API.GET_REASONER('{rtype}', '{name}')",
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"\nGET_REASONER({rtype}, {name}) failed: {exc}")
        finally:
            cur.close()
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
