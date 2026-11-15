import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.detect import detect  # noqa: E402

F = SKILL / "tests/fixtures"


def test_uv_hexagonal():
    d = detect(F / "uv_hexagonal")
    assert d["python"]["pkg_manager"] == "uv"
    assert d["python"]["audit_export"] and "uv export" in d["python"]["audit_export"]
    assert d["python"]["layout"]["src_layout"] is True
    assert "app.core" in d["python"]["layout"]["core_candidates"]


def test_poetry_flat():
    d = detect(F / "poetry_flat")
    assert d["python"]["pkg_manager"] == "poetry"
    assert d["python"]["layout"]["src_layout"] is False
    assert (
        d["python"]["layout"]["core_candidates"] == []
    )  # no core pkg -> import-linter skipped later


def test_greenfield_no_lock():
    d = detect(F / "greenfield")
    assert d["python"]["pkg_manager"] is None  # SKILL.md will offer `uv init`
    assert d["python"]["existing"]["ruff"] is False


def test_partial_config_detected():
    d = detect(F / "partial_config")
    assert d["python"]["existing"]["ruff"] is True
    assert d["python"]["existing"]["precommit"] is True


def test_detect_rust():
    d = detect(F / "lang_rust")
    assert (d["language"], d["candidates"]) == ("rust", ["rust"])


def test_detect_go():
    assert detect(F / "lang_go")["language"] == "go"


def test_detect_react_ts():
    assert detect(F / "lang_react_ts")["language"] == "react-ts"


def test_detect_python():
    d = detect(F / "lang_python")
    assert d["language"] == "python" and "git" in d


def test_detect_polyglot():
    d = detect(F / "lang_polyglot")
    assert d["language"] is None and d["candidates"] == ["go", "react-ts"]


def test_detect_bare_packagejson_unsupported():
    d = detect(F / "lang_bare_pkg")
    assert d["language"] is None and d["candidates"] == []
