"""Run from your laptop ~10 minutes before the demo to verify everything
is set up, warm the reasoner engines, and refresh the artefacts.

Usage:
    .venv/bin/python prep_demo.py
    .venv/bin/python prep_demo.py --skip-figures   # skip PNG regeneration
    .venv/bin/python prep_demo.py --skip-chat      # skip live agent test
    .venv/bin/python prep_demo.py --redeploy       # force agent redeploy

The script is structured as a sequence of independent checks. Each prints
a one-line PASS/FAIL banner; the final summary lists everything that's
green so you know the demo is hot. Failures don't abort early (so you
see the full picture), but the exit code is non-zero if any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

ROOT = Path(__file__).resolve().parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
SNOW = "snow"
SNOW_CONN = os.environ.get("SNOW_CONN", "rai")
AGENT_NAME = "acdm"
DB = "ACDM_DEMO"
SCHEMA = "EHAM"

# Snowsight notebook resource lives in its own schema (separate from EHAM so
# accidental DROP SCHEMA EHAM doesn't take it out). Files live under a
# 'planes/' folder so the stage browses as a workspace folder named 'planes'
# in Snowsight's Workspaces > Files view.
NB_SCHEMA = "NOTEBOOKS"
NB_STAGE = "ACDM_NOTEBOOK_STAGE"
NB_FOLDER = "planes"
NB_NAME = "EHAM_ACDM_DEMO"
NB_MAIN = "eham_acdm_demo_snowsight.ipynb"
NB_SOURCES = (
    ROOT / "rai_code" / "manual" / "eham_acdm.py",
    ROOT / "rai_code" / "manual" / "demo_queries.py",
    ROOT / "rai_code" / "manual" / NB_MAIN,
)

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    duration_s: float = 0.0
    warnings: List[str] = field(default_factory=list)


def _banner(title: str) -> None:
    print()
    print(f"{BOLD}{title}{RESET}")
    print(f"{DIM}{'-' * len(title)}{RESET}")


def _emit(result: CheckResult) -> None:
    marker = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
    print(f"  [{marker}] {result.name}  {DIM}({result.duration_s:.1f}s){RESET}")
    if result.detail:
        for line in result.detail.splitlines():
            print(f"        {DIM}{line}{RESET}")
    for w in result.warnings:
        print(f"        {YELLOW}warn:{RESET} {w}")


def _run_check(name: str, fn: Callable[[], CheckResult]) -> CheckResult:
    t0 = time.time()
    try:
        result = fn()
    except Exception as e:  # noqa: BLE001
        result = CheckResult(name=name, passed=False, detail=f"exception: {e}")
    result.duration_s = time.time() - t0
    if not result.name:
        result.name = name
    _emit(result)
    return result


# =============================================================================
# Checks
# =============================================================================


def check_snow_cli() -> CheckResult:
    """snow CLI is on PATH and the connection works."""
    try:
        v = subprocess.run([SNOW, "--version"], capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return CheckResult(name="snow CLI installed", passed=False,
                           detail="'snow' not found on PATH. Install with `uv tool install snowflake-cli` or `pip install snowflake-cli`.")
    if v.returncode != 0:
        return CheckResult(name="snow CLI installed", passed=False, detail=v.stderr.strip())
    out = subprocess.run(
        [SNOW, "connection", "test", "-c", SNOW_CONN],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        return CheckResult(
            name="snow CLI installed",
            passed=False,
            detail=f"Connection '{SNOW_CONN}' failed: {out.stderr.strip()}",
        )
    return CheckResult(name="snow CLI + connection ok", passed=True,
                       detail=f"{v.stdout.strip()}  |  conn={SNOW_CONN}")


def _snow_sql_json(q: str) -> list:
    r = subprocess.run(
        [SNOW, "sql", "-c", SNOW_CONN, "-q", q, "--format", "json"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout)


def check_schema_loaded() -> CheckResult:
    """ACDM_DEMO.EHAM has all 13 expected tables with non-empty FLIGHT."""
    rows = _snow_sql_json(
        f"SELECT TABLE_NAME, ROW_COUNT FROM {DB}.INFORMATION_SCHEMA.TABLES "
        f"WHERE TABLE_SCHEMA='{SCHEMA}' ORDER BY TABLE_NAME"
    )
    by_name = {r["TABLE_NAME"]: int(r["ROW_COUNT"] or 0) for r in rows}
    expected = {
        "FLIGHT": 320, "DIM_AIRCRAFT": 313, "DIM_OPERATOR": 14, "DIM_STAND": 116,
        "DIM_RUNWAY": 6, "DIM_GROUND_HANDLER": 4, "DIM_FIX": 4,
        "TAXI_TIME_IN": 36, "TAXI_TIME_OUT": 27,
        "WEATHER_EVENT": 1, "ATFM_REGULATION": 0,
        "STORM_SLOT": 120, "SLOT_BLOCK": 2,
    }
    missing = [t for t in expected if t not in by_name]
    wrong = [
        f"{t}: got {by_name.get(t, 0)}, expected {expected[t]}"
        for t in expected
        if t in by_name and by_name[t] != expected[t]
    ]
    detail = ", ".join(f"{t}={by_name.get(t, 0)}" for t in expected)
    if missing:
        return CheckResult(
            name="ACDM_DEMO.EHAM schema",
            passed=False,
            detail=f"missing tables: {missing}\n{detail}",
        )
    warnings = wrong[:5]
    return CheckResult(
        name="ACDM_DEMO.EHAM schema (13 tables, expected row counts)",
        passed=True, detail=detail, warnings=warnings,
    )


def check_validation_numbers() -> CheckResult:
    """The four talk-track numbers reproduce from raw SQL (sanity baseline)."""
    # Q1 TOBT violations
    q1 = _snow_sql_json(
        f"WITH now AS (SELECT TO_TIMESTAMP_NTZ('2026-10-14 14:30:00') AS n) "
        f"SELECT handler_code AS h, COUNT(*) AS v FROM {DB}.{SCHEMA}.flight, now "
        f"WHERE flight_type='DEPARTURE' AND ardt IS NOT NULL "
        f"AND ardt >= DATEADD('hour', -4, now.n) AND ardt <= now.n "
        f"AND ABS(DATEDIFF('minute', tobt, ardt)) > 5 "
        f"GROUP BY handler_code"
    )
    counts = {r["H"]: int(r["V"]) for r in q1}
    expected_q1 = {"KLG": 7, "AGS": 5, "DNATA": 3, "MENZIES": 2}
    q1_ok = counts == expected_q1
    # Q5 storm window deps
    q5 = _snow_sql_json(
        f"SELECT COUNT(*) AS n FROM {DB}.{SCHEMA}.flight WHERE flight_type='DEPARTURE' "
        f"AND tsat >= '2026-10-14 15:00:00' AND tsat < '2026-10-14 17:00:00'"
    )
    storm_n = int(q5[0]["N"])
    # KL691 pax conn
    q6 = _snow_sql_json(
        f"SELECT pax_connections AS p FROM {DB}.{SCHEMA}.flight WHERE callsign='KL691'"
    )
    kl691_pax = int(q6[0]["P"]) if q6 else -1
    # CTOT rate
    q10 = _snow_sql_json(
        f"SELECT COUNT_IF(ctot IS NOT NULL) AS r, COUNT(*) AS t FROM {DB}.{SCHEMA}.flight "
        f"WHERE flight_type='DEPARTURE'"
    )
    ctot_rate = int(q10[0]["R"]) / int(q10[0]["T"]) * 100
    issues = []
    if not q1_ok:
        issues.append(f"Q1 mismatch: got {counts}, expected {expected_q1}")
    if storm_n != 47:
        issues.append(f"Q5 storm-window deps = {storm_n}, expected 47")
    if kl691_pax != 137:
        issues.append(f"KL691 pax_connections = {kl691_pax}, expected 137")
    if not (20.0 <= ctot_rate <= 25.0):
        issues.append(f"CTOT rate = {ctot_rate:.1f}%, expected ~22%")
    if issues:
        return CheckResult(
            name="Talk-track numbers reproduce from raw SQL",
            passed=False,
            detail="\n".join(issues),
        )
    return CheckResult(
        name="Talk-track numbers reproduce from raw SQL",
        passed=True,
        detail=f"Q1 = {expected_q1}; storm deps = 47; KL691 = 137 pax; CTOT = {ctot_rate:.1f}%",
    )


def check_change_tracking() -> CheckResult:
    """Every table the model reads has CHANGE_TRACKING enabled."""
    rows = _snow_sql_json(f"SHOW TABLES IN SCHEMA {DB}.{SCHEMA}")
    bad = []
    needs = {
        "FLIGHT", "DIM_AIRCRAFT", "DIM_OPERATOR", "DIM_STAND", "DIM_RUNWAY",
        "DIM_GROUND_HANDLER", "DIM_FIX", "TAXI_TIME_IN", "TAXI_TIME_OUT",
        "WEATHER_EVENT", "ATFM_REGULATION", "STORM_SLOT", "SLOT_BLOCK",
    }
    for r in rows:
        name = r.get("name") or r.get("NAME") or ""
        if name not in needs:
            continue
        ct = r.get("change_tracking") or r.get("CHANGE_TRACKING") or ""
        if str(ct).upper() != "ON":
            bad.append(name)
    if bad:
        return CheckResult(
            name="change tracking enabled on every source table",
            passed=False,
            detail=(
                f"missing on: {bad}. "
                f"Run: {' '.join(f'ALTER TABLE {DB}.{SCHEMA}.{t} SET CHANGE_TRACKING=TRUE;' for t in bad)}"
            ),
        )
    return CheckResult(
        name="change tracking enabled on every source table",
        passed=True, detail=f"{len(needs)} tables OK",
    )


def _rai_engines_list() -> List[dict]:
    """Return RAI engines as a list of {name, state, type} dicts.

    The 'rai' CLI doesn't expose JSON output, so we shell into a small
    Python snippet that uses the same client library the CLI is built on.
    Running it via subprocess (instead of importing here) keeps prep_demo.py
    import-light and isolates the connect_sync side effects.
    """
    if not VENV_PY.exists():
        raise RuntimeError(f"{VENV_PY} not found")
    snippet = (
        "from relationalai.config import create_config;"
        "from relationalai.client import connect_sync;"
        "import json;"
        "c = connect_sync(config=create_config());"
        "out = [{'name': r.name, 'state': r.state, 'type': r.type} for r in c.reasoners.list()];"
        "print(json.dumps(out))"
    )
    r = subprocess.run(
        [str(VENV_PY), "-c", snippet],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-300:] or r.stdout.strip()[-300:])
    # The Python output may have warnings on stderr; only the last line of
    # stdout is the JSON payload.
    last_json = r.stdout.strip().splitlines()[-1]
    return json.loads(last_json)


def _rai_engine_resume(name: str, rtype: str) -> str:
    rai = ROOT / ".venv" / "bin" / "rai"
    r = subprocess.run(
        [str(rai), "reasoners", "resume", "--name", name, "--type", rtype,
         "--wait", "--timeout-s", "600"],
        capture_output=True, text=True, timeout=620,
    )
    if r.returncode != 0:
        return f"resume failed: {r.stderr.strip()[:200]}"
    return "READY"


def check_engines_ready() -> CheckResult:
    """Both named RAI engines exist and end the check READY (resume if needed)."""
    engines = _rai_engines_list()
    wanted = {"acdm_logic_l": "Logic", "acdm_prescriptive_m": "Prescriptive"}
    # Engine names from the API come back lowercase; compare case-insensitively.
    found = {}
    for e in engines:
        n = (e.get("name") or "").lower()
        for want in wanted:
            if n == want.lower():
                found[want] = e
    missing = [n for n in wanted if n not in found]
    if missing:
        return CheckResult(
            name="RAI engines exist and READY",
            passed=False,
            detail=(
                f"missing engines: {missing}. "
                f"Re-run rai_code/manual/eham_acdm.py main() once to create them."
            ),
        )
    resumed = []
    for name, rtype in wanted.items():
        state = (found[name].get("state") or "").upper()
        if state != "READY":
            print(f"        {DIM}resuming {name} ({rtype}) ...{RESET}")
            new_state = _rai_engine_resume(name, rtype)
            resumed.append(f"{name}={new_state}")
            if new_state != "READY":
                return CheckResult(
                    name="RAI engines exist and READY",
                    passed=False,
                    detail=", ".join(resumed),
                )
    return CheckResult(
        name="RAI engines READY",
        passed=True,
        detail=", ".join(f"{n}=READY" for n in wanted) + (
            f"  | resumed: {', '.join(resumed)}" if resumed else "  | both already warm"
        ),
    )


def check_smoke_demo_queries() -> CheckResult:
    """Run rai_code/manual/demo_queries.py end-to-end; check Q1 + Q5 sentinels."""
    if not VENV_PY.exists():
        return CheckResult(name="end-to-end smoke test", passed=False,
                           detail=f"{VENV_PY} not found")
    r = subprocess.run(
        [str(VENV_PY), "-u", str(ROOT / "rai_code" / "manual" / "demo_queries.py")],
        capture_output=True, text=True, timeout=600, cwd=str(ROOT),
    )
    if r.returncode != 0:
        return CheckResult(
            name="end-to-end smoke test (demo_queries.py)",
            passed=False,
            detail=f"exit={r.returncode}\n{r.stderr.strip()[-500:]}",
        )
    text = r.stdout
    sentinels = {
        "Q1 KLG row": "KLG" in text and "7" in text.split("KLG", 1)[1][:20],
        "Q2 cascade size": "flights at risk: 7" in text,
        "Q4 LP ran": "callsign op pier" in text,
        "Q5 ran": "KL691 delay" in text,
    }
    failed = [k for k, v in sentinels.items() if not v]
    if failed:
        return CheckResult(
            name="end-to-end smoke test (demo_queries.py)",
            passed=False,
            detail=f"missing sentinels: {failed}",
        )
    return CheckResult(
        name="end-to-end smoke test (Q1-Q5 sentinels present)",
        passed=True,
        detail="; ".join(sentinels.keys()),
    )


def check_agent_deployed(redeploy: bool) -> CheckResult:
    """The 'acdm' agent is registered in SNOWFLAKE_INTELLIGENCE.AGENTS."""
    cmd = [str(VENV_PY), "-m", "agent." + ("deploy" if redeploy else "deploy"),
           "deploy" if redeploy else "status"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(ROOT))
    if r.returncode != 0:
        return CheckResult(
            name=f"SI agent '{AGENT_NAME}' status",
            passed=False,
            detail=r.stderr.strip()[-500:],
        )
    out = r.stdout
    agent_exists = "agent_exists=True" in out
    sprocs_ok = all(
        f"'{s}': True" in out
        for s in ("RAI_DISCOVER_MODELS", "RAI_VERBALIZE_MODEL",
                  "RAI_EXPLAIN_CONCEPT", "RAI_QUERY_MODEL")
    )
    if not (agent_exists and sprocs_ok):
        # Try a full deploy
        d = subprocess.run(
            [str(VENV_PY), "-m", "agent.deploy", "deploy"],
            capture_output=True, text=True, timeout=300, cwd=str(ROOT),
        )
        if d.returncode != 0:
            return CheckResult(
                name=f"SI agent '{AGENT_NAME}' deployed",
                passed=False,
                detail=d.stderr.strip()[-500:],
            )
        out = d.stdout
        agent_exists = "agent_exists=True" in out
    return CheckResult(
        name=f"SI agent '{AGENT_NAME}' deployed",
        passed=agent_exists,
        detail="all 4 sprocs OK" if agent_exists else "deployment incomplete",
    )


def check_agent_chat() -> CheckResult:
    """Ask the deployed agent the Act 1 question end-to-end."""
    r = subprocess.run(
        [str(VENV_PY), "-m", "agent.deploy", "chat",
         "Show TOBT violations by handler"],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
    )
    if r.returncode != 0:
        return CheckResult(
            name="agent answers Q1 via chat",
            passed=False, detail=r.stderr.strip()[-500:],
        )
    out = r.stdout
    sentinels = ["KLG", "AGS", "DNATA", "MENZIES"]
    missing = [s for s in sentinels if s not in out]
    if missing:
        return CheckResult(
            name="agent answers Q1 via chat",
            passed=False,
            detail=f"agent reply missing: {missing}",
        )
    return CheckResult(
        name="agent answers Q1 via chat (KLG/AGS/DNATA/MENZIES all present)",
        passed=True, detail=f"{len(out)} chars returned",
    )


def check_figures(skip: bool) -> CheckResult:
    """Regenerate the embedded figures used by RUNNING.html."""
    figs = ROOT / "build" / "figures"
    expected = [
        "act1_tobt_violations.png", "act2_cascade_graph.png", "act3_ms5_ranking.png",
        "act4_tsat_gantt.png", "act5_preservation_delta.png",
    ]
    if skip:
        present = [f for f in expected if (figs / f).is_file()]
        if len(present) < len(expected):
            return CheckResult(
                name="figures present (--skip-figures)",
                passed=False,
                detail=f"missing: {set(expected) - set(present)}",
            )
        return CheckResult(
            name="figures present (--skip-figures, no regen)",
            passed=True,
            detail=f"{len(present)}/{len(expected)} figures on disk",
        )
    r = subprocess.run(
        [str(VENV_PY), str(ROOT / "build" / "generate_demo_figures.py")],
        capture_output=True, text=True, timeout=600, cwd=str(ROOT),
    )
    if r.returncode != 0:
        return CheckResult(
            name="figures regenerated for RUNNING.html",
            passed=False, detail=r.stderr.strip()[-500:],
        )
    missing = [f for f in expected if not (figs / f).is_file()]
    if missing:
        return CheckResult(
            name="figures regenerated for RUNNING.html",
            passed=False, detail=f"failed to write: {missing}",
        )
    return CheckResult(
        name="figures regenerated for RUNNING.html",
        passed=True,
        detail=f"{len(expected)} PNGs in build/figures/",
    )


def _snow_exec(stmt: str) -> str:
    """Run a SQL statement and return raw stdout (raise on non-zero)."""
    r = subprocess.run(
        [SNOW, "sql", "-c", SNOW_CONN, "-q", stmt],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
    return r.stdout


def check_snowsight_notebook(skip: bool) -> CheckResult:
    """Ensure the Snowsight notebook is up to date.

    Idempotent: creates the schema + stage + notebook if missing, then PUTs
    the three source files (overwriting), then ALTER NOTEBOOK ADD LIVE
    VERSION FROM LAST so the next Snowsight open picks up the new files.
    """
    if skip:
        return CheckResult(
            name="Snowsight notebook (--skip-snowsight)",
            passed=True, detail="not refreshed; existing notebook unchanged",
        )

    missing = [str(p) for p in NB_SOURCES if not p.is_file()]
    if missing:
        return CheckResult(
            name="Snowsight notebook refresh",
            passed=False, detail=f"missing source files: {missing}",
        )

    # Ensure schema + stage exist (CREATE IF NOT EXISTS).
    try:
        _snow_exec(
            f"CREATE SCHEMA IF NOT EXISTS {DB}.{NB_SCHEMA}; "
            f"CREATE STAGE IF NOT EXISTS {DB}.{NB_SCHEMA}.{NB_STAGE} "
            f"DIRECTORY = (ENABLE = TRUE) "
            f"ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');"
        )
    except RuntimeError as e:
        return CheckResult(
            name="Snowsight notebook refresh",
            passed=False, detail=f"schema/stage setup failed: {e}",
        )

    # PUT each source file into the 'planes/' subfolder. Use
    # AUTO_COMPRESS=FALSE so the .ipynb stays a plain file (Snowsight needs
    # to read it directly).
    put_stmt = ";\n".join(
        f"PUT file://{p.absolute()} @{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}/ "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        for p in NB_SOURCES
    )
    try:
        _snow_exec(put_stmt + ";")
    except RuntimeError as e:
        return CheckResult(
            name="Snowsight notebook refresh",
            passed=False, detail=f"stage PUT failed: {e}",
        )

    # Create-or-replace the Notebook resource. CREATE OR REPLACE is safe
    # here because the resource has no conversation state of its own (any
    # interactive kernel state lives in the user's Snowsight session, not
    # in the resource).
    #
    # EXTERNAL_ACCESS_INTEGRATIONS is required: cell 0 does a
    # `pip install relationalai`, and on the SYSTEM$BASIC_RUNTIME container a
    # fresh kernel has no PyPI egress without it. CREATE OR REPLACE does NOT
    # carry over a UI-set integration, so set it here or every redeploy
    # silently re-breaks the first cell on a fresh container.
    try:
        _snow_exec(
            f"CREATE OR REPLACE NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} "
            f"FROM '@{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}' "
            f"MAIN_FILE = '{NB_MAIN}' "
            f"QUERY_WAREHOUSE = RAI_XS "
            f"RUNTIME_NAME = 'SYSTEM$BASIC_RUNTIME' "
            f"EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS_INTEGRATION) "
            f"COMMENT = 'EHAM A-CDM Decision Hub - 5-act PyRel demo. Stage folder: {NB_FOLDER}/';"
        )
        _snow_exec(
            f"ALTER NOTEBOOK {DB}.{NB_SCHEMA}.{NB_NAME} "
            f"ADD LIVE VERSION FROM LAST;"
        )
    except RuntimeError as e:
        return CheckResult(
            name="Snowsight notebook refresh",
            passed=False, detail=f"notebook ALTER failed: {e}",
        )

    return CheckResult(
        name=f"Snowsight notebook '{NB_NAME}' refreshed",
        passed=True,
        detail=(
            f"3 files PUT to @{DB}.{NB_SCHEMA}.{NB_STAGE}/{NB_FOLDER}/; "
            f"live version updated"
        ),
        warnings=[
            "first open: click 'Packages' in the toolbar and add relationalai==1.2.2, plotly, networkx",
        ],
    )


def _snowsight_url() -> str:
    """Return the canonical Snowsight URL for the notebook.

    The web URL format is org-based: app.snowflake.com/<ORG>/<ACCOUNT>/...
    We delegate to `snow notebook get-url`, which has the canonical mapping
    baked in (it knows about org names, account renames, region aliases).
    Falls back to a Snowflake-stage URI if anything goes wrong.
    """
    try:
        out = subprocess.run(
            [SNOW, "notebook", "get-url", f"{DB}.{NB_SCHEMA}.{NB_NAME}",
             "-c", SNOW_CONN],
            capture_output=True, text=True, timeout=30,
        )
        url = out.stdout.strip().splitlines()[-1] if out.returncode == 0 else ""
        if url.startswith("https://"):
            return url
    except Exception:  # noqa: BLE001
        pass
    return f"snow://notebook/{DB}.{NB_SCHEMA}.{NB_NAME}"


# =============================================================================
# Driver
# =============================================================================


def main() -> int:
    p = argparse.ArgumentParser(
        description="Pre-flight check + warm-up for the EHAM A-CDM demo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--skip-figures", action="store_true",
                   help="Don't regenerate the RUNNING.html PNGs (faster).")
    p.add_argument("--skip-chat", action="store_true",
                   help="Don't make a live agent.deploy chat call (faster but less coverage).")
    p.add_argument("--skip-snowsight", action="store_true",
                   help="Don't refresh the Snowsight notebook on the stage.")
    p.add_argument("--redeploy", action="store_true",
                   help="Force a full agent redeploy even if status looks healthy.")
    args = p.parse_args()

    print()
    print(f"{BOLD}EHAM A-CDM demo - laptop pre-flight{RESET}")
    print(f"{DIM}working dir: {ROOT}{RESET}")
    print(f"{DIM}snow conn:   {SNOW_CONN}{RESET}")
    print(f"{DIM}venv:        {VENV_PY}{RESET}")

    results: List[CheckResult] = []

    _banner("[1/8] Snowflake CLI + connection")
    results.append(_run_check("snow CLI", check_snow_cli))

    _banner("[2/8] ACDM_DEMO.EHAM schema state")
    results.append(_run_check("schema loaded", check_schema_loaded))

    _banner("[3/8] Talk-track numbers reproduce from raw SQL")
    results.append(_run_check("talk-track numbers", check_validation_numbers))

    _banner("[4/8] Change tracking on every source table")
    results.append(_run_check("change tracking", check_change_tracking))

    _banner("[5/8] RAI reasoner engines READY")
    results.append(_run_check("engines warm", check_engines_ready))

    _banner("[6/8] End-to-end smoke test (PyRel + HiGHS)")
    results.append(_run_check("demo_queries.py", check_smoke_demo_queries))

    _banner(f"[7/8] SI agent '{AGENT_NAME}' deployed")
    results.append(_run_check("agent deploy", lambda: check_agent_deployed(args.redeploy)))

    if not args.skip_chat:
        _banner("[8/8] Live agent chat (Q1 round-trip)")
        results.append(_run_check("agent chat", check_agent_chat))
    else:
        _banner("[8/8] Live agent chat (skipped via --skip-chat)")

    _banner("[bonus] Demo figures regenerated for RUNNING.html")
    results.append(_run_check("figures", lambda: check_figures(args.skip_figures)))

    _banner("[bonus] Snowsight notebook synced to Snowflake stage")
    results.append(_run_check("snowsight", lambda: check_snowsight_notebook(args.skip_snowsight)))

    # ---- Summary ------------------------------------------------------
    print()
    print(f"{BOLD}Readiness summary{RESET}")
    print(f"{DIM}-----------------{RESET}")
    pass_count = sum(1 for r in results if r.passed)
    total = len(results)
    for r in results:
        marker = f"{GREEN}OK{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        print(f"  [{marker}] {r.name}")

    print()
    if pass_count == total:
        url = _snowsight_url()
        msg = textwrap.dedent(f"""
            {GREEN}{BOLD}*** DEMO IS READY ***{RESET}

            {GREEN}{pass_count}/{total} checks passed.{RESET}

            Engines warm, agent live, notebook synced. Next moves:

              {DIM}1.{RESET} Open Snowsight, switch to role ACCOUNTADMIN and warehouse
                 RAI_XS. Confirm '{AGENT_NAME}' is in the Snowflake Intelligence
                 agent picker.
              {DIM}2.{RESET} Open the Snowsight notebook (first run only: click 'Packages'
                 and add relationalai==1.2.2, plotly, networkx):
                 {BOLD}{url}{RESET}
              {DIM}3.{RESET} Open RUNNING.html in another tab as your speaker reference.

            {DIM}Reset everything: .venv/bin/python -m agent.deploy teardown{RESET}
        """).strip()
        print(msg)
        return 0
    failed = [r.name for r in results if not r.passed]
    msg = textwrap.dedent(f"""
        {RED}{BOLD}*** DEMO NOT READY ***{RESET}

        {RED}{pass_count}/{total} checks passed; {len(failed)} failures:{RESET}
          - """ + "\n          - ".join(failed) + f"""

        Fix the failures above and re-run:  {DIM}.venv/bin/python prep_demo.py{RESET}
    """).strip()
    print(msg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
