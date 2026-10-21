"""Deployment CLI for the telco network recovery Cortex agent."""

import argparse
import os
from pathlib import Path

import yaml
from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig, ToolRegistry
from relationalai.config import SnowflakeConnection, create_config
from relationalai.semantics import Model
from snowflake import snowpark

_AGENT_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _AGENT_DIR / "rai-agent-config.yaml"
_EXTRA_PACKAGES = ["httpx", "pyyaml", "opentelemetry-api==1.44.0"]


def _load_config() -> dict:
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


_cfg = _load_config()
AGENT_NAME = _cfg["agent"]["name"]
DATABASE = _cfg["agent"]["database"]
SCHEMA = _cfg["agent"]["schema"]
WAREHOUSE = _cfg["agent"]["warehouse"]
MODEL_NAME = _cfg["agent"]["model_name"]


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME,
            database=DATABASE,
            schema=SCHEMA,
            warehouse=WAREHOUSE,
            model_name=MODEL_NAME,
            allow_preview=True,
            sproc_config_overrides={
                "data": {
                    "ensure_change_tracking": False,
                    "wait_for_stream_sync": False,
                }
            },
        ),
    )


def init_tools(model: Model) -> ToolRegistry:
    """Executed inside each stored procedure invocation."""
    from pathlib import Path

    import relationalai.util.schema as _schema_mod

    _schema_mod.CACHE_PATH = Path("/tmp/rai_cache/schemas.json")

    try:
        from telco_agent.ontology import initialize_upgrade_plan
        from telco_agent.queries import build_tool_registry
    except ModuleNotFoundError as exc:
        if exc.name != "telco_agent":
            raise
        from ontology import initialize_upgrade_plan
        from queries import build_tool_registry

    initialize_upgrade_plan(model)
    return build_tool_registry(model)


def _imports():
    return [
        str(_AGENT_DIR / "ontology.py"),
        str(_AGENT_DIR / "queries.py"),
        str(_AGENT_DIR.parent / "run_optimization.py"),
        str(_AGENT_DIR.parent / "deployed_ontology.py"),
        str(_AGENT_DIR.parent / "reasoner_common.py"),
    ]


def cmd_deploy(manager: CortexAgentManager) -> None:
    print(f"Deploying '{AGENT_NAME}' to {DATABASE}.{SCHEMA} ...")
    manager.deploy(
        init_tools=init_tools,
        imports=_imports(),
        extra_packages=_EXTRA_PACKAGES,
    )
    print(manager.status())


def cmd_update(manager: CortexAgentManager) -> None:
    print(f"Updating stored procedures for '{AGENT_NAME}' ...")
    manager.update(
        init_tools=init_tools,
        imports=_imports(),
        extra_packages=_EXTRA_PACKAGES,
    )
    print(manager.status())


def cmd_status(manager: CortexAgentManager) -> None:
    print(manager.status())


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    response = manager.chat().send(message)
    print(response.full_text())


def cmd_setup_sql(manager: CortexAgentManager, deployer_role: str | None) -> None:
    kwargs = {}
    if deployer_role:
        kwargs["deployer_role"] = deployer_role
    manager.print_setup_sql(**kwargs)


def cmd_preflight(manager: CortexAgentManager) -> None:
    report = manager.preflight(init_tools=init_tools)
    print(report.format(config=manager.config))


def cmd_teardown(manager: CortexAgentManager) -> None:
    print(f"Tearing down '{AGENT_NAME}' from {DATABASE}.{SCHEMA} ...")
    print("WARNING: this permanently deletes Snowflake Intelligence history for the agent.")
    manager.cleanup()
    print(manager.status())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("deploy", help="Create schema, stage, stored procedures, and agent")
    sub.add_parser("update", help="Update stored procedures without re-registering")
    sub.add_parser("status", help="Print deployment status")
    sub.add_parser("preflight", help="Check deployment privileges and payload sizes")
    sub.add_parser("teardown", help="Remove all agent resources")

    setup = sub.add_parser("setup-sql", help="Print Snowflake grants needed for deploy")
    setup.add_argument("--deployer-role", default=os.environ.get("SNOWFLAKE_ROLE"))

    chat = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat.add_argument("message")

    args = parser.parse_args()
    manager = _build_manager()

    if args.command == "deploy":
        cmd_deploy(manager)
    elif args.command == "update":
        cmd_update(manager)
    elif args.command == "status":
        cmd_status(manager)
    elif args.command == "preflight":
        cmd_preflight(manager)
    elif args.command == "setup-sql":
        cmd_setup_sql(manager, args.deployer_role)
    elif args.command == "chat":
        cmd_chat(manager, args.message)
    elif args.command == "teardown":
        cmd_teardown(manager)


if __name__ == "__main__":
    main()
