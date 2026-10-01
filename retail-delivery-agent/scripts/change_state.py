"""Change only North's availability and increment the source revision atomically."""

from __future__ import annotations

import argparse

from scripts._snowflake import connect, identifier, require_owned_schema


def change_state(connection: object, database: str, schema: str, *, close: bool) -> int:
    database, schema = identifier(database), identifier(schema)
    prefix = f"{database}.{schema}"
    with connection.cursor() as cursor:
        require_owned_schema(cursor, database, schema)
        cursor.execute(
            f"SELECT DEPOT_ID, IS_OPEN FROM {prefix}.DEPOTS WHERE DEPOT_ID = %s",
            ("North",),
        )
        depot_rows = cursor.fetchall()
        cursor.execute(f"SELECT REVISION FROM {prefix}.DEMO_STATE")
        revision_rows = cursor.fetchall()
        if len(depot_rows) != 1 or len(revision_rows) != 1:
            raise RuntimeError("Expected exactly North and one revision; no changes were made")
        if bool(depot_rows[0][1]) == (not close):
            raise RuntimeError("North is already in the requested state; no revision was changed")
        revision = int(revision_rows[0][0])
        try:
            cursor.execute("BEGIN")
            cursor.execute(
                f"UPDATE {prefix}.DEPOTS SET IS_OPEN = %s "
                "WHERE DEPOT_ID = %s AND IS_OPEN = %s",
                (not close, "North", close),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("North changed concurrently; refusing to advance revision")
            cursor.execute(
                f"UPDATE {prefix}.DEMO_STATE SET REVISION = REVISION + 1 "
                "WHERE REVISION = %s",
                (revision,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Revision changed concurrently; rolling back North update")
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
    return revision + 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["close", "reopen"])
    parser.add_argument("--connection", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--source-schema", default="DELIVERY_SOURCES")
    args = parser.parse_args()
    database, schema = identifier(args.database), identifier(args.source_schema)
    with connect(args.connection) as connection:
        revision = change_state(connection, database, schema, close=args.action == "close")
    print(f"North is now {'closed' if args.action == 'close' else 'open'}; revision {revision}.")


if __name__ == "__main__":
    main()
