"""Create a new, demo-owned source schema and load validated synthetic CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.check_oracle import read_fixture
from scripts._snowflake import OWNER_MARKER, connect, identifier, schema_comment

ROOT = Path(__file__).resolve().parents[1]


def typed_rows(sources: dict[str, list[dict[str, str]]]) -> dict[str, list[tuple]]:
    return {
        "DEPOTS": [
            (
                row["depot_id"], row["node_id"], row["is_open"].lower() == "true",
                int(row["stock_units"]),
            )
            for row in sources["depots"]
        ],
        "STORES": [(row["store_id"], row["node_id"]) for row in sources["stores"]],
        "ROADS": [
            (row["from_node_id"], row["to_node_id"], float(row["travel_minutes"]))
            for row in sources["roads"]
        ],
        "ORDERS": [
            (
                row["order_id"], row["store_id"], int(row["units"]),
                float(row["deadline_minutes"]),
            )
            for row in sources["orders"]
        ],
        "DEMO_STATE": [(int(sources["demo_state"][0]["revision"]),)],
    }


def load_fixture(connection: object, database: str, schema: str) -> None:
    database, schema = identifier(database), identifier(schema)
    sources = read_fixture()
    rows = typed_rows(sources)
    ddl = (ROOT / "sql/00_create_sources.sql").read_text(encoding="utf-8")
    ddl = ddl.replace("{{DATABASE}}", database).replace("{{SOURCE_SCHEMA}}", schema)
    with connection.cursor() as cursor:
        if schema_comment(cursor, database, schema) is not None:
            raise RuntimeError(
                f"{database}.{schema} already exists; refusing to replace even demo data"
            )
        for statement in ddl.split(";"):
            if statement.strip():
                cursor.execute(statement)
        if schema_comment(cursor, database, schema) != OWNER_MARKER:
            raise RuntimeError("New schema lacks the expected ownership marker")
        try:
            cursor.execute("BEGIN")
            for table, records in rows.items():
                placeholders = ", ".join(["%s"] * len(records[0]))
                cursor.executemany(
                    f"INSERT INTO {database}.{schema}.{table} VALUES ({placeholders})",
                    records,
                )
                cursor.execute(f"SELECT COUNT(*) FROM {database}.{schema}.{table}")
                if cursor.fetchone()[0] != len(records):
                    raise RuntimeError(f"{table}: inserted row count does not match fixture")
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
    print(f"Loaded five synthetic source tables in {database}.{schema}, revision 1.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", required=True, help="Existing local Snowflake connection name")
    parser.add_argument("--database", required=True, help="Existing dedicated database")
    parser.add_argument("--source-schema", default="DELIVERY_SOURCES")
    args = parser.parse_args()
    database, schema = identifier(args.database), identifier(args.source_schema)
    with connect(args.connection) as connection:
        load_fixture(connection, database, schema)


if __name__ == "__main__":
    main()
