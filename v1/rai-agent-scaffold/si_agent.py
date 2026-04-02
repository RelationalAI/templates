"""
Deployment script for a RelationalAI Cortex agent.

Usage:
    python si_agent.py deploy
    python si_agent.py update
    python si_agent.py status
    python si_agent.py chat "<your question>"
    python si_agent.py teardown
"""
import argparse
import os

import yaml
from snowflake import snowpark

from relationalai.semantics import Model
from relationalai.config import create_config, SnowflakeConnection
from relationalai.agent.cortex import (
    CortexAgentManager,
    DeploymentConfig,
    ToolRegistry,
)

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_AGENT_DIR, "rai-agent-config.yaml")

# ---------------------------------------------------------------------------
# Configuration — loaded from rai-agent-config.yaml
# ---------------------------------------------------------------------------
def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)

_cfg = _load_config()

AGENT_NAME  = _cfg["agent"]["name"]
DATABASE    = _cfg["agent"]["database"]
SCHEMA      = _cfg["agent"]["schema"]
WAREHOUSE   = _cfg["agent"]["warehouse"]
MODEL_NAME  = _cfg["agent"]["model_name"]

# Packages used by relationalai.agent.cortex not auto-installed as transitive deps.
_EXTRA_PACKAGES = ["httpx"]


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
        ),
    )


# ---------------------------------------------------------------------------
# init_tools — executed inside each stored procedure with a fresh Model.
# Must be self-contained: no sessions, DataFrames, or other runtime state.
# ---------------------------------------------------------------------------
def init_tools(model: Model) -> ToolRegistry:
    # Workaround for v1.0.x: redirect schema cache to /tmp (UDF sandbox restriction)
    import relationalai.util.schema as _schema_mod
    from pathlib import Path
    _schema_mod.CACHE_PATH = Path("/tmp/rai_cache/schemas.json")

    from queries import build_tool_registry
    return build_tool_registry(model)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def _imports():
    return [
        os.path.join(_AGENT_DIR, "ontology.py"),
        os.path.join(_AGENT_DIR, "queries.py"),
    ]


def cmd_deploy(manager: CortexAgentManager) -> None:
    print(f"Deploying '{AGENT_NAME}' to {DATABASE}.{SCHEMA} ...")
    manager.deploy(init_tools=init_tools, imports=_imports(), extra_packages=_EXTRA_PACKAGES)
    print(manager.status())


def cmd_update(manager: CortexAgentManager) -> None:
    print(f"Updating stored procedures for '{AGENT_NAME}' ...")
    manager.update(init_tools=init_tools, imports=_imports(), extra_packages=_EXTRA_PACKAGES)
    print(manager.status())


def cmd_status(manager: CortexAgentManager) -> None:
    print(manager.status())


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    response = manager.chat().send(message)
    print(response.full_text())


def cmd_teardown(manager: CortexAgentManager) -> None:
    print(f"Tearing down '{AGENT_NAME}' from {DATABASE}.{SCHEMA} ...")
    print("WARNING: permanently deletes all SI conversation history for this agent.")
    manager.cleanup()
    print(manager.status())


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the Cortex agent lifecycle.")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy",   help="Create schema, stage, sprocs, and agent")
    sub.add_parser("update",   help="Update sprocs without re-registering the agent")
    sub.add_parser("status",   help="Print deployment status")
    sub.add_parser("teardown", help="Remove all agent resources")

    chat_p = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")

    args = parser.parse_args()
    manager = _build_manager()

    commands = {
        "deploy":   lambda: cmd_deploy(manager),
        "update":   lambda: cmd_update(manager),
        "status":   lambda: cmd_status(manager),
        "chat":     lambda: cmd_chat(manager, args.message),
        "teardown": lambda: cmd_teardown(manager),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
