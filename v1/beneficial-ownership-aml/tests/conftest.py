import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RAI_SF") == "1":
        return
    skip_sf = pytest.mark.skip(reason="Snowflake test: set RAI_SF=1 to run")
    for item in items:
        if "snowflake" in item.keywords:
            item.add_marker(skip_sf)


@pytest.fixture
def offline_cfg():
    from config import offline_config

    return offline_config()


@pytest.fixture
def snowflake_cfg(monkeypatch):
    # raiconfig.yaml sits at the template root; make sure it is the one discovered.
    monkeypatch.chdir(ROOT)
    return None  # Model() auto-discovers raiconfig.yaml
