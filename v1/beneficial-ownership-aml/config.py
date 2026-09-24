"""Every tunable knob for the template, plus connection helpers.

Override any setting with an environment variable of the same name, e.g.
`AUDIT_HOURS=200 python beneficial_ownership_local.py`.
"""

import dataclasses
import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # Control and ownership (P1 Def 2.3, 2.5, 2.6; P3 Rules 4-8)
    CONTROL_T: float = 0.5
    MAX_CONTROL_DEPTH: int = 12
    CLOSE_LINK_T: float = 0.2
    CEO_RULE: bool = True
    PHI_METHOD: str = "unrolled"  # "unrolled" | "paths"
    PHI_MAX_HOPS: int = 8
    PHI_EPS: float = 0.005
    EDGE_EPS: float = 0.01

    # Family links and VADA-LINK augmentation (P1 Alg. 1, 3, 7; Eq. 3)
    LINK_TYPES: tuple = ("PARTNER_OF", "SIBLING_OF")
    LINK_T: dict = field(default_factory=lambda: {"PARTNER_OF": 0.90, "SIBLING_OF": 0.90})
    LINK_T_MIN: float = 0.9
    BLOCK_KEYS: dict = field(default_factory=lambda: {
        "PARTNER_OF": ("province",),
        "SIBLING_OF": ("surname3",),
    })  # chosen by eval/augmentation_eval.py --sweep: best F1 (recall .84, precision .87 in one round)
    BLOCKING_L1: str = "louvain_projection"  # "louvain_projection" | "none"
    FEATURE_PROBS: str = ""  # calibrated Graham feature table; default data/sample/feature_probs.csv
    MAX_BLOCK: int = 2000
    MAX_ROUNDS: int = 3
    MAX_FAMILY_SIZE: int = 12

    # Predictive reasoner (GNN)
    USE_GNN_LINK: bool = True
    USE_GNN_ACCOUNT: bool = True
    GNN_DEVICE: str = "cpu"  # "cuda" only if a GPU engine exists
    # GNN top-k pairs as extra VADA-LINK candidates (P1 #GraphEmbedClust). Off: on the sample it raised recall
    # .84 -> .85 but dropped precision .86 -> .01 (base-rate problem; see eval/out/link_ablation.csv).
    GNN_CANDIDATES: bool = False
    STREAM_LOGS: bool = False

    # Query-driven case mode (P3 "ethical decisions")
    CASE_MODE_HOPS: int = 3

    # Triage optimization (P3 risk-driven optimization)
    AUDIT_HOURS: float = 400
    CASE_SETUP_HOURS: float = 6
    HOURS_PER_STR: float = 2
    MAX_CLASS_SHARE: float = 0.5
    TRIAGE_MODE: str = "select"  # "select" | "assign"

    # Snowflake locations
    DATA_SCHEMA: str = "BENEFICIAL_OWNERSHIP.DATA"
    EXP_DATABASE: str = "BENEFICIAL_OWNERSHIP"
    EXP_SCHEMA: str = "EXPERIMENTS"

    SEED: int = 7

    def with_calibration(self, data_dir) -> "Settings":
        """Use the calibrated feature table and link thresholds written by calibrate.py, if present."""
        from pathlib import Path

        d = Path(data_dir)
        out = self
        if (d / "link_thresholds.json").exists():
            lt = json.loads((d / "link_thresholds.json").read_text())
            out = dataclasses.replace(out, LINK_T={**out.LINK_T, **lt}, LINK_T_MIN=min(lt.values()))
        if (d / "feature_probs.csv").exists():
            out = dataclasses.replace(out, FEATURE_PROBS=str(d / "feature_probs.csv"))
        return out

    @classmethod
    def from_env(cls) -> "Settings":
        overrides = {}
        for f in dataclasses.fields(cls):
            raw = os.environ.get(f.name)
            if raw is None:
                continue
            default = f.default if f.default is not dataclasses.MISSING else f.default_factory()
            if isinstance(default, bool):
                overrides[f.name] = raw.lower() in ("1", "true", "yes")
            elif isinstance(default, (dict, tuple, list)):
                overrides[f.name] = type(default)(json.loads(raw))
            else:
                overrides[f.name] = type(default)(raw)
        return cls(**overrides)


def offline_config(path: str = ":memory:"):
    """Local DuckDB config: ontology, queries and rules only (no graph, GNN or solver)."""
    from relationalai.config import DuckDBConnection, create_config

    return create_config(
        connections={"local": DuckDBConnection(path=path)},
        default_connection="local",
        deployment={"schema": "main", "auto_deploy": True},
    )
