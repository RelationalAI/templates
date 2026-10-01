"""Remove only the exact, marked five-table demo source schema on explicit request."""

from __future__ import annotations

import argparse

from scripts._snowflake import connect, identifier, require_owned_schema

EXPECTED = {"DEPOTS", "STORES", "ROADS", "ORDERS", "DEMO_STATE"}


def teardown(connection: object, database: str, schema: str, confirmation: str) -> None:
    database, schema = identifier(database), identifier(schema)
    target = f"{database}.{schema}"
    if confirmation != target:
        raise ValueError(f"Type the exact target {target} to confirm")
    with connection.cursor() as cursor:
        require_owned_schema(cursor, database, schema)
        cursor.execute(f"SHOW OBJECTS IN SCHEMA {target}")
        names = {
            str(row[[col[0].lower() for col in cursor.description].index("name")]).upper()
            for row in cursor.fetchall()
        }
        if names != EXPECTED:
            raise RuntimeError(
                f"Schema has unexpected objects {sorted(names ^ EXPECTED)}; no drop performed"
            )
        cursor.execute(f"DROP SCHEMA {target} RESTRICT")
    print(f"Removed only marked source schema {target}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--source-schema", default="DELIVERY_SOURCES")
    parser.add_argument("--confirm", required=True, help="Exact DATABASE.SCHEMA")
    args = parser.parse_args()
    with connect(args.connection) as connection:
        teardown(
            connection, identifier(args.database), identifier(args.source_schema),
            args.confirm,
        )


if __name__ == "__main__":
    main()
