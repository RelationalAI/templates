"""Shared fail-closed connection and ownership checks for demo source scripts."""

from __future__ import annotations

import re
from typing import Any

OWNER_MARKER = "rai-retail-delivery-agent-owned:1"
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError("Use an unquoted Snowflake identifier (letters, digits, underscore)")
    return value.upper()


def connect(profile: str) -> Any:
    from snowflake.connector import connect as snowflake_connect

    if not profile or profile.lower() == "default":
        raise ValueError("Pass an explicit Snowflake connector connection name")
    return snowflake_connect(connection_name=profile)


def schema_comment(cursor: Any, database: str, schema: str) -> str | None:
    database, schema = identifier(database), identifier(schema)
    cursor.execute(f"SHOW SCHEMAS IN DATABASE {database}")
    fields = [column[0].lower() for column in cursor.description]
    for raw in cursor.fetchall():
        row = dict(zip(fields, raw, strict=True))
        if str(row["name"]).upper() == schema:
            return str(row.get("comment") or "")
    return None


def require_owned_schema(cursor: Any, database: str, schema: str) -> None:
    if schema_comment(cursor, database, schema) != OWNER_MARKER:
        raise RuntimeError(
            f"{database}.{schema} is missing or lacks the demo ownership marker; "
            "no objects were changed"
        )
