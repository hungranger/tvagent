import shutil
import sys
import tomllib
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.manifest import ManifestError  # noqa: E402
from gate_setup.render import render  # noqa: E402

FAKE = SKILL / "tests" / "fixtures" / "profile_fake"
M = {"thresholds": {"coverage_floor": 87, "complexity_max": 7}}


def test_render_emits_flag_from_manifest():
    assert "--cov-fail-under=87" in render(FAKE, M)["ci.yml"]


def test_render_emits_native_config():
    assert "max-complexity = 7" in render(FAKE, M)["ruff.toml"]


def test_render_no_residual_tokens():
    assert all("{{" not in v for v in render(FAKE, M).values())


def test_render_deterministic():
    assert list(render(FAKE, M).items()) == list(render(FAKE, M).items())


def test_render_writes_drift_into_manifest():
    out = tomllib.loads(render(FAKE, M)["quality-gates.toml"])
    assert out["drift"] == {"ruff.toml#lint.mccabe.max-complexity": "complexity_max"}
    assert out["thresholds"] == M["thresholds"]


def _profile(tmp_path: Path, old: str, new: str) -> Path:
    shutil.copytree(FAKE, tmp_path / "p")
    f = tmp_path / "p" / "profile.toml"
    f.write_text(f.read_text().replace(old, new))
    return tmp_path / "p"


def test_render_fails_on_unbound_config_key(tmp_path: Path):
    prof = _profile(tmp_path, '"ruff.toml#', '# "ruff.toml#')
    with pytest.raises(ManifestError, match="complexity_max"):
        render(prof, M)


def test_render_missing_threshold_key_is_manifest_error(tmp_path: Path):
    prof = _profile(tmp_path, 'threshold_key = "coverage_floor"\n', "")
    with pytest.raises(ManifestError, match="missing threshold_key"):
        render(prof, M)
