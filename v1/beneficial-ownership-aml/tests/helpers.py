"""Shared test helpers: build fixture models once per (fixture, backend, stages) and query them."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pytest
import yaml
from config import Settings, offline_config
from model import build_model
from model.load import FrameSource

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "F1": "f1_weaving_fig1", "F2": "f2_weaving_fig2", "F3": "f3_acme", "F4": "f4_slush", "F5": "f5_level2",
}

# Reasoning tests run on Snowflake. DuckDB (offline) is correct but far too slow to compile the depth-layered
# rule stacks (one F1 control test took 23 min offline vs seconds on Snowflake), so offline covers contracts,
# the generator, loading and pure math. Set BO_OFFLINE_REASONING=1 to also run reasoning tests on DuckDB.
BACKENDS = [pytest.param("snowflake", marks=pytest.mark.snowflake, id="snowflake")]
if os.environ.get("BO_OFFLINE_REASONING") == "1":
    BACKENDS.insert(0, pytest.param("offline", marks=pytest.mark.offline, id="offline"))
LOAD_BACKENDS = [
    pytest.param("offline", marks=pytest.mark.offline, id="offline"),
    pytest.param("snowflake", marks=pytest.mark.snowflake, id="snowflake"),
]


def expected(fixture: str) -> dict:
    return yaml.safe_load((ROOT / "data" / "fixtures" / FIXTURES[fixture] / "expected.yaml").read_text())


@lru_cache(maxsize=None)
def fixture_model(fixture: str, backend: str, stages: tuple[str, ...] | None = None, **overrides):
    settings = Settings(**overrides)
    source = FrameSource.from_dir(ROOT / "data" / "fixtures" / FIXTURES[fixture])
    config = offline_config() if backend == "offline" else None
    if backend == "snowflake":
        os.chdir(ROOT)
    tag = "_".join(stages) if stages is not None else "all"
    name = f"bo_test_{fixture.lower()}_{backend}_{abs(hash((tag, tuple(sorted(overrides.items()))))) % 10**6}"
    return build_model(settings, source, name=name, stages=list(stages) if stages is not None else None, config=config)


def pairs(df, a, b):
    return {tuple(x) for x in df[[a, b]].values.tolist()}
