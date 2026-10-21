"""Deploy the eham_acdm manual ontology as a Snowflake Intelligence agent.

Run from project root:

    .venv/bin/python -m agent.deploy deploy
    .venv/bin/python -m agent.deploy update
    .venv/bin/python -m agent.deploy status
    .venv/bin/python -m agent.deploy chat "Show TOBT violations by handler"
    .venv/bin/python -m agent.deploy teardown

The agent is registered in SNOWFLAKE_INTELLIGENCE.AGENTS so it appears in
Snowsight's Snowflake Intelligence picker. Stored procedures and the
dependency stage live in BERTOLANI.AIRPORT_OPERATIONS_AGENT.
"""
import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path

from snowflake import snowpark

from relationalai.agent.cortex import (
    CortexAgentManager,
    DeploymentConfig,
    QueryCatalog,
    ToolRegistry,
)
from relationalai.config import SnowflakeConnection, create_config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AGENT_NAME = "airport_operations"
DATABASE = "BERTOLANI"
SCHEMA = "AIRPORT_OPERATIONS_AGENT"
AGENT_SCHEMA = "SNOWFLAKE_INTELLIGENCE.AGENTS"  # agent must live here to appear in the Snowflake Intelligence picker; sprocs stay in {DATABASE}.{SCHEMA}
WAREHOUSE = "RAI_XS"
EXTRA_PACKAGES = ["httpx", "opentelemetry-api==1.44.0"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _imports():
    names = (
        "agent/__init__.py",
        "agent/deploy.py",
        "agent/queries.py",
        "rai_code/__init__.py",
        "rai_code/manual/__init__.py",
        "rai_code/manual/eham_acdm.py",
        "rai_code/manual/demo_queries.py",
    )
    contents = [(name, (PROJECT_ROOT / name).read_bytes()) for name in names]
    digest = hashlib.sha256()
    for name, data in contents:
        digest.update(name.encode("ascii"))
        digest.update(data)
    bundle = Path(tempfile.gettempdir()) / f"airport_agent_{digest.hexdigest()[:16]}.zip"
    if not bundle.exists():
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in contents:
                archive.writestr(name, data)
    return [str(bundle)]


def _agent_location() -> str:
    return AGENT_SCHEMA or f"{DATABASE}.{SCHEMA}"


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}").collect()
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME,
            database=DATABASE,
            schema=SCHEMA,
            agent_schema=AGENT_SCHEMA,
            warehouse=WAREHOUSE,
            allow_preview=True,  # required for QueryCatalog (PREVIEW)
            query_timeout_s=600,
            sproc_config_overrides={
                "data": {
                    "ensure_change_tracking": False,
                    "wait_for_stream_sync": False,
                }
            },
        ),
    )


