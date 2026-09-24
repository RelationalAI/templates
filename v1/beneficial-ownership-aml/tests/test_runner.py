"""Phase 10: end-to-end pipeline on the CI data, the explanation for its top STR, and the notebook."""

import subprocess
import sys

import pytest

from tests.helpers import ROOT


@pytest.mark.snowflake
def test_pipeline_end_to_end_ci():
    import pipeline
    from config import Settings
    from model.explain import explain, render_text
    from model.load import FrameSource

    S = Settings().with_calibration(ROOT / "data" / "sample")
    r = pipeline.run(S, FrameSource.from_dir(ROOT / "data" / "ci"), gnn=False, log=lambda *_: None,
                     name="bo_test_pipeline_ci")
    s = r["summary"]
    assert s["control_pairs"] > 0 and s["strs"] == 52
    assert r["triage"]["plan"]["status"] == "OPTIMAL"
    assert r["triage"]["plan"]["objective"] >= r["triage"]["naive"]["value"] - 1e-6 or S.MAX_CLASS_SHARE < 1
    text = pipeline.headline(r)
    for key in ("Control pairs", "Hidden family links", "STRs scored", "Triage", "Naive", "Uplift"):
        assert key in text
    top = r["strs"].sort_values("score", ascending=False).str_id.iloc[0]
    assert render_text(explain(r["model"], r["onto"], top)).startswith(f"STR {top}")


@pytest.mark.snowflake
def test_notebook_executes():
    res = subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                          "--ExecutePreprocessor.timeout=1800", "--output", "/tmp/bo_walkthrough_out.ipynb",
                          str(ROOT / "ownership_rules_walkthrough.ipynb")], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-3000:]
