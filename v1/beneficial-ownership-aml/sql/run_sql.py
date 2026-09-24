"""Run a .sql file statement by statement over the raiconfig.yaml Snowflake connection.

Usage:  python sql/run_sql.py sql/setup.sql
"""

import sys
from pathlib import Path

from relationalai.semantics import Model


def statements(text: str) -> list[str]:
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main(path: str) -> None:
    session = Model("bo_aml_sql").config.get_session()
    for stmt in statements(Path(path).read_text()):
        first_line = stmt.splitlines()[0]
        result = session.sql(stmt).collect()
        status = result[0][0] if result else "ok"
        print(f"{first_line}\n    -> {status}")


if __name__ == "__main__":
    main(sys.argv[1])
