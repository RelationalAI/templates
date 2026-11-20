"""Cybersecurity attack-path analysis (graph paths) template.

Enumerates multi-step attack chains across an enterprise asset graph by composing
distinct attacker techniques in series -- a capability unlocked by multi-edge path
patterns (relationalai>=1.21):

- Loads Asset nodes (hosts, services, accounts) and three DISTINCT directed edges
  between them, one per technique: exploit_to (vulnerability exploitation),
  cred_to (credential reuse), pivot_to (network lateral movement).
- Enumerates kill-chain attack paths with a multi-relationship sequence:
  ``model.path(a.exploit_to, b.cred_to, c.pivot_to.repeat(1, N), dst)`` -- the
  classic order (exploit a perimeter host, reuse credentials inward, then pivot to
  a crown jewel). The edge order is enforced by the pattern; a single unioned
  "can move" edge or a flat join cannot express "exploit FIRST, then creds, then
  pivots". ``p.relationships`` labels the technique used at each hop.
- Runs a point query between one named internet-facing entry and one named crown
  jewel over a derived ``can_reach`` edge, enumerating every route between them.
- Scores each kill-chain by the asset exposure summed along it, and persists
  ``Asset.on_attack_path`` back to the ontology for the assets that lie on a
  crown-jewel-reaching chain.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh; `python -m
    queries.attack_path_report` then prints the report from the deployed model.
"""

from .reasoning import (
    ENTRY_ASSET,
    MAX_PIVOTS,
    MAX_ROUTE_HOPS,
    TARGET_ASSET,
    KillChainExposure,
    KillChainHop,
    KillChainStep,
    RouteStep,
)
from .schema import Asset, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "ENTRY_ASSET",
    "MAX_PIVOTS",
    "MAX_ROUTE_HOPS",
    "TARGET_ASSET",
    "Asset",
    "KillChainExposure",
    "KillChainHop",
    "KillChainStep",
    "RouteStep",
    "model",
]
