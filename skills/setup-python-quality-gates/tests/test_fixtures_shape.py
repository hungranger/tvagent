from pathlib import Path

F = Path(__file__).resolve().parents[1] / "tests/fixtures"


def test_fixture_markers_present():
    assert (F / "greenfield/src/pkg/__init__.py").exists()
    assert not (F / "greenfield/uv.lock").exists()
    assert (F / "uv_hexagonal/uv.lock").exists()
    assert (F / "uv_hexagonal/src/app/core/__init__.py").exists()
    assert (F / "poetry_flat/poetry.lock").exists()
    assert (F / "poetry_flat/mod.py").exists()
    assert "[tool.ruff]" in (F / "partial_config/pyproject.toml").read_text()
