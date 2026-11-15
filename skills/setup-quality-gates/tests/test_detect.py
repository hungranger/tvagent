import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.detect import detect  # noqa: E402

F = SKILL / "tests/fixtures"

def test_uv_hexagonal():
    d = detect(F / "uv_hexagonal")
    assert d["pkg_manager"] == "uv"
    assert d["audit_export"] and "uv export" in d["audit_export"]
    assert d["layout"]["src_layout"] is True
    assert "app.core" in d["layout"]["core_candidates"]

def test_poetry_flat():
    d = detect(F / "poetry_flat")
    assert d["pkg_manager"] == "poetry"
    assert d["layout"]["src_layout"] is False
    assert d["layout"]["core_candidates"] == []   # no core pkg -> import-linter skipped later

def test_greenfield_no_lock():
    d = detect(F / "greenfield")
    assert d["pkg_manager"] is None                # SKILL.md will offer `uv init`
    assert d["existing"]["ruff"] is False

def test_partial_config_detected():
    d = detect(F / "partial_config")
    assert d["existing"]["ruff"] is True
    assert d["existing"]["precommit"] is True