# ---------------------------------------------------------------------------
# init_tools - executed inside each sproc invocation.
# ---------------------------------------------------------------------------
def init_tools():
    from rai_code.manual import demo_queries, eham_acdm

    from . import queries

    return ToolRegistry().add(
        model=eham_acdm.model,
        description=(
            "EHAM Schiphol A-CDM ontology over ACDM_DEMO.EHAM. Concepts: "
            "Flight (with subtypes Departure/Arrival), Operator, Aircraft, "
            "Stand, Runway, GroundHandler, Fix, TaxiTimeIn, TaxiTimeOut, "
            "WeatherEvent, AtfmRegulation. Each Flight carries 16 A-CDM "
            "milestones (SOBT, EOBT, TOBT, TSAT, CTOT, ARDT, ASRT, ASAT, "
            "TTOT, AOBT, ATOT, TLDT, ELDT, ALDT, AIBT, ACGT). Derived: "
            "feeds_callsign(Flight, Flight) rotation edge, slot_blocks"
            "(Flight, Flight) pushback-contention edge, shares_stand"
            "(Flight, Flight) stand-contention edge, TOBTViolation(Flight) "
            "for MS12 +/- 5 min audit, StormWindowDeparture(Flight) for "
            "Act 4 scope, PreservedFlight(Flight) for the Act 5 "
            "persistent operator rule. Five questions answer the demo arc: "
            "TOBT compliance audit, rotation cascade from KL1234, MS5 "
            "gate-conflict heuristic ranking, TSAT re-sequence under storm, and TSAT "
            "re-sequence with KL high-pax preservation. The MS5 score is not "
            "a calibrated conflict probability. The seed baseline already "
            "satisfies the eight-minute KL cap, so do not claim the cap forced "
            "a better KL691 slot. Compare solver outcomes with "
            "tsat_preservation_impact before discussing Act 5. "
            "CHART HINTS: every '*_chart' query returns a dict shaped as "
            "{records: [...], chart_hint: {type, x, y, title, color}}. "
            "When you call a *_chart query, ALWAYS conclude your text "
            "reply with a sentence like: 'Click the chart icon next to the "
            "table to visualise this as a {chart_hint.type} of "
            "{chart_hint.y} by {chart_hint.x}.' This guides the user to "
            "Snowsight's one-click visualiser. Prefer the *_chart variant "
            "for any question that's visualisation-shaped (rankings, "
            "comparisons, before/after, sequences); use the plain variant "
            "for graph-cascade output (Q2) or when the user explicitly "
            "asks for a full ranked table."
        ),
        queries=QueryCatalog(
            queries.tobt_violations_by_handler,
            queries.tobt_violations_by_handler_chart,
            queries.rotation_cascade_from_kl1234,
            queries.ms5_conflict_ranking,
            queries.ms5_conflict_ranking_chart,
            queries.tsat_resequence_under_storm,
            queries.tsat_resequence_under_storm_chart,
            queries.tsat_resequence_with_preservation,
            queries.tsat_preservation_impact,
            queries.tsat_act4_vs_act5_chart,
        ),
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_deploy(manager: CortexAgentManager) -> None:
    print(
        f"Deploying sprocs to {DATABASE}.{SCHEMA} "
        f"and agent {AGENT_NAME} to {_agent_location()} ..."
    )
    manager.deploy(
        init_tools=init_tools,
        imports=_imports(),
        extra_packages=EXTRA_PACKAGES,
    )
    print(manager.status())


def cmd_update(manager: CortexAgentManager) -> None:
    print(f"Updating stored procedures for {AGENT_NAME} ...")
    manager.update(
        init_tools=init_tools,
        imports=_imports(),
        extra_packages=EXTRA_PACKAGES,
    )
    print(manager.status())


def cmd_status(manager: CortexAgentManager) -> None:
    print(manager.status())


def cmd_preflight(manager: CortexAgentManager) -> None:
    report = manager.preflight(init_tools=init_tools)
    print(report.format(config=manager.config))


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    chat = manager.chat()
    response = chat.send(message)
    print(response.full_text())


def cmd_teardown(manager: CortexAgentManager) -> None:
    print(
        f"Tearing down agent {AGENT_NAME} from {_agent_location()} "
        f"and sprocs from {DATABASE}.{SCHEMA} ..."
    )
    print("WARNING: this permanently deletes SI conversation history.")
    manager.cleanup()
    print(manager.status())


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the airport operations Cortex agent lifecycle."
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy", help="Create schema, stage, sprocs, and agent")
    sub.add_parser("update", help="Update sprocs without re-registering the agent")
    sub.add_parser("status", help="Print deployment status")
    sub.add_parser("preflight", help="Check grants and tool payloads")

    chat_p = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")

    sub.add_parser("teardown", help="Remove all agent resources")

    args = parser.parse_args()
    manager = _build_manager()

    commands = {
        "deploy": lambda: cmd_deploy(manager),
        "update": lambda: cmd_update(manager),
        "status": lambda: cmd_status(manager),
        "preflight": lambda: cmd_preflight(manager),
        "chat": lambda: cmd_chat(manager, args.message),
        "teardown": lambda: cmd_teardown(manager),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
